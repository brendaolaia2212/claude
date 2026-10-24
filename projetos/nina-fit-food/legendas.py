"""Tempo de cada palavra das legendas: o whisper ouve o trecho já cortado e as palavras escritas à mão
(roteiro.py, 'texto') são encaixadas nas que ele ouviu. Palavra que ele não ouviu ganha um tempo
proporcional entre as vizinhas. Resultado em cache: trabalho/nina/legendas.json.

legendas(nome, a, b, texto) -> [(palavra, início, fim)] em segundos do clipe.
"""
import difflib
import json
import re
import unicodedata

import numpy as np

import cortes as C
from marca import PASTA

CACHE = PASTA / "legendas.json"
_cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
_modelo = None


def _norm(p):
    p = unicodedata.normalize("NFD", p.lower())
    return re.sub(r"[^a-z0-9]", "", "".join(c for c in p if unicodedata.category(c) != "Mn"))


def _ouvir(nome, a, b):
    global _modelo
    if _modelo is None:
        from faster_whisper import WhisperModel
        _modelo = WhisperModel("large-v3", device="cpu", compute_type="int8", cpu_threads=4)
    x = C._audio(nome)[int(a * C.SR):int(b * C.SR)].copy()
    segs, _ = _modelo.transcribe(np.concatenate([np.zeros(8000, np.float32), x, np.zeros(8000, np.float32)]),
                                 language="pt", word_timestamps=True, beam_size=5)
    return [(w.word.strip(), a + w.start - 0.5, a + w.end - 0.5) for s in segs for w in s.words if w.word.strip()]


def _encaixar(escritas, ouvidas, a, b):
    """Tempos das palavras escritas a partir das ouvidas. Devolve (inicios, fins, quantas casaram)."""
    inicio = [None] * len(escritas)
    fim = [None] * len(escritas)
    sm = difflib.SequenceMatcher(None, [_norm(p) for p in escritas], [_norm(o[0]) for o in ouvidas], autojunk=False)
    casadas = 0
    for bloco in sm.get_matching_blocks():
        for k in range(bloco.size):
            _, s, e = ouvidas[bloco.b + k]
            if a - 0.05 <= s <= b:
                inicio[bloco.a + k], fim[bloco.a + k] = max(a, s), min(b, max(e, s + 0.08))
                casadas += 1
    # quem ficou sem tempo: reparte o espaço entre as vizinhas pelo tamanho da palavra
    k = 0
    while k < len(escritas):
        if inicio[k] is not None:
            k += 1
            continue
        j = k
        while j < len(escritas) and inicio[j] is None:
            j += 1
        t0 = fim[k - 1] if k > 0 else a + 0.05
        t1 = inicio[j] if j < len(escritas) else b - 0.05
        t1 = max(t1, t0 + 0.12 * (j - k))
        pesos = np.cumsum([0] + [len(escritas[i]) for i in range(k, j)])
        for i in range(k, j):
            inicio[i] = t0 + (t1 - t0) * pesos[i - k] / pesos[-1]
            fim[i] = t0 + (t1 - t0) * pesos[i - k + 1] / pesos[-1]
        k = j
    fora_de_ordem = sum(1 for i in range(1, len(inicio)) if inicio[i] < inicio[i - 1] - 0.01)
    return inicio, fim, casadas - 2 * fora_de_ordem


def legendas(nome, a, b, texto, tempos=None):
    """tempos: início de cada palavra escrito à mão (quando o whisper erra feio no trecho)."""
    escritas = texto.split()
    if tempos:
        ini = list(tempos)
        out = [(p, round(s, 3), round(ini[i + 1] if i + 1 < len(ini) else b, 3)) for i, (p, s) in enumerate(zip(escritas, ini))]
        return out
    chave = f"{nome}|{a:.3f}|{b:.3f}|{texto}"
    if chave in _cache:
        return [tuple(x) for x in _cache[chave]]
    # duas escutas: o trecho cortado e o clipe inteiro (com mais contexto); fica a que casa mais palavras
    candidatos = [_encaixar(escritas, _ouvir(nome, a, b), a, b),
                  _encaixar(escritas, [p for p in C.palavras(nome) if a - 0.3 <= p[1] <= b + 0.3], a, b)]
    inicio, fim, _ = max(candidatos, key=lambda c: c[2])
    for i in range(1, len(inicio)):             # nunca volta no tempo
        if inicio[i] < inicio[i - 1] + 0.06:
            inicio[i] = inicio[i - 1] + 0.06
        fim[i] = max(fim[i], inicio[i] + 0.06)
    out = [(p, round(float(min(s, b - 0.05)), 3), round(float(min(e, b)), 3)) for p, s, e in zip(escritas, inicio, fim)]
    _cache[chave] = out
    CACHE.write_text(json.dumps(_cache, ensure_ascii=False))
    return out
