"""Vídeo 11/11 (episódio 3): edição yap madura. Gancho no 1º segundo, cartões com as frases
dela que reabrem a curiosidade ao longo do vídeo, aproximações sutis, sons discretos, sem emoji.
Tudo achado pela frase (não pelo índice) -> edicao.json (tempos no corte)."""
import json
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, "/home/user/claude")
from editor.aula import _mapa_tempo
from editor.corte import _transcricao_do_corte

NOME = "video-11nov"
P = Path("/home/user/claude/trabalho") / NOME
ed = json.loads((P / "edicao.json").read_text())
ws = json.loads((P / "transcricao.json").read_text())
manter = set(ed["corte"]["palavras"])
segs = ed["corte"]["segmentos"]
para, D = _mapa_tempo(segs)
emendas, _acc = [0.0], 0.0
for _s, _e in segs:                       # emendas no tempo do corte (onde um trecho encosta no outro)
    _acc += _e - _s
    emendas.append(round(_acc, 4))


def norm(t):
    t = unicodedata.normalize("NFD", t.lower())
    return re.sub(r"[^\w ]", "", "".join(c for c in t if unicodedata.category(c) != "Mn"))


NW = [norm(w["w"]) for w in ws]


def achar(frase, depois=0):
    alvo = norm(frase).split()
    for i in range(depois, len(ws)):
        if i not in manter or not NW[i] or NW[i].split()[0] != alvo[0]:
            continue
        toks, j = [], i
        while j < len(ws) and len(toks) < len(alvo):
            if j in manter and NW[j]:
                toks.extend(NW[j].split())
            j += 1
        if toks[:len(alvo)] == alvo:
            return i, j - 1
    sys.exit(f"Não achei no corte: {frase!r} (depois de {depois})")


def ini(i, antes=0.08):
    return round(max(0.0, para(ws[i]["s"], "inicio") - antes), 3)


def fim(i, depois=0.3):
    return round(min(D - 0.05, para(ws[i]["e"], "fim") + depois), 3)


def emenda_depois(t):
    """Primeira emenda depois de t (aproximação lenta termina num corte: sem pulo de volta)."""
    return next(e for e in emendas if e > t + 0.5)


A, FX, SX = [], [], []


def texto(frase_ini, frase_fim, t, depois=0, ate=0.7, antes=0.12, **k):
    i0, _ = achar(frase_ini, depois)
    _, i1 = achar(frase_fim, i0)
    A.append(dict({"tipo": "texto", "texto": t, "inicio": ini(i0, antes), "fim": fim(i1, ate)}, **k))
    return i0


def zoom(frase, dur=1.0, escala=1.10, depois=0, antes=0.04, **k):
    i, _ = achar(frase, depois)
    t = ini(i, antes)
    FX.append(dict({"tipo": "zoom", "inicio": t, "fim": round(min(D, t + dur), 3), "escala": escala,
                    "entrada": 0.35, "saida": 0.35}, **k))
    return t


def dolly(t0, t1, escala=1.07):
    FX.append({"tipo": "dolly", "inicio": round(t0, 3), "fim": round(t1, 3), "escala": escala})


# ---------------- gancho ----------------
_, g1 = achar("compulsiva da Shopee e do TikTok Shop")
ed["estilo"] = {"legenda": "yap", "gancho": "yap", "cor": "#FFFFFF", "zoom": True, "animacoes": "poucas",
                "sons": True}
ed["gancho"] = {"texto": "Ela nunca imaginou que essas\ncompras continuariam chegando", "sobre": "Episódio 3",
                "sub": "abrindo as compras da minha mãe", "inicio": 0.0, "fim": fim(g1, 0.3)}
dolly(0.0, emenda_depois(1.0), 1.07)          # aproximação lenta enquanto ela conta da mãe

# ---------------- por que um pacote por vez ----------------
texto("cada um desses pacotes merece", "o seu próprio momento", "cada um desses pacotes\nmerece o seu próprio momento",
      tam=100, som=None, ate=0.9)
texto("Um é óculos e o outro", "peças dos óculos", "um é óculos e o outro\nsão peças dos óculos",
      fonte="kalam", tam=86, som="pop", db=-23, ate=0.8)

# ---------------- primeiro pacote ----------------
i_lindo, _ = achar("Olha que lindo")
t_lindo = ini(i_lindo, 0.05)
FX.append({"tipo": "flash", "inicio": t_lindo, "fim": round(t_lindo + 0.35, 3), "forca": 0.3})
SX.append({"t": round(t_lindo, 3), "tipo": "brilho", "db": -21, "junto": True})
zoom("Olha que lindo", 1.6, 1.10)
texto("vocês venceram", "vocês venceram", "vocês venceram", fonte="kalam", tam=110, som="pop", db=-22, ate=0.7)
zoom("vocês venceram", 1.2, 1.08)

