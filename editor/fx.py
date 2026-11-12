"""Efeitos no próprio vídeo, em pé ou deitado: aproximação rápida (zoom), aproximação
lenta (dolly), pulso, tremor, flash e troca seca de enquadramento.

As decisões ficam em edicao.json → "fx" (tempos no corte):
  {"tipo": "zoom", "inicio": 12.3, "fim": 14.0, "escala": 1.22, "centro": "rosto"}
  {"tipo": "dolly", "inicio": 30, "fim": 38, "escala": 1.12}
  {"tipo": "pulso", "inicio": 50.2, "fim": 50.6, "forca": 0.08}
  {"tipo": "tremor", "inicio": 61.0, "fim": 61.6, "forca": 16}
  {"tipo": "flash", "inicio": 70.0, "fim": 70.35, "forca": 0.85}
  {"tipo": "enquadrar", "inicio": 80.0, "fim": 83.5, "escala": 1.14}
"enquadrar" = troca de enquadramento SECA (sem animação): já entra na escala, centrada no
rosto (centro fixo no trecho, como uma segunda câmera) e fica assim de inicio a fim. Serve pra
trocar o enquadramento a cada frase.
"centro": "rosto" (padrão, segue o rosto), "meio" (meio de baixo do quadro, onde ela
mostra o produto) ou [x, y].

aplicar(nome) grava corte_fx.mp4 (mesmo som do corte) e o vídeo final passa a usar ele.
"""
import bisect
import math
import subprocess
from concurrent.futures import ProcessPoolExecutor

import numpy as np

from .base import FPS, ffmpeg, ler_edicao, ler_json, pasta, sondar


def _ease_out(p):
    p = min(1.0, max(0.0, p))
    return 1 - (1 - p) ** 3


def _ease_io(p):
    p = min(1.0, max(0.0, p))
    return p * p * (3 - 2 * p)


def _ruido(t, sem):
    return (math.sin(t * 1.7 + sem) * 0.5 + math.sin(t * 3.1 + sem * 2) * 0.3
            + math.sin(t * 5.3 + sem * 3) * 0.2)


