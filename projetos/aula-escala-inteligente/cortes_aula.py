"""Módulo 1 da aula: decide os cortes (pausas, muletas, respiros, repetições) e gera cortes.json.

Uso:
  python codigo/cortes_aula.py                      # calcula e grava cortes.json
  python codigo/cortes_aula.py --proxy x.mp4 [--de T --ate T]   # vídeo de conferência (T em tempo de SAÍDA)
  python codigo/cortes_aula.py --relatorio           # mostra o que sai, com o texto

Para os outros módulos:  from cortes_aula import saida_de, gravacao_de, trechos
"""
import argparse
import json
import re
import subprocess
import sys
import unicodedata
import wave
from bisect import bisect_right
from pathlib import Path

import numpy as np

AULA = Path("/home/user/claude/trabalho/aula")
TRANSCRICAO = AULA / "transcricao_small.jsonl"
VOZ = AULA / "voz16k.wav"
AUDIO48 = AULA / "audio48k.wav"
BASE = AULA / "base720.mp4"
SAIDA = AULA / "cortes.json"

FPS = 30
SR = 16000
HOP = 0.01                 # passo da energia (10 ms)

PAUSA_MAX = 0.25           # silêncio até isso fica como está
PAUSA_FRASE = 0.20         # pausa que fica depois de ponto final / pergunta
PAUSA_VIRGULA = 0.15       # depois de vírgula
PAUSA_MEIO = 0.12          # no meio da frase
RESPIRO_MIN = 0.08
MIN_TIRAR = 0.14           # pausa só é encurtada se sair pelo menos isso (senão a imagem dá um tranco à toa)         # bolha sem voz menor que isso é estalo, conta como silêncio

# muleta que sai sempre / que sai só quando está sozinha entre pausas (com acento, minúscula)
MULETAS = {"hum", "hmm", "hm", "humm", "éé", "ééé", "éee", "ehh", "uh", "uhm", "hã", "ãh", "ããã"}
MULETAS_SOLTAS = {"ah", "ahn", "ã", "eh", "aa", "aaa", "aah", "han", "ãã"}
# "é" sozinho pode ser verbo: nunca sai sozinho, vai pra dúvidas (ver _muletas)


# ---------------------------------------------------------------- áudio

def _ler_wav(caminho):
    with wave.open(str(caminho)) as w:
        x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
        return x, w.getframerate()


