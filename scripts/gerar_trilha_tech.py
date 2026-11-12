#!/usr/bin/env python3
"""Trilha de fundo original "tech suave": lo-fi eletrônico, 96 BPM, 3:00 em laço perfeito.

Tudo é sintetizado aqui com numpy (nenhuma amostra ou música de terceiros). O buffer é
tratado como um círculo: caudas de nota, eco e reverb que passam do fim voltam pro começo,
o "pump" e os movimentos lentos têm número inteiro de ciclos em 3:00, e a EQ é feita no
domínio da frequência sobre o sinal inteiro. Assim o fim emenda no começo sem estalo
(o editor repete a trilha com -stream_loop).

Mixagem pensada pra ficar baixinha embaixo da voz: sem melodia protagonista, graves
contidos, vale suave entre 1 e 4 kHz (onde mora a inteligibilidade da fala) e agudos
macios. Saída normalizada (ganho linear, sem mexer no laço) para ~-20 LUFS.

Uso: python scripts/gerar_trilha_tech.py [saida.wav]   (determinístico: mesma semente)
"""
import re
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np

SR = 48000
BPM = 96
BEAT = SR * 60 // BPM          # 30000 amostras = 0,625 s
BAR = 4 * BEAT                 # 2,5 s
BARS = 72                      # 72 compassos = 180 s
N = BARS * BAR                 # 8 640 000 amostras
ALVO_LUFS = -20.0
SWING = 0.07                   # colcheia do contratempo atrasada 7% do tempo

rng = np.random.default_rng(20261112)