class Rostos:
    def __init__(self, dados):
        self.ts = [d["t"] for d in dados]
        self.dados = dados

    def centro(self, t, L, A):
        i = bisect.bisect_left(self.ts, t)
        for j in (i, i - 1, i + 1, i - 2, i + 2):
            if 0 <= j < len(self.dados) and self.dados[j]["rosto"]:
                r = self.dados[j]["rosto"]
                return r["x"] + r["w"] / 2, r["y"] + r["h"] / 2
        return L / 2, A * 0.4

    def centro_fixo(self, t0, t1, L, A):
        """Centro mediano do rosto entre t0 e t1 (pra um enquadramento que não balança)."""
        cs = [d["rosto"] for d in self.dados if d["rosto"] and t0 - 0.5 <= d["t"] <= t1 + 0.5]
        if not cs:
            return self.centro((t0 + t1) / 2, L, A)
        xs = sorted(r["x"] + r["w"] / 2 for r in cs)
        ys = sorted(r["y"] + r["h"] / 2 for r in cs)
        return xs[len(xs) // 2], ys[len(ys) // 2]


def transformar(frame, ativos, t, rostos):
    """Aplica os efeitos ativos em t no quadro (numpy RGB)."""
    import cv2
    A, L = frame.shape[:2]
    s, tx, ty = 1.0, 0.0, 0.0
    flash = 0.0
    centro = None
    for ev in ativos:
        tr = t - ev["inicio"]
        dur = max(0.05, ev["fim"] - ev["inicio"])
        tipo = ev["tipo"]
        if tipo == "zoom":
            alvo = ev.get("escala", 1.22)
            ent, sai = ev.get("entrada", 0.16), ev.get("saida", 0.18)
            if tr < ent:
                k = _ease_out(tr / ent)
            elif tr < dur - sai:
                k = 1.0
            else:
                k = _ease_io((dur - tr) / sai) if sai > 0 else 0.0
            s *= 1 + (alvo - 1) * k
        elif tipo == "dolly":
            s *= 1 + (ev.get("escala", 1.12) - 1) * _ease_io(tr / dur)
        elif tipo == "pulso":
            s *= 1 + ev.get("forca", 0.08) * math.sin(math.pi * min(1.0, tr / min(dur, 0.3)))
        elif tipo == "tremor":
            amp = ev.get("forca", 16) * math.exp(-tr * 3.5)
            tx += amp * _ruido(t * 9, 1.7)
            ty += amp * _ruido(t * 9, 4.2)
            s *= 1.04
        elif tipo == "flash":
            flash = max(flash, ev.get("forca", 0.85) * max(0.0, 1 - tr / dur))
        elif tipo == "enquadrar":
            s *= ev.get("escala", 1.14)          # seco: já está na escala desde o 1º quadro
        if centro is None and tipo in ("zoom", "dolly", "pulso", "enquadrar"):
            c = ev.get("centro", "rosto")
            if c == "meio":
                centro = (L / 2, A * 0.62)
            elif isinstance(c, (list, tuple)):
                centro = tuple(c)
            elif tipo == "enquadrar":
                if "_centro" not in ev:
                    ev["_centro"] = rostos.centro_fixo(ev["inicio"], ev["fim"], L, A)
                centro = ev["_centro"]
    if abs(s - 1) < 1e-3 and abs(tx) < 0.5 and abs(ty) < 0.5 and flash <= 0.003:
        return frame
    cx, cy = centro or rostos.centro(t, L, A)
    M = cv2.getRotationMatrix2D((cx, cy), 0, s)
    M[0, 2] += tx
    M[1, 2] += ty
    out = cv2.warpAffine(frame, M, (L, A), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    if flash > 0.003:
        out = (out.astype(np.float32) * (1 - flash) + 255 * flash).astype(np.uint8)
    return out


def _pedaco(args):
    nome, q0, q1, saida = args
    p = pasta(nome)
    ed = ler_edicao(nome)
    eventos = sorted(ed.get("fx", []), key=lambda e: e["inicio"])
    rostos = Rostos(ler_json(p / "rosto.json", []))
    comp = None
    if ed.get("fundo") is not None and (p / "fundo_alfa.npy").exists():
        from .fundo import Compositor
        comp = Compositor(nome)          # fundo desfocado + luz no rosto, antes do zoom
    info = sondar(p / "corte.mp4")
    L, A = info["largura"], info["altura"]
    dec = subprocess.Popen(["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", f"{q0 / FPS:.6f}",
                            "-i", str(p / "corte.mp4"), "-frames:v", str(q1 - q0), "-an",
                            "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    enc = subprocess.Popen(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo",
                            "-pix_fmt", "rgb24", "-s", f"{L}x{A}", "-r", str(FPS), "-i", "-",
                            "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", "-pix_fmt", "yuv420p",
                            "-g", "30", "-threads", "2", "-video_track_timescale", "15360", str(saida)],
                           stdin=subprocess.PIPE)
    tam = L * A * 3
    ultimo = None
    for q in range(q0, q1):
        buf = dec.stdout.read(tam)
        if len(buf) < tam:
            if ultimo is None:
                break
            frame = ultimo
        else:
            frame = np.frombuffer(buf, np.uint8).reshape(A, L, 3)
            ultimo = frame
        t = q / FPS
        if comp is not None:
            frame = comp.aplicar(frame, q)
        ativos = [e for e in eventos if e["inicio"] <= t < e["fim"]]
        if ativos:
            frame = transformar(frame.copy(), ativos, t, rostos)
        enc.stdin.write(np.ascontiguousarray(frame).tobytes())
    enc.stdin.close()
    dec.stdout.close()
    dec.wait()
    if enc.wait() != 0:
        raise RuntimeError(f"Falhou ao gravar o pedaço {q0}-{q1}")
    return saida


def centro_movimento(nome, t0, t1, rosto_fora=True):
    """Onde as mãos estão trabalhando entre t0 e t1 (tempo do corte): centro do movimento
    na metade de baixo do quadro, fora do rosto. Pro zoom de "foco na mão" ao abrir o pacote."""
    import cv2
    p = pasta(nome)
    info = sondar(p / "corte.mp4")
    L, A = info["largura"], info["altura"]
    w, h = L // 4, A // 4
    dec = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", f"{t0:.3f}", "-t", f"{t1 - t0:.3f}",
                          "-i", str(p / "corte.mp4"), "-vf", f"fps=10,scale={w}:{h}", "-f", "rawvideo",
                          "-pix_fmt", "gray", "-"], capture_output=True).stdout
    n = len(dec) // (w * h)
    if n < 2:
        return [L / 2, A * 0.62]
    fr = np.frombuffer(dec[: n * w * h], np.uint8).reshape(n, h, w).astype(np.float32)
    mov = np.abs(np.diff(fr, axis=0)).sum(axis=0)
    mov[: int(h * 0.30)] = 0                      # cabeça e fundo lá em cima não contam
    if rosto_fora:
        rost = Rostos(ler_json(p / "rosto.json", []))
        for d in rost.dados:
            if d["rosto"] and t0 - 0.5 <= d["t"] <= t1 + 0.5:
                r = d["rosto"]
                mov[int(r["y"] / 4):int((r["y"] + r["h"] * 1.2) / 4), int(r["x"] / 4):int((r["x"] + r["w"]) / 4)] = 0
    mov = cv2.GaussianBlur(mov, (0, 0), 6)
    lim = np.percentile(mov, 97)
    ys, xs = np.nonzero(mov >= lim)
    pesos = mov[ys, xs]
    cx, cy = float((xs * pesos).sum() / pesos.sum()) * 4, float((ys * pesos).sum() / pesos.sum()) * 4
    return [round(cx), round(cy)]


def aplicar(nome, trabalhadores=3):
    """Grava corte_fx.mp4 com os efeitos de "fx" (o som é o mesmo do corte)."""
    p = pasta(nome)
    D = sondar(p / "corte.mp4")["duracao"]
    total = int(round(D * FPS))
    tmp = p / "render_fx"
    tmp.mkdir(exist_ok=True)
    for f in tmp.glob("*"):
        f.unlink()
    passo = FPS * 20
    tarefas = [(nome, q, min(total, q + passo), str(tmp / f"v{k:04d}.mp4"))
               for k, q in enumerate(range(0, total, passo))]
    with ProcessPoolExecutor(trabalhadores) as ex:
        partes = list(ex.map(_pedaco, tarefas))
    (tmp / "v.txt").write_text("".join(f"file '{x}'\n" for x in partes))
    ffmpeg("-f", "concat", "-safe", 0, "-i", tmp / "v.txt", "-c", "copy", tmp / "video.mp4")
    ffmpeg("-i", tmp / "video.mp4", "-i", p / "corte.mp4", "-map", "0:v", "-map", "1:a", "-c", "copy",
           "-movflags", "+faststart", p / "corte_fx.mp4")
    for f in tmp.glob("*"):
        f.unlink()
    return p / "corte_fx.mp4", sondar(p / "corte_fx.mp4")["duracao"]
