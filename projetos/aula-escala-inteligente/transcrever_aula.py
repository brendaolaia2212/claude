"""Transcreve a aula com tempo por palavra, salvando segmento a segmento (dá pra acompanhar e retomar)."""
import json, sys, time, wave
import numpy as np
from faster_whisper import WhisperModel

wav, saida, modelo = sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "small"
with wave.open(wav) as w:
    x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
m = WhisperModel(modelo, device="cpu", compute_type="int8", cpu_threads=4)
segs, _ = m.transcribe(x, language="pt", word_timestamps=True, vad_filter=True,
                       vad_parameters={"min_silence_duration_ms": 250},
                       initial_prompt="Aula sobre TikTok Shop, afiliados, algoritmo, escala, POV, UGC, GMV, Cria aí.")
ini = time.time()
with open(saida, "w") as f:
    for s in segs:
        f.write(json.dumps({"s": s.start, "e": s.end, "t": s.text.strip(),
                            "w": [[w.word.strip(), round(w.start, 3), round(w.end, 3), round(w.probability, 3)]
                                  for w in s.words or [] if w.word.strip()]}, ensure_ascii=False) + "\n")
        f.flush()
        print(f"{s.end:7.1f}s  {time.time() - ini:6.0f}s", flush=True)
print("FIM", flush=True)