# ---------------- segundo pacote: a surpresa ----------------
texto("são mais três óculos", "são mais três óculos", "são mais três óculos!", fonte="instrument-italico",
      tam=116, som="plim", db=-19, ate=0.8)
zoom("Ah não são mais três óculos", 1.4, 1.12)
texto("três óculos iguais", "três óculos iguais", "três óculos iguais", sobre="como sempre, minha mãe…",
      tam=118, som="pop", db=-22, ate=0.8)
i_rel, j_rel = achar("oferta relâmpago")
A.append({"tipo": "carimbo", "texto": "relâmpago", "cor": "#F3E3C3", "giro": -7, "inicio": ini(i_rel, 0.04),
          "fim": fim(j_rel, 0.9)})
zoom("com certeza era oferta relâmpago", 1.2, 1.08)
# pose com o óculos (depois de "eu mesma, Brenda"): aproximação lenta até o corte
_, i_br = achar("eu mesma Brenda")
t_pose = fim(i_br, 0.0)
dolly(t_pose, emenda_depois(t_pose), 1.06)
SX.append({"t": round(t_pose + 0.1, 3), "tipo": "swish", "db": -22})
texto("Para a felicidade da nação", "felicidade da nação", "para a felicidade da nação", fonte="kalam", tam=100,
      som="pop", db=-23, ate=0.6)

# ---------------- a história por trás ----------------
texto("eu não sei falar pouco", "exatamente da minha mãe", "eu não sei falar pouco",
      sub="e isso veio exatamente da minha mãe", tam=110, som=None, ate=0.6)
i_ctx, _ = achar("Porque eu não tô só descobrindo")
texto("ela nunca nunca nunca imaginou", "depois que ela partisse",
      "ela nunca imaginou que essas\ncompras continuariam chegando", sub="depois que ela partisse",
      fonte="instrument-italico", tam=96, som=None, ate=0.8)
texto("A minha mãe não queria morrer", "não queria morrer", "a minha mãe não queria morrer",
      fonte="instrument-italico", tam=104, som=None, ate=1.0)
texto("Pra muitas pessoas é só mais um pacote", "só mais um pacote", "pra muitas pessoas\né só mais um pacote",
      tam=104, som=None, ate=0.5)
texto("pra mim carrega um pedaço", "momento da vida dela", "pra mim, carrega um pedaço\nde um momento da vida dela",
      fonte="instrument-italico", tam=96, som=None, ate=0.8)
texto("honrar de alguma forma", "escolhas que a minha mãe fez", "honrar de alguma forma\ntodas as escolhas que a minha mãe fez",
      tam=92, som=None, ate=0.6)
texto("o sobrenome da minha mãe", "era alegria", "o sobrenome da minha mãe\nera alegria",
      fonte="instrument-italico", tam=108, som="brilho", db=-25, ate=1.0)
# aproximações lentas no monólogo: cada uma vai até a emenda seguinte (sem pulo de volta)
t = ini(i_ctx, 0.0)
while t < para(ws[achar("Mas eu também tô amando")[0]]["s"], "inicio") - 3:
    e = emenda_depois(t)
    if e - t >= 6:
        dolly(t + 0.2, e, 1.06)
    t = e

# ---------------- final ----------------
i_amanha, _ = achar("então te espero amanhã")      # o cartão entra na despedida e fica até o sorriso final
A.append({"tipo": "texto", "texto": "Episódio 4", "sobre": "amanhã", "sub": "faltam 8 pacotes", "tam": 128,
          "som": "whoosh", "db": -22, "inicio": ini(i_amanha, 0.1), "fim": round(D - 0.05, 3)})

# ---------------- grava ----------------
A.sort(key=lambda a: a["inicio"])
FX.sort(key=lambda e: e["inicio"])
ed["animacoes"] = A
ed["fx"] = FX
ed["sons_extra"] = sorted(SX, key=lambda s: s["t"])
ed["legenda_oculta"] = ([[a["inicio"], a["fim"]] for a in A if a["tipo"] in ("texto", "carimbo")]
                        + [[0.0, ed["gancho"]["fim"]]])
ed.pop("chamada", None)
(P / "edicao.json").write_text(json.dumps(ed, ensure_ascii=False, indent=2))
_transcricao_do_corte(NOME, segs)


def mm(x):
    return f"{int(x // 60)}:{x % 60:05.2f}"


print("corte", mm(D), "| gancho até", ed["gancho"]["fim"])
for a in A:
    print(f"{mm(a['inicio'])}-{mm(a['fim'])} {a['tipo']:8s} {a.get('texto', '').replace(chr(10), ' / ')[:60]}")
for e in FX:
    print(f"   fx {e['tipo']:6s} {mm(e['inicio'])}-{mm(e['fim'])} {e.get('escala', e.get('forca', ''))}")
print(len(A), "elementos,", len(FX), "efeitos,", len(SX), "sons extras")
