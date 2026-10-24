"""Trilha original (sem direitos autorais) feita aqui: ukulele, baixo, palmas, chocalho e sininhos.

120 bpm (1 tempo = 0,5 s, 1 compasso = 2 s). A grade é ancorada no início da história,
pra cada virada de seção cair num tempo forte. Uso: gerar(duracao, ancora, secoes) -> np.array estéreo.
"""
import numpy as np

SR = 48000
BPM = 120
TEMPO = 60 / BPM
COMPASSO = 4 * TEMPO

rng = np.random.default_rng(7)


def nota(n):
    """'C4' -> Hz."""
    nomes = {"C": -9, "C#": -8, "D": -7, "D#": -6, "E": -5, "F": -4, "F#": -3, "G": -2, "G#": -1,
             "A": 0, "A#": 1, "B": 2}
    letra, oit = (n[:2], n[2:]) if n[1] == "#" else (n[:1], n[1:])
    return 440.0 * 2 ** ((nomes[letra] + 12 * (int(oit) - 4)) / 12)


def filtro_fft(x, lo=None, hi=None, sr=SR):
    """Passa-faixa suave no domínio da frequência (offline)."""
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / sr)
    g = np.ones_like(f)
    if lo:
        g *= 1 / np.sqrt(1 + (lo / np.maximum(f, 1e-3)) ** 4)
    if hi:
        g *= 1 / np.sqrt(1 + (f / hi) ** 4)
    return np.fft.irfft(X * g, len(x))


def ks(freq, dur, decay=0.996, maciez=2, seed=0):
    """Corda dedilhada (Karplus-Strong) afinada: gera numa taxa ajustada e reamostra."""
    N = max(2, int(SR / freq))
    sr2 = (N + 0.5) * freq
    total = int(dur * sr2) + N + 2
    r = np.random.default_rng(seed)
    y = np.zeros(total)
    ex = r.uniform(-1, 1, N)
    for _ in range(maciez):
        ex = 0.5 * (ex + np.roll(ex, 1))
    y[:N] = ex
    k = N + 1
    y[N] = decay * 0.5 * (y[0] + y[N - 1])
    while k < total:
        m = min(N, total - k)
        y[k:k + m] = decay * 0.5 * (y[k - N:k - N + m] + y[k - N - 1:k - N - 1 + m])
        k += m
    t_out = np.arange(int(dur * SR)) / SR
    out = np.interp(t_out * sr2, np.arange(total), y)
    ataque = np.minimum(1, np.arange(len(out)) / (0.002 * SR))
    return out * ataque


UKE = {  # afinação gCEA (G4 reentrante)
    "C": ["G4", "C4", "E4", "C5"],
    "G": ["G4", "D4", "G4", "B4"],
    "Am": ["A4", "C4", "E4", "A4"],
    "F": ["A4", "C4", "F4", "A4"],
}
BAIXO = {"C": ("C2", "G2"), "G": ("G1", "D2"), "Am": ("A1", "E2"), "F": ("F1", "C2")}
SINO = {"C": ["E5", "G5", "C6", "G5", "E5"], "G": ["D5", "G5", "B5", "G5", "D5"],
        "Am": ["C5", "E5", "A5", "E5", "C5"], "F": ["C5", "F5", "A5", "C6", "A5"]}
PROGRESSAO = ["C", "G", "Am", "F"]

_cache = {}


def _corda(n, dur, decay, seed):
    chave = (n, round(dur, 2), decay, seed % 6)
    if chave not in _cache:
        _cache[chave] = ks(nota(n), dur, decay=decay, maciez=2, seed=seed % 6)
    return _cache[chave]


def somar(buf, sinal, t, ganho=1.0, pan=0.0):
    i = int(round(t * SR))
    if i >= buf.shape[1] or i + len(sinal) <= 0:
        return
    s = sinal
    if i < 0:
        s, i = s[-i:], 0
    s = s[:buf.shape[1] - i]
    esq = ganho * np.cos((pan + 1) * np.pi / 4)
    dir_ = ganho * np.sin((pan + 1) * np.pi / 4)
    buf[0, i:i + len(s)] += s * esq
    buf[1, i:i + len(s)] += s * dir_


def batida_uke(buf, t, acorde, para_baixo=True, forca=1.0, dur=1.2, seed=0):
    cordas = UKE[acorde] if para_baixo else UKE[acorde][::-1]
    espaco = 0.011 if para_baixo else 0.008
    for k, n in enumerate(cordas):
        s = _corda(n, dur, 0.9965 if para_baixo else 0.995, seed + k)
        somar(buf, s, t + k * espaco, 0.22 * forca, pan=-0.25 + 0.5 * k / 3)