# ---------------------------------------------------------------- utilidades
def midi(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def pan(sig, p):
    """Pan de potência constante, p em [-1, 1]. Devolve (2, n)."""
    a = (p + 1) * np.pi / 4
    return np.stack([sig * np.cos(a), sig * np.sin(a)])


def put(buf, start, sig):
    """Soma sig (2, n) em buf a partir de start, dando a volta no fim (laço)."""
    start = int(round(start)) % N
    n = sig.shape[-1]
    if start + n <= N:
        buf[:, start:start + n] += sig
    else:
        k = N - start
        buf[:, start:] += sig[:, :k]
        buf[:, :n - k] += sig[:, k:]


def hp(f, fc, ordem=2):
    return 1 / np.sqrt(1 + (fc / np.maximum(f, 1e-3)) ** (2 * ordem))


def lp(f, fc, ordem=2):
    return 1 / np.sqrt(1 + (f / fc) ** (2 * ordem))


def sino(f, fc, db, largura_oit, forma=2.0):
    x = np.log2(np.maximum(f, 1.0) / fc)
    return 10 ** (db * np.exp(-0.5 * np.abs(x / largura_oit) ** forma) / 20)


def prateleira_grave(f, fc, db):
    return 10 ** (db / (1 + (f / fc) ** 2) / 20)


def filtrar(x, H):
    """Filtro de fase zero e circular (FFT do sinal inteiro). H(f) -> ganho."""
    x = np.asarray(x, dtype=np.float64)
    n = x.shape[-1]
    X = np.fft.rfft(x, axis=-1)
    X *= H(np.fft.rfftfreq(n, 1 / SR))
    return np.fft.irfft(X, n=n, axis=-1)


def ruido(n, H):
    return filtrar(rng.standard_normal(n), H)


def rms_db(x):
    return 20 * np.log10(np.sqrt(np.mean(np.square(x, dtype=np.float64))) + 1e-12)


# ---------------------------------------------------------------- harmonia
# acordes: (voicing do pad, nota do baixo, notas do arpejo)
ACORDES = {
    "Fmaj9":  ([57, 60, 64, 67], 41, [65, 69, 72, 76, 79]),
    "Gadd9":  ([59, 62, 67, 69], 43, [67, 71, 74, 79, 81]),
    "Em7":    ([55, 59, 62, 64], 40, [64, 67, 71, 74, 76]),
    "Am9":    ([55, 59, 60, 64], 45, [64, 69, 71, 72, 76]),
    "Dm9":    ([53, 57, 60, 64], 38, [62, 65, 69, 72, 76]),
    "G9sus4": ([57, 60, 62, 65], 43, [67, 69, 72, 74, 77]),
}
PROG = {"A": ["Fmaj9", "Gadd9", "Em7", "Am9"], "B": ["Dm9", "Em7", "Fmaj9", "G9sus4"]}
# (compasso inicial, final, progressão, variação)
SECOES = [(0, 16, "A", 1), (16, 32, "A", 2), (32, 48, "B", 3), (48, 64, "A", 4), (64, 72, "A", 5)]


def secao(b):
    for ini, fim, prog, var in SECOES:
        if ini <= b < fim:
            return prog, var
    raise ValueError(b)


def acorde(b):
    prog, _ = secao(b)
    return PROG[prog][b % 4]


def pos(b, tempo):
    return b * BAR + tempo * BEAT


def colcheia(k):
    """Tempo (em batidas) da k-ésima colcheia do compasso, com swing."""
    return k // 2 + (0.5 + SWING if k % 2 else 0.0)


# ---------------------------------------------------------------- instrumentos
TBL = 4096
_fase = np.arange(TBL) / TBL * 2 * np.pi


def tabela(nharm, queda):
    w = sum(np.sin(k * _fase + 0.3 * k) / k ** queda for k in range(1, nharm + 1))
    w = w / np.abs(w).max()
    return np.append(w, w[0])


ESCURA, CLARA = tabela(8, 1.6), tabela(14, 1.05)


def osc(tab, f, n, fase0):
    idx = ((fase0 + f * np.arange(n) / SR) % 1.0) * TBL
    i0 = idx.astype(np.int64)
    fr = idx - i0
    return tab[i0] * (1 - fr) + tab[i0 + 1] * fr


PAD_ATAQUE, PAD_SOLTA = 0.30, 1.7


def env_pad():
    t = np.arange(int(BAR + PAD_SOLTA * SR)) / SR
    e = np.ones_like(t)
    a = t < PAD_ATAQUE
    e[a] = 0.5 - 0.5 * np.cos(np.pi * t[a] / PAD_ATAQUE)
    r = t >= BAR / SR
    tr = t[r] - BAR / SR
    e[r] = np.exp(-tr / 0.5) * (0.5 + 0.5 * np.cos(np.pi * tr / PAD_SOLTA))
    return e


def pad_acorde(notas):
    """Devolve (escuro, claro), cada um (2, n): 3 vozes desafinadas por nota."""
    e = env_pad()
    n = e.size
    esc = np.zeros((2, n))
    cla = np.zeros((2, n))
    for m in notas:
        for cents, p in ((-9, -0.75), (0, 0.0), (9, 0.75)):
            f = midi(m) * 2 ** (cents / 1200)
            f0 = rng.random()
            esc += pan(osc(ESCURA, f, n, f0) * e, p)
            cla += pan(osc(CLARA, f, n, f0) * e, p)
    return esc / len(notas), cla / len(notas)


def baixo_nota(f, dur):
    n = int((dur + 0.10) * SR)
    t = np.arange(n) / SR
    y = (np.sin(2 * np.pi * f * t) + 0.30 * np.sin(4 * np.pi * f * t + 0.4)
         + 0.07 * np.sin(6 * np.pi * f * t) + 0.20 * np.sin(np.pi * f * t))
    y = np.tanh(1.2 * y) / np.tanh(1.2)
    e = np.minimum(1, t / 0.008) * (0.72 + 0.28 * np.exp(-t / 0.30))
    fim = t > dur
    e[fim] *= 0.5 + 0.5 * np.cos(np.pi * (t[fim] - dur) / 0.10)
    return y * e


def bumbo():
    n = int(0.5 * SR)
    t = np.arange(n) / SR
    f = 47 + 66 * np.exp(-t / 0.032)
    y = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.19) * (1 - np.exp(-t / 0.0015))
    batedor = ruido(n, lambda fr: lp(fr, 1400, 2)) * np.exp(-t / 0.004)
    y = y + 0.06 * batedor / np.abs(batedor).max()
    return y * (0.5 + 0.5 * np.cos(np.pi * t / t[-1]))


