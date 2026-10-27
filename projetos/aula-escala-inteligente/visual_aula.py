#!/usr/bin/env python3
"""Módulo 2 — visual e render final da aula (ver ESPEC.md).

Monta o vídeo final 1280x720 30 qps a partir de base720.mp4 + audio48k.wav, aplicando os cortes de
cortes.json (trechos mantidos, tempo da GRAVAÇÃO) e desenhando por cima os eventos de eventos.json
(tempo da SAÍDA). Quadro sem evento ativo passa direto (bytes YUV do decodificador vão direto pro
codificador). Todo desenho é feito em YUV 4:2:0 (BT.709, faixa limitada), sem conversão de cor por quadro.

USO
  python codigo/visual_aula.py --eventos eventos.json --saida final.mp4
  python codigo/visual_aula.py --eventos eventos.json --saida teste.mp4 --de 120 --ate 180
  python codigo/visual_aula.py --eventos eventos.json --quadros folha.jpg 3.0 61.5 130 [--soltos pasta/]
  opções: --base base720.mp4 --audio audio48k.wav --cortes cortes.json --raiz <pasta da aula>
          --threads N (0 = todos os núcleos) --cache rosto_cache.json --bitrate 1800k --preset veryfast
  Sem cortes.json, usa a gravação inteira (sem cortes) e avisa.

EVENTOS (lista JSON; "ini"/"fim" em segundos da SAÍDA)
  {"tipo": "zoom", "ini", "fim", "escala": 1.15}
      Aproximação suave (entra e sai em ~0,6 s) centrada no rosto.
  {"tipo": "texto", "ini", "fim", "texto": str, "estilo": "titulo|palavra|rodape", "lado": "esq|dir" (palavra),
   "x": px, "y": px (opcionais, canto sup. esq.)}
      titulo = cartão azul-noite com traço laranja, embaixo à esquerda; rodape = faixa embaixo, centralizada;
      palavra = adesivo laranja que "pula" ao lado do rosto (lado livre, ou "lado").
  {"tipo": "abertura", "ini", "fim", "titulo": str, "sub": str, "kicker": "AULA" (opcional)}
      Degradê azul-noite embaixo, kicker laranja, traço que cresce, título grande e subtítulo.
  {"tipo": "slide", "ini", "fim", "slide": 6 (ou caminho), "modo": "dividida|canto|cheia",
   "recorte": [x0,y0,x1,y1] (px do slide 2001x1125, opcional), "passeio": [{"t": 40, "caixa": [x0,y0,x1,y1]}, ...],
   "nota": "texto curto embaixo do slide (dividida)", "fundo": "claro|escuro" (padrão: o que contrasta com o slide),
   "pip": "inf_dir|sup_dir" (cheia),
   "largura": 360 (canto)}
      dividida: Brenda à esquerda (576 px, recorte no rosto) e o slide à direita num cartão com sombra.
        O cartão tem o formato do recorte; "passeio" move/aproxima a janela dentro do slide (0,7 s, suave).
        Slide inteiro em 624 px de largura fica com letra pequena (~12–19 px): use recorte pra ler.
      canto: slide pequeno no canto superior direito, sem cobrir o rosto.
      cheia: slide na tela toda (letra legível) e a Brenda num quadradinho arredondado no canto.
  {"tipo": "esquema", "ini", "fim", "modelo": ..., "dados": {...}, "fundo": "escuro|claro"}
      Painel da direita (layout dividido). Modelos e "dados": ver ESQUEMAS_DOC abaixo.
  {"tipo": "videos", "ini", "fim", "arquivos": ["extras/exemplo1.mov", ...], "rotulos": ["Original", ...],
   "titulo": "opcional", "modo": "cheia|dividida",
   "destaques": [{"t": 105, "texto": "mesma blusa, outra cor", "alvo": [2,3,4,5], "ate": 110}]}
      Grade dos vídeos em pé tocando sem som, em loop, com rótulo em cima. Cada destaque mostra a legenda
      embaixo a partir de t (até "ate" ou o próximo destaque); "alvo" (1 = primeiro vídeo) ganha moldura
      laranja com ✓ e os outros escurecem. cheia: Brenda num quadradinho no canto superior direito.
  {"tipo": "imagem", "ini", "fim", "arquivo": "extras/dados_tiktok.png", "recorte": [x0,y0,x1,y1] (px da imagem),
   "destaque": [x0,y0,x1,y1] (px da imagem), "t_destaque": float, "seta": true, "texto": "legenda opcional",
   "fundo": "escuro|claro"}
      Print no painel da direita; o destaque é uma moldura laranja que pulsa, com seta balançando.
  Eventos de painel (slide dividida/cheia, esquema, imagem, videos) colados um no outro (folga < 0,5 s)
  não fazem a Brenda voltar pra tela cheia: o painel novo entra por cima do anterior (cortina de 0,45 s).

"""

import argparse
import bisect
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import time
import wave

import cv2
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import desenhos_aula as D  # noqa: E402

__doc__ = (__doc__ or "") + D.ESQUEMAS_DOC

W, H, FPS = 1280, 720, 30
TAM_QUADRO = W * H * 3 // 2
AULA = "/home/user/claude/trabalho/aula"
MODELO_ROSTO = "/home/user/claude/recursos/modelos/face_detection_yunet_2023mar.onnx"
SR = 48000
AMOSTRAS_POR_QUADRO = SR // FPS  # 1600
LARG_PAINEL = 704  # painel da direita no layout dividido (Brenda fica com 576 px = 45%)
FAIXA = 6  # faixinha laranja na emenda


def pipe_grande(proc):
    """Aumenta o buffer do pipe de saída (deixa o ffmpeg adiantar alguns quadros)."""
    try:
        import fcntl
        fcntl.fcntl(proc.stdout.fileno(), 1031, 1 << 20)  # F_SETPIPE_SZ = 1 MB
    except Exception:
        pass
    return proc


def log(*a):
    print("[visual]", *a, file=sys.stderr, flush=True)


# ============================================================== cor (BT.709, faixa limitada)
def rgb_para_yuv(rgb):
    """RGB uint8 (h,w,3) -> Y, U, V em float32 na resolução cheia."""
    f = rgb.astype(np.float32)
    r, g, b = f[..., 0], f[..., 1], f[..., 2]
    y = 0.2126 * r + 0.7152 * g + 0.0722 * b
    Y = 16 + y * (219 / 255)
    U = 128 + (b - y) / 1.8556 * (224 / 255)
    V = 128 + (r - y) / 1.5748 * (224 / 255)
    return Y, U, V


_KY = np.array([0.2126, 0.7152, 0.0722])
_M709 = np.zeros((3, 4), np.float32)
_M709[0, :3] = _KY * 219 / 255
_M709[1, :3] = (np.array([0, 0, 1.0]) - _KY) / 1.8556 * 224 / 255
_M709[2, :3] = (np.array([1.0, 0, 0]) - _KY) / 1.5748 * 224 / 255
_M709[:, 3] = [16, 128, 128]  # cv2.transform já arredonda


def yuv_para_rgb(Y, U, V):
    """Planos uint8 4:2:0 -> RGB uint8."""
    h, w = Y.shape
    Uc = cv2.resize(U, (w, h), interpolation=cv2.INTER_LINEAR).astype(np.float32) - 128
    Vc = cv2.resize(V, (w, h), interpolation=cv2.INTER_LINEAR).astype(np.float32) - 128
    y = (Y.astype(np.float32) - 16) * (255 / 219)
    pb = Uc * (255 / 224)
    pr = Vc * (255 / 224)
    r = y + 1.5748 * pr
    b = y + 1.8556 * pb
    g = (y - 0.2126 * r - 0.0722 * b) / 0.7152
    return np.clip(np.stack([r, g, b], -1) + 0.5, 0, 255).astype(np.uint8)