def baixo(n, dur):
    f = nota(n)
    t = np.arange(int(dur * SR)) / SR
    env = np.minimum(1, t / 0.008) * np.exp(-t * 3.2) * np.minimum(1, (dur - t) / 0.03)
    s = (np.sin(2 * np.pi * f * t) + 0.35 * np.sin(4 * np.pi * f * t) + 0.12 * np.sin(6 * np.pi * f * t))
    return np.tanh(1.1 * s) / np.tanh(1.1) * env


def bumbo():
    t = np.arange(int(0.35 * SR)) / SR
    f = 48 + 110 * np.exp(-t * 32)
    fase = 2 * np.pi * np.cumsum(f) / SR
    return np.sin(fase) * np.exp(-t * 9) + 0.25 * rng.uniform(-1, 1, len(t)) * np.exp(-t * 300)


def palma():
    n = int(0.25 * SR)
    s = np.zeros(n)
    for k, d in enumerate([0.0, 0.011, 0.022, 0.034]):
        i = int(d * SR)
        m = n - i
        tt = np.arange(m) / SR
        s[i:] += rng.uniform(-1, 1, m) * np.exp(-tt * (90 if k < 3 else 22)) * (0.8 if k < 3 else 1.0)
    return filtro_fft(s, lo=900, hi=5000) * 1.6


def chocalho(forte=False):
    n = int(0.06 * SR)
    t = np.arange(n) / SR
    env = np.minimum(1, t / 0.006) * np.exp(-t * (55 if forte else 75))
    return filtro_fft(rng.uniform(-1, 1, n), lo=5500, hi=14000) * env


def estalo():
    n = int(0.12 * SR)
    t = np.arange(n) / SR
    s = rng.uniform(-1, 1, n) * np.exp(-t * 120) + 0.6 * np.sin(2 * np.pi * 1900 * t) * np.exp(-t * 90)
    return filtro_fft(s, lo=1200, hi=6000)


def sino(n, dur=1.2):
    f = nota(n)
    t = np.arange(int(dur * SR)) / SR
    parciais = [(1, 1.0, 3.2), (2.76, 0.42, 7.0), (5.40, 0.22, 12.0), (8.93, 0.10, 18.0)]
    s = sum(a * np.sin(2 * np.pi * f * r * t) * np.exp(-t * d) for r, a, d in parciais)
    return s * np.minimum(1, t / 0.002)


def pad(acorde, dur):
    t = np.arange(int(dur * SR)) / SR
    env = np.minimum(1, t / 0.6) * np.minimum(1, (dur - t) / 0.6)
    s = np.zeros(len(t))
    for n in UKE[acorde]:
        f = nota(n) / 2
        for d in (-0.15, 0.15):
            s += np.sin(2 * np.pi * f * (1 + d / 100) * t) + 0.3 * np.sin(4 * np.pi * f * (1 + d / 100) * t)
    return s * env / 8


def prato(dur=2.5):
    n = int(dur * SR)
    t = np.arange(n) / SR
    s = rng.uniform(-1, 1, n) * np.exp(-t * 2.2)
    return filtro_fft(s, lo=4000, hi=16000) * 0.9