def caixa():
    n = int(0.4 * SR)
    t = np.arange(n) / SR
    corpo = np.sin(2 * np.pi * 188 * t + 2.0 * np.exp(-t / 0.01)) * np.exp(-t / 0.045)
    nz = ruido(n, lambda f: hp(f, 900, 2) * lp(f, 5200, 2))
    nz /= np.abs(nz).max()
    y = 0.55 * corpo + 0.8 * nz * np.exp(-t / 0.085)
    return y * (1 - np.exp(-t / 0.0008)) * (0.5 + 0.5 * np.cos(np.pi * t / t[-1]))


def chimbal(aberto):
    n = int((0.55 if aberto else 0.12) * SR)
    t = np.arange(n) / SR
    nz = ruido(n, lambda f: hp(f, 6800, 3) * lp(f, 11500, 2))
    nz /= np.abs(nz).max()
    y = nz * np.exp(-t / (0.14 if aberto else 0.020)) * (1 - np.exp(-t / 0.0006))
    return y * (0.5 + 0.5 * np.cos(np.pi * t / t[-1]))


def pluck(f):
    n = int(1.3 * SR)
    t = np.arange(n) / SR
    mod = 0.9 * np.exp(-t / 0.045) * np.sin(2 * np.pi * 2 * f * t)
    y = np.sin(2 * np.pi * f * t + mod) + 0.16 * np.sin(4 * np.pi * f * t) * np.exp(-t / 0.10)
    e = np.exp(-t / 0.30) * (1 - np.exp(-t / 0.003))
    return y * e * (0.5 + 0.5 * np.cos(np.pi * t / t[-1]))


def reverb_ir(dur=3.4, pre=0.018):
    n = int(dur * SR)
    t = np.arange(n) / SR
    ir = np.zeros((2, n))
    for ch in range(2):
        nz = rng.standard_normal(n)
        for lo, hi, rt in ((0, 650, 2.5), (650, 3200, 1.9), (3200, 20000, 1.0)):
            H = (lambda f, lo=lo, hi=hi: (hp(f, lo, 3) if lo else 1.0) * lp(f, hi, 3))
            ir[ch] += filtrar(nz, H) * 10 ** (-3 * t / rt)
    ir *= (1 - np.exp(-t / 0.012)) * (0.5 + 0.5 * np.cos(np.pi * t / dur))
    ir = np.concatenate([np.zeros((2, int(pre * SR))), ir], axis=1)
    return ir / np.sqrt(np.sum(ir ** 2) / 2)


def conv_circular(x_mono, ir):
    X = np.fft.rfft(x_mono)
    out = np.empty((2, N), dtype=np.float32)
    for ch in range(2):
        out[ch] = np.fft.irfft(X * np.fft.rfft(ir[ch], n=N), n=N)
    return out


# ---------------------------------------------------------------- arranjo
def zeros():
    return np.zeros((2, N), dtype=np.float32)


