"""Ouve de novo cada trecho com fala, já cortado, e mostra o que o whisper entende.
Palavra comida na borda aparece como palavra errada ou faltando no começo ou no fim."""
import numpy as np
from faster_whisper import WhisperModel

import cortes as C
import roteiro as R

m = WhisperModel("large-v3", device="cpu", compute_type="int8", cpu_threads=4)


def ouvir(nome, a, b, sem_som=None):
    x = C._audio(nome)[int(a * C.SR):int(b * C.SR)].copy()
    if sem_som:
        s0, s1 = int((sem_som[0] - a) * C.SR), int((sem_som[1] - a) * C.SR)
        x[max(0, s0):max(0, s1)] = 0
    f = int(0.015 * C.SR)
    x[:f] *= np.linspace(0, 1, f)
    x[-f:] *= np.linspace(1, 0, f)
    segs, _ = m.transcribe(np.concatenate([np.zeros(8000, np.float32), x, np.zeros(8000, np.float32)]),
                           language="pt", beam_size=5)
    return " ".join(s.text.strip() for s in segs)


trechos = [("abertura", t) for t in R.abertura()]
for rot, ts in R.reacoes():
    trechos += [(rot, t) for t in ts]
trechos += [("final", t) for t in R.final()]
for rot, (nome, a, b, op) in trechos:
    if not op.get("voz"):
        continue
    esperado = " ".join(w for w, s, e in C.palavras(nome) if (s + e) / 2 >= a and (s + e) / 2 <= b)
    print(f"{rot:24s} {nome} {a:6.2f}-{b:6.2f}")
    print(f"     esperado: {esperado}")
    print(f"     ouvido:   {ouvir(nome, a, b, op.get('sem_som'))}")
