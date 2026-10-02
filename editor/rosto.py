"""Onde está o rosto a cada 0,5 s, pra nunca pôr texto em cima dos olhos e da boca."""
import json

from .base import ALTURA, LARGURA, MODELO_ROSTO, ler_json, pasta

PASSO = 0.5


def detectar(nome):
    import cv2

    cv2.utils.logging.setLogLevel(cv2.utils.logging.LOG_LEVEL_ERROR)
    p = pasta(nome)
    cap = cv2.VideoCapture(str(p / "corte.mp4"))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    det = None
    try:
        det = cv2.FaceDetectorYN.create(str(MODELO_ROSTO), "", (LARGURA // 2, ALTURA // 2), 0.6)
    except Exception:
        haar = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    out = []
    passo = max(1, int(round(PASSO * fps)))
    for q in range(0, total, passo):
        cap.set(cv2.CAP_PROP_POS_FRAMES, q)
        ok, img = cap.read()
        if not ok:
            break
        peq = cv2.resize(img, (LARGURA // 2, ALTURA // 2))
        caixa = None
        if det is not None:
            _, faces = det.detect(peq)
            if faces is not None and len(faces):
                f = max(faces, key=lambda f: f[2] * f[3]) * 2
                x, y, w, h = f[:4]
                olhos_y = min(f[5], f[7])
                boca_y = max(f[11], f[13])
                caixa = {"x": float(x), "y": float(y), "w": float(w), "h": float(h),
                         "olhos": float(olhos_y), "boca": float(boca_y)}
        else:
            cinza = cv2.cvtColor(peq, cv2.COLOR_BGR2GRAY)
            faces = haar.detectMultiScale(cinza, 1.1, 5, minSize=(60, 60))
            if len(faces):
                x, y, w, h = [v * 2 for v in max(faces, key=lambda f: f[2] * f[3])]
                caixa = {"x": float(x), "y": float(y), "w": float(w), "h": float(h),
                         "olhos": y + 0.38 * h, "boca": y + 0.78 * h}
        out.append({"t": round(q / fps, 2), "rosto": caixa})
    cap.release()
    (p / "rosto.json").write_text(json.dumps(out))
    return out


class Rostos:
    """Consulta rápida: zona proibida (olhos até boca) num intervalo de tempo."""

    def __init__(self, nome):
        self.dados = ler_json(pasta(nome) / "rosto.json", [])

    def zona(self, ini, fim):
        """(x0, y0, x1, y1) que cobre olhos e boca de ini a fim, ou None."""
        caixas = [d["rosto"] for d in self.dados
                  if d["rosto"] and ini - PASSO <= d["t"] <= fim + PASSO]
        if not caixas:
            return None
        x0 = min(c["x"] for c in caixas)
        x1 = max(c["x"] + c["w"] for c in caixas)
        y0 = min(c["olhos"] - 0.12 * c["h"] for c in caixas)
        y1 = max(c["boca"] + 0.08 * c["h"] for c in caixas)
        return (x0, y0, x1, y1)

    def centro(self):
        """Centro mediano do rosto no vídeo todo (pro zoom e pra tela dividida)."""
        cs = [d["rosto"] for d in self.dados if d["rosto"]]
        if not cs:
            return (LARGURA / 2, ALTURA * 0.4)
        xs = sorted(c["x"] + c["w"] / 2 for c in cs)
        ys = sorted(c["y"] + c["h"] / 2 for c in cs)
        return (xs[len(xs) // 2], ys[len(ys) // 2])