def montar():
    hastes = {}

    # pads: escuro e claro separados, misturados por um movimento lento (4 ciclos em 3:00)
    cache = {}
    esc, cla = zeros(), zeros()
    for b in range(BARS):
        c = acorde(b)
        if c not in cache:
            cache[c] = pad_acorde(ACORDES[c][0])
        put(esc, b * BAR, cache[c][0])
        put(cla, b * BAR, cache[c][1])
    g = np.arange(N) / N
    mistura = (0.42 + 0.20 * np.sin(2 * np.pi * 4 * g - np.pi / 2)).astype(np.float32)
    pad = esc * (1 - mistura) + cla * mistura
    del esc, cla
    p = (np.arange(N) % BEAT) / SR                       # "pump" leve em cada batida
    pump = (1 - 0.17 * np.exp(-p / 0.15) * (1 - np.exp(-p / 0.006))).astype(np.float32)
    pad *= pump
    hastes["pad"] = pad

    # baixo
    baixo = zeros()
    for b in range(BARS):
        _, var = secao(b)
        f = midi(ACORDES[acorde(b)][1])
        notas = [(0, 3.55)] if var == 3 else [(0, 1.55), (colcheia(5), 1.25)]
        for tempo, dur in notas:
            put(baixo, pos(b, tempo), pan(baixo_nota(f, dur * BEAT / SR), 0.0))
    hastes["baixo"] = baixo

    # bateria
    k, cx = bumbo(), [caixa() for _ in range(3)]
    ch_f, ch_a = [chimbal(False) for _ in range(4)], [chimbal(True) for _ in range(2)]
    bum, caix, chim = zeros(), zeros(), zeros()
    for b in range(BARS):
        _, var = secao(b)
        golpes = [(0, 1.0), (2.5 + SWING, 0.7)] if var == 3 else [(0, 1.0), (2, 0.85)]
        if b % 4 == 3 and var != 3:
            golpes.append((colcheia(7), 0.55))
        for tempo, v in golpes:
            put(bum, pos(b, tempo), pan(k * v, 0.0))
        for tempo in (1, 3):
            v = (0.55 if var == 3 else 0.8) * rng.uniform(0.9, 1.05)
            jit = rng.normal(0, 0.002 * SR)
            put(caix, pos(b, tempo) + jit, pan(cx[rng.integers(3)] * v, 0.08))
        for kk in range(8):
            if var == 3 and kk % 2 == 0 and kk != 0:
                continue                              # seção calma: menos chimbal
            aberto = (kk == 7 and b % 4 == 3 and var in (2, 4))
            v = (0.75 if kk % 2 == 0 else 0.55) * rng.uniform(0.85, 1.1)
            amostra = ch_a[rng.integers(2)] if aberto else ch_f[rng.integers(4)]
            put(chim, pos(b, colcheia(kk)) + rng.normal(0, 0.0015 * SR), pan(amostra * v, 0.25))
        if b % 2 == 1 and var in (2, 4, 5):               # fantasminha de semicolcheia
            put(chim, pos(b, 3.75), pan(ch_f[0] * 0.28, 0.25))
    hastes["bumbo"], hastes["caixa"], hastes["chimbal"] = bum, caix, chim

    # arpejo / pluck discreto
    P = {
        1: [(0, 0, 0.8), (1, 2, 0.55), (2, 3, 0.6), (4, 4, 0.65), (5, 3, 0.5), (7, 1, 0.5)],
        2: [(0, 1, 0.7), (2, 3, 0.6), (3, 4, 0.5), (4, 2, 0.65), (6, 3, 0.55), (7, 4, 0.45)],
        3: [(0, 0, 0.6), (3, 2, 0.45), (6, 4, 0.4)],
    }
    P[4], P[5] = P[1], P[2]
    plk = {}
    arp = zeros()
    for b in range(BARS):
        _, var = secao(b)
        tons = ACORDES[acorde(b)][2]
        padrao = P[var]
        if b % 4 == 3 and var != 3:                     # resposta descendo no 4º compasso
            padrao = padrao[:4] + [(5, 2, 0.45), (6, 1, 0.42), (7, 0, 0.4)]
        for slot, ti, v in padrao:
            m = tons[ti]
            if m not in plk:
                plk[m] = pluck(midi(m))
            v *= rng.uniform(0.88, 1.06)
            put(arp, pos(b, colcheia(slot)) + rng.normal(0, 0.003 * SR),
                pan(plk[m] * v, 0.3 if slot % 2 else -0.3))
    arp *= pump
    hastes["arpejo"] = arp

    # eco pingue-pongue (colcheia pontuada), circular por np.roll
    D = int(0.75 * BEAT)
    mono = arp.mean(axis=0)
    eco = zeros()
    for i, gtap in enumerate((0.45, 0.30, 0.19, 0.11), start=1):
        eco[(i + 1) % 2] += gtap * np.roll(mono, i * D)
    eco = filtrar(eco, lambda f: hp(f, 300, 2) * lp(f, 3000, 2)).astype(np.float32)
    hastes["eco"] = eco
    return hastes


