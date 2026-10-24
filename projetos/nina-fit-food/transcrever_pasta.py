import json, glob, os, sys, time, wave
import numpy as np
from faster_whisper import WhisperModel
pasta = sys.argv[1]
m = WhisperModel(sys.argv[2], device="cpu", compute_type="int8", cpu_threads=4)
for wav in sorted(glob.glob(os.path.join(pasta, "*.wav"))):
    saida = wav[:-4] + "." + sys.argv[2] + ".json"
    if os.path.exists(saida):
        continue
    t0 = time.time()
    with wave.open(wav) as w:
        audio = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
    segs, info = m.transcribe(audio, language="pt", word_timestamps=True, vad_filter=False,
                              initial_prompt="Nina Fit Food, bolo, PIB Guarapari, Farol, Danilo, Nina.")
    out = []
    for s in segs:
        out.append({"s": s.start, "e": s.end, "t": s.text, "w": [{"w": w.word, "s": w.start, "e": w.end, "p": w.probability} for w in (s.words or [])]})
    json.dump(out, open(saida, "w"), ensure_ascii=False, indent=0)
    print(os.path.basename(wav), f"{time.time()-t0:.0f}s", flush=True)
    for s in out:
        print(f"  [{s['s']:.1f}-{s['e']:.1f}] {s['t']}", flush=True)