class Audio:
    """Energia (dB) e vozeamento da voz 16 kHz."""

    def __init__(self, caminho=VOZ):
        self.x, sr = _ler_wav(caminho)
        assert sr == SR
        self.dur = len(self.x) / SR
        self.c = np.concatenate([[0.0], np.cumsum(self.x.astype(np.float64) ** 2)])
        # energia em janelas de 20 ms a cada 10 ms (quadro k centrado em k*HOP)
        self.t = np.arange(int(self.dur / HOP)) * HOP
        self.db = self.rms(self.t, 0.02)
        self.chao = float(np.percentile(self.db, 10))      # ruído da sala
        self.fala = float(np.percentile(self.db, 75))      # nível típico de fala

    def rms(self, t, janela=0.04):
        """RMS em dB de janelas centradas em t (segundos)."""
        t = np.atleast_1d(np.asarray(t, float))
        a = np.clip(((t - janela / 2) * SR).astype(np.int64), 0, len(self.x))
        b = np.clip(((t + janela / 2) * SR).astype(np.int64), 0, len(self.x))
        e = (self.c[b] - self.c[a]) / np.maximum(b - a, 1)
        return 10 * np.log10(e + 1e-12)

    def vozeado(self, t):
        """Força da periodicidade (0..1) em janelas de 40 ms centradas em t: voz tem, respiro não."""
        t = np.atleast_1d(t)
        n, lag0, lag1 = 640, SR // 400, SR // 60
        out = np.zeros(len(t))
        for i0 in range(0, len(t), 4000):
            tt = t[i0:i0 + 4000]
            ini = np.clip((tt * SR).astype(np.int64) - n // 2, 0, len(self.x) - n)
            q = self.x[ini[:, None] + np.arange(n)]
            q = q - q.mean(1, keepdims=True)
            f = np.fft.rfft(q * np.hanning(n), 2048)
            ac = np.fft.irfft(np.abs(f) ** 2)[:, :lag1 + 1]
            out[i0:i0 + 4000] = ac[:, lag0:].max(1) / np.maximum(ac[:, 0], 1e-9)
        return out


def _corridas(mask):
    """[(ini, fim)] em índices de trechos True."""
    m = np.concatenate([[False], mask, [False]]).astype(np.int8)
    d = np.diff(m)
    return list(zip(np.where(d == 1)[0], np.where(d == -1)[0]))


def unidades_de_som(au):
    """Blocos de som separados por silêncio. Cada um: ini, fim, voz (tem voz?), pico."""
    lim = au.chao + 9
    ativo = au.db > lim
    # fecha buracos curtos (oclusiva, ex. "p", "t") e tira estalos muito curtos
    for a, b in _corridas(~ativo):
        if b - a <= 6 and a > 0:
            ativo[a:b] = True
    blocos = []
    for a, b in _corridas(ativo):
        if b - a < 3:
            continue
        blocos.append([a, b])
    # vozeamento só nos quadros fortes de cada bloco
    idx = np.concatenate([np.arange(a, b) for a, b in blocos])
    forte = au.db[idx] > au.chao + 18
    v = np.zeros(len(idx))
    v[forte] = au.vozeado(au.t[idx[forte]])
    pos = 0
    out = []
    for a, b in blocos:
        vv = v[pos:pos + b - a]
        dd = au.db[a:b]
        pos += b - a
        out.append({"ini": round(a * HOP, 3), "fim": round(b * HOP, 3),
                    "voz": int(((vv > 0.55) & (dd > au.chao + 18)).sum()),   # quadros de 10 ms com voz
                    "pico": round(float(dd.max()), 1)})
    return out




# ---------------------------------------------------------------- texto

def sem_acento(s):
    s = unicodedata.normalize("NFD", s.lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]", "", s)


def ler_palavras(caminho=TRANSCRICAO):
    ws = []
    for linha in open(caminho, encoding="utf-8"):
        linha = linha.strip()
        if not linha.startswith("{"):
            continue
        try:
            seg = json.loads(linha)
        except json.JSONDecodeError:
            continue           # última linha ainda sendo escrita
        for w, a, b, p in seg["w"]:
            ws.append({"w": w, "n": sem_acento(w), "r": re.sub(r"[^\w]", "", w.lower()), "s": a, "e": b, "p": p,
                       "pont": w[-1] if w and w[-1] in ".,?!…:;" else ""})
    for i, w in enumerate(ws):
        w["i"] = i
    return ws


# ---------------------------------------------------------------- decisões feitas lendo a aula
# (tempo aproximado da gravação, texto exato que sai). Fala errada, conversa fora da aula, tomada abandonada.
CORTES_MANUAIS = [
    (36.0, "Amor, depois fecha a porta aqui para mim, por favor,"),       # fala com alguém na sala
    (109.0, "levando ali com os filhos,"),                                 # recomeço: "levando os filhos..."
    (646.0, "para a gente"),                                               # fica só a 2ª tomada: "pra não tomar..."
    (449.7, "mas ela separa duas formas completamente da gente, ela errei, corta essa parte,"),  # ela pediu
    (1303.0, "e você,"),                                                   # frase abandonada
    (2076.0, "o que que você,"),                                           # frase abandonada
    (3362.0, "é é"),                                                       # "então é, é, é ali" -> "então é ali"
]
# repetições achadas sozinhas mas que são de propósito (ênfase): (tempo aproximado, texto da 1ª vez)
NAO_CORTAR = [
    (3486.0, "no TikTok"),          # "cinco contas no TikTok, né, no TikTok Shop": tempos do whisper ruins aqui
]
# blocos sem texto que são conversa fora da aula (ela esperando algo carregar: "Carrega! Carrega!")
APARTES_SEM_TEXTO = [
    (933.4, 946.6, "esperando carregar: \"ahn... carrega, carrega\""),
]
# o que ficou mas vale ela ouvir (tempo da gravação)
DUVIDAS_MANUAIS = [
    (45.2, "\"tudo que eu vou te esclarecer, ou que eu estou buscando te esclarecer, né, melhor dizendo\": ela se corrige; ficou inteiro"),
    (1074.0, "\"talvez se um negócio, né, de repente ali deu errado, você que dá implementado\": frase confusa; ficou"),
    (2107.0, "\"saiu uma venda dos... deixa oportunidade de passar. E a... fazer essa ficha\": frase truncada; ficou"),
    (2220.9, "\"Então a gente começa, quando a gente começa a entender essa visão, a gente começa a entender\": recomeço? ficou inteiro"),
    (3087.0, "\"escalar aquele produto que está vendendo, aquele vídeo que está vendendo\": se corrige (produto→vídeo); ficou"),
    (3461.8, "\"é assim que você vai transformar, é assim que eu transformo\": se corrige; ficou"),
]
# trechos com outro vídeo tocando: não corta por dentro
PROTEGER = [
]


def _achar_seq(ws, t, texto, folga=6.0):
    """Índices (i, j) das palavras que formam `texto` perto do tempo t."""
    alvo = [sem_acento(x) for x in texto.split() if sem_acento(x)]
    melhor = None
    for i in range(len(ws)):
        if abs(ws[i]["s"] - t) > folga or ws[i]["n"] != alvo[0]:
            continue
        k, j = 0, i
        while j < len(ws) and k < len(alvo):
            if not ws[j]["n"]:
                j += 1
                continue
            if ws[j]["n"] != alvo[k]:
                break
            k += 1
            j += 1
        if k == len(alvo) and (melhor is None or abs(ws[i]["s"] - t) < abs(ws[melhor[0]]["s"] - t)):
            melhor = (i, j - 1)
    return melhor


# ---------------------------------------------------------------- regras de conteúdo

def _so_muleta(texto):
    """Texto só de "éé", "ahn", "hum"..."""
    ps = [re.sub(r"[^\w]", "", x.lower()) for x in texto.split()]
    ps = [x for x in ps if x]
    return bool(ps) and all(re.fullmatch(r"(é+|e+|ã+|a+h*n*|h?u+m+|hm+|eh+|hã)", x) for x in ps)


def _isolada(w, unid_de):
    """A palavra está sozinha no seu bloco de som (silêncio antes e depois)?"""
    u = unid_de.get(w["i"])
    return u is not None and len(u["palavras"]) == 1


def _muletas(ws, unid_de):
    fora, duvidas = set(), []
    for i, w in enumerate(ws):
        n, r, prox = w["n"], w["r"], ws[i + 1]["n"] if i + 1 < len(ws) else ""
        if r in MULETAS or (r in MULETAS_SOLTAS and _isolada(w, unid_de) and prox != "brenda"):
            fora.add(i)          # ("Ah, Brenda, mas..." é a fala do aluno que ela imita: fica)
        elif n == "e" and w["w"].lower().startswith("é") and _isolada(w, unid_de):
            # o tempo do whisper erra: o bloco "sozinho" pode ter outra palavra junto (ex. "não é")
            if True:
                duvidas.append({"t": round(w["s"], 1), "o_que": "\"é\" sozinho entre pausas: muleta ou verbo? ficou"})
        elif n == "tipo" and prox == "assim" and i + 1 < len(ws):
            u = unid_de.get(i)
            if u is not None and [p["n"] for p in u["palavras"]] == ["tipo", "assim"]:
                fora |= {i, i + 1}
    return fora, duvidas


# palavrinhas que podem sobrar no fim da tentativa abandonada ("...conteúdo não, pra | não tomar...")
SOBRAS = {"pra", "para", "eita", "e", "é", "o", "a", "os", "as", "de", "da", "do", "que", "né", "ah", "aí",
          "no", "na", "com", "então", "mas", "ou", "tipo", "assim", "já"}
SOBRAS_2 = {"eita", "né", "ah", "aí", "tipo", "assim", "e", "é"}
# palavra repetida colada que é natural ou ênfase ("o que que", "muito muito", "não, não")
GAGUEIRA_NAO = {"que", "muito", "não", "isso", "todo", "dia", "sim", "bem", "cada", "mais"}
NUMEROS = {"um", "uma", "dois", "duas", "três", "quatro", "cinco", "seis", "sete", "oito", "nove", "dez",
           "vinte", "trinta", "cem", "mil"}


def _repeticoes(ws):
    """Tomada recomeçada: ela começa, para e repete o começo inteiro, seguindo adiante.
    Fica a última versão. Listas paralelas ("qual foi o produto, qual foi o formato") não contam:
    o que sobra da 1ª tentativa tem que ser só palavrinha de ligação, não conteúdo.
    Devolve (cortes, dúvidas)."""
    cand, duv = [], []
    r = [w["r"] for w in ws]
    i = 0
    while i < len(ws) - 1:
        achou = None
        a = r[i]
        for j in range(i + 1, min(len(ws), i + 14)):
            if ws[j]["s"] - ws[i]["s"] > 12:
                break
            if r[j] != a or not a or a in NUMEROS or a.isdigit():
                continue
            F, S = r[i:j], r[j:j + (j - i) + 1]
            if r[j + len(F):j + 2 * len(F)] == F or r[max(0, i - len(F)):i] == F:
                achou = (i, j + 2 * len(F), None)        # três vezes = ênfase: fica tudo
                break
            L = 0
            while L < min(len(F), len(S)) and F[L] == S[L]:
                L += 1
            sobra = F[L:]
            # não atravessa fim de frase ("cinco e cinco. E manter", "uma dúvida. Que que é uma dúvida?")
            if any(w["pont"] in ".?!" and w["pont"] for w in ws[i:i + L - 1] + ws[j:j + L - 1]):
                continue
            if len(F) == 1:
                if a in GAGUEIRA_NAO or ws[i]["w"][:1].isupper():
                    continue
                if ws[i]["pont"] in ("", "…") or ws[i]["w"].endswith("..."):
                    achou = (i, j, "gagueira")       # "meu meu", "vai... vai"
                else:
                    duv.append({"t": round(ws[i]["s"], 1),
                                "o_que": f"\"{ws[i]['w']} {ws[j]['w']}\": gaguejou ou ênfase? ficou"})
                break
            if L >= 2 and len(S) > L and (not sobra or (len(sobra) == 1 and sobra[0] in SOBRAS)
                                          or (len(sobra) == 2 and set(sobra) <= SOBRAS_2)):
                achou = (i, j, "recomeço")
            if achou:
                break
        if achou:
            if achou[2]:
                cand.append({"i": achou[0], "j": achou[1], "tipo": achou[2]})
            i = achou[1]
        else:
            i += 1
    return cand, duv


# ---------------------------------------------------------------- cortes

class Plano:
    def __init__(self, au=None, ws=None, recheck=None):
        self.au = au or Audio()
        self.ws = ws if ws is not None else ler_palavras()
        self.recheck = recheck or {}          # resultado do whisper em blocos sem palavra (cache)
        self.duvidas = []
        self.cont = {"pausas": 0, "muletas": 0, "respiros": 0, "repeticoes": 0, "falas_erradas": 0}

    # -- ponto de corte: quadro (1/30 s) mais quieto entre lo e hi, perto do alvo
    def ponto(self, lo, hi, alvo):
        k0, k1 = int(np.ceil(lo * FPS - 1e-6)), int(np.floor(hi * FPS + 1e-6))
        if k1 < k0:
            k = int(round(alvo * FPS))
            return k / FPS
        ks = np.arange(k0, k1 + 1)
        db = self.au.rms(ks / FPS, 0.04)
        ok = ks[db <= db.min() + 2]
        return ok[np.argmin(np.abs(ok / FPS - alvo))] / FPS

    def blocos(self):
        us = unidades_de_som(self.au)
        fim_tr = self.ws[-1]["e"] if self.ws else 0
        for u in us:
            u["palavras"] = []
        # cada palavra vai pro bloco com voz em que ela mais se sobrepõe (o whisper erra uns décimos)
        com_voz = [u for u in us if u["voz"] >= 3]
        inis = [u["ini"] for u in com_voz]
        unid_de = {}
        for w in self.ws:
            k = bisect_right(inis, w["e"] + 0.3)
            melhor, mv = None, -1e9
            for u in com_voz[max(0, k - 4):k + 1]:
                sob = min(w["e"], u["fim"]) - max(w["s"], u["ini"])
                if sob > mv:
                    melhor, mv = u, sob
            if melhor is not None and mv > -0.35:
                melhor["palavras"].append(w)
                unid_de[w["i"]] = melhor
        self.us, self.unid_de, self.fim_tr = us, unid_de, fim_tr
        return us

    def decidir(self):
        ws = self.ws
        if not hasattr(self, "us"):
            self.blocos()
        fora = {}            # índice da palavra -> motivo
        m, d = _muletas(ws, self.unid_de)
        for i in m:
            fora[i] = "muletas"
        self.duvidas += d
        self.duvidas += [{"t": t, "o_que": o} for t, o in DUVIDAS_MANUAIS if t < self.fim_tr]
        for a, b, o in APARTES_SEM_TEXTO:
            self.duvidas.append({"t": a, "o_que": f"saiu {b - a:.0f}s fora da aula: {o}"})
        # cortes manuais
        for t, texto in CORTES_MANUAIS:
            r = _achar_seq(ws, t, texto)
            if r is None:
                if t < self.fim_tr:
                    print(f"aviso: não achei '{texto}' perto de {t}", file=sys.stderr)
                continue
            for i in range(r[0], r[1] + 1):
                fora[i] = "falas_erradas"
        # repetições
        nao = []
        for t, texto in NAO_CORTAR:
            r = _achar_seq(ws, t, texto)
            if r:
                nao.append(r[0])
        self.cand_rep, d = _repeticoes(ws)
        self.duvidas += d
        for c in self.cand_rep:
            if c["i"] in nao:
                continue
            if any(i in fora for i in range(c["i"], c["j"])):
                continue
            for i in range(c["i"], c["j"]):
                fora[i] = "repeticoes"
        self.fora = fora
        # blocos: com voz e sem palavra = muleta/ruído; sem voz = respiro/estalo
        for u in self.us:
            if u["ini"] > self.fim_tr:
                u["sai"] = None
                continue
            if u["voz"] < 3:
                u["sai"] = "respiros" if u["fim"] - u["ini"] >= RESPIRO_MIN else "silencio"
            elif not u["palavras"]:
                r = self.recheck.get(f"{u['ini']:.2f}")
                if any(a <= u["ini"] and u["fim"] <= b for a, b, _ in APARTES_SEM_TEXTO):
                    u["sai"] = "falas_erradas"
                elif r and self._fala_real(u, r):
                    u["sai"] = None
                    if r.get("fala"):
                        d = self.duvidas[-1] if self.duvidas else {}
                        if d.get("tipo") == "pulou" and u["ini"] - d["fim"] < 3:
                            if r["texto"] not in d["texto"]:
                                d["texto"] += " " + r["texto"]
                            d["fim"] = u["fim"]
                        else:
                            self.duvidas.append({"t": round(u["ini"], 1), "tipo": "pulou", "texto": r["texto"], "fim": u["fim"]})
                elif not (r and (r.get("muleta") or _so_muleta(r["texto"]))) and self._colado(u):
                    u["sai"] = None      # colado numa palavra: deve ser o fim/começo dela (ex. "impor|tante")
                else:
                    u["sai"] = "muletas" if (r and (r.get("muleta") or _so_muleta(r["texto"]))) else "respiros"
            elif all(w["i"] in fora for w in u["palavras"]):
                u["sai"] = fora[u["palavras"][0]["i"]]
            else:
                u["sai"] = None

    def _colado(self, u, folga=0.15):
        return any(v["voz"] >= 3 and v["palavras"] and (0 <= u["ini"] - v["fim"] < folga or 0 <= v["ini"] - u["fim"] < folga)
                   for v in self._us_entre(u["ini"] - 1, u["fim"] + 1))

    def _fala_real(self, u, r):
        """O whisper ouviu palavra de verdade nesse bloco sem texto?"""
        if r.get("fala"):
            return True
        pal = [sem_acento(x) for x in r["texto"].split() if not _so_muleta(x)]
        pal = [x for x in pal if x]
        if not pal:
            return False
        # a palavra existe na transcrição ali perto (o whisper só pôs no lugar errado)
        perto = {w["n"] for w in self.ws if abs(w["s"] - u["ini"]) < 2.5}
        if any(x in perto for x in pal):
            return True
        # vizinho de um bloco que é fala ("Ambas!" entre "...em comum." e "Compram no TikTok")
        for v in self.us:
            if v is not u and v["voz"] >= 3 and not v["palavras"] and (abs(v["ini"] - u["fim"]) < 1.0 or abs(u["ini"] - v["fim"]) < 1.0):
                rv = self.recheck.get(f"{v['ini']:.2f}")
                if rv and rv.get("fala"):
                    return True
        return False

    def pedacos(self):
        """Pedaços de fala que ficam: [ini, fim, pontuação da última palavra, motivo do que vem antes]."""
        out = []
        for u in self.us:
            if u["ini"] > self.fim_tr:
                break
            if u["sai"] or u["voz"] < 3:
                continue
            ps = u["palavras"]
            if not any(w["i"] in self.fora for w in ps):
                out.append([u["ini"], u["fim"], ps[-1]["pont"] if ps else ""])
                continue
            # divide o bloco nas fronteiras entre palavra que fica e palavra que sai
            ini = u["ini"]
            dentro = ps[0]["i"] not in self.fora
            for a, b in zip(ps, ps[1:]):
                sai_a, sai_b = a["i"] in self.fora, b["i"] in self.fora
                if sai_a == sai_b:
                    continue
                lo = max((a["s"] + a["e"]) / 2, u["ini"])
                hi = min((b["s"] + b["e"]) / 2, u["fim"])
                p = self.ponto(lo, hi, (a["e"] + b["s"]) / 2)
                if not sai_a:
                    out.append([ini, p, a["pont"]])
                else:
                    ini = p
            if ps[-1]["i"] not in self.fora:
                out.append([ini, u["fim"], ps[-1]["pont"]])
        return [p for p in out if p[1] - p[0] > 0.02]

    def _livre(self, t, sentido):
        """Quanto silêncio limpo há a partir de t (sentido +1 depois, -1 antes)."""
        k = int(round(t / HOP))
        lim = self.au.chao + 9
        n = 0
        while 0 <= k + sentido * (n + 1) < len(self.au.db) and self.au.db[k + sentido * (n + 1)] <= lim and n < 300:
            n += 1
        return n * HOP

    def trechos(self):
        ps = self.pedacos()
        dur = int(self.au.dur * FPS) / FPS
        tr = []
        ini = 0.0
        # antes da 1ª fala: deixa só uma folga
        if ps:
            ini = self.ponto(max(0, ps[0][0] - 0.25), max(0, ps[0][0] - 0.08), ps[0][0] - 0.15)
        for A, B in zip(ps, ps[1:]):
            gap = B[0] - A[1]
            # algo saiu no meio? (palavra, muleta, respiro)
            saiu = any(u["sai"] and u["sai"] != "silencio" and u["ini"] >= A[1] - 0.01 and u["fim"] <= B[0] + 0.01
                       for u in self._us_entre(A[1], B[0]))
            if gap <= PAUSA_MAX and not saiu:
                continue
            P = PAUSA_FRASE if A[2] in ".?!…" and A[2] else (PAUSA_VIRGULA if A[2] in ",;:" and A[2] else PAUSA_MEIO)
            la, lb = self._livre(A[1], +1), self._livre(B[0], -1)
            la, lb = min(la, gap), min(lb, gap)
            ta = min(la, max(P / 2, P - lb))
            tb = min(lb, P - ta)
            if ta + tb >= gap - 1 / FPS:
                continue                         # não sobra nada pra tirar
            x = self.ponto(A[1] + min(ta, 0.04), A[1] + la - 0.01 if la > 0.05 else A[1], A[1] + ta)
            y = self.ponto(B[0] - lb + 0.01 if lb > 0.05 else B[0], B[0] - min(tb, 0.04), B[0] - tb)
            if y - x < 1 / FPS or (not saiu and y - x < MIN_TIRAR):
                continue                         # pulo de imagem por quase nada não compensa
            tr.append([ini, x])
            ini = y
            if not saiu:
                self.cont["pausas"] += 1
        fim = ps[-1][1] + 0.3 if ps else dur
        tr.append([ini, min(dur, self.ponto(fim - 0.1, fim + 0.2, fim))])
        # trechos protegidos entram inteiros
        for a, b in PROTEGER:
            tr.append([np.floor(a * FPS) / FPS, np.ceil(b * FPS) / FPS])
        tr.sort()
        res = []
        for a, b in tr:
            if res and a <= res[-1][1] + 1e-6:
                res[-1][1] = max(res[-1][1], b)
            else:
                res.append([a, b])
        return [{"a": round(a, 4), "b": round(b, 4)} for a, b in res if b - a >= 1.5 / FPS]

    def _us_entre(self, a, b):
        return [u for u in self.us if u["fim"] > a and u["ini"] < b]

    def contar(self, trechos):
        """Conta o que saiu de fato (o que caiu fora dos trechos)."""
        kept = [(t["a"], t["b"]) for t in trechos]

        def dentro(x):
            return any(a - 1e-3 <= x <= b + 1e-3 for a, b in kept)
        vistos = set()
        for u in self.us:
            if u.get("sai") in ("respiros", "muletas") and not dentro((u["ini"] + u["fim"]) / 2):
                self.cont[u["sai"]] += 1
        for i, mot in self.fora.items():
            w = self.ws[i]
            if dentro((w["s"] + w["e"]) / 2):
                continue
            # conta por ocorrência (sequência de palavras seguidas com o mesmo motivo)
            if (i - 1, mot) in vistos:
                vistos.add((i, mot))
                continue
            vistos.add((i, mot))
            self.cont[mot] += 1
        for a, b, _ in APARTES_SEM_TEXTO:
            if not dentro((a + b) / 2):
                self.cont["falas_erradas"] += 1
        total = sum(b - a for a, b in kept)
        self.cont["segundos"] = round(self.au.dur - total, 1)
        return self.cont


def _duvidas(ds):
    out = []
    for d in ds:
        if d.get("tipo") == "pulou":
            d = {"t": d["t"], "o_que": f"fala que a transcrição tinha pulado (ficou; não está no texto): \"{d['texto']}\""}
        out.append(d)
    return out


def calcular(recheck=None, salvar=True):
    pl = Plano(recheck=recheck)
    pl.blocos()
    pl.recheck = rechecar(pl, recheck)
    pl.decidir()
    tr = pl.trechos()
    cont = pl.contar(tr)
    out = {"trechos": tr, "proteger": [list(p) for p in PROTEGER], "removidos": cont,
           "duvidas": sorted(_duvidas(pl.duvidas), key=lambda d: d["t"]),
           "rechecagem": pl.recheck}
    if salvar:
        SAIDA.write_text(json.dumps(out, ensure_ascii=False, indent=1))
        _cache.clear()
    return pl, out


# ---------------------------------------------------------------- tempos (para os outros módulos)

_cache = {}


def trechos():
    if "tr" not in _cache:
        d = json.loads(SAIDA.read_text())
        tr = [(t["a"], t["b"]) for t in d["trechos"]]
        acum, s = [], 0.0
        for a, b in tr:
            acum.append(s)
            s += b - a
        _cache.update(tr=tr, acum=acum, ini=[a for a, _ in tr], total=s)
    return _cache["tr"]


def duracao_saida():
    trechos()
    return _cache["total"]


def saida_de(t):
    """Tempo da gravação -> tempo de saída. Se t caiu num pedaço cortado, devolve o começo do trecho seguinte."""
    tr = trechos()
    k = bisect_right(_cache["ini"], t) - 1
    if k < 0:
        return 0.0
    a, b = tr[k]
    if t <= b:
        return round(_cache["acum"][k] + t - a, 4)
    return round(_cache["acum"][k + 1], 4) if k + 1 < len(tr) else round(_cache["total"], 4)


def gravacao_de(s):
    """Tempo de saída -> tempo da gravação."""
    tr = trechos()
    k = max(0, bisect_right(_cache["acum"], s) - 1)
    a, b = tr[k]
    return round(min(b, a + s - _cache["acum"][k]), 4)


# ---------------------------------------------------------------- conferência

def relatorio(pl, out):
    """Lista as palavras que saem (por motivo), com um pouco de contexto."""
    ws, fora = pl.ws, pl.fora
    i = 0
    while i < len(ws):
        if i not in fora:
            i += 1
            continue
        j = i
        while j + 1 < len(ws) and j + 1 in fora:
            j += 1
        antes = " ".join(w["w"] for w in ws[max(0, i - 6):i])
        depois = " ".join(w["w"] for w in ws[j + 1:j + 7])
        print(f"{ws[i]['s']:8.2f} {fora[i]:13s} …{antes} [{' '.join(w['w'] for w in ws[i:j + 1])}] {depois}…")
        i = j + 1
    # pedaços grandes sem palavra que saíram
    tr = out["trechos"]
    for A, B in zip(tr, tr[1:]):
        if B["a"] - A["b"] > 1.5:
            print(f"{A['b']:8.2f} {'silêncio/ruído':13s} {B['a'] - A['b']:.1f}s")


def _ffmpeg(*args):
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *map(str, args)], check=True)


