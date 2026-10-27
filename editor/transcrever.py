"""Transcrição com tempo por palavra (faster-whisper) e silêncios (ffmpeg)."""
import json
import re
import wave

from .base import pasta, ler_edicao, rodar


def _ler_wav(caminho):
    """16 kHz mono em float32. O faster-whisper não abre o arquivo sozinho com o PyAV mais novo."""
    import numpy as np

    with wave.open(str(caminho)) as w:
        return np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768


def transcrever(nome, modelo="small"):
    from faster_whisper import WhisperModel

    p = pasta(nome)
    ed = ler_edicao(nome)
    wav = p / "voz16k.wav"
    rodar(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", ed["original"],
           "-vn", "-ac", "1", "-ar", "16000", str(wav)])
    m = WhisperModel(modelo, device="cpu", compute_type="int8")
    dica = ed.get("nomes_dificeis") or None
    segs, _ = m.transcribe(_ler_wav(wav), language="pt", word_timestamps=True, vad_filter=True,
                           vad_parameters={"min_silence_duration_ms": 250},
                           initial_prompt=(", ".join(dica) if dica else None))
    palavras = []
    for s in segs:
        for w in s.words or []:
            txt = w.word.strip()
            if txt:
                palavras.append({"w": txt, "s": round(w.start, 3), "e": round(w.end, 3),
                                 "p": round(w.probability, 3)})
    (p / "transcricao.json").write_text(json.dumps(palavras, ensure_ascii=False, indent=1))
    (p / "silencios.json").write_text(json.dumps(silencios(ed["original"])))
    return palavras


def silencios(arquivo, ruido="-35dB", minimo=0.25):
    r = rodar(["ffmpeg", "-hide_banner", "-i", str(arquivo), "-vn",
               "-af", f"silencedetect=noise={ruido}:d={minimo}", "-f", "null", "-"], checar=False)
    ini = [float(x) for x in re.findall(r"silence_start: (-?[\d.]+)", r.stderr)]
    fim = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", r.stderr)]
    if len(fim) < len(ini):
        from .base import sondar
        fim.append(sondar(arquivo)["duracao"])
    return [[max(0.0, a), b] for a, b in zip(ini, fim)]
