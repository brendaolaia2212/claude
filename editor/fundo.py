"""Fundo desfocado (efeito retrato) e luz no rosto, quadro a quadro.

O celular dela grava tudo nítido (janela, carro lá fora, porta). Aqui a profundidade de cada
quadro (Depth Anything V2 small, ONNX, CPU) separa o que está perto da câmera (ela, a mesa e
os pacotes) do que está longe (parede, janela). O longe é desfocado e escurece um pouco; o
rosto ganha uma luz suave. O que ela segura na mão fica nítido porque também está perto.

- mascaras(nome, passo=3): profundidade a cada `passo` quadros do corte.mp4 ->
  fundo_alfa.npy + fundo_quadros.npy (alfa 0..255 em 270x480 por quadro-chave). Leva uns minutos.
- Compositor(nome): aplicar(frame, t) -> frame com fundo desfocado + luz no rosto
  (o fx.py chama antes do zoom).

edicao.json -> "fundo": {"desfoque": 18, "escurecer": 0.86, "luz_rosto": 0.16}
"""
import bisect
import subprocess

import numpy as np

from .base import FPS, RAIZ, ler_edicao, ler_json, pasta, sondar

MODELO = RAIZ / "recursos" / "modelos" / "depth_v2s_q.onnx"
URL = "https://huggingface.co/onnx-community/depth-anything-v2-small/resolve/main/onnx/model_quantized.onnx"
BW, BH = 270, 480            # resolução das máscaras guardadas
MEAN = np.array([0.485, 0.456, 0.406], np.float32)
STD = np.array([0.229, 0.224, 0.225], np.float32)


def _sessao(threads=4):
    import onnxruntime as ort
    if not MODELO.exists():
        subprocess.run(["curl", "-sSL", URL, "-o", str(MODELO)], check=True)
    so = ort.SessionOptions()
    so.intra_op_num_threads = threads
    return ort.InferenceSession(str(MODELO), so, providers=["CPUExecutionProvider"])


def _otsu(v):
    h = np.bincount(v.ravel(), minlength=256).astype(np.float64)
    p = h / h.sum()
    w = np.cumsum(p)
    mu = np.cumsum(p * np.arange(256))
    with np.errstate(divide="ignore", invalid="ignore"):
        s = (mu[-1] * w - mu) ** 2 / (w * (1 - w))
    return int(np.nanargmax(s))


def alfa_da_profundidade(sess, rgb, limiar_ant=None, rosto=None):
    """rgb uint8 (qualquer tamanho) -> (alfa float 0..1 em BHxBW, limiar usado).

    rosto = (x0, y0, x1, y1) normalizado 0..1. O limiar separa o FUNDO (o mais longe) de tudo
    que está na distância dela ou mais perto: os pacotes na mesa ficam bem mais perto que ela,
    então dividir em "perto x longe" sem referência jogaria ela pro fundo."""
    import cv2
    x = (cv2.resize(rgb, (266, 476), interpolation=cv2.INTER_AREA).astype(np.float32) / 255 - MEAN) / STD
    d = sess.run(None, {"pixel_values": x.transpose(2, 0, 1)[None]})[0][0]
    lo, hi = np.percentile(d, 2), np.percentile(d, 98)
    d = np.clip((d - lo) / (hi - lo + 1e-6), 0, 1)
    H, W = d.shape
    alto = d[: int(H * 0.6)]                      # parte de cima: só ela e o fundo (a mesa fica embaixo)
    fundo = float(np.percentile(alto, 12))
    if rosto is not None:
        x0, y0, x1, y1 = rosto
        caixa = d[int(y0 * H):max(int(y0 * H) + 1, int(y1 * H)), int(x0 * W):max(int(x0 * W) + 1, int(x1 * W))]
        pessoa = float(np.median(caixa))
        thr = fundo + 0.42 * (pessoa - fundo) if pessoa > fundo + 0.08 else _otsu((alto * 255).astype(np.uint8)) / 255
    else:
        thr = _otsu((alto * 255).astype(np.uint8)) / 255
    if limiar_ant is not None:                     # sem piscar de um quadro pro outro
        thr = 0.7 * limiar_ant + 0.3 * thr
    a = np.clip((d - (thr - 0.06)) / 0.12, 0, 1)
    a = cv2.resize(a, (BW, BH), interpolation=cv2.INTER_LINEAR)
    return cv2.GaussianBlur(a, (0, 0), 1.2), thr