def proxy(saida, de=None, ate=None, largura=640, altura=360):
    """Vídeo leve com os cortes aplicados (de/ate em tempo de SAÍDA), pra ouvir se ficou palavra comida."""
    tr = trechos()
    total = duracao_saida()
    de = 0.0 if de is None else max(0.0, de)
    ate = total if ate is None else min(total, ate)
    # recorta a lista de trechos ao intervalo pedido (tudo em quadros inteiros)
    sel = []
    for (a, b), s0 in zip(tr, _cache["acum"]):
        s1 = s0 + b - a
        if s1 <= de + 1e-6 or s0 >= ate - 1e-6:
            continue
        a2 = a + max(0.0, de - s0)
        b2 = b - max(0.0, s1 - ate)
        fa, fb = int(round(a2 * FPS)), int(round(b2 * FPS))
        if fb > fa:
            sel.append((fa, fb))
    if not sel:
        sys.exit("nada nesse intervalo")
    tmp = Path(saida).with_suffix(".tmp.wav")
    # som: costura com 8 ms de fade em cada corte (sem clique); 1600 amostras por quadro a 48 kHz
    x, sr = _ler_wav(AUDIO48)
    spq = sr // FPS
    rampa = np.linspace(0, 1, int(0.008 * sr), dtype=np.float32)
    partes = []
    for k, (fa, fb) in enumerate(sel):
        p = x[fa * spq:fb * spq].copy()
        if len(p) < (fb - fa) * spq:
            p = np.pad(p, (0, (fb - fa) * spq - len(p)))
        if len(p) > 2 * len(rampa):
            if k > 0 or fa > 0:
                p[:len(rampa)] *= rampa
            p[-len(rampa):] *= rampa[::-1]
        partes.append(p)
    y = np.concatenate(partes)
    with wave.open(str(tmp), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((np.clip(y, -1, 1) * 32767).astype(np.int16).tobytes())
    # imagem: escolhe os quadros pelo número (base720 é 30 qps certinho)
    video = BASE if _pronto(BASE) else AULA / "original.mp4"
    ss = max(0.0, sel[0][0] / FPS - 1.0)
    f0 = int(round(ss * FPS))
    expr = "+".join(f"between(n,{fa - f0},{fb - f0 - 1})" for fa, fb in sel)
    filtro = Path(saida).with_suffix(".filtro.txt")
    filtro.write_text(f"[0:v]fps={FPS},select='{expr}',setpts=N/{FPS}/TB,"
                      f"scale={largura}:{altura},format=yuv420p[v]")
    dur_in = sel[-1][1] / FPS - ss + 0.5          # só decodifica o pedaço necessário
    _ffmpeg("-ss", f"{ss:.4f}", "-t", f"{dur_in:.3f}", "-i", video, "-i", tmp, "-filter_complex_script", filtro,
            "-map", "[v]", "-map", "1:a", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "30",
            "-c:a", "aac", "-b:a", "96k", "-shortest", "-movflags", "+faststart", saida)
    tmp.unlink()
    filtro.unlink()
    return saida


def _pronto(p):
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                           capture_output=True, text=True)
        return r.returncode == 0 and float(r.stdout.strip()) > 3000
    except (ValueError, OSError):
        return False


