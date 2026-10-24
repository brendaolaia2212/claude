"""Rosto (olhos até boca) em cada trecho da linha do tempo, a cada 0,25 s, em coordenadas da tela."""
import subprocess, json
import numpy as np, cv2
from montagem import montar_linha, Video, Cena, W, H, FPS
from marca import PASTA
det = cv2.FaceDetectorYN.create("/home/user/claude/recursos/modelos/face_detection_yunet_2023mar.onnx", "", (540, 960), 0.6)
trechos, audios, leg, marcos = montar_linha()
out = []
for t0, obj in trechos:
    v = obj if isinstance(obj, Video) else getattr(obj, "base", None)
    if v is None:
        continue
    passo = 0.25
    tl = 0.0
    while tl < obj.dur - 1e-6:
        r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", f"{v.ini + tl:.3f}", "-i", v.arq,
                            "-frames:v", "1", "-vf", "scale=540:960", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"],
                           capture_output=True).stdout
        if len(r) == 540 * 960 * 3:
            img = np.frombuffer(r, np.uint8).reshape(960, 540, 3)
            _, faces = det.detect(img)
            caixas = []
            if faces is not None:
                for f in faces:
                    x, y, w, h = (f[:4] * 2).tolist()
                    olhos = float(min(f[5], f[7]) * 2); boca = float(max(f[11], f[13]) * 2)
                    caixas.append([round(x), round(olhos - 0.15 * h), round(x + w), round(boca + 0.1 * h)])
            out.append(dict(t=round(t0 + tl, 2), fonte=v.arq.split("/")[-1], src=round(v.ini + tl, 2), caixas=caixas))
        tl += passo
json.dump(out, open(PASTA / "rostos_linha.json", "w"))
for o in out:
    print(f"{o['t']:6.2f} {o['fonte'][:8]} {o['src']:6.2f} {o['caixas']}")