def mascaras(nome, passo=3, threads=4):
    """Profundidade a cada `passo` quadros do corte.mp4 -> fundo_alfa.npz."""
    p = pasta(nome)
    info = sondar(p / "corte.mp4")
    L, A = info["largura"], info["altura"]
    total = int(round(info["duracao"] * FPS))
    sess = _sessao(threads)
    dec = subprocess.Popen(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(p / "corte.mp4"),
                            "-vf", f"select='not(mod(n\\,{passo}))',scale={BW * 2}:{BH * 2}", "-vsync", "0",
                            "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    tam = BW * 2 * BH * 2 * 3
    rost = [r for r in ler_json(p / "rosto.json", []) if r["rosto"]]
    rt = [r["t"] for r in rost]

    def caixa(t):
        if not rt:
            return None
        j = min(range(len(rt)), key=lambda j: abs(rt[j] - t)) if len(rt) < 50 else \
            min((k for k in (bisect.bisect_left(rt, t) - 1, bisect.bisect_left(rt, t)) if 0 <= k < len(rt)),
                key=lambda k: abs(rt[k] - t))
        if abs(rt[j] - t) > 1.5:
            return None
        r = rost[j]["rosto"]
        return (r["x"] / L, r["y"] / A, (r["x"] + r["w"]) / L, (r["y"] + r["h"]) / A)

    quadros, alfas, thr = [], [], None
    q = 0
    while True:
        buf = dec.stdout.read(tam)
        if len(buf) < tam:
            break
        rgb = np.frombuffer(buf, np.uint8).reshape(BH * 2, BW * 2, 3)
        a, thr = alfa_da_profundidade(sess, rgb, thr, caixa(q / FPS))
        quadros.append(q)
        alfas.append((a * 255).astype(np.uint8))
        q += passo
    dec.wait()
    np.save(p / "fundo_alfa.npy", np.array(alfas))
    np.save(p / "fundo_quadros.npy", np.array(quadros))
    return len(quadros)


def _guiado(guia, alvo, r=6, eps=2e-3):
    """Filtro guiado (He et al.): a borda da máscara gruda na borda de verdade do quadro (cabelo)."""
    import cv2
    k = (2 * r + 1, 2 * r + 1)
    m_i = cv2.boxFilter(guia, -1, k)
    m_p = cv2.boxFilter(alvo, -1, k)
    c_ip = cv2.boxFilter(guia * alvo, -1, k) - m_i * m_p
    v_i = cv2.boxFilter(guia * guia, -1, k) - m_i * m_i
    a = c_ip / (v_i + eps)
    b = m_p - a * m_i
    return cv2.boxFilter(a, -1, k) * guia + cv2.boxFilter(b, -1, k)


class Compositor:
    def __init__(self, nome):
        p = pasta(nome)
        self.quadros = list(np.load(p / "fundo_quadros.npy"))
        self.alfas = np.load(p / "fundo_alfa.npy", mmap_mode="r")
        ed = ler_edicao(nome)
        cfg = ed.get("fundo", {})
        self.desfoque = float(cfg.get("desfoque", 18))      # sigma em px no tamanho cheio
        self.escurecer = float(cfg.get("escurecer", 0.86))
        self.dessaturar = float(cfg.get("dessaturar", 0.18))
        self.luz = float(cfg.get("luz_rosto", 0.16))
        rost = [r for r in ler_json(p / "rosto.json", []) if r["rosto"]]
        self.rt = [r["t"] for r in rost]
        self.rostos = [r["rosto"] for r in rost]
        # trechos (tempo do corte): sem desfoque (a profundidade se perde, ex.: a peça colada na
        # câmera) e "teto fora" (planos abertos: teto e cortina perto da câmera ficam nítidos)
        self.sem_desfoque = [tuple(x) for x in cfg.get("sem_desfoque", [])]
        self.teto_fora = [tuple(x) for x in cfg.get("teto_fora", [])]
        # emendas em quadros: a média no tempo não atravessa um corte
        segs = ed["corte"]["segmentos"]
        acc, self.emendas = 0.0, [0]
        for a_, b_ in segs:
            acc += b_ - a_
            self.emendas.append(int(round(acc * FPS)))
        self._emendas_set = set(self.emendas)
        # movimento: onde a imagem mexe (mão gesticulando, peça sendo erguida) a mediana no tempo
        # apagaria a mão; ali vale a máscara crua dos quadros-chave vizinhos (união)
        self._prev, self._prev_q, self._mov = None, None, None

    def _chave(self, i, q):
        """Máscara do quadro-chave i, mediana com os vizinhos do mesmo plano (sem piscar)."""
        e = bisect.bisect_right(self.emendas, q) - 1
        lo, hi = self.emendas[e], self.emendas[e + 1] if e + 1 < len(self.emendas) else 10 ** 9
        viz = [j for j in range(i - 2, i + 3) if 0 <= j < len(self.quadros) and lo <= self.quadros[j] < hi]
        if len(viz) >= 3:
            return np.median(np.stack([self.alfas[j] for j in viz]), axis=0).astype(np.float32) / 255
        return self.alfas[i].astype(np.float32) / 255

    def _bruto(self, q):
        """União das máscaras cruas dos dois quadros-chave em volta de q (mesmo plano)."""
        i = max(0, bisect.bisect_right(self.quadros, q) - 1)
        e = bisect.bisect_right(self.emendas, q) - 1
        lo, hi = self.emendas[e], self.emendas[e + 1] if e + 1 < len(self.emendas) else 10 ** 9
        viz = [j for j in (i, i + 1) if 0 <= j < len(self.quadros) and lo <= self.quadros[j] < hi] or [i]
        return np.max(np.stack([self.alfas[j] for j in viz]), axis=0).astype(np.float32) / 255

    def _movimento(self, frame, q):
        import cv2
        peq = cv2.cvtColor(cv2.resize(frame, (BW, BH), interpolation=cv2.INTER_AREA),
                           cv2.COLOR_RGB2GRAY).astype(np.float32)
        if self._prev is not None and q == self._prev_q + 1 and q not in self._emendas_set:
            d = cv2.GaussianBlur(np.abs(peq - self._prev), (0, 0), 2)
            self._mov = d if self._mov is None else np.maximum(d, self._mov * 0.85)
        else:
            self._mov = None
        self._prev, self._prev_q = peq, q
        if self._mov is None:
            return None
        m = (self._mov > 10).astype(np.uint8)
        return cv2.dilate(m, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))) > 0

    def _alfa(self, q):
        i = bisect.bisect_right(self.quadros, q) - 1
        if i < 0:
            return self._chave(0, q)
        if i + 1 >= len(self.quadros):
            return self._chave(len(self.quadros) - 1, q)
        q0, q1 = self.quadros[i], self.quadros[i + 1]
        e = bisect.bisect_right(self.emendas, q) - 1           # não mistura máscara de outro plano
        lo, hi = self.emendas[e], self.emendas[e + 1] if e + 1 < len(self.emendas) else 10 ** 9
        if q1 >= hi:
            return self._chave(i, q)
        if q0 < lo:
            return self._chave(i + 1, q)
        w = (q - q0) / max(1, q1 - q0)
        return self._chave(i, q) * (1 - w) + self._chave(i + 1, q) * w

    @staticmethod
    def _ilhas(a, face):
        """Fica só o primeiro plano ligado ao corpo (toca o rosto) ou à mesa (toca a borda de
        baixo). Quadro na parede ou pedaço de cortina solto voltam pro fundo."""
        import cv2
        n, rot = cv2.connectedComponents((a > 0.5).astype(np.uint8), connectivity=8)
        if n <= 2:
            return a
        manter = set(np.unique(rot[-3:, :])) | set(np.unique(rot[face > 0.5]))
        manter.discard(0)
        ok = np.isin(rot, list(manter))
        # suaviza a borda do que saiu
        return np.where(ok | (a <= 0.5), a, a * 0.0)

    def _rosto(self, t):
        if not self.rt:
            return None
        i = bisect.bisect_left(self.rt, t)
        cands = [j for j in (i - 1, i) if 0 <= j < len(self.rt)]
        j = min(cands, key=lambda j: abs(self.rt[j] - t))
        return self.rostos[j] if abs(self.rt[j] - t) < 1.5 else None

    def aplicar(self, frame, q):
        import cv2
        A, L = frame.shape[:2]
        t = q / FPS
        a = self._alfa(q)
        mov = self._movimento(frame, q)
        if mov is not None and mov.any():
            bruto = cv2.dilate(self._bruto(q), np.ones((5, 5), np.uint8))   # cobre o caminho entre chaves
            a = np.where(mov, np.maximum(a, bruto), a)
        # o rosto é sempre primeiro plano (segurança contra máscara errada)
        r = self._rosto(t)
        if r is not None:
            sx, sy = BW / L, BH / A
            cx, cy = (r["x"] + r["w"] / 2) * sx, (r["y"] + r["h"] / 2) * sy
            face = np.zeros_like(a)
            cv2.ellipse(face, (int(cx), int(cy)), (int(r["w"] * sx * 0.55), int(r["h"] * sy * 0.68)), 0, 0, 360, 1, -1)
            a = self._ilhas(a, face)
            # logo acima da cabeça é teto/parede parado: sem auréola nítida (mão erguida ali fica)
            topo_cab = int((r["y"] - 0.30 * r["h"]) * sy)
            if topo_cab > 2:
                xa, xb = max(0, int((r["x"] - 0.2 * r["w"]) * sx)), int((r["x"] + 1.2 * r["w"]) * sx)
                cima = a[:topo_cab, xa:xb]
                fixo = ~mov[:topo_cab, xa:xb] if mov is not None else np.ones_like(cima, bool)
                a[:topo_cab, xa:xb] = np.where(fixo, 0.0, cima)
            if any(x0 <= t < x1 for x0, x1 in self.teto_fora):
                topo = max(0, int((r["y"] - 0.35 * r["h"]) * sy))
                a[:topo] = 0
                # cortina/parede dos lados só até a linha dos ombros (cotovelos e mãos ficam)
                ombro = int((r["y"] + 1.25 * r["h"]) * sy)
                faixa = int(r["w"] * sx * 3.0)
                a[:ombro, : max(0, int(cx) - faixa)] = 0
                a[:ombro, int(cx) + faixa:] = 0
            a = np.maximum(a, cv2.GaussianBlur(face, (0, 0), 2))
        for x0, x1 in self.sem_desfoque:           # rampa de 0,3 s (sem rampa quando cai numa emenda)
            r0 = 0.0 if any(abs(x0 * FPS - e) <= 1 for e in self.emendas) else 0.3
            r1 = 0.0 if any(abs(x1 * FPS - e) <= 1 for e in self.emendas) else 0.3
            if x0 - r0 <= t < x1 + r1:
                k0 = 1.0 if r0 == 0 else (t - (x0 - r0)) / r0
                k1 = 1.0 if r1 == 0 else ((x1 + r1) - t) / r1
                a = np.maximum(a, float(np.clip(min(1.0, k0, k1), 0, 1)))
        # borda fina presa na imagem (meia resolução)
        mw, mh = L // 2, A // 2
        guia = cv2.cvtColor(cv2.resize(frame, (mw, mh), interpolation=cv2.INTER_AREA), cv2.COLOR_RGB2GRAY)
        guia = guia.astype(np.float32) / 255
        am = _guiado(guia, cv2.resize(a, (mw, mh), interpolation=cv2.INTER_LINEAR))
        am = np.clip(am, 0, 1)
        alfa = cv2.resize(am, (L, A), interpolation=cv2.INTER_LINEAR)[..., None]
        # fundo: desfoque normalizado (a cor dela não vaza pro fundo) em 1/4 da resolução
        pw, ph = L // 4, A // 4
        peq = cv2.resize(frame, (pw, ph), interpolation=cv2.INTER_AREA).astype(np.float32)
        wf = 1 - cv2.resize(a, (pw, ph), interpolation=cv2.INTER_AREA)
        sig = self.desfoque / 4
        num = cv2.GaussianBlur(peq * wf[..., None], (0, 0), sig)
        den = cv2.GaussianBlur(wf, (0, 0), sig)[..., None]
        borr = np.where(den > 0.05, num / np.maximum(den, 1e-3), cv2.GaussianBlur(peq, (0, 0), sig))
        cinza = borr.mean(axis=2, keepdims=True)
        borr = (borr * (1 - self.dessaturar) + cinza * self.dessaturar) * self.escurecer
        borr = cv2.resize(borr, (L, A), interpolation=cv2.INTER_LINEAR)
        out = frame.astype(np.float32) * alfa + borr * (1 - alfa)
        # luz suave no rosto (e um tico mais quente)
        if r is not None and self.luz > 0:
            gw, gh = L // 8, A // 8
            yy, xx = np.mgrid[0:gh, 0:gw].astype(np.float32)
            cx, cy = (r["x"] + r["w"] / 2) / 8, (r["y"] + r["h"] * 0.55) / 8
            sx, sy = r["w"] / 8 * 0.9, r["h"] / 8 * 1.1
            g = np.exp(-(((xx - cx) / sx) ** 2 + ((yy - cy) / sy) ** 2) / 2)
            g = cv2.resize(g, (L, A), interpolation=cv2.INTER_LINEAR)[..., None]
            ganho = 1 + self.luz * g * np.array([1.0, 0.985, 0.95], np.float32)
            out = out * ganho
        return np.clip(out, 0, 255).astype(np.uint8)