def rechecar(pl, cache=None):
    """Blocos com voz que a transcrição não pegou: ouve de novo (whisper sem filtro de voz).
    Se tiver fala de verdade, o bloco fica; se for "éé"/ruído, sai. Guarda o resultado (cache)."""
    cache = dict(cache or {})
    orfas = [u for u in pl.us if u["voz"] >= 3 and not u["palavras"] and u["ini"] <= pl.fim_tr]
    grupos = []
    for u in orfas:
        if grupos and u["ini"] - grupos[-1][-1]["fim"] < 0.6:
            grupos[-1].append(u)
        else:
            grupos.append([u])
    falta = [g for g in grupos if f"{g[0]['ini']:.2f}" not in cache]
    if falta:
        from faster_whisper import WhisperModel
        m = WhisperModel("small", device="cpu", compute_type="int8", cpu_threads=3)
        x = pl.au.x
        for g in falta:
            a, b = max(0, g[0]["ini"] - 0.15), g[-1]["fim"] + 0.15
            segs, _ = m.transcribe(x[int(a * SR):int(b * SR)], language="pt", word_timestamps=True,
                                   vad_filter=False, initial_prompt="Éé... hum... ahn... Então, né?")
            boas, muleta, texto = [], False, []
            for sg in segs:
                for w in sg.words or []:
                    t = a + (w.start + w.end) / 2
                    if not any(u["ini"] - 0.1 <= t <= u["fim"] + 0.1 for u in g):
                        continue
                    r = re.sub(r"[^\w]", "", w.word.lower())
                    texto.append(w.word.strip())
                    if r in MULETAS or r in MULETAS_SOLTAS or r in ("é", "e", "ééé", "ah", "eita"):
                        muleta = True
                    elif r and w.probability > 0.4 and r not in ("obrigado", "obrigada", "tchau", "legenda"):
                        boas.append(r)
            r = {"fala": len(boas) >= 2, "muleta": muleta, "texto": " ".join(texto)}
            for u in g:
                cache[f"{u['ini']:.2f}"] = r
            print(f"  {a:8.2f}-{b:8.2f} {r}", file=sys.stderr)
    return cache


def main():
    ap = argparse.ArgumentParser(description="Cortes da aula")
    ap.add_argument("--proxy", help="gera vídeo de conferência com os cortes")
    ap.add_argument("--de", type=float, help="início (tempo de saída, s)")
    ap.add_argument("--ate", type=float, help="fim (tempo de saída, s)")
    ap.add_argument("--relatorio", action="store_true", help="mostra o que sai, com o texto")
    a = ap.parse_args()
    if a.proxy:
        proxy(a.proxy, a.de, a.ate)
        return
    rc = json.loads(SAIDA.read_text()).get("rechecagem") if SAIDA.exists() else None
    pl, out = calcular(rc)
    if a.relatorio:
        relatorio(pl, out)
    print(json.dumps(out["removidos"], ensure_ascii=False))
    print(f"trechos: {len(out['trechos'])}  saída: {sum(t['b'] - t['a'] for t in out['trechos']):.1f}s")


if __name__ == "__main__":
    main()