# volume de cada parte (RMS em dB, referência arbitrária; o total é normalizado depois)
NIVEIS = {"pad": -18.0, "baixo": -23.5, "bumbo": -28.5, "caixa": -35.0, "chimbal": -38.5,
          "arpejo": -28.5, "eco": -35.0}
ENVIO_REVERB = {"pad": 0.45, "arpejo": 0.55, "eco": 0.5, "caixa": 0.35, "chimbal": 0.10}
NIVEL_REVERB = -24.5


def eq_master(f):
    return (hp(f, 32, 2)                    # tira o subgrave que só ocupa espaço
            * prateleira_grave(f, 90, -3.0)  # graves contidos
            * sino(f, 350, -1.5, 0.8)        # um pouco de espaço pro corpo da voz
            * sino(f, 2000, -6.0, 1.0, 4)    # vale suave 1-4 kHz pra voz passar
            * lp(f, 11000, 2))               # agudos macios


def medir(x):
    """Integrado (LUFS) e pico verdadeiro (dBTP) pelo ebur128 do ffmpeg."""
    raw = np.ascontiguousarray(x.T, dtype=np.float32).tobytes()
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-f", "f32le", "-ar", str(SR), "-ac", "2",
                        "-i", "-", "-af", "ebur128=peak=true", "-f", "null", "-"],
                       input=raw, capture_output=True)
    txt = r.stderr.decode(errors="replace").split("Summary:")[-1]
    i = float(re.search(r"I:\s+(-?[\d.]+) LUFS", txt).group(1))
    tp = float(re.search(r"Peak:\s+(-?[\d.inf]+) dBFS", txt).group(1))
    return i, tp


def gravar_wav(x, saida):
    lsb = 1 / 32768
    tpdf = (rng.random(x.shape) - rng.random(x.shape)) * lsb
    q = np.clip(np.round((x + tpdf) * 32767), -32768, 32767).astype("<i2")
    with wave.open(str(saida), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(np.ascontiguousarray(q.T).tobytes())


def main():
    saida = Path(sys.argv[1] if len(sys.argv) > 1 else
                 Path(__file__).resolve().parent.parent / "recursos/trilhas/tech_suave.wav")
    saida.parent.mkdir(parents=True, exist_ok=True)
    hastes = montar()
    mix = np.zeros((2, N), dtype=np.float64)
    envio = np.zeros(N, dtype=np.float64)
    for nome, h in hastes.items():
        h *= 10 ** ((NIVEIS[nome] - rms_db(h)) / 20)
        mix += h
        envio += ENVIO_REVERB.get(nome, 0.0) * h.mean(axis=0)
        print(f"{nome:8s} {rms_db(h):6.1f} dB")
    wet = conv_circular(envio, reverb_ir())
    wet *= 10 ** ((NIVEL_REVERB - rms_db(wet)) / 20)
    print(f"{'reverb':8s} {rms_db(wet):6.1f} dB")
    mix += wet
    del hastes, wet
    mix = filtrar(mix, eq_master)
    i, tp = medir(mix)
    mix *= 10 ** ((ALVO_LUFS - i) / 20)
    i2, tp2 = medir(mix)
    print(f"antes: {i:.2f} LUFS, {tp:.2f} dBTP  ->  depois: {i2:.2f} LUFS, {tp2:.2f} dBTP")
    if tp2 > -3.0:
        raise SystemExit("pico verdadeiro acima de -3 dBTP")
    gravar_wav(mix, saida)
    print(saida)


if __name__ == "__main__":
    main()
