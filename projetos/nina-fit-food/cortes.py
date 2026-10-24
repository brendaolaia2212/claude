"""Cortes limpos: cada corte cai num silêncio de verdade, nunca no meio de uma palavra.

As palavras vêm do whisper (modelo grande), mas os tempos que ele marca erram por até meio segundo
(a última sílaba ainda soa, ou a palavra começa antes). Por isso o ponto de corte é procurado no
áudio: o trecho mais baixo entre o meio de uma palavra e o meio da vizinha, sempre num quadro
inteiro do vídeo (30 qps).
"""
import json
import re
import wave
from functools import lru_cache

import numpy as np

from marca import PASTA, FPS

SR = 16000


@lru_cache(maxsize=32)
def _audio(nome):
    with wave.open(str(PASTA / "proxy" / f"{nome}.wav")) as w:
        return np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768


@lru_cache(maxsize=32)
def palavras(nome):
    """[(texto, início, fim)] do clipe inteiro."""
    out = []
    for s in json.load(open(PASTA / "proxy" / f"{nome}.large-v3.json")):
        for w in s["w"]:
            t = w["w"].strip()
            if t:
                out.append((t, float(w["s"]), float(w["e"])))
    return out


def energia(nome, t, janela=0.03):
    """Volume (dB) em volta do tempo t."""
    a = _audio(nome)
    i0, i1 = max(0, int((t - janela / 2) * SR)), min(len(a), int((t + janela / 2) * SR))
    if i1 <= i0:
        return -120.0
    x = a[i0:i1]
    return float(20 * np.log10(np.sqrt((x ** 2).mean()) + 1e-9))


def _achar(nome, ref, quando):
    """Palavra pelo texto (sem pontuação) mais perto do tempo 'quando'."""
    ps = palavras(nome)
    norm = lambda s: re.sub(r"[^\wà-ú]", "", s.lower())
    cands = [(abs(p[1] - quando), i) for i, p in enumerate(ps) if norm(p[0]) == norm(ref)]
    if not cands:
        raise ValueError(f"não achei '{ref}' perto de {quando} em {nome}")
    return min(cands)[1]


def entrada(nome, ref, quando):
    """Corte de entrada antes da palavra ref (perto de 'quando'): o ponto mais quieto entre o meio da
    palavra anterior e o meio desta. Entre pontos quase tão quietos, fica o mais perto da palavra."""
    ps = palavras(nome)
    i = _achar(nome, ref, quando)
    meio = (ps[i][1] + ps[i][2]) / 2
    antes = (ps[i - 1][1] + ps[i - 1][2]) / 2 if i > 0 else 0.0
    return _quieto(nome, max(antes, ps[i][1] - 0.6), min(meio, ps[i][1] + 0.25), tarde=True)


def saida(nome, ref, quando):
    """Corte de saída depois da palavra ref: o ponto mais quieto entre o meio dela e o meio da próxima.
    Entre pontos quase tão quietos, fica o mais perto da palavra (sem silêncio sobrando)."""
    ps = palavras(nome)
    i = _achar(nome, ref, quando)
    meio = (ps[i][1] + ps[i][2]) / 2
    depois = (ps[i + 1][1] + ps[i + 1][2]) / 2 if i + 1 < len(ps) else ps[i][2] + 0.6
    return _quieto(nome, max(meio, ps[i][2] - 0.25), min(depois, ps[i][2] + 0.6), tarde=False)


def _quieto(nome, ini, fim, tarde):
    q0, q1 = int(np.ceil(ini * FPS)), int(np.floor(fim * FPS))
    if q1 < q0:
        q0 = q1 = int(round((ini + fim) / 2 * FPS))
    cands = [(energia(nome, q / FPS, 0.04), q / FPS) for q in range(q0, q1 + 1)]
    piso = min(c[0] for c in cands)
    bons = [t for e, t in cands if e <= piso + 2.0]
    return max(bons) if tarde else min(bons)


def pausas(nome, ini, fim, maxima=0.45, deixa=0.14, limiar=9.0):
    """Trechos de fala de ini a fim sem as pausas longas: [(a, b), ...].
    Pausa = mais de 'maxima' segundos abaixo do piso + 'limiar' dB; dela ficam 'deixa' s de cada lado."""
    passo = 0.01
    ts = np.arange(ini, fim, passo)
    es = np.array([energia(nome, t, 0.03) for t in ts])
    piso = np.percentile(es, 10)
    fala = es > piso + limiar
    trechos, a = [], ini
    i = 0
    while i < len(ts):
        if not fala[i]:
            j = i
            while j < len(ts) and not fala[j]:
                j += 1
            if (j - i) * passo > maxima and i > 0 and j < len(ts):
                corte_a = round((ts[i] + deixa) * FPS) / FPS
                corte_b = round((ts[j - 1] - deixa) * FPS) / FPS
                if corte_b - corte_a > 0.1:
                    trechos.append((a, corte_a))
                    a = corte_b
            i = j
        else:
            i += 1
    trechos.append((a, fim))
    return trechos


def silencio(nome, quando, raio=0.2):
    """Corte num ponto sem fala perto de 'quando' (pra trechos só de imagem)."""
    return _quieto(nome, quando - raio, quando + raio, tarde=False)


def relatorio(nome, ini, fim):
    """Texto com as palavras e o volume em volta de um trecho (pra conferir na mão)."""
    linhas = []
    for t, a, b in palavras(nome):
        if b >= ini - 0.5 and a <= fim + 0.5:
            linhas.append(f"{a:6.2f}-{b:6.2f} {t}")
    return "\n".join(linhas)
