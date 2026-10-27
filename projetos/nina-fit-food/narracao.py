"""Narração da história, no estilo de narrador de série de comédia, com voz livre (Piper, voz 'cadu', CC0).

Gera um .wav por fala em trabalho/nina/narracao/ e um falas.json com a duração e o tempo de cada palavra
(pra o texto da tela entrar junto com a voz). Uso: python narracao.py
"""
import json
import subprocess
import wave

import numpy as np

from marca import PASTA

SAIDA = PASTA / "narracao"
VOZ = PASTA / "vozes" / "pt_BR-cadu-medium.onnx"
VELOCIDADE = 0.82        # length_scale: menor = mais rápido

FALAS = {
    "pib": "Somos membros da PIB Guarapari.",
    "grande": "Uma igreja grande. Grande mesmo.",
    "grupo": "Por isso, a gente se uniu num pequeno grupo...",
    "farol": "que a gente chama de Farol.",
    "encontros": "Esses são os nossos encontros.",
    "casal": "Até que, no ano passado, um casal chegou pra fazer parte do grupo.",
    "danilo": "Ele se chama Danilo.",
    "nina": "E ela, Nina.",
    "juntos": "E juntos, eles têm a Nina Fit Food.",
    "lanchinho": "No Farol, a gente sempre leva um lanchinho.",
    "todos": "E todos nós...",
    "cidade": "e a cidade de Guarapari...",
    "apaixonados": "nos tornamos apaixonados pelas delícias que a Nina prepara.",
    "reacao": "E esse vídeo mostra a reação de quem come essas delícias... e se apaixona.",
}

# timbre de narrador: tira o grave embolado, dá corpo e presença, comprime de leve
FILTRO = ("highpass=f=80,equalizer=f=160:t=q:w=1:g=2.5,equalizer=f=3200:t=q:w=1.2:g=3,"
          "acompressor=threshold=-20dB:ratio=3:attack=5:release=120:makeup=3,"
          "aecho=0.8:0.5:18|31:0.12|0.07,loudnorm=I=-18:TP=-2:LRA=7")


def sintetizar():
    from piper import PiperVoice, SynthesisConfig

    SAIDA.mkdir(parents=True, exist_ok=True)
    v = PiperVoice.load(str(VOZ))
    sr = v.config.sample_rate
    for chave, txt in FALAS.items():
        cfg = SynthesisConfig(length_scale=VELOCIDADE, noise_scale=0.72, noise_w_scale=0.85)
        audio = np.concatenate([c.audio_float_array for c in v.synthesize(txt, cfg)])
        bruto = SAIDA / f"_{chave}.wav"
        with wave.open(str(bruto), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(sr)
            w.writeframes((np.clip(audio, -1, 1) * 32767).astype(np.int16).tobytes())
        # 48 kHz estéreo, sem o silêncio das pontas (fica 40 ms)
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(bruto), "-af",
                        "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.04,"
                        "areverse,silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.06,areverse,"
                        f"aresample=48000:resampler=soxr,{FILTRO},aresample=48000",
                        "-ac", "2", "-ar", "48000", str(SAIDA / f"{chave}.wav")], check=True)
        bruto.unlink()


def tempos_das_palavras():
    """Tempo de cada palavra de cada fala (o whisper ouve a própria narração)."""
    from faster_whisper import WhisperModel

    m = WhisperModel("large-v3", device="cpu", compute_type="int8", cpu_threads=4)
    dados = {}
    for chave, txt in FALAS.items():
        r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(SAIDA / f"{chave}.wav"),
                            "-ac", "1", "-ar", "16000", "-f", "f32le", "-"], capture_output=True, check=True).stdout
        x = np.frombuffer(r, np.float32)
        segs, _ = m.transcribe(np.concatenate([np.zeros(8000, np.float32), x, np.zeros(8000, np.float32)]),
                               language="pt", word_timestamps=True, initial_prompt=txt)
        ouvidas = [(w.word.strip(), max(0.0, w.start - 0.5), max(0.0, w.end - 0.5)) for s in segs for w in s.words]
        palavras = txt.split()
        if len(ouvidas) == len(palavras):
            inicios = [o[1] for o in ouvidas]
        else:                       # se o whisper juntar ou separar palavras, reparte pelo tamanho
            dur = len(x) / 16000
            pesos = np.cumsum([0] + [len(p) for p in palavras[:-1]])
            inicios = list(0.05 + (dur - 0.3) * pesos / sum(len(p) for p in palavras))
        dados[chave] = {"texto": txt, "duracao": len(x) / 16000, "inicios": [round(t, 3) for t in inicios],
                        "ouvido": " ".join(o[0] for o in ouvidas)}
        print(f"{chave:12s} {len(x) / 16000:5.2f}s | {dados[chave]['ouvido']}")
    (SAIDA / "falas.json").write_text(json.dumps(dados, ensure_ascii=False, indent=1))
    return dados


def falas():
    return json.loads((SAIDA / "falas.json").read_text())


if __name__ == "__main__":
    sintetizar()
    tempos_das_palavras()