def meia(a):
    h, w = a.shape[:2]
    return cv2.resize(a, (w // 2, h // 2), interpolation=cv2.INTER_AREA)


def par(v):
    return int(round(v / 2.0)) * 2


class Planos:
    """Três planos Y (h,w), U e V (h/2,w/2) uint8."""

    def __init__(self, Y, U, V):
        self.Y, self.U, self.V = Y, U, V

    @classmethod
    def de_rgb(cls, rgb):
        rgb = np.ascontiguousarray(np.asarray(rgb)[:, :, :3])
        h, w = rgb.shape[0] // 2 * 2, rgb.shape[1] // 2 * 2
        rgb = rgb[:h, :w]
        yuv = cv2.transform(rgb, _M709)
        return cls(np.ascontiguousarray(yuv[..., 0]), meia(np.ascontiguousarray(yuv[..., 1])),
                   meia(np.ascontiguousarray(yuv[..., 2])))

    def copia(self):
        return Planos(self.Y.copy(), self.U.copy(), self.V.copy())

    def rgb(self):
        return yuv_para_rgb(self.Y, self.U, self.V)


class Quadro(Planos):
    def __init__(self, buf):
        a = np.frombuffer(buf, dtype=np.uint8)
        n = W * H
        super().__init__(a[:n].reshape(H, W), a[n:n + n // 4].reshape(H // 2, W // 2),
                         a[n + n // 4:].reshape(H // 2, W // 2))
        self.buf = buf


class Sprite:
    """Imagem pronta pra colar em YUV. RGB = opaca; RGBA = com transparência (pré-multiplicada)."""

    def __init__(self, img):
        arr = np.asarray(img)
        h, w = arr.shape[0], arr.shape[1]
        h2, w2 = h + (h % 2), w + (w % 2)
        if arr.shape[2] == 3:
            if (h2, w2) != (h, w):
                arr = cv2.copyMakeBorder(arr, 0, h2 - h, 0, w2 - w, cv2.BORDER_REPLICATE)
            p = Planos.de_rgb(arr)
            self.Y, self.U, self.V, self.a = p.Y, p.U, p.V, None
        else:
            if (h2, w2) != (h, w):
                arr = cv2.copyMakeBorder(arr, 0, h2 - h, 0, w2 - w, cv2.BORDER_CONSTANT, value=(0, 0, 0, 0))
            a = arr[..., 3].astype(np.float32) / 255.0
            Yf, Uf, Vf = rgb_para_yuv(arr[..., :3])
            self.a = a
            self.Y = Yf * a
            self.ah = meia(a)
            self.U = meia(Uf * a)
            self.V = meia(Vf * a)
        self.h, self.w = h2, w2

    def colar(self, dst, x, y, opac=1.0, larg_max=None):
        """Cola em dst (Planos/Quadro) com o canto em (x, y). larg_max corta a largura (efeito de crescer)."""
        if opac <= 0.003:
            return
        x, y = par(x), par(y)
        dh, dw = dst.Y.shape
        w = self.w if larg_max is None else min(self.w, par(larg_max))
        x0, y0 = max(x, 0), max(y, 0)
        x1, y1 = min(x + w, dw), min(y + self.h, dh)
        if x1 <= x0 or y1 <= y0:
            return
        sx0, sy0 = x0 - x, y0 - y
        sx1, sy1 = sx0 + (x1 - x0), sy0 + (y1 - y0)
        regY = (slice(y0, y1), slice(x0, x1))
        regC = (slice(y0 // 2, y1 // 2), slice(x0 // 2, x1 // 2))
        sY = (slice(sy0, sy1), slice(sx0, sx1))
        sC = (slice(sy0 // 2, sy1 // 2), slice(sx0 // 2, sx1 // 2))
        if self.a is None:
            if opac >= 0.997:
                dst.Y[regY] = self.Y[sY]
                dst.U[regC] = self.U[sC]
                dst.V[regC] = self.V[sC]
            else:
                for d_, s_, r_, ss in ((dst.Y, self.Y, regY, sY), (dst.U, self.U, regC, sC), (dst.V, self.V, regC, sC)):
                    b = d_[r_].astype(np.float32)
                    d_[r_] = (b + (s_[ss].astype(np.float32) - b) * opac + 0.5).astype(np.uint8)
            return
        a = self.a[sY] * opac
        b = dst.Y[regY].astype(np.float32)
        dst.Y[regY] = np.clip(b * (1 - a) + self.Y[sY] * opac + 0.5, 0, 255).astype(np.uint8)
        ah = self.ah[sC] * opac
        for d_, s_ in ((dst.U, self.U), (dst.V, self.V)):
            b = d_[regC].astype(np.float32)
            d_[regC] = np.clip(b * (1 - ah) + s_[sC] * opac + 0.5, 0, 255).astype(np.uint8)


def colar_com_mascara(dst, src, x, y, mY, mC):
    """Cola planos src em dst em (x,y) usando máscaras float (1 = src)."""
    x, y = par(x), par(y)
    h, w = src.Y.shape
    dh, dw = dst.Y.shape
    if x < 0 or y < 0 or x + w > dw or y + h > dh:
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(dw, x + w), min(dh, y + h)
        if x1 <= x0 or y1 <= y0:
            return
        sub = Planos(src.Y[y0 - y:y1 - y, x0 - x:x1 - x], src.U[(y0 - y) // 2:(y1 - y) // 2, (x0 - x) // 2:(x1 - x) // 2],
                     src.V[(y0 - y) // 2:(y1 - y) // 2, (x0 - x) // 2:(x1 - x) // 2])
        colar_com_mascara(dst, sub, x0, y0, mY[y0 - y:y1 - y, x0 - x:x1 - x],
                          mC[(y0 - y) // 2:(y1 - y) // 2, (x0 - x) // 2:(x1 - x) // 2])
        return
    for d_, s_, m, k in ((dst.Y, src.Y, mY, 1), (dst.U, src.U, mC, 2), (dst.V, src.V, mC, 2)):
        r = (slice(y // k, y // k + s_.shape[0]), slice(x // k, x // k + s_.shape[1]))
        b = d_[r].astype(np.float32)
        d_[r] = (b + (s_.astype(np.float32) - b) * m + 0.5).astype(np.uint8)


def mascara_arredondada(w, h, raio):
    tl = D.Tela(w, h, None)
    tl.ret(0, 0, w, h, (255, 255, 255), raio=raio)
    a = np.asarray(tl.final())[..., 3].astype(np.float32) / 255.0
    return a, meia(a)


# ============================================================== linha do tempo (cortes)
class Linha:
    """Trechos mantidos em quadros da gravação [a, b) e o mapeamento saída -> gravação."""

    def __init__(self, trechos):
        self.tr = trechos
        self.ini = [0]
        for a, b in trechos:
            self.ini.append(self.ini[-1] + (b - a))
        self.n = self.ini[-1]

    @classmethod
    def carregar(cls, caminho, n_src):
        if caminho and os.path.exists(caminho):
            with open(caminho) as f:
                dados = json.load(f)
            tr = []
            for t in dados["trechos"]:
                a, b = int(round(float(t["a"]) * FPS)), int(round(float(t["b"]) * FPS))
                a, b = max(0, a), min(n_src, b)
                if tr and a < tr[-1][1]:
                    a = tr[-1][1]
                if b > a:
                    tr.append((a, b))
            log("cortes: %d trechos, saída %.1f s (gravação %.1f s)" % (len(tr), sum(b - a for a, b in tr) / FPS, n_src / FPS))
            return cls(tr)
        log("AVISO: sem cortes.json (%s) — usando a gravação inteira, sem cortes" % caminho)
        return cls([(0, n_src)])

    def src(self, i):
        """quadro da saída -> quadro da gravação"""
        k = bisect.bisect_right(self.ini, i) - 1
        k = min(max(k, 0), len(self.tr) - 1)
        return self.tr[k][0] + (i - self.ini[k])

    def t_src(self, t):
        i = t * FPS
        k = bisect.bisect_right(self.ini, int(i)) - 1
        k = min(max(k, 0), len(self.tr) - 1)
        return (self.tr[k][0] + (i - self.ini[k])) / FPS

    def intervalos(self, i0, i1):
        out = []
        for k, (a, b) in enumerate(self.tr):
            o0, o1 = self.ini[k], self.ini[k + 1]
            s, e = max(o0, i0), min(o1, i1)
            if e > s:
                out.append((a + s - o0, a + e - o0))
        return out


# ============================================================== rosto
class Rosto:
    """Centro do rosto (YuNet a cada 0,5 s, suavizado), com cache em disco."""

    def __init__(self, base, linha, cache, threads=0):
        self.base, self.linha, self.cache_path = base, linha, cache
        self.threads = threads
        self.am = {}
        if cache and os.path.exists(cache):
            try:
                with open(cache) as f:
                    c = json.load(f)
                if c.get("base") == os.path.abspath(base):
                    self.am = {int(k): v for k, v in c["amostras"].items()}
            except Exception:
                pass
        self.tt = None

    def _detectar(self, s0, s1):
        cv2.setNumThreads(2)
        det = cv2.FaceDetectorYN.create(MODELO_ROSTO, "", (640, 360), 0.6, 0.3, 50)
        cmd = ["ffmpeg", "-v", "error", "-threads", str(self.threads or 2), "-ss", "%.3f" % s0, "-t", "%.3f" % (s1 - s0),
               "-i", self.base, "-vf", "fps=2,scale=640:360", "-pix_fmt", "bgr24", "-f", "rawvideo", "-"]
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        k0 = int(math.ceil(s0 * 2 - 1e-6))
        j = 0
        tam = 640 * 360 * 3
        while True:
            b = p.stdout.read(tam)
            if len(b) < tam:
                break
            img = np.frombuffer(b, np.uint8).reshape(360, 640, 3)
            _, fs = det.detect(img)
            v = None
            if fs is not None and len(fs):
                f = max(fs, key=lambda r: r[2] * r[3] * (0.5 + r[14]))
                x, y, w, h = [float(z) * 2 for z in f[:4]]
                v = [x + w / 2, y + h / 2, w, h]
            self.am[k0 + j] = v
            j += 1
        p.wait()
        return j

    def preparar(self, faixas_saida):
        """faixas_saida: [(t0, t1)] em tempo de SAÍDA onde o rosto será usado."""
        spans = []
        for t0, t1 in faixas_saida:
            i0, i1 = int(t0 * FPS), int(math.ceil(t1 * FPS))
            for a, b in self.linha.intervalos(max(0, i0), min(self.linha.n, i1)):
                spans.append([a / FPS - 1.0, b / FPS + 1.0])
        spans.sort()
        juntos = []
        for s in spans:
            if juntos and s[0] <= juntos[-1][1] + 4:
                juntos[-1][1] = max(juntos[-1][1], s[1])
            else:
                juntos.append(list(s))
        novos = 0
        t_ini = time.time()
        for s0, s1 in juntos:
            s0 = max(0.0, s0)
            ks = range(int(math.ceil(s0 * 2)), int(s1 * 2))
            if sum(k in self.am for k in ks) >= 0.9 * len(ks):
                continue
            novos += self._detectar(s0, s1)
        if novos:
            log("rosto: %d amostras novas em %.1f s" % (novos, time.time() - t_ini))
            if self.cache_path:
                try:
                    with open(self.cache_path, "w") as f:
                        json.dump({"base": os.path.abspath(self.base), "amostras": self.am}, f)
                except OSError:
                    pass
        self._suavizar()

    def _suavizar(self):
        ks = sorted(self.am)
        if not ks:
            self.tt = None
            return
        t = np.array(ks, np.float64) / 2.0
        v = np.array([self.am[k] if self.am[k] else [np.nan] * 4 for k in ks], np.float64)
        ok = ~np.isnan(v[:, 0])
        if ok.sum() == 0:
            self.tt = None
            return
        for c in range(4):
            v[:, c] = np.interp(t, t[ok], v[ok, c])
        # mediana (5) + gaussiana (sigma ~1 s)
        if len(t) >= 5:
            pad = np.pad(v, ((2, 2), (0, 0)), mode="edge")
            v = np.median(np.stack([pad[i:i + len(t)] for i in range(5)]), axis=0)
            k = np.exp(-0.5 * (np.arange(-6, 7) / 2.0) ** 2)
            k /= k.sum()
            pad = np.pad(v, ((6, 6), (0, 0)), mode="edge")
            v = np.stack([np.convolve(pad[:, c], k, mode="valid") for c in range(4)], 1)
        self.tt, self.vv = t, v

    def em(self, t_saida):
        """(cx, cy, w, h) do rosto no quadro 1280x720 no tempo de saída."""
        if self.tt is None:
            return (W * 0.53, H * 0.36, 280.0, 330.0)
        ts = self.linha.t_src(t_saida)
        return tuple(float(np.interp(ts, self.tt, self.vv[:, c])) for c in range(4))


# ============================================================== eventos
class Ctx:
    def __init__(self, raiz, rosto):
        self.raiz, self.rosto = raiz, rosto

    def caminho(self, p):
        p = str(p)
        return p if os.path.isabs(p) else os.path.join(self.raiz, p)


class Evento:
    camada = 3
    precisa_rosto = False

    def __init__(self, d, ctx):
        self.d, self.ctx = d, ctx
        self.ini, self.fim = float(d["ini"]), float(d["fim"])
        self.pronto = False

    def garantir(self):
        if not self.pronto:
            self.preparar()
            self.pronto = True

    def preparar(self):
        pass

    def aplicar(self, q, t):
        pass

    def encerrar(self):
        pass

    def envelope(self, t, din=0.45, dout=0.4):
        return min(D.lim((t - self.ini) / din), D.lim((self.fim - t) / dout))


# -------------------------------------------------------------- zoom
class Zoom(Evento):
    camada = 0
    precisa_rosto = True

    def aplicar(self, q, t):
        dur = min(0.6, (self.fim - self.ini) / 3)
        e = D.vaivem((t - self.ini) / dur) * D.vaivem((self.fim - t) / dur)
        s = 1 + (float(self.d.get("escala", 1.15)) - 1) * e
        if s <= 1.0005:
            return
        cx, cy, fw, fh = self.ctx.rosto.em(t)
        cy = cy + fh * 0.1
        w, h = W / s, H / s
        x0 = min(max(cx - w / 2, 0), W - w)
        y0 = min(max(cy - h / 2, 0), H - h)
        M = np.float32([[s, 0, -x0 * s], [0, s, -y0 * s]])
        Mc = np.float32([[s, 0, -x0 * s / 2 + (s - 1) * 0.25], [0, s, -y0 * s / 2 + (s - 1) * 0.25]])
        q.Y[:] = cv2.warpAffine(q.Y, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        q.U[:] = cv2.warpAffine(q.U, Mc, (W // 2, H // 2), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        q.V[:] = cv2.warpAffine(q.V, Mc, (W // 2, H // 2), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)


# -------------------------------------------------------------- textos sobrepostos
def cartao_texto(txt, nome, tam, cor_txt, cor_fundo, alfa_fundo=0.94, pad=(28, 18), larg_max=1000, traco=False,
                 raio=18, faixa=False, alinhar="esq", sombra=True):
    tam, linhas = D.caber(txt, nome, tam, larg_max - 2 * pad[0], 3, 26)
    tw = max(D.medir(l, nome, tam) for l in linhas)
    lh = tam * 1.2
    extra_top = 22 if traco else 0
    w = tw + 2 * pad[0] + (10 if faixa else 0)
    h = lh * len(linhas) + 2 * pad[1] + extra_top
    m = 24 if sombra else 0
    tl = D.Tela(w + 2 * m, h + 2 * m, None)
    if sombra:
        tl.sombra(m, m, m + w, m + h, raio=raio, desfoque=14, opac=0.35, desloc=(0, 6))
    tl.ret(m, m, m + w, m + h, tuple(cor_fundo) + (int(255 * alfa_fundo),), raio=raio)
    x = m + pad[0] + (10 if faixa else 0)
    if faixa:
        tl.ret(m, m, m + 10, m + h, D.LARANJA, raio=0)
        tl.ret(m, m, m + raio * 2, m + h, D.LARANJA, raio=raio)
        tl.ret(m + 10, m, m + raio * 2 + 10, m + h, tuple(cor_fundo) + (int(255 * alfa_fundo),), raio=0)
    y = m + pad[1]
    if traco:
        tl.ret(x, y + 2, x + 48, y + 7, D.LARANJA, raio=2)
        y += extra_top
    tl.bloco(x, y, linhas, nome, tam, cor_txt, entre=1.2, alinhar=alinhar, largura=tw)
    return tl.final(), m


class Texto(Evento):
    camada = 3
    precisa_rosto = True

    def preparar(self):
        est = self.d.get("estilo", "titulo")
        txt = self.d.get("texto", "")
        self.est = est
        if est == "palavra":
            cx, cy, fw, fh = self.ctx.rosto.em((self.ini + self.fim) / 2)
            esq_livre = cx - fw * 0.95 - 28  # rosto + cabelo (+ folga pra um zoom)
            dir_livre = W - (cx + fw * 0.95) - 28
            lado = self.d.get("lado") or ("esq" if esq_livre >= dir_livre else "dir")
            livre = esq_livre if lado == "esq" else dir_livre
            larg = int(min(560, max(300, livre - 10)))
            tam = 58 if len(txt) <= 14 else 46
            img, m = cartao_texto(txt, "xbold", tam, D.CREME, D.LARANJA, 1.0, pad=(24, 12), larg_max=larg, raio=16)
            img = img.rotate(3.5, resample=Image.BICUBIC, expand=True)
            self.base_img = img
            self.cache = {}
            if lado == "esq":
                xc = min(max(img.width / 2 + 16, esq_livre / 2 + 12), esq_livre + 24 - img.width / 2 + m)
            else:
                xc = max(min(W - img.width / 2 - 16, W - dir_livre / 2 - 12), W - dir_livre - 24 + img.width / 2 - m)
            self.xc = self.d.get("x", xc - img.width / 2) + img.width / 2
            self.yc = self.d.get("y", cy + fh * 0.25 - img.height / 2) + img.height / 2
        elif est == "rodape":
            img, m = cartao_texto(txt, "semi", 34, D.CREME, D.AZUL_NOITE, 0.92, pad=(26, 16), larg_max=1040,
                                  faixa=True, raio=16)
            self.sp = Sprite(img)
            self.x = self.d.get("x", (W - img.width) / 2)
            self.y = self.d.get("y", H - 30 - img.height + m)
        else:  # titulo
            img, m = cartao_texto(txt, "bold", 46, D.CREME, D.AZUL_NOITE, 0.94, pad=(30, 22), larg_max=900,
                                  traco=True, raio=20)
            self.sp = Sprite(img)
            self.x = self.d.get("x", 40 - m + 8)
            self.y = self.d.get("y", H - 40 - img.height + m)

    def aplicar(self, q, t):
        e_in = D.lim((t - self.ini) / 0.45)
        e_out = D.lim((self.fim - t) / 0.35)
        if self.est == "palavra":
            s = 0.35 + 0.65 * D.mola(D.lim((t - self.ini) / 0.4), 2.4)
            s *= 0.85 + 0.15 * D.suave(e_out)
            k = round(s * 40) / 40
            sp = self.cache.get(k)
            if sp is None:
                im = self.base_img
                sp = Sprite(im.resize((max(2, int(im.width * k)), max(2, int(im.height * k))), Image.LANCZOS))
                self.cache[k] = sp
            sp.colar(q, self.xc - sp.w / 2, self.yc - sp.h / 2, opac=D.suave(e_out) * D.lim(e_in * 3))
            return
        dy = 26 * (1 - D.sai(e_in))
        self.sp.colar(q, self.x, self.y + dy, opac=D.suave(e_in) * D.suave(e_out))


class Abertura(Evento):
    camada = 3

    def preparar(self):
        d = self.d
        g = np.zeros((440, W, 4), np.uint8)
        g[..., :3] = D.AZUL_NOITE
        x_ = np.clip(np.arange(440) / 440.0 * 1.6, 0, 1)
        rampa = x_ * x_ * (3 - 2 * x_) * 0.9
        g[..., 3] = (rampa[:, None] * 255).astype(np.uint8)
        self.grad = Sprite(Image.fromarray(g, "RGBA"))
        x = 64
        tam, linhas = D.caber(d.get("titulo", ""), "xbold", 66, 1120, 2, 40)
        tl = D.Tela(1160, int(tam * 1.12 * len(linhas) + 20), None)
        tl.bloco(0, 6, linhas, "xbold", tam, D.CREME, entre=1.12)
        self.tit = Sprite(tl.final())
        self.sub = None
        if d.get("sub"):
            t2, l2 = D.caber(d["sub"], "medio", 32, 1100, 2, 26)
            tl = D.Tela(1160, int(t2 * 1.25 * len(l2) + 12), None)
            tl.bloco(0, 4, l2, "medio", t2, (215, 214, 235))
            self.sub = Sprite(tl.final())
        self.kick = None
        if d.get("kicker"):
            tl = D.Tela(900, 44, None)
            tl.texto(0, 22, d["kicker"].upper(), "bold", 28, D.LARANJA, anchor="lm")
            self.kick = Sprite(tl.final())
        tl = D.Tela(80, 6, None)
        tl.ret(0, 0, 80, 6, D.LARANJA, raio=2)
        self.traco = Sprite(tl.final())
        # layout de baixo pra cima
        y = H - 52
        self.y_sub = None
        if self.sub:
            y -= self.sub.h
            self.y_sub = y
            y -= 14
        y -= self.tit.h
        self.y_tit = y
        y -= 22
        self.y_traco = y
        y -= 14
        if self.kick:
            y -= self.kick.h
            self.y_kick = y
        self.x = x

    def aplicar(self, q, t):
        rel = t - self.ini
        sair = D.suave((self.fim - t) / 0.5)
        self.grad.colar(q, 0, H - self.grad.h, opac=D.suave(rel / 0.5) * sair)
        if self.kick:
            p = D.lim((rel - 0.1) / 0.4)
            self.kick.colar(q, self.x, self.y_kick + 10 * (1 - D.sai(p)), opac=p * sair)
        p = D.lim((rel - 0.2) / 0.45)
        self.traco.colar(q, self.x, self.y_traco, opac=sair, larg_max=max(2, 80 * D.sai(p)))
        p = D.lim((rel - 0.3) / 0.55)
        self.tit.colar(q, self.x, self.y_tit + 30 * (1 - D.sai(p)), opac=D.suave(p) * sair)
        if self.sub:
            p = D.lim((rel - 0.7) / 0.5)
            self.sub.colar(q, self.x, self.y_sub + 16 * (1 - D.sai(p)), opac=D.suave(p) * sair)


# -------------------------------------------------------------- Brenda no quadradinho (PiP)
class Pip:
    def __init__(self, lado=176, raio=22):
        self.lado = par(lado)
        self.mY, self.mC = mascara_arredondada(self.lado, self.lado, raio)
        m = 20
        tl = D.Tela(self.lado + 2 * m, self.lado + 2 * m, None)
        tl.ret(m - 1, m - 1, m + self.lado + 1, m + self.lado + 1, None, raio=raio + 1, borda=D.CREME, larg=4)
        self.borda = Sprite(tl.final())
        self.m = m

    def sombra_em(self, tl, x, y):
        tl.sombra(x, y, x + self.lado, y + self.lado, raio=22, desfoque=14, opac=0.45, desloc=(0, 8))

    def colar(self, dst, q, rosto, x, y):
        cx, cy, fw, fh = rosto
        lado = int(min(H, max(240, fh * 2.5)))
        lado -= lado % 2
        x0 = par(min(max(cx - lado / 2, 0), W - lado))
        y0 = par(min(max(cy + fh * 0.12 - lado / 2, 0), H - lado))
        n = self.lado
        src = Planos(cv2.resize(q.Y[y0:y0 + lado, x0:x0 + lado], (n, n), interpolation=cv2.INTER_AREA),
                     cv2.resize(q.U[y0 // 2:(y0 + lado) // 2, x0 // 2:(x0 + lado) // 2], (n // 2, n // 2), interpolation=cv2.INTER_AREA),
                     cv2.resize(q.V[y0 // 2:(y0 + lado) // 2, x0 // 2:(x0 + lado) // 2], (n // 2, n // 2), interpolation=cv2.INTER_AREA))
        colar_com_mascara(dst, src, x, y, self.mY, self.mC)
        self.borda.colar(dst, x - self.m, y - self.m)


# -------------------------------------------------------------- painéis (layout dividido / tela cheia)
class EventoTela(Evento):
    """Base dos eventos que ocupam o painel da direita (dividida) ou a tela toda (cheia)."""
    camada = 1
    precisa_rosto = True
    cheia = False

    def __init__(self, d, ctx):
        super().__init__(d, ctx)
        self.manter_esq = self.manter_dir = False
        self.anterior = None
        self.ultimo = None

    @property
    def largura(self):
        return W if self.cheia else LARG_PAINEL

    def painel(self, t, q):
        raise NotImplementedError

    def aplicar(self, q, t):
        din = 0.45
        e_in = 1.0 if self.manter_esq else D.vaivem((t - self.ini) / din)
        e_out = 1.0 if self.manter_dir else D.vaivem((self.fim - t) / din)
        e = min(e_in, e_out)
        rosto = self.ctx.rosto.em(t)
        P = self.painel(t, q, rosto)
        if self.manter_dir:
            self.ultimo = (t, P)
        if self.manter_esq and self.anterior is not None and t - self.ini < 0.45:
            # cortina: o painel novo entra da emenda pra direita, com uma linha laranja na borda
            a = D.vaivem((t - self.ini) / 0.45)
            ult = self.anterior.ultimo
            if ult is not None and abs(ult[0] - (self.anterior.fim - 1.0 / FPS)) < 1e-3:
                Pa = ult[1]
            else:
                self.anterior.garantir()
                Pa = self.anterior.painel(self.anterior.fim - 1.0 / FPS, q, rosto)
            if Pa.Y.shape == P.Y.shape:
                L_ = P.Y.shape[1]
                xb = par(L_ * a)
                if xb < L_:
                    Pn = Pa.copia()
                    Pn.Y[:, :xb] = P.Y[:, :xb]
                    Pn.U[:, :xb // 2] = P.U[:, :xb // 2]
                    Pn.V[:, :xb // 2] = P.V[:, :xb // 2]
                    BORDA.colar(Pn, max(0, xb - 4), 0)
                    P = Pn
        L = self.largura
        Wt = W - L
        if self.cheia:
            x0f = W
        else:
            x0f = min(max(rosto[0] - Wt / 2, 0), W - Wt)
        Wp = par(W + (Wt - W) * e)
        x0 = par(x0f * e)
        if Wp > 0 and x0 > 0:
            x0 = min(x0, W - Wp)
            q.Y[:, :Wp] = q.Y[:, x0:x0 + Wp].copy()
            q.U[:, :Wp // 2] = q.U[:, x0 // 2:(x0 + Wp) // 2].copy()
            q.V[:, :Wp // 2] = q.V[:, x0 // 2:(x0 + Wp) // 2].copy()
        vis = W - Wp
        if vis > 0:
            q.Y[:, Wp:] = P.Y[:, :vis]
            q.U[:, Wp // 2:] = P.U[:, :vis // 2]
            q.V[:, Wp // 2:] = P.V[:, :vis // 2]


BORDA = Sprite(np.tile(np.array(D.LARANJA, np.uint8), (H, FAIXA, 1)))


def fundo_painel(fundo, w=LARG_PAINEL, faixa=True):
    pal = D.paleta(fundo)
    tl = D.Tela(w, H, pal["bg"])
    if faixa:
        tl.ret(0, 0, FAIXA, H, D.LARANJA)
    return tl, pal


def carregar_rgb(caminho):
    im = Image.open(caminho).convert("RGB")
    return np.asarray(im)


def caixa_no_aspecto(cx0, cy0, cx1, cy1, aspecto, lim_w, lim_h):
    """Expande a caixa pro aspecto (w/h) dado, sem sair da imagem."""
    w, h = cx1 - cx0, cy1 - cy0
    if w / h < aspecto:
        w = h * aspecto
    else:
        h = w / aspecto
    if w > lim_w:
        w, h = lim_w, lim_w / aspecto
    if h > lim_h:
        h, w = lim_h, lim_h * aspecto
    mx, my = (cx0 + cx1) / 2, (cy0 + cy1) / 2
    x0 = min(max(mx - w / 2, 0), lim_w - w)
    y0 = min(max(my - h / 2, 0), lim_h - h)
    return [x0, y0, x0 + w, y0 + h]


def arquivo_slide(d, ctx):
    s = d.get("slide")
    if isinstance(s, (int, float)) or (isinstance(s, str) and s.isdigit()):
        return os.path.join(ctx.raiz, "slides", "s-%02d.png" % int(s))
    return ctx.caminho(s)


class Slide(EventoTela):
    """Slide em modo dividida ou cheia. (modo canto é a classe SlideCanto.)"""

    def __init__(self, d, ctx):
        super().__init__(d, ctx)
        self.cheia = d.get("modo") == "cheia"

    def _arquivo(self):
        return arquivo_slide(self.d, self.ctx)

    def preparar(self):
        self.img = carregar_rgb(self._arquivo())
        ih, iw = self.img.shape[:2]
        rec = self.d.get("recorte") or [0, 0, iw, ih]
        rec = [float(v) for v in rec]
        self.cache = {}
        if self.cheia:
            self.aspecto = W / H
            self.cw, self.ch = W, H
            self.cx, self.cy = 0, 0
            self.janela0 = caixa_no_aspecto(*rec, self.aspecto, iw, ih)
            self.pip = Pip(184)
            canto = self.d.get("pip", "inf_dir")
            self.pip_xy = (W - 24 - self.pip.lado, 24 if canto == "sup_dir" else H - 24 - self.pip.lado)
            tl = D.Tela(W, H, D.AZUL_NOITE)
            self.base = None
        else:
            self.aspecto = (rec[2] - rec[0]) / (rec[3] - rec[1])
            nota = self.d.get("nota")
            area_w = LARG_PAINEL - FAIXA - 2 * 40
            area_h = H - 2 * 46 - (76 if nota else 0)
            cw = area_w
            ch = cw / self.aspecto
            if ch > area_h:
                ch = area_h
                cw = ch * self.aspecto
            self.cw, self.ch = par(cw), par(ch)
            self.cx = par(FAIXA + (LARG_PAINEL - FAIXA - self.cw) / 2)
            self.cy = par((H - (76 if nota else 0) - self.ch) / 2)
            fundo = self.d.get("fundo")
            if not fundo:  # contraste automático: slide claro -> painel escuro, slide escuro -> painel creme
                y0_, x0_, y1_, x1_ = int(rec[1]), int(rec[0]), int(rec[3]), int(rec[2])
                fundo = "escuro" if self.img[y0_:y1_:8, x0_:x1_:8].mean() > 140 else "claro"
            tl, pal = fundo_painel(fundo)
            tl.sombra(self.cx, self.cy, self.cx + self.cw, self.cy + self.ch, raio=16, desfoque=20, opac=0.42,
                      desloc=(0, 12))
            tl.ret(self.cx - 2, self.cy - 2, self.cx + self.cw + 2, self.cy + self.ch + 2, pal["linha"], raio=17)
            if nota:
                tam, ls = D.caber(nota, "bold", 32, area_w, 2, 26)
                tl.bloco(FAIXA + 40, self.cy + self.ch + 26, ls, "bold", tam, pal["fg"], alinhar="centro", largura=area_w)
            self.base = Planos.de_rgb(np.asarray(tl.final()))
            self.mY, self.mC = mascara_arredondada(self.cw, self.ch, 16)
            self.janela0 = rec
        self.passeio = []
        for p in self.d.get("passeio", []):
            self.passeio.append((float(p["t"]), caixa_no_aspecto(*[float(v) for v in p["caixa"]], self.aspecto, iw, ih)))
        self.passeio.sort()

    def janela(self, t):
        jan = list(self.janela0)
        for tp, cx in self.passeio:
            if t <= tp:
                break
            a = D.vaivem((t - tp) / 0.7)
            jan = [jan[i] + (cx[i] - jan[i]) * a for i in range(4)]
        return jan

    def _conteudo(self, jan):
        k = tuple(int(round(v)) for v in jan)
        p = self.cache.get(k)
        if p is None:
            x0, y0, x1, y1 = jan
            sx = (x1 - x0) / self.cw
            sy = (y1 - y0) / self.ch
            M = np.float32([[sx, 0, x0 + 0.5 * sx - 0.5], [0, sy, y0 + 0.5 * sy - 0.5]])
            interp = cv2.INTER_AREA if sx > 1.05 else cv2.INTER_CUBIC
            if abs(x0 - round(x0)) < 1e-3 and abs(y0 - round(y0)) < 1e-3 and sx > 1:
                crop = self.img[int(round(y0)):int(round(y1)), int(round(x0)):int(round(x1))]
                rgb = cv2.resize(crop, (self.cw, self.ch), interpolation=interp)
            else:
                rgb = cv2.warpAffine(self.img, M, (self.cw, self.ch), flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP,
                                     borderMode=cv2.BORDER_REPLICATE)
            p = Planos.de_rgb(rgb)
            if len(self.cache) > 64:
                self.cache.clear()
            self.cache[k] = p
        return p

    def painel(self, t, q, rosto):
        c = self._conteudo(self.janela(t))
        if self.cheia:
            P = c.copia()
            self.pip.colar(P, q, rosto, *self.pip_xy)
            return P
        P = self.base.copia()
        colar_com_mascara(P, c, self.cx, self.cy, self.mY, self.mC)
        return P

    def encerrar(self):
        self.cache = {}


class SlideCanto(Evento):
    camada = 2
    precisa_rosto = True

    def preparar(self):
        img = carregar_rgb(arquivo_slide(self.d, self.ctx))
        ih, iw = img.shape[:2]
        rec = [int(v) for v in (self.d.get("recorte") or [0, 0, iw, ih])]
        img = img[rec[1]:rec[3], rec[0]:rec[2]]
        asp = img.shape[1] / img.shape[0]
        w = float(self.d.get("largura", 360))
        # não cobrir o rosto
        cx, cy, fw, fh = self.ctx.rosto.em((self.ini + self.fim) / 2)
        dir_rosto = cx + fw * 0.62
        livre = W - 24 - dir_rosto - 16
        if livre < w:
            w = max(260.0, livre)
        w, h = par(w), par(w / asp)
        m = 22
        tl = D.Tela(w + 2 * m, h + 2 * m, None)
        tl.sombra(m, m, m + w, m + h, raio=14, desfoque=14, opac=0.5, desloc=(0, 8))
        tl.ret(m - 3, m - 3, m + w + 3, m + h + 3, D.CREME, raio=16)
        mini = Image.fromarray(cv2.resize(img, (w * 2, h * 2), interpolation=cv2.INTER_AREA))
        masc = Image.new("L", mini.size, 0)
        from PIL import ImageDraw
        ImageDraw.Draw(masc).rounded_rectangle((0, 0, mini.width, mini.height), radius=26, fill=255)
        mini.putalpha(masc)
        tl.img.alpha_composite(mini, (m * 2, m * 2))
        self.sp = Sprite(tl.final())
        self.m = m
        self.x = W - 24 - w - m
        self.y = 24 - m

    def aplicar(self, q, t):
        e = min(D.lim((t - self.ini) / 0.5), D.lim((self.fim - t) / 0.4))
        dx = (1 - D.sai(e)) * (self.sp.w + 40)
        self.sp.colar(q, self.x + dx, self.y)


class Esquema(EventoTela):
    def preparar(self):
        fundo = self.d.get("fundo", "escuro")
        self.esq = D.Esquema(self.d.get("modelo", "lista"), self.d.get("dados", {}), LARG_PAINEL - FAIXA, H, fundo)
        self.cache = {}

    def painel(self, t, q, rosto):
        k = self.esq.chave(t)
        P = self.cache.get(k)
        if P is None:
            img = np.asarray(self.esq.desenhar(t))
            faixa = np.zeros((H, FAIXA, 3), np.uint8)
            faixa[:] = D.LARANJA
            P = Planos.de_rgb(np.concatenate([faixa, img], 1))
            if len(self.cache) > 400:
                self.cache.clear()
            self.cache[k] = P
        return P

    def encerrar(self):
        self.cache = {}


class Imagem(EventoTela):
    def preparar(self):
        d = self.d
        img = carregar_rgb(self.ctx.caminho(d["arquivo"]))
        ih, iw = img.shape[:2]
        rec = [int(v) for v in (d.get("recorte") or [0, 0, iw, ih])]
        img = img[rec[1]:rec[3], rec[0]:rec[2]]
        texto = d.get("texto")
        fundo = d.get("fundo", "escuro")
        tl, pal = fundo_painel(fundo)
        area_w = LARG_PAINEL - FAIXA - 2 * 40
        area_h = H - 2 * 40 - (70 if texto else 0)
        com_seta = bool(d.get("destaque")) and d.get("seta", True)
        if com_seta:
            area_w -= 76  # sobra uma calha à direita pra seta, fora do print
        asp = img.shape[1] / img.shape[0]
        cw = area_w
        ch = cw / asp
        if ch > area_h:
            ch = area_h
            cw = ch * asp
        cw, ch = int(cw), int(ch)
        cx = FAIXA + (LARG_PAINEL - FAIXA - cw - (76 if com_seta else 0)) / 2
        cy = (H - (70 if texto else 0) - ch) / 2
        tl.sombra(cx, cy, cx + cw, cy + ch, raio=20, desfoque=18, opac=0.5, desloc=(0, 10))
        mini = Image.fromarray(cv2.resize(img, (cw * 2, ch * 2), interpolation=cv2.INTER_AREA))
        from PIL import ImageDraw
        masc = Image.new("L", mini.size, 0)
        ImageDraw.Draw(masc).rounded_rectangle((0, 0, mini.width, mini.height), radius=36, fill=255)
        mini.putalpha(masc)
        tl.img.alpha_composite(mini, (int(cx * 2), int(cy * 2)))
        self.y_texto = None
        if texto:
            tam, ls = D.caber(texto, "bold", 32, area_w, 2, 26)
            self.y_texto = cy + ch + 22
            tl.bloco(FAIXA + 40, cy + ch + 22, ls, "bold", tam, pal["fg"], alinhar="centro", largura=area_w)
        self.base_img = tl.final()
        self.base = Planos.de_rgb(np.asarray(self.base_img))
        self.esc = cw / img.shape[1]
        self.ox, self.oy = cx, cy
        self.cartao = (cx, cy, cx + cw, cy + ch)
        self.dest = None
        if d.get("destaque"):
            x0, y0, x1, y1 = [float(v) for v in d["destaque"]]
            self.dest = [cx + (x0 - rec[0]) * self.esc, cy + (y0 - rec[1]) * self.esc,
                         cx + (x1 - rec[0]) * self.esc, cy + (y1 - rec[1]) * self.esc]
        self.t_dest = float(d.get("t_destaque", self.ini + 0.6))
        self.cache = {}

    def _seta_geo(self):
        """De onde a seta vem (direita, baixo ou esquerda), sem sair do painel, sem cobrir a legenda nem o resto do
        print. Se não couber em lugar nenhum, fica só a moldura pulsando."""
        x0, y0, x1, y1 = self.dest
        cx0, cy0, cx1, cy1 = self.cartao
        baixo_lim = self.y_texto - 6 if self.y_texto else H - 12
        cyb = (y0 + y1) / 2
        xr = min(x1 - 50, x0 + (x1 - x0) * 0.75)
        L = min(96, LARG_PAINEL - 14 - x1 - 12)
        if L >= 50 and max(x1, cx1) + 10 < LARG_PAINEL - 14:  # da direita, de fora do print
            return (LARG_PAINEL - 14, cyb + L * 0.5), (x1 + 12, cyb)
        if y1 + 70 < baixo_lim and y1 + 60 > cy1:  # de baixo, se o destaque encosta no fim do print
            return (xr + 40, min(baixo_lim, y1 + 100)), (xr, y1 + 12)
        if x0 - 70 > FAIXA + 12:
            return (FAIXA + 14, cyb + 40), (x0 - 12, cyb)
        return None

    def painel(self, t, q, rosto):
        if not self.dest or t < self.t_dest:
            return self.base
        p = D.lim((t - self.t_dest) / 0.4)
        fase = int(((t - self.t_dest) % 1.2) / 1.2 * 16)
        k = (int(p * 10), fase)
        P = self.cache.get(k)
        if P is None:
            tl = D.Tela(LARG_PAINEL, H, (0, 0, 0))
            tl.img = self.base_img.convert("RGBA").resize((LARG_PAINEL * 2, H * 2), Image.BICUBIC)
            from PIL import ImageDraw
            tl.d = ImageDraw.Draw(tl.img)
            x0, y0, x1, y1 = self.dest
            ph = fase / 16.0
            g = 6 + 10 * ph
            cor_g = D.mix(D.CREME, D.LARANJA, 0.3)
            if p >= 1:
                tl.ret(x0 - g, y0 - g, x1 + g, y1 + g, None, raio=14 + g, borda=cor_g + (int(200 * (1 - ph)),), larg=3)
            pad = 6 + 4 * (1 - D.mola(p))
            tl.ret(x0 - pad, y0 - pad, x1 + pad, y1 + pad, None, raio=14, borda=D.LARANJA, larg=5)
            if self.d.get("seta", True) and p > 0.3:
                seta = self._seta_geo()
                if seta:
                    (sx, sy), (ex, ey) = seta
                    ux, uy = (ex - sx), (ey - sy)
                    nrm = math.hypot(ux, uy) or 1
                    bob = 9 * math.sin(ph * 2 * math.pi)
                    ox, oy = ux / nrm * bob, uy / nrm * bob
                    tl.seta(sx + ox, sy + oy, ex + ox, ey + oy, D.CREME, larg=13, ponta=30)
                    tl.seta(sx + ox, sy + oy, ex + ox, ey + oy, D.LARANJA, larg=7, ponta=22)
            P = Planos.de_rgb(np.asarray(tl.final()))
            self.cache[k] = P
        return P

    def encerrar(self):
        self.cache = {}


class FonteVideo:
    """Vídeo em pé tocando em loop, sem som, entregue quadro a quadro já no tamanho do ladrilho."""

    def __init__(self, arq, w, h, threads=1):
        self.arq, self.w, self.h = arq, w, h
        self.proc = None
        self.idx = -10
        self.tam = w * h * 3 // 2
        self.threads = threads
        try:
            self.dur = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                                      "-of", "csv=p=0", arq]).decode().strip())
        except Exception:
            self.dur = 10.0
        self.ultimo = None

    def _abrir(self, k):
        self.fechar()
        ss = (k / FPS) % max(self.dur - 0.05, 0.1)
        vf = ("scale=%d:%d:force_original_aspect_ratio=increase,crop=%d:%d,fps=%d,format=yuv420p"
              % (self.w, self.h, self.w, self.h, FPS))
        cmd = ["ffmpeg", "-v", "error", "-threads", str(self.threads), "-stream_loop", "-1", "-ss", "%.3f" % ss,
               "-i", self.arq, "-an", "-vf", vf, "-f", "rawvideo", "-"]
        self.proc = pipe_grande(subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=self.tam * 4))
        self.idx = k - 1

    def quadro(self, t_local):
        k = int(round(t_local * FPS))
        if k == self.idx and self.ultimo is not None:
            return self.ultimo
        if self.proc is None or k != self.idx + 1:
            self._abrir(k)
        b = self.proc.stdout.read(self.tam)
        if len(b) < self.tam:
            if self.ultimo is not None:
                return self.ultimo
            b = bytes(self.tam)
        a = np.frombuffer(b, np.uint8)
        n = self.w * self.h
        self.ultimo = Planos(a[:n].reshape(self.h, self.w), a[n:n + n // 4].reshape(self.h // 2, self.w // 2),
                             a[n + n // 4:].reshape(self.h // 2, self.w // 2))
        self.idx = k
        return self.ultimo

    def fechar(self):
        if self.proc:
            try:
                self.proc.kill()
                self.proc.wait(timeout=2)
            except Exception:
                pass
        self.proc = None


class Videos(EventoTela):
    def __init__(self, d, ctx):
        super().__init__(d, ctx)
        self.cheia = d.get("modo", "cheia") != "dividida"

    def preparar(self):
        d = self.d
        arqs = [self.ctx.caminho(a) for a in d.get("arquivos", [])]
        n = max(1, len(arqs))
        rot = d.get("rotulos", [])
        titulo = d.get("titulo")
        L = self.largura
        pal = D.paleta(d.get("fundo", "escuro"))
        tl = D.Tela(L, H, pal["bg"])
        if not self.cheia:
            tl.ret(0, 0, FAIXA, H, D.LARANJA)
        x_area0 = (FAIXA + 26) if not self.cheia else 48
        x_area1 = L - (26 if not self.cheia else 48)
        top = 40
        if titulo:
            tl.ret(x_area0, 34, x_area0 + 56, 39, D.LARANJA, raio=2)
            tam, ls = D.caber(titulo, "bold", 36, (x_area1 - x_area0) - (230 if self.cheia else 0), 1, 28)
            tl.texto(x_area0, 72, ls[0], "bold", tam, pal["fg"], anchor="lm")
            top = 104
        if self.cheia:
            self.pip = Pip(168)
            self.pip_xy = (W - 24 - self.pip.lado, 20)
            self.pip.sombra_em(tl, *self.pip_xy)
            top = max(top, 20 + self.pip.lado + 10)
        rot_h = 40 if self.cheia else 34
        base_reserva = 92 if self.cheia else 80
        gap = 20 if self.cheia else 30
        area_w = x_area1 - x_area0
        area_h = H - top - base_reserva
        melhor = None
        for linhas in range(1, n + 1):
            cols = math.ceil(n / linhas)
            tw = (area_w - (cols - 1) * gap) / cols
            th = tw * 16 / 9
            hmax = (area_h - (linhas - 1) * 14) / linhas - rot_h
            if th > hmax:
                th = hmax
                tw = th * 9 / 16
            if melhor is None or tw > melhor[2]:
                melhor = (linhas, cols, tw, th)
        linhas, cols, tw, th = melhor
        tw, th = par(tw - 1), par(th - 1)
        self.tw, self.th = tw, th
        bloco_h = linhas * (th + rot_h) + (linhas - 1) * 14
        y0 = top + max(0, (area_h - bloco_h) / 2)
        self.pos = []
        for i in range(n):
            li, ci = divmod(i, cols)
            na = min(cols, n - li * cols)
            x0 = x_area0 + (area_w - (na * tw + (na - 1) * gap)) / 2
            x = par(x0 + ci * (tw + gap))
            y = par(y0 + li * (th + rot_h + 14) + rot_h)
            self.pos.append((x, y))
            tl.sombra(x, y, x + tw, y + th, raio=16, desfoque=12, opac=0.5, desloc=(0, 8))
            if i < len(rot) and rot[i]:
                tam, ls = D.caber(rot[i], "semi", 26, tw + gap - 12, 1, 18)
                tl.texto(x + tw / 2, y - rot_h / 2 - 2, ls[0], "semi", tam, pal["fg"], anchor="mm")
        self.y_leg = (y0 + bloco_h + H) / 2
        self.base = Planos.de_rgb(np.asarray(tl.final()))
        self.mY, self.mC = mascara_arredondada(tw, th, 16)
        thr = 1
        self.fontes = [FonteVideo(a, tw, th, thr) for a in arqs]
        # destaques
        des = sorted(d.get("destaques", []), key=lambda x: float(x["t"]))
        self.dest = []
        for j, x in enumerate(des):
            t0 = float(x["t"])
            t1 = float(x.get("ate", des[j + 1]["t"] if j + 1 < len(des) else self.fim))
            self.dest.append((t0, t1, x))
        self.sp_leg = {}
        self.sp_moldura = None
        self.pal = pal

    def _legenda(self, j, x):
        sp = self.sp_leg.get(j)
        if sp is None:
            txt = x.get("texto", "")
            if not txt:
                sp = None
            else:
                img, m = cartao_texto(txt, "bold", 32, D.CREME, D.LARANJA, 1.0, pad=(30, 14),
                                      larg_max=self.largura - 80, raio=28, alinhar="centro")
                sp = (Sprite(img), m)
            self.sp_leg[j] = sp
        return sp

    def _moldura(self):
        if self.sp_moldura is None:
            m = 16
            tl = D.Tela(self.tw + 2 * m, self.th + 2 * m, None)
            tl.ret(m - 5, m - 5, m + self.tw + 5, m + self.th + 5, None, raio=20, borda=D.LARANJA, larg=6)
            bx, by = m + self.tw - 24, m + self.th - 24
            tl.circ(bx, by, 17, D.LARANJA, borda=D.CREME, larg=3)
            tl.check(bx, by + 1, 20, D.CREME, 3.6)
            self.sp_moldura = (Sprite(tl.final()), m)
        return self.sp_moldura

    def painel(self, t, q, rosto):
        P = self.base.copia()
        ativo = None
        for j, (t0, t1, x) in enumerate(self.dest):
            if t0 <= t < t1:
                ativo = (j, t0, t1, x)
        alvo = set(ativo[3].get("alvo", [])) if ativo else set()
        p = D.lim((t - ativo[1]) / 0.35) if ativo else 0
        po = D.lim((ativo[2] - t) / 0.3) if ativo else 0
        for i, fv in enumerate(self.fontes):
            fr = fv.quadro(t - self.ini)
            if alvo and (i + 1) not in alvo:
                k = 1 - 0.55 * D.suave(p) * D.suave(po)
                fr = Planos(((fr.Y.astype(np.float32) - 16) * k + 16).astype(np.uint8),
                            ((fr.U.astype(np.float32) - 128) * k + 128).astype(np.uint8),
                            ((fr.V.astype(np.float32) - 128) * k + 128).astype(np.uint8))
            x, y = self.pos[i]
            colar_com_mascara(P, fr, x, y, self.mY, self.mC)
            if alvo and (i + 1) in alvo:
                sp, m = self._moldura()
                sp.colar(P, x - m, y - m, opac=D.suave(p) * D.suave(po))
        if ativo:
            leg = self._legenda(ativo[0], ativo[3])
            if leg:
                sp, m = leg
                dy = 14 * (1 - D.sai(p))
                sp.colar(P, (self.largura - sp.w) / 2 + (FAIXA / 2 if not self.cheia else 0),
                         self.y_leg - sp.h / 2 + dy, opac=D.suave(p) * D.suave(po))
        if self.cheia:
            self.pip.colar(P, q, rosto, *self.pip_xy)
        return P

    def encerrar(self):
        for f in getattr(self, "fontes", []):
            f.fechar()


TIPOS = {"zoom": Zoom, "texto": Texto, "abertura": Abertura, "esquema": Esquema, "imagem": Imagem, "videos": Videos}


def criar_evento(d, ctx):
    tipo = d.get("tipo")
    if tipo == "slide":
        return SlideCanto(d, ctx) if d.get("modo", "dividida") == "canto" else Slide(d, ctx)
    if tipo not in TIPOS:
        raise ValueError("tipo de evento desconhecido: %r" % tipo)
    return TIPOS[tipo](d, ctx)


def carregar_eventos(caminho, ctx):
    with open(caminho) as f:
        lista = json.load(f)
    evs = [criar_evento(d, ctx) for d in lista if not d.get("desligado")]
    evs = [e for e in evs if e.fim > e.ini]
    evs.sort(key=lambda e: (e.ini, e.camada))
    # painéis colados: sem voltar pra tela cheia no meio
    telas = [e for e in evs if isinstance(e, EventoTela)]
    for a, b in zip(telas, telas[1:]):
        if b.ini < a.fim - 0.01:
            log("AVISO: painéis sobrepostos em %.2f s (%s / %s): o primeiro termina antes" % (b.ini, a.d["tipo"], b.d["tipo"]))
            a.fim = b.ini
        if b.ini - a.fim < 0.5 and a.largura == b.largura:
            a.fim = b.ini
            a.manter_dir = True
            b.manter_esq = True
            b.anterior = a
    return evs


class Agenda:
    def __init__(self, eventos):
        self.ev = eventos
        self.fi = [(int(round(e.ini * FPS)), int(round(e.fim * FPS)), e) for e in eventos]

    def ativos(self, i):
        return sorted([e for a, b, e in self.fi if a <= i < b], key=lambda e: e.camada)


# ============================================================== áudio
def ler_wav_trechos(caminho, intervalos):
    w = wave.open(caminho, "rb")
    nch, sw, sr, nfr = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
    if sr != SR or sw != 2:
        raise RuntimeError("áudio precisa ser PCM 16 bits 48 kHz (veio %d Hz, %d bytes)" % (sr, sw))
    partes = []
    fade = int(0.008 * SR)
    rampa = (0.5 - 0.5 * np.cos(np.linspace(0, np.pi, fade))).astype(np.float32)
    for k, (a, b) in enumerate(intervalos):
        s0, s1 = a * AMOSTRAS_POR_QUADRO, b * AMOSTRAS_POR_QUADRO
        n = s1 - s0
        seg = np.zeros((n, nch), np.float32)
        if s0 < nfr:
            w.setpos(s0)
            raw = w.readframes(min(n, nfr - s0))
            x = np.frombuffer(raw, np.int16).reshape(-1, nch).astype(np.float32)
            seg[:len(x)] = x
        colado_antes = k > 0 and intervalos[k - 1][1] == a
        colado_depois = k + 1 < len(intervalos) and intervalos[k + 1][0] == b
        if not colado_antes and n > 2 * fade:
            seg[:fade] *= rampa[:, None]
        if not colado_depois and n > 2 * fade:
            seg[-fade:] *= rampa[::-1, None]
        partes.append(seg)
    w.close()
    return np.concatenate(partes) if partes else np.zeros((0, 1), np.float32), nch


def preparar_audio(caminho, intervalos, pasta, n_quadros):
    t0 = time.time()
    x, nch = ler_wav_trechos(caminho, intervalos)
    bruto = os.path.join(pasta, "audio_cortado.wav")
    with wave.open(bruto, "wb") as w:
        w.setnchannels(nch)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(np.clip(x, -32768, 32767).astype(np.int16).tobytes())
    alvo = "I=-16:TP=-1.5:LRA=11"
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", bruto, "-af", "loudnorm=%s:print_format=json" % alvo,
                        "-f", "null", "-"], capture_output=True, text=True)
    txt = r.stderr
    j = json.loads(txt[txt.rindex("{"):txt.rindex("}") + 1])
    filtro = ("loudnorm=%s:measured_I=%s:measured_TP=%s:measured_LRA=%s:measured_thresh=%s:offset=%s:linear=true"
              % (alvo, j["input_i"], j["input_tp"], j["input_lra"], j["input_thresh"], j["target_offset"]))
    norm = os.path.join(pasta, "audio_norm.wav")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", bruto, "-af", filtro, "-ar", str(SR), "-c:a", "pcm_s16le", norm],
                   check=True)
    # garante duração exata = n_quadros / 30
    alvo_n = n_quadros * AMOSTRAS_POR_QUADRO
    with wave.open(norm, "rb") as w:
        nn = w.getnframes()
        if nn != alvo_n:
            dados = np.frombuffer(w.readframes(nn), np.int16).reshape(-1, w.getnchannels())
            ch = w.getnchannels()
        else:
            dados = None
    if dados is not None:
        fix = np.zeros((alvo_n, ch), np.int16)
        fix[:min(alvo_n, len(dados))] = dados[:alvo_n]
        with wave.open(norm, "wb") as w:
            w.setnchannels(ch)
            w.setsampwidth(2)
            w.setframerate(SR)
            w.writeframes(fix.tobytes())
    log("áudio: %.1f s cortado e normalizado (entrada %s LUFS) em %.1f s" % (alvo_n / SR, j["input_i"], time.time() - t0))
    return norm


# ============================================================== vídeo
def duracao_quadros(base):
    out = subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                   "stream=nb_frames:format=duration", "-of", "json", base]).decode()
    j = json.loads(out)
    try:
        n = int(j["streams"][0]["nb_frames"])
        if n > 0:
            return n
    except Exception:
        pass
    return int(float(j["format"]["duration"]) * FPS)


_TAM_BASE = {}


def filtro_escala(base):
    """'' se a base já é 1280x720; senão um scale (permite testar com original.mp4)."""
    if base not in _TAM_BASE:
        try:
            out = subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                           "stream=width,height:stream_side_data=rotation", "-of", "json", base]).decode()
            st = json.loads(out)["streams"][0]
            w, h = st["width"], st["height"]
            rot = 0
            for sd in st.get("side_data_list", []):
                rot = int(sd.get("rotation", 0))
            if abs(rot) == 90:
                w, h = h, w
            _TAM_BASE[base] = (w, h)
        except Exception:
            _TAM_BASE[base] = (W, H)
    return "" if _TAM_BASE[base] == (W, H) else "scale=%d:%d," % (W, H)


def abrir_decodificador(base, intervalos, pasta, threads):
    f0 = intervalos[0][0]
    f_fim = intervalos[-1][1]
    cmd = ["ffmpeg", "-v", "error", "-threads", str(threads)]
    if f0 > 0:
        cmd += ["-ss", "%.6f" % ((f0 - 0.5) / FPS)]
    cmd += ["-t", "%.3f" % ((f_fim - f0) / FPS + 1.0), "-i", base]
    esc = filtro_escala(base)
    contiguo = len(intervalos) == 1
    if not contiguo:
        expr = "+".join("between(n,%d,%d)" % (a - f0, b - f0 - 1) for a, b in intervalos)
        script = os.path.join(pasta, "selecao.txt")
        with open(script, "w") as f:
            f.write("select='%s',%ssetpts=N/(%d*TB)" % (expr, esc, FPS))
        cmd += ["-filter_script:v", script]
    elif esc:
        cmd += ["-vf", esc.rstrip(",")]
    n = sum(b - a for a, b in intervalos)
    cmd += ["-frames:v", str(n), "-fps_mode", "passthrough", "-an", "-pix_fmt", "yuv420p", "-f", "rawvideo", "-"]
    return pipe_grande(subprocess.Popen(cmd, stdout=subprocess.PIPE, bufsize=TAM_QUADRO * 2))


def ler_exato(f, buf):
    mv = memoryview(buf)
    lido = 0
    while lido < len(buf):
        k = f.readinto(mv[lido:])
        if not k:
            break
        lido += k
    return lido


def faixas_rosto(eventos, t0, t1):
    out = []
    for e in eventos:
        if e.precisa_rosto and e.fim > t0 and e.ini < t1:
            out.append((max(e.ini, t0), min(e.fim, t1)))
    return out


def renderizar(a):
    base = a.base
    n_src = duracao_quadros(base)
    linha = Linha.carregar(a.cortes, n_src)
    i0 = int(round((a.de or 0) * FPS))
    i1 = linha.n if a.ate is None else min(linha.n, int(round(a.ate * FPS)))
    if i1 <= i0:
        raise SystemExit("intervalo vazio")
    N = i1 - i0
    rosto = Rosto(base, linha, a.cache, a.threads)
    ctx = Ctx(a.raiz, rosto)
    evs = carregar_eventos(a.eventos, ctx)
    rosto.preparar(faixas_rosto(evs, i0 / FPS, i1 / FPS))
    agenda = Agenda(evs)
    pasta = tempfile.mkdtemp(prefix="render_", dir=os.path.dirname(os.path.abspath(a.saida)))
    try:
        intervalos = linha.intervalos(i0, i1)
        audio = preparar_audio(a.audio, intervalos, pasta, N)
        dec = abrir_decodificador(base, intervalos, pasta, a.threads)
        enc_cmd = ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "yuv420p", "-s", "%dx%d" % (W, H),
                   "-r", str(FPS), "-i", "-", "-i", audio, "-map", "0:v", "-map", "1:a",
                   "-c:v", "libx264", "-preset", a.preset, "-b:v", a.bitrate, "-maxrate", "2600k", "-bufsize", "5200k",
                   "-pix_fmt", "yuv420p", "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
                   "-color_range", "tv", "-threads", str(a.threads),
                   "-c:a", "aac", "-b:a", "128k", "-ar", str(SR), "-movflags", "+faststart", "-shortest", a.saida]
        enc = subprocess.Popen(enc_cmd, stdin=subprocess.PIPE, bufsize=TAM_QUADRO * 2)
        buf = bytearray(TAM_QUADRO)
        ativos_ant = set()
        t_ini = time.time()
        n_over = 0
        t_over = 0.0
        ultimo_log = t_ini
        for k in range(N):
            got = ler_exato(dec.stdout, buf)
            if got < TAM_QUADRO:
                log("AVISO: decodificador acabou no quadro %d de %d (repetindo o último)" % (k, N))
            i = i0 + k
            ativos = agenda.ativos(i)
            s = set(ativos)
            for e in ativos_ant - s:
                e.encerrar()
            ativos_ant = s
            if ativos:
                tq = time.time()
                q = Quadro(buf)
                t = i / FPS
                for e in ativos:
                    e.garantir()
                    e.aplicar(q, t)
                n_over += 1
                t_over += time.time() - tq
            enc.stdin.write(buf)
            if time.time() - ultimo_log > 20:
                ultimo_log = time.time()
                el = ultimo_log - t_ini
                log("%d/%d quadros (%.0f%%), %.1f q/s, faltam ~%.0f min" % (k + 1, N, 100 * (k + 1) / N, (k + 1) / el,
                                                                           (N - k - 1) / ((k + 1) / el) / 60))
        for e in ativos_ant:
            e.encerrar()
        enc.stdin.close()
        enc.wait()
        dec.stdout.close()
        dec.wait()
        el = time.time() - t_ini
        log("pronto: %s — %d quadros (%.1f s) em %.1f s = %.1f q/s; %d quadros com desenho (%.1f ms/quadro de Python)"
            % (a.saida, N, N / FPS, el, N / el, n_over, 1000 * t_over / max(1, n_over)))
        if enc.returncode:
            raise SystemExit("codificador falhou")
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


# ============================================================== folha de quadros
def quadro_unico(base, f_src, threads):
    cmd = ["ffmpeg", "-v", "error", "-threads", str(threads)]
    if f_src > 0:
        cmd += ["-ss", "%.6f" % ((f_src - 0.5) / FPS)]
    cmd += ["-i", base, "-frames:v", "1"]
    if filtro_escala(base):
        cmd += ["-vf", filtro_escala(base).rstrip(",")]
    cmd += ["-pix_fmt", "yuv420p", "-f", "rawvideo", "-"]
    b = subprocess.run(cmd, capture_output=True).stdout
    buf = bytearray(TAM_QUADRO)
    buf[:len(b[:TAM_QUADRO])] = b[:TAM_QUADRO]
    return buf


def folha(a):
    base = a.base
    n_src = duracao_quadros(base)
    linha = Linha.carregar(a.cortes, n_src)
    rosto = Rosto(base, linha, a.cache, a.threads)
    ctx = Ctx(a.raiz, rosto)
    evs = carregar_eventos(a.eventos, ctx)
    ts = [float(x) for x in a.tempos]
    faixas = []
    for t in ts:
        faixas += faixas_rosto(evs, t - 3, t + 3)
    rosto.preparar(faixas)
    agenda = Agenda(evs)
    imgs = []
    if a.soltos:
        os.makedirs(a.soltos, exist_ok=True)
    for t in ts:
        i = int(round(t * FPS))
        buf = quadro_unico(base, linha.src(min(i, linha.n - 1)), a.threads)
        q = Quadro(buf)
        for e in agenda.ativos(i):
            e.garantir()
            e.aplicar(q, t)
        rgb = q.rgb()
        im = Image.fromarray(rgb)
        if a.soltos:
            im.save(os.path.join(a.soltos, "q_%07.2f.jpg" % t), quality=92)
        imgs.append((t, im))
    for e in evs:
        e.encerrar()
    cols = 2 if len(imgs) <= 4 else 3
    tw = 640 if cols == 2 else 560
    th = tw * H // W
    lab = 30
    rows = math.ceil(len(imgs) / cols)
    sheet = Image.new("RGB", (cols * tw + (cols + 1) * 8, rows * (th + lab) + (rows + 1) * 8), (30, 30, 36))
    from PIL import ImageDraw
    dr = ImageDraw.Draw(sheet)
    for k, (t, im) in enumerate(imgs):
        r, c = divmod(k, cols)
        x = 8 + c * (tw + 8)
        y = 8 + r * (th + lab + 8)
        dr.text((x + 4, y + 4), "%d:%04.1f (%.2f s)" % (t // 60, t % 60, t), font=D.fonte("semi", 20), fill=(240, 240, 240))
        sheet.paste(im.resize((tw, th), Image.LANCZOS), (x, y + lab))
    sheet.save(a.quadros, quality=90)
    log("folha salva: %s (%d quadros)" % (a.quadros, len(imgs)))


# ============================================================== CLI
def main():
    ap = argparse.ArgumentParser(description="Render visual da aula (módulo 2)")
    ap.add_argument("--eventos", required=True)
    ap.add_argument("--saida")
    ap.add_argument("--de", type=float)
    ap.add_argument("--ate", type=float)
    ap.add_argument("--quadros", help="folha.jpg; os tempos (s de saída) vêm depois")
    ap.add_argument("tempos", nargs="*")
    ap.add_argument("--soltos", help="pasta pra salvar cada quadro da folha em tamanho cheio")
    ap.add_argument("--raiz", default=AULA)
    ap.add_argument("--base")
    ap.add_argument("--audio")
    ap.add_argument("--cortes")
    ap.add_argument("--cache")
    ap.add_argument("--threads", type=int, default=0)
    ap.add_argument("--preset", default="veryfast")
    ap.add_argument("--bitrate", default="1800k")
    a = ap.parse_args()
    a.base = a.base or os.path.join(a.raiz, "base720.mp4")
    a.audio = a.audio or os.path.join(a.raiz, "audio48k.wav")
    a.cortes = a.cortes or os.path.join(a.raiz, "cortes.json")
    destino = a.quadros or a.saida
    if not destino:
        ap.error("informe --saida ou --quadros")
    a.cache = a.cache or os.path.join(os.path.dirname(os.path.abspath(destino)), "rosto_cache.json")
    if a.quadros:
        if not a.tempos:
            ap.error("--quadros precisa de tempos")
        folha(a)
    else:
        renderizar(a)


if __name__ == "__main__":
    main()
