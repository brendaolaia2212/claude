"""Transcrição inteira do vídeo do Cria Aí com o modelo medium, sem filtro de voz (pega reação baixa)."""
import sys, json
sys.path.insert(0, "/home/user/claude")
from editor.transcrever import _ler_wav
from faster_whisper import WhisperModel
P = "/home/user/claude/trabalho/criaai-1"
x = _ler_wav(f"{P}/voz16k.wav")
m = WhisperModel("medium", device="cpu", compute_type="int8", cpu_threads=4)
segs, _ = m.transcribe(x, language="pt", beam_size=5, word_timestamps=True, vad_filter=False,
                       condition_on_previous_text=False,
                       initial_prompt="Cria Aí! Google Flow, prompts, inteligência artificial, IA, POV Studio, UGC Studio, "
                                      "Motion Control, faceless, no face, Veo, Gemini, TikTok Shop, Shopee, Brenda.")
out = []
for s in segs:
    for w in s.words or []:
        t = w.word.strip()
        if t:
            out.append({"w": t, "s": round(w.start, 3), "e": round(w.end, 3), "p": round(w.probability, 3)})
    print(f"{s.start:7.2f} {s.text.strip()[:110]}", flush=True)
json.dump(out, open(f"{P}/transcricao_medium.json", "w"), ensure_ascii=False, indent=1)
print("FIM", len(out))
