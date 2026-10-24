"""Onde estão os rostos (olhos até boca) em cada trecho, pra nada ficar em cima de ninguém.

rostos(nome, t) -> [(x0, y0, x1, y1), ...] na tela 1080x1920 (antes do zoom do trecho), com cache em disco.
"""
import json
import subprocess

import numpy as np

from marca import PASTA

CACHE = PASTA / "rostos_cache.json"
_cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
_det = None


def _detector():
    global _det
    if _det is None:
        import cv2
        _det = cv2.FaceDetectorYN.create("/home/user/claude/recursos/modelos/face_detection_yunet_2023mar.onnx",
                                         "", (540, 960), 0.6)
    return _det


def rostos(nome, t):
    chave = f"{nome}|{t:.2f}"
    if chave not in _cache:
        r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", f"{t:.3f}", "-i",
                            str(PASTA / "proxy" / f"{nome}.mp4"), "-frames:v", "1", "-f", "rawvideo",
                            "-pix_fmt", "bgr24", "-"], capture_output=True).stdout
        caixas = []
        if len(r) == 540 * 960 * 3:
            _, faces = _detector().detect(np.frombuffer(r, np.uint8).reshape(960, 540, 3))
            for f in (faces if faces is not None else []):
                x, y, w, h = (f[:4] * 2).tolist()
                if w < 90:                     # rosto pequeno lá no fundo não conta
                    continue
                olhos = float(min(f[5], f[7]) * 2)
                boca = float(max(f[11], f[13]) * 2)
                caixas.append([round(x), round(olhos - 0.18 * h), round(x + w), round(boca + 0.12 * h)])
        _cache[chave] = caixas
    return _cache[chave]


def no_trecho(nome, a, b, passo=0.25):
    out = []
    t = a
    while t < b - 1e-6:
        out += rostos(nome, round(t, 2))
        t += passo
    return out


def salvar():
    CACHE.write_text(json.dumps(_cache))