def subida(dur=2.0):
    """Ruído que sobe (prato ao contrário) pra entrar numa seção."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    s = filtro_fft(rng.uniform(-1, 1, n), lo=2500, hi=14000)
    return s * (t / dur) ** 2.6 * 0.8


def reverb(buf, mistura=0.18, dur=1.4):
    n = int(dur * SR)
    t = np.arange(n) / SR
    ir = rng.uniform(-1, 1, (2, n)) * np.exp(-t * 4.2)
    ir[:, :int(0.012 * SR)] = 0
    ir /= np.sqrt((ir ** 2).sum(axis=1, keepdims=True))
    out = np.empty_like(buf)
    L = buf.shape[1] + n
    nfft = 1 << (L - 1).bit_length()
    for c in range(2):
        out[c] = np.fft.irfft(np.fft.rfft(buf[c], nfft) * np.fft.rfft(ir[c], nfft), nfft)[:buf.shape[1]]
    return buf + mistura * out


def gerar(duracao, ancora, secoes, final_em=None):
    """secoes: lista de (inicio, fim, estilo) com estilo em intro|historia|reacts|cta.
    ancora: tempo (s) de um tempo forte (início do compasso 0). final_em: acorde final (tempo forte)."""
    n_total = int(duracao * SR) + SR
    uke, grave, sinos, fundo, seco = (np.zeros((2, n_total)) for _ in range(5))
    hum = np.random.default_rng(11)

    def humano(t, ms=6):
        return t + hum.normal(0, ms / 1000)

    k0 = int(np.floor((0 - ancora) / COMPASSO)) - 1
    k1 = int(np.ceil((duracao - ancora) / COMPASSO)) + 1

    def estilo_em(t):
        for a, b, e in secoes:
            if a - 1e-6 <= t < b - 1e-6:
                return e
        return None

    seed = 0
    for k in range(k0, k1):
        ini = ancora + k * COMPASSO
        if final_em is not None and ini >= final_em - 1e-6:
            break
        acorde = PROGRESSAO[k % 4]
        for tempo in range(8):                      # colcheias
            t = ini + tempo * TEMPO / 2
            if t < 0 or t >= duracao:
                continue
            e = estilo_em(t)
            if e is None:
                continue
            seed += 1
            v = 1 + hum.normal(0, 0.08)                 # força varia um pouco, como gente tocando
            if e == "intro":
                if tempo in (0, 3, 6):
                    n = UKE[acorde][[1, 2, 3][tempo // 3]]
                    somar(uke, _corda(n, 1.5, 0.997, seed), humano(t), 0.30 * v, pan=-0.2 + 0.2 * (tempo // 3))
                if tempo == 0:
                    somar(fundo, pad(acorde, COMPASSO), t, 0.30)
                continue
            # ukulele: D - D U - U D U
            padrao = {0: (True, 1.0), 2: (True, 0.8), 3: (False, 0.55), 5: (False, 0.55), 6: (True, 0.75),
                      7: (False, 0.5)}
            if tempo in padrao:
                d, f = padrao[tempo]
                batida_uke(uke, humano(t), acorde, d, f * v * (0.85 if e == "cta" else 1.0), seed=seed)
            # baixo
            if tempo == 0:
                somar(grave, baixo(BAIXO[acorde][0], 0.42), t, 0.55)
            elif tempo == 3:
                somar(grave, baixo(BAIXO[acorde][0], 0.2), t, 0.42)
            elif tempo == 4:
                somar(grave, baixo(BAIXO[acorde][1], 0.42), t, 0.5)
            elif tempo == 7:
                somar(grave, baixo(BAIXO[acorde][0], 0.2), t, 0.4)
            # bateria
            forte = e in ("reacts", "cta")
            if tempo in (0, 4) or (forte and tempo == 5 and k % 2 == 1):
                somar(seco, bumbo(), t, 0.75 if forte else 0.5)
            if tempo in (2, 6):
                somar(seco, palma() if forte else estalo(), humano(t, 3), (0.42 if forte else 0.35) * v, pan=0.1)
            somar(seco, chocalho(tempo % 2 == 1), humano(t, 4), (0.07 if tempo % 2 else 0.04) * v, pan=0.35)
            # sininhos nas reações
            if e == "reacts" and k % 2 == 0:
                pos = {0: 0, 1: 1, 3: 2, 4: 3, 6: 4}
                if tempo in pos:
                    somar(sinos, sino(SINO[acorde][pos[tempo]]), t, 0.11 * v, pan=0.3)
    # viradas: subida antes da história e das reações, prato na entrada
    for a, b, e in secoes:
        if e in ("historia", "reacts") and a > 2.0:
            somar(seco, subida(1.8), a - 1.8, 0.30)
            somar(seco, prato(), a, 0.26)
    if final_em is not None:
        batida_uke(uke, final_em, "C", True, 1.2, dur=3.0, seed=999)
        somar(grave, baixo("C2", 1.6), final_em, 0.6)
        somar(sinos, sino("C6", 2.5), final_em, 0.16)
        somar(sinos, sino("G5", 2.5), final_em + 0.06, 0.12)
        somar(seco, prato(3.0), final_em, 0.30)
        somar(seco, bumbo(), final_em, 0.8)
    # cada grupo com seu filtro: ukulele com corpo de madeira, baixo redondo, sem chiado
    for c in range(2):
        uke[c] = filtro_fft(uke[c], lo=170, hi=7500)
        grave[c] = filtro_fft(grave[c], lo=35, hi=900)
        sinos[c] = filtro_fft(sinos[c], lo=400, hi=9000)
        fundo[c] = filtro_fft(fundo[c], lo=120, hi=2500)
        seco[c] = filtro_fft(seco[c], lo=30, hi=12000)
    molhado = reverb(uke + sinos + fundo, 0.22)
    mix = molhado + grave + seco
    mix = mix[:, :int(duracao * SR)]
    mix = np.tanh(mix * 1.2) / 1.2
    pico = np.abs(mix).max()
    return (mix / pico * 0.89).astype(np.float32)


if __name__ == "__main__":
    import sys
    import wave
    dur = 24.0
    m = gerar(dur, 4.0, [(0, 4, "intro"), (4, 12, "historia"), (12, 20, "reacts"), (20, 24, "cta")], final_em=22.0)
    with wave.open(sys.argv[1], "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((m.T * 32767).astype(np.int16).tobytes())
    print("ok", m.shape)
