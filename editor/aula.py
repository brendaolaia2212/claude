"""Aula em 16:9 pro YouTube, desenhada quadro a quadro sobre o corte.mp4 (1920x1080).

- legenda embaixo, a palavra falada em laranja;
- capítulo: abertura animada de cada parte da aula e uma etiqueta fixa no canto;
- termo: o comando na tela quando ela fala dele (/orbit + o que significa);
- slide: a página do material ao lado dela quando ela explica algo que está no slide;
- camera: o efeito aplicado no próprio vídeo dela (dolly in, órbita, pan, tilt,
  câmera lenta, golden hour, cinematic...) com um desenho que mostra o movimento.

Decisões em edicao.json → "aula" (tempos no corte):
  "decks": {"ocultos": "/caminho/arquivo.pdf"},
  "eventos": [
    {"tipo": "capitulo", "inicio": 10, "fim": 300, "numero": "01", "titulo": "Movimento de câmera"},
    {"tipo": "termo", "inicio": 31, "fim": 36, "termo": "/orbit", "texto": "a câmera circula o assunto"},
    {"tipo": "camera", "efeito": "orbit", "inicio": 31.5, "fim": 35},
    {"tipo": "slide", "deck": "ocultos", "pagina": 10, "inicio": 50, "fim": 62}
  ],
  "legenda_oculta": [[a, b]]

Tudo roda em pedaços paralelos (cada um decodifica, desenha e codifica a sua parte);
o som é a voz do corte + efeitos sonoros, com volume final em -14 LUFS.
"""
import bisect
import json
import math
import re
import subprocess
from concurrent.futures import ProcessPoolExecutor
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from .base import FPS, ffmpeg, fonte, ler_edicao, ler_json, mmss, pasta, rodar, sondar

L, A = 1920, 1080
AZUL = (13, 43, 62)
AZUL_PROF = (7, 30, 43)
AZUL_MEDIO = (18, 69, 89)
LARANJA = (255, 106, 0)
DOURADO = (255, 178, 0)
BRANCO = (255, 255, 255)

EFEITOS = ["dollyin", "dollyout", "orbit", "tracking", "follow", "pan", "tilt", "craneup",
           "handheld", "static", "pov", "macro", "closeup", "mediumshot", "wideshot",
           "shallowdepth", "deepfocus", "rackfocus", "slowmotion", "speedramp", "hyperlapse",
           "softlight", "goldenhour", "cinematic", "naturaldaylight", "motionblur", "glitch",
           "vhs", "particulas", "glow", "reveal", "loop", "9:16", "16:9"]


# ---------------------------------------------------------------- utilidades

def _clamp(p):
    return 0.0 if p < 0 else 1.0 if p > 1 else p


def suave(p):
    p = _clamp(p)
    return p * p * (3 - 2 * p)


def ease_io(p):
    p = _clamp(p)
    return 4 * p ** 3 if p < 0.5 else 1 - (-2 * p + 2) ** 3 / 2


def ease_out(p):
    p = _clamp(p)
    return 1 - (1 - p) ** 3


def presenca(t, ini, fim, entra=0.35, sai=0.25):
    """0..1: entrada, parado, saída."""
    if t < ini or t >= fim:
        return 0.0
    return min(ease_out((t - ini) / entra) if entra else 1.0, _clamp((fim - t) / sai) if sai else 1.0)


def rgba(img):
    return np.asarray(img.convert("RGBA"))


def colar(frame, img, x, y, alfa=1.0):
    """Cola img (RGBA numpy) em frame (RGB numpy) na posição x, y."""
    if alfa <= 0.003:
        return
    H, W = frame.shape[:2]
    h, w = img.shape[:2]
    x, y = int(round(x)), int(round(y))
    x0, y0, x1, y1 = max(0, x), max(0, y), min(W, x + w), min(H, y + h)
    if x1 <= x0 or y1 <= y0:
        return
    sub = img[y0 - y:y1 - y, x0 - x:x1 - x]
    a = sub[..., 3:4].astype(np.float32) * (alfa / 255.0)
    reg = frame[y0:y1, x0:x1].astype(np.float32)
    frame[y0:y1, x0:x1] = (reg + (sub[..., :3].astype(np.float32) - reg) * a).astype(np.uint8)


def sombra(img, raio=16, deslocar=(0, 8), alfa=120):
    """Sombra suave atrás de um RGBA (PIL)."""
    m = raio * 2
    base = Image.new("RGBA", (img.width + 2 * m, img.height + 2 * m), (0, 0, 0, 0))
    a = img.getchannel("A").point(lambda v: v * alfa // 255)
    s = Image.new("RGBA", img.size, (0, 0, 0, 255))
    s.putalpha(a)
    base.alpha_composite(s, (m + deslocar[0], m + deslocar[1]))
    base = base.filter(ImageFilter.GaussianBlur(raio))
    base.alpha_composite(img, (m, m))
    return base, m


def _quebrar(texto, f, larg):
    linhas, atual = [], ""
    for p in texto.split():
        t = (atual + " " + p).strip()
        if f.getlength(t) <= larg or not atual:
            atual = t
        else:
            linhas.append(atual)
            atual = p
    if atual:
        linhas.append(atual)
    return linhas


# ---------------------------------------------------------------- legenda

def linhas_legenda(palavras, max_chars=46, max_pal=9):
    linhas, atual = [], []
    for w in palavras:
        if atual:
            gap = w["s"] - atual[-1]["e"]
            chars = sum(len(x["w"]) + 1 for x in atual) + len(w["w"])
            if gap > 0.7 or chars > max_chars or len(atual) >= max_pal:
                linhas.append(atual)
                atual = []
        atual.append(w)
        if re.search(r"[.?!…]$", w["w"]) and len(atual) >= 3:
            linhas.append(atual)
            atual = []
    if atual:
        linhas.append(atual)
    out = []
    for k, ln in enumerate(linhas):
        ini = ln[0]["s"] - 0.04
        fim = ln[-1]["e"] + 0.35
        if k + 1 < len(linhas):
            fim = min(fim, linhas[k + 1][0]["s"] - 0.04)
        out.append({"ini": ini, "fim": max(fim, ln[-1]["e"]), "palavras": ln})
    return out


def _limpar(w, ultima):
    t = w.strip()
    if ultima:
        t = re.sub(r"[.,;:]+$", "", t)
    return t


class Legenda:
    def __init__(self, palavras, ocultas=()):
        self.linhas = linhas_legenda([w for w in palavras if w["w"].strip()])
        self.inis = [l["ini"] for l in self.linhas]
        self.ocultas = ocultas
        self.f = fonte("manrope", 44, 700)
        self.cache = {}

    def _imagem(self, li, ativa):
        chave = (li, ativa)
        if chave in self.cache:
            return self.cache[chave]
        ws = self.linhas[li]["palavras"]
        txts = [_limpar(w["w"], i == len(ws) - 1) for i, w in enumerate(ws)]
        esp = self.f.getlength(" ")
        larg = sum(self.f.getlength(t) for t in txts) + esp * (len(txts) - 1)
        asc, desc = self.f.getmetrics()
        W, H = int(larg + 56), int(asc + desc + 26)
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle([0, 0, W - 1, H - 1], 18, fill=AZUL + (205,))
        x = 28
        for i, t in enumerate(txts):
            cor = LARANJA if i == ativa else BRANCO
            d.text((x, 12), t, font=self.f, fill=cor + (255,))
            x += self.f.getlength(t) + esp
        arr = rgba(img)
        if len(self.cache) > 400:
            self.cache.clear()
        self.cache[chave] = arr
        return arr

    def desenhar(self, frame, t, y_base=A - 54):
        for a, b in self.ocultas:
            if a <= t < b:
                return
        i = bisect.bisect_right(self.inis, t) - 1
        if i < 0:
            return
        ln = self.linhas[i]
        if t >= ln["fim"]:
            return
        ativa = -1
        for k, w in enumerate(ln["palavras"]):
            if w["s"] - 0.02 <= t:
                ativa = k
        if ativa >= 0 and t > ln["palavras"][ativa]["e"] + 0.15 and ativa == len(ln["palavras"]) - 1:
            ativa = -1
        img = self._imagem(i, ativa)
        colar(frame, img, (L - img.shape[1]) / 2, y_base - img.shape[0])


# ---------------------------------------------------------------- elementos fixos

@lru_cache(maxsize=64)
def img_termo(termo, texto):
    ft, fx = fonte("archivo", 70, 900), fonte("manrope", 34, 600)
    linhas = _quebrar(texto, fx, 470) if texto else []
    W = int(max([ft.getlength(termo)] + [fx.getlength(l) for l in linhas]) + 84)
    H = 46 + 80 + (len(linhas) * 44 + 10 if linhas else 0) + 26
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, W - 1, H - 1], 28, fill=AZUL + (236,))
    d.rounded_rectangle([0, 0, 12, H - 1], 6, fill=LARANJA + (255,))
    d.text((44, 30), termo, font=ft, fill=LARANJA + (255,))
    y = 30 + 92
    for l in linhas:
        d.text((44, y), l, font=fx, fill=BRANCO + (255,))
        y += 44
    s, m = sombra(img, 18, (0, 10), 110)
    return rgba(s), m


@lru_cache(maxsize=32)
def img_etiqueta(numero, titulo):
    fn, ft = fonte("archivo", 28, 900), fonte("manrope", 26, 800)
    tt = titulo.upper()
    W = int(fn.getlength(numero) + ft.getlength(tt) + 26 + 60)
    img = Image.new("RGBA", (W, 54), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, W - 1, 53], 27, fill=AZUL + (215,))
    d.text((28, 11), numero, font=fn, fill=LARANJA + (255,))
    d.text((28 + fn.getlength(numero) + 18, 13), tt, font=ft, fill=BRANCO + (255,))
    return rgba(img)


@lru_cache(maxsize=32)
def img_abertura(numero, titulo, sub):
    fn, ft, fs = fonte("archivo", 150, 900), fonte("archivo", 78, 800), fonte("manrope", 34, 600)
    linhas = _quebrar(titulo.upper(), ft, 820)
    subl = _quebrar(sub, fs, 780) if sub else []
    W = 900
    H = 170 + len(linhas) * 88 + 30 + len(subl) * 44 + 20
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.text((0, 0), numero, font=fn, fill=LARANJA + (255,))
    y = 175
    for l in linhas:
        d.text((0, y), l, font=ft, fill=BRANCO + (255,))
        y += 88
    d.rounded_rectangle([0, y + 8, 140, y + 16], 4, fill=LARANJA + (255,))
    y += 36
    for l in subl:
        d.text((0, y), l, font=fs, fill=(225, 232, 238, 255))
        y += 44
    return rgba(img)


@lru_cache(maxsize=1)
def degrade_esquerda():
    x = np.linspace(1, 0, 1100, dtype=np.float32) ** 1.4
    a = (x * 225).astype(np.uint8)
    img = np.zeros((A, 1100, 4), np.uint8)
    img[..., 0], img[..., 1], img[..., 2] = AZUL_PROF
    img[..., 3] = a[None, :]
    return img


# ---------------------------------------------------------------- desenhos dos movimentos

def _camera(d, x, y, ang, cor=LARANJA, esc=1.0, alfa=255):
    """Câmera vista de cima: corpo + lente apontando pra ang (graus)."""
    r = math.radians(ang)
    c, s = math.cos(r), math.sin(r)

    def pt(px, py):
        return (x + (px * c - py * s) * esc, y + (px * s + py * c) * esc)
    corpo = [pt(-18, -13), pt(10, -13), pt(10, 13), pt(-18, 13)]
    lente = [pt(10, -7), pt(26, -14), pt(26, 14), pt(10, 7)]
    d.polygon(corpo, fill=cor + (alfa,))
    d.polygon(lente, fill=cor + (alfa,))


def _pessoa(d, x, y, esc=1.0, cor=BRANCO, alfa=255):
    d.ellipse([x - 13 * esc, y - 40 * esc, x + 13 * esc, y - 14 * esc], fill=cor + (alfa,))
    d.rounded_rectangle([x - 22 * esc, y - 10 * esc, x + 22 * esc, y + 40 * esc], int(12 * esc),
                        fill=cor + (alfa,))


def _seta(d, a, b, cor=DOURADO, larg=5, alfa=255):
    d.line([a, b], fill=cor + (alfa,), width=larg)
    ang = math.atan2(b[1] - a[1], b[0] - a[0])
    p1 = (b[0] - 16 * math.cos(ang - 0.45), b[1] - 16 * math.sin(ang - 0.45))
    p2 = (b[0] - 16 * math.cos(ang + 0.45), b[1] - 16 * math.sin(ang + 0.45))
    d.polygon([b, p1, p2], fill=cor + (alfa,))


ROTULOS = {
    "dollyin": "DOLLY IN", "dollyout": "DOLLY OUT", "orbit": "ORBIT", "tracking": "TRACKING",
    "follow": "FOLLOW", "pan": "PAN", "tilt": "TILT", "craneup": "CRANE UP", "handheld": "HANDHELD",
    "static": "CÂMERA FIXA", "pov": "POV", "macro": "MACRO", "closeup": "CLOSE-UP",
    "mediumshot": "MEDIUM SHOT", "wideshot": "WIDE SHOT", "shallowdepth": "SHALLOW DEPTH",
    "deepfocus": "DEEP FOCUS", "rackfocus": "RACK FOCUS", "slowmotion": "SLOW MOTION",
    "speedramp": "SPEED RAMP", "hyperlapse": "HYPERLAPSE", "softlight": "SOFT LIGHT",
    "goldenhour": "GOLDEN HOUR", "cinematic": "CINEMATIC", "naturaldaylight": "NATURAL DAYLIGHT",
    "motionblur": "MOTION BLUR", "glitch": "GLITCH", "vhs": "VHS", "particulas": "PARTÍCULAS",
    "glow": "GLOW", "reveal": "REVEAL", "loop": "LOOP", "9:16": "9:16 · VERTICAL",
    "16:9": "16:9 · HORIZONTAL",
}
COM_DESENHO = {"dollyin", "dollyout", "orbit", "tracking", "follow", "pan", "tilt", "craneup",
               "handheld", "static", "pov", "macro", "closeup", "mediumshot", "wideshot",
               "slowmotion", "speedramp", "hyperlapse", "rackfocus", "shallowdepth", "deepfocus", "loop"}


def desenho(efeito, p, t):
    """Cartão 380x280 com o movimento animado (p = 0..1 do efeito)."""
    W, H = 380, 280
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, W - 1, H - 1], 26, fill=AZUL + (232,))
    f = fonte("manrope", 22, 800)
    rot = ROTULOS.get(efeito, efeito.upper())
    d.text(((W - f.getlength(rot)) / 2, 14), rot, font=f, fill=LARANJA + (255,))
    cx, cy = W / 2, 160
    q = ease_io(p)
    if efeito == "orbit":
        rx, ry = 130, 58
        d.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], outline=(120, 160, 185, 255), width=3)
        _pessoa(d, cx, cy, 0.9)
        th = math.pi / 2 + 2 * math.pi * q
        x, y = cx + rx * math.cos(th), cy + ry * math.sin(th)
        atras = math.sin(th) < 0
        _camera(d, x, y, math.degrees(math.atan2(cy - y, cx - x)), esc=0.8 if atras else 1.0,
                alfa=150 if atras else 255)
        if not atras:
            _pessoa(d, cx, cy, 0.9) if False else None
    elif efeito in ("dollyin", "dollyout"):
        _pessoa(d, 300, cy, 0.9)
        x = 70 + 120 * (q if efeito == "dollyin" else 1 - q)
        d.line([(50, cy + 52), (250, cy + 52)], fill=(120, 160, 185, 255), width=3)
        _camera(d, x, cy + 10, 0)
        if efeito == "dollyin":
            _seta(d, (x + 40, cy - 50), (x + 100, cy - 50))
        else:
            _seta(d, (x + 30, cy - 50), (x - 30, cy - 50))
    elif efeito in ("tracking", "follow"):
        px = 110 + 160 * q
        _pessoa(d, px, cy - 20, 0.8)
        _seta(d, (px + 34, cy - 30), (px + 74, cy - 30))
        d.line([(40, cy + 66), (340, cy + 66)], fill=(120, 160, 185, 255), width=3)
        _camera(d, px, cy + 66, -90)
    elif efeito == "pan":
        x0, y0 = cx, cy + 80
        ang = -125 + 70 * q
        for da in (-16, 16):
            r = math.radians(ang + da)
            d.line([(x0, y0), (x0 + 190 * math.cos(r), y0 + 190 * math.sin(r))],
                   fill=DOURADO + (200,), width=3)
        _camera(d, x0, y0, ang)
        d.arc([x0 - 70, y0 - 70, x0 + 70, y0 + 70], -125, -55, fill=(160, 190, 210, 255), width=3)
    elif efeito in ("tilt", "craneup"):
        if efeito == "tilt":
            x0, y0, ang = 90, cy + 20, 25 - 50 * q
        else:
            x0, y0, ang = 90, cy + 80 - 120 * q, 10 - 20 * q
            d.line([(60, cy + 100), (x0, y0)], fill=(160, 190, 210, 255), width=6)
        _pessoa(d, 290, cy + 10, 1.1)
        for da in (-14, 14):
            r = math.radians(ang + da)
            d.line([(x0, y0), (x0 + 230 * math.cos(r), y0 + 230 * math.sin(r))],
                   fill=DOURADO + (200,), width=3)
        _camera(d, x0, y0, ang)
    elif efeito in ("handheld", "pov", "static"):
        jx = 6 * math.sin(t * 13) + 3 * math.sin(t * 29) if efeito != "static" else 0
        jy = 5 * math.sin(t * 11 + 1) + 3 * math.sin(t * 23) if efeito != "static" else 0
        _camera(d, cx + jx, cy + jy, 0, esc=1.8)
        if efeito == "static":
            d.rounded_rectangle([cx + 30, cy - 60, cx + 70, cy - 25], 6, fill=DOURADO + (255,))
            d.arc([cx + 36, cy - 82, cx + 64, cy - 50], 180, 360, fill=DOURADO + (255,), width=6)
        elif efeito == "pov":
            fp = fonte("manrope", 26, 700)
            d.text((cx - fp.getlength("1ª pessoa") / 2, cy + 60), "1ª pessoa", font=fp, fill=BRANCO + (255,))
    elif efeito in ("macro", "closeup", "mediumshot", "wideshot"):
        _pessoa(d, cx, cy + 20, 1.6)
        alvo = {"macro": (cx - 8, cy - 40, 22, 16), "closeup": (cx, cy - 30, 48, 40),
                "mediumshot": (cx, cy, 70, 80), "wideshot": (cx, cy + 20, 160, 110)}[efeito]
        x, y, rw, rh = alvo
        k = 1.6 - 0.6 * q
        d.rectangle([x - rw * k, y - rh * k, x + rw * k, y + rh * k], outline=LARANJA + (255,), width=4)
    elif efeito in ("slowmotion", "speedramp", "hyperlapse"):
        fp = fonte("archivo", 74, 900)
        txt = {"slowmotion": "0,5×", "speedramp": "1× → 3×", "hyperlapse": "»»»"}[efeito]
        if efeito == "speedramp":
            txt = "3×" if 0.35 < p < 0.7 else "1×"
        d.text((cx - fp.getlength(txt) / 2, cy - 50), txt, font=fp, fill=BRANCO + (255,))
    elif efeito in ("rackfocus", "shallowdepth", "deepfocus"):
        foco = (q if efeito == "rackfocus" else 1.0)
        for i, (x, r) in enumerate(((110, 42), (270, 30))):
            nitido = (i == 0 and foco > 0.5) or (i == 1 and foco <= 0.5) or efeito == "deepfocus"
            camada = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            ImageDraw.Draw(camada).ellipse([x - r, cy - r, x + r, cy + r],
                                           fill=(LARANJA if i == 0 else DOURADO) + (255,))
            if not nitido:
                camada = camada.filter(ImageFilter.GaussianBlur(9))
            img.alpha_composite(camada)
    elif efeito == "loop":
        d.arc([cx - 70, cy - 70, cx + 70, cy + 70], 30 + 360 * q, 320 + 360 * q, fill=LARANJA + (255,), width=10)
    return rgba(img)


# ---------------------------------------------------------------- efeitos no vídeo dela

def _cv2():
    import cv2
    return cv2


def _afim(frame, s, cx, cy, tx=0.0, ty=0.0, ang=0.0):
    cv2 = _cv2()
    M = cv2.getRotationMatrix2D((cx, cy), ang, s)
    M[0, 2] += tx
    M[1, 2] += ty
    return cv2.warpAffine(frame, M, (frame.shape[1], frame.shape[0]), flags=cv2.INTER_LINEAR,
                          borderMode=cv2.BORDER_REFLECT)


def _girar_y(frame, graus, cx, cy, esc=1.12, f=1700.0):
    """Gira o plano do vídeo em volta do eixo vertical (câmera andando em volta)."""
    cv2 = _cv2()
    H, W = frame.shape[:2]
    r = math.radians(graus)
    src = np.float32([[0, 0], [W, 0], [W, H], [0, H]])
    dst = []
    for x, y in src:
        X, Y = (x - cx) * esc, (y - cy) * esc
        Xr, Zr = X * math.cos(r), X * math.sin(r)
        k = f / (f + Zr)
        dst.append([cx + Xr * k, cy + Y * k])
    M = cv2.getPerspectiveTransform(src, np.float32(dst))
    return cv2.warpPerspective(frame, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)


def _desfocar(frame, sigma):
    cv2 = _cv2()
    peq = cv2.resize(frame, (frame.shape[1] // 4, frame.shape[0] // 4), interpolation=cv2.INTER_AREA)
    peq = cv2.GaussianBlur(peq, (0, 0), max(0.5, sigma / 4))
    return cv2.resize(peq, (frame.shape[1], frame.shape[0]), interpolation=cv2.INTER_LINEAR)


@lru_cache(maxsize=8)
def _mascara_elipse(cx, cy, rx, ry):
    yy, xx = np.mgrid[0:A, 0:L].astype(np.float32)
    d = ((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2
    return np.clip(1.6 - d, 0, 1)[..., None] ** 1.5


@lru_cache(maxsize=1)
def _vinheta():
    yy, xx = np.mgrid[0:A, 0:L].astype(np.float32)
    d = ((xx - L / 2) / (L * 0.62)) ** 2 + ((yy - A / 2) / (A * 0.62)) ** 2
    return np.clip(1.15 - d * 0.75, 0.25, 1)[..., None]


def _misturar(a, b, k):
    return (a.astype(np.float32) * (1 - k) + b.astype(np.float32) * k).astype(np.uint8)


def _ruido(t, sem):
    return (math.sin(t * 1.7 + sem) * 0.5 + math.sin(t * 3.1 + sem * 2) * 0.3
            + math.sin(t * 5.3 + sem * 3) * 0.2)


class Rosto:
    def __init__(self, dados):
        self.ts = [d["t"] for d in dados]
        self.dados = dados

    def em(self, t):
        if not self.dados:
            return None
        i = bisect.bisect_left(self.ts, t)
        for j in (i, i - 1, i + 1, i - 2, i + 2):
            if 0 <= j < len(self.dados) and self.dados[j]["rosto"]:
                return self.dados[j]["rosto"]
        return None

    def centro(self, t):
        r = self.em(t)
        if not r:
            return L / 2, A * 0.42
        return r["x"] + r["w"] / 2, r["y"] + r["h"] / 2


def aplicar_camera(frame, ev, t, ctx):
    """Aplica o efeito de câmera do evento no quadro (t no corte)."""
    cv2 = _cv2()
    ini, fim = ev["inicio"], ev["fim"]
    dur = max(0.4, fim - ini)
    tr = t - ini
    p = _clamp((tr - 0.1) / max(0.3, dur - 0.45))   # movimento ao longo do efeito
    q = ease_io(p)
    e = ev["efeito"]
    cx, cy = ev.get("_centro") or ctx["rosto"].centro(ini)
    forca = ev.get("forca", 1.0)
    k_in = ease_out(tr / 0.35)                         # entrada rápida (efeitos de imagem)
    if e == "dollyin":
        return _afim(frame, 1 + 0.34 * forca * q, cx, cy)
    if e == "dollyout":
        return _afim(frame, 1 + 0.34 * forca * (1 - q), cx, cy)
    if e == "closeup":
        return _afim(frame, 1 + 0.65 * forca * ease_out(tr / 0.6), cx, cy)
    if e == "macro":
        r = ctx["rosto"].em(ini)
        mx, my = (r["olho_d"] if r and "olho_d" in r else (cx, cy - 40))
        return _afim(frame, 1 + 2.4 * forca * ease_out(tr / 0.7), mx, my)
    if e == "wideshot":
        s = 1 - 0.38 * forca * q
        fundo = _desfocar(_afim(frame, 1.15, cx, cy), 30)
        fundo = (fundo.astype(np.float32) * (1 - 0.45 * q)).astype(np.uint8)
        peq = cv2.resize(frame, (int(L * s), int(A * s)), interpolation=cv2.INTER_AREA)
        x0, y0 = int(cx - cx * s), int(cy - cy * s)
        fundo[y0:y0 + peq.shape[0], x0:x0 + peq.shape[1]] = peq
        return fundo
    if e == "mediumshot":
        return _afim(frame, 1 + 0.25 * (1 - ease_out(tr / 0.6)), cx, cy)
    if e == "orbit":
        th = math.pi / 2 + 2 * math.pi * q
        graus = -24 * forca * math.cos(th - math.pi / 2)
        return _girar_y(frame, graus, cx, cy, esc=1.16)
    if e in ("tracking", "follow"):
        s = 1.24
        tx = L * 0.085 * forca * (1 - 2 * q)
        return _afim(frame, s, cx, cy, tx=tx)
    if e == "pan":
        s = 1.22
        tx = L * 0.08 * forca * (1 - 2 * q)
        return _girar_y(_afim(frame, s, cx, cy, tx=tx), 6 * (2 * q - 1), cx, cy, esc=1.04)
    if e == "tilt":
        s = 1.3
        ty = A * (-0.13 + 0.17 * q) * forca
        return _afim(frame, s, cx, cy, ty=ty)
    if e == "craneup":
        s = 1.36 - 0.36 * q
        ty = -A * 0.15 * (1 - q) * forca
        return _afim(frame, s, cx, cy, ty=ty)
    if e == "handheld":
        tx, ty = 14 * forca * _ruido(t, 1.3), 10 * forca * _ruido(t * 1.1, 4.1)
        return _afim(frame, 1.07, cx, cy, tx=tx, ty=ty, ang=0.7 * forca * _ruido(t * 0.9, 7.7))
    if e == "pov":
        tx, ty = 8 * _ruido(t, 2.2), 6 * _ruido(t * 1.2, 5.5)
        out = _afim(frame, 1.12, cx, cy, tx=tx, ty=ty, ang=0.4 * _ruido(t, 9.1))
        v = 1 - (1 - _vinheta()) * k_in * 1.2
        return (out.astype(np.float32) * np.clip(v, 0, 1)).astype(np.uint8)
    if e in ("shallowdepth", "rackfocus"):
        r = ctx["rosto"].em(ini)
        rx, ry = ((r["w"] * 1.6, r["h"] * 2.3) if r else (330, 430))
        m = _mascara_elipse(int(cx), int(cy + (r["h"] * 0.5 if r else 120)), int(rx), int(ry))
        borrado = _desfocar(frame, 22)
        if e == "shallowdepth":
            k = k_in
            mm = 1 - (1 - m) * k
        else:   # foco começa no fundo e viaja pro rosto
            k = ease_io(_clamp((tr - 0.3) / max(0.5, dur * 0.5)))
            mm = (1 - m) * (1 - k) + m * k
            mm = 0.15 + 0.85 * mm
        return (frame.astype(np.float32) * mm + borrado.astype(np.float32) * (1 - mm)).astype(np.uint8)
    if e == "slowmotion":
        prev = ctx.get("_eco")
        out = frame if prev is None or prev.shape != frame.shape else _misturar(frame, prev, 0.62)
        ctx["_eco"] = out
        return out
    if e == "speedramp":
        b = math.sin(math.pi * _clamp((p - 0.3) / 0.45)) if 0.3 < p < 0.75 else 0.0
        out = _afim(frame, 1 + 0.14 * b, cx, cy)
        if b > 0.05:
            z = [_afim(out, 1 + 0.03 * b * i, cx, cy) for i in (1, 2, 3)]
            out = np.mean([out.astype(np.float32)] + [x.astype(np.float32) for x in z], axis=0).astype(np.uint8)
        return out
    if e in ("hyperlapse", "motionblur"):
        n = 31 if e == "motionblur" else 45
        k = cv2.blur(frame, (n, 1))
        out = _misturar(frame, k, 0.75 * k_in)
        if e == "hyperlapse":
            out = _afim(out, 1.05 + 0.08 * q, cx, cy)
        return out
    if e in ("softlight", "glow"):
        b = _desfocar(frame, 26).astype(np.float32)
        f32 = frame.astype(np.float32)
        tela = 255 - (255 - f32) * (255 - b) / 255
        forte = 0.45 if e == "softlight" else 0.7
        out = f32 * (1 - forte * k_in) + tela * forte * k_in
        out = out * (1 - 0.08 * k_in) + 255 * 0.08 * k_in
        return np.clip(out, 0, 255).astype(np.uint8)
    if e == "goldenhour":
        f32 = frame.astype(np.float32)
        quente = f32 * np.array([1.16, 1.0, 0.72], np.float32) + np.array([18, 6, 0], np.float32)
        yy, xx = np.mgrid[0:A:4, 0:L:4].astype(np.float32)
        luz = np.clip(1 - np.hypot((xx - L) / (L * 0.8), (yy) / (A * 0.9)), 0, 1)
        luz = cv2.resize(luz, (L, A))[..., None]
        quente = quente + luz * np.array([120, 60, 0], np.float32) * 0.6
        return np.clip(f32 * (1 - k_in) + quente * k_in, 0, 255).astype(np.uint8)
    if e == "cinematic":
        f32 = frame.astype(np.float32)
        lum = f32.mean(axis=2, keepdims=True) / 255
        sombra_c = np.array([-10, 12, 22], np.float32) * (1 - lum)
        luz_c = np.array([22, 6, -18], np.float32) * lum
        g = (f32 - 128) * 1.12 + 128 + sombra_c + luz_c
        g = g * _vinheta()
        out = np.clip(f32 * (1 - k_in) + g * k_in, 0, 255).astype(np.uint8)
        barra = int(132 * k_in)
        if barra:
            out[:barra] = 0
            out[A - barra:] = 0
        return out
    if e == "naturaldaylight":
        f32 = frame.astype(np.float32)
        cinza = f32.mean(axis=2, keepdims=True)
        n = cinza + (f32 - cinza) * 0.55
        n = n * np.array([1.07, 1.06, 0.93], np.float32) + 8
        return np.clip(f32 * (1 - k_in) + n * k_in, 0, 255).astype(np.uint8)
    if e in ("glitch", "vhs"):
        out = frame.copy()
        desl = 10 if e == "glitch" else 5
        out[..., 0] = np.roll(frame[..., 0], desl, axis=1)
        out[..., 2] = np.roll(frame[..., 2], -desl, axis=1)
        rng = np.random.default_rng(int(t * 30))
        if e == "glitch":
            for _ in range(5):
                y0 = int(rng.integers(0, A - 60))
                h = int(rng.integers(8, 60))
                out[y0:y0 + h] = np.roll(out[y0:y0 + h], int(rng.integers(-60, 60)), axis=1)
        else:
            out = (out.astype(np.float32) * 0.92 + rng.normal(0, 9, out.shape).astype(np.float32)).clip(0, 255)
            out = out.astype(np.uint8)
            out[::3] = (out[::3].astype(np.float32) * 0.8).astype(np.uint8)
        return out
    if e == "particulas":
        return frame
    if e == "reveal":
        r = ease_out(tr / 1.0) * math.hypot(L, A) / 2
        m = np.zeros((A, L), np.uint8)
        cv2.circle(m, (int(cx), int(cy)), int(r), 255, -1)
        m = cv2.GaussianBlur(m, (0, 0), 12)[..., None].astype(np.float32) / 255
        fundo = np.empty_like(frame)
        fundo[:] = AZUL_PROF
        return (frame * m + fundo * (1 - m)).astype(np.uint8)
    if e == "9:16":
        out = (frame.astype(np.float32) * (1 - 0.6 * k_in)).astype(np.uint8)
        w = int(A * 9 / 16)
        x0 = int(cx - w / 2)
        out[:, x0:x0 + w] = frame[:, x0:x0 + w]
        cv2.rectangle(out, (x0, 2), (x0 + w, A - 3), LARANJA, 5)
        return out
    if e == "16:9":
        out = frame.copy()
        cv2.rectangle(out, (4, 4), (L - 5, A - 5), LARANJA, 8)
        return out
    return frame


def particulas(frame, ev, t):
    rng = np.random.default_rng(7)
    n = 70
    xs = rng.uniform(0, L, n)
    vs = rng.uniform(60, 160, n)
    fs = rng.uniform(0, 1000, n)
    rs = rng.uniform(3, 9, n)
    tr = t - ev["inicio"]
    k = presenca(t, ev["inicio"], ev["fim"], 0.4, 0.4)
    img = Image.new("RGBA", (L, A), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for x, v, f, r in zip(xs, vs, fs, rs):
        y = A - ((f + tr * v) % (A + 40))
        xx = x + 20 * math.sin(tr * 1.3 + f)
        d.ellipse([xx - r, y - r, xx + r, y + r], fill=(DOURADO if r < 5 else LARANJA) + (int(200 * k),))
    img = img.filter(ImageFilter.GaussianBlur(1.2))
    colar(frame, rgba(img), 0, 0)


def anel_orbita(frame, ev, t, ctx):
    """Anel em volta dela com a câmera (ponto laranja) dando a volta."""
    ini, fim = ev["inicio"], ev["fim"]
    dur = max(0.4, fim - ini)
    p = _clamp((t - ini - 0.1) / max(0.3, dur - 0.45))
    q = ease_io(p)
    k = presenca(t, ini, fim, 0.3, 0.25)
    cx, cy = ev.get("_centro") or ctx["rosto"].centro(ini)
    ox, oy, rx, ry = cx, cy + 300, 600, 120
    W, H = int(2 * rx + 80), int(2 * ry + 80)
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    c0x, c0y = W / 2, H / 2
    pts = [(c0x + rx * math.cos(a), c0y + ry * math.sin(a)) for a in np.linspace(0, 2 * math.pi, 120)]
    for i in range(len(pts) - 1):
        a = 2 * math.pi * i / (len(pts) - 1)
        frente = math.sin(a) > 0
        d.line([pts[i], pts[i + 1]], fill=(LARANJA if frente else DOURADO) + ((230 if frente else 90),),
               width=6 if frente else 3)
    th = math.pi / 2 + 2 * math.pi * q
    for j in range(10, 0, -1):     # rastro
        a = th - j * 0.05
        x, y = c0x + rx * math.cos(a), c0y + ry * math.sin(a)
        r = 6 * (1 - j / 11)
        d.ellipse([x - r, y - r, x + r, y + r], fill=LARANJA + (int(160 * (1 - j / 11)),))
    x, y = c0x + rx * math.cos(th), c0y + ry * math.sin(th)
    atras = math.sin(th) < 0
    esc = 0.75 if atras else 1.25
    _camera(d, x, y, math.degrees(math.atan2(c0y - y, c0x - x)), esc=esc, alfa=150 if atras else 255)
    img = img.filter(ImageFilter.GaussianBlur(0.6))
    colar(frame, rgba(img), ox - W / 2, oy - H / 2, k)


# ---------------------------------------------------------------- slides

def preparar_slides(nome, ed):
    """Páginas dos PDFs → PNG 1920x1080 em trabalho/<nome>/slides/ (só as que vão ser usadas)."""
    p = pasta(nome)
    out = p / "slides"
    out.mkdir(exist_ok=True)
    decks = ed.get("aula", {}).get("decks", {})
    for ev in ed.get("aula", {}).get("eventos", []):
        if ev["tipo"] != "slide":
            continue
        arq = out / f"{ev['deck']}-{ev['pagina']:02d}.png"
        if arq.exists():
            continue
        pdf = decks[ev["deck"]]
        base = out / f"_{ev['deck']}-{ev['pagina']}"
        rodar(["pdftoppm", "-f", str(ev["pagina"]), "-l", str(ev["pagina"]), "-scale-to-x", "1920",
               "-scale-to-y", "-1", "-png", "-singlefile", pdf, str(base)])
        Path(str(base) + ".png").rename(arq)
    return out


@lru_cache(maxsize=6)
def _slide_img(caminho, W, H):
    img = Image.open(caminho).convert("RGB").resize((W, H), Image.LANCZOS)
    m = Image.new("L", (W, H), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, W - 1, H - 1], 22, fill=255)
    img = img.convert("RGBA")
    img.putalpha(m)
    s, mg = sombra(img, 22, (0, 12), 140)
    return rgba(s), mg


@lru_cache(maxsize=1)
def _fundo_slides():
    yy, xx = np.mgrid[0:A, 0:L].astype(np.float32)
    k = np.clip(np.hypot((xx - L * 0.3) / L, (yy - A * 0.2) / A), 0, 1)[..., None]
    a, b = np.array(AZUL_MEDIO, np.float32), np.array(AZUL_PROF, np.float32)
    return (a * (1 - k) + b * k).astype(np.uint8)


SX, SY, SW, SH = 40, 112, 1488, 837       # slide
CX, CY, CW, CH = 1560, 112, 320, 837      # coluna dela


def tela_slide(frame, ev, t, ctx, caminho, camera=None, saida=True):
    """frame: o que já está na tela; camera: o quadro dela (pra coluna);
    saida=False quando outro slide entra logo depois (sem voltar pro vídeo dela no meio)."""
    cv2 = _cv2()
    camera = frame if camera is None else camera
    k = presenca(t, ev["inicio"], ev["fim"], 0.45, 0.35 if saida else 0)
    if k <= 0:
        return frame
    cx, cy = ctx["rosto"].centro(t)
    # recorte em pé do vídeo dela, centrado no rosto
    alt = A
    larg = int(alt * CW / CH)
    x0 = int(min(max(0, cx - larg / 2), L - larg))
    col = cv2.resize(camera[:, x0:x0 + larg], (CW, CH), interpolation=cv2.INTER_AREA)
    tela = _fundo_slides().copy()
    m = np.zeros((CH, CW), np.uint8)
    cv2.rectangle(m, (0, 0), (CW - 1, CH - 1), 255, -1)
    tela[CY:CY + CH, CX:CX + CW] = col
    cv2.rectangle(tela, (CX - 3, CY - 3), (CX + CW + 2, CY + CH + 2), LARANJA, 4)
    img, mg = _slide_img(str(caminho), SW, SH)
    dx = (1 - ease_out((t - ev["inicio"]) / 0.45)) * -140 if t - ev["inicio"] < 0.45 else 0
    colar(tela, img, SX - mg + dx, SY - mg)
    if k >= 0.999:
        return tela
    return _misturar(frame, tela, k)


# ---------------------------------------------------------------- linha do tempo

class Aula:
    def __init__(self, nome):
        self.nome = nome
        p = pasta(nome)
        ed = ler_edicao(nome)
        self.ed = ed
        cfg = ed.get("aula", {})
        self.eventos = sorted(cfg.get("eventos", []), key=lambda e: e["inicio"])
        self.legenda = Legenda(ler_json(p / "transcricao_corte.json", []),
                               [tuple(x) for x in cfg.get("legenda_oculta", [])])
        self.rosto = Rosto(ler_json(p / "rosto.json", []))
        self.slides = p / "slides"
        self.ctx = {"rosto": self.rosto}
        for ev in self.eventos:
            if ev["tipo"] == "camera" and "_centro" not in ev:
                ev["_centro"] = self.rosto.centro(ev["inicio"] + 0.1)

    def ativos(self, t, tipo):
        return sorted([e for e in self.eventos if e["tipo"] == tipo and e["inicio"] <= t < e["fim"]],
                      key=lambda e: e["inicio"])

    def quadro(self, frame, t):
        slides = self.ativos(t, "slide")
        cams = [] if slides else self.ativos(t, "camera")
        for ev in cams:
            if ev["efeito"] == "slowmotion" and ev.get("_ultimo_t", -1) > t:
                self.ctx.pop("_eco", None)
            ev["_ultimo_t"] = t
            frame = aplicar_camera(frame, ev, t, self.ctx)
        if not any(e["efeito"] == "slowmotion" for e in cams):
            self.ctx.pop("_eco", None)
        if not frame.flags.writeable:
            frame = frame.copy()
        for ev in cams:
            if ev["efeito"] == "orbit":
                anel_orbita(frame, ev, t, self.ctx)
            elif ev["efeito"] == "particulas":
                particulas(frame, ev, t)
        camera = frame
        for i, ev in enumerate(slides):      # slides em ordem de entrada
            frame = tela_slide(frame, ev, t, self.ctx,
                               self.slides / f"{ev['deck']}-{ev['pagina']:02d}.png",
                               camera=camera, saida=(i == len(slides) - 1))
        # abertura de capítulo e etiqueta fixa
        for ev in self.ativos(t, "capitulo"):
            tr = t - ev["inicio"]
            dur_ab = ev.get("abertura", 3.2)
            if tr < dur_ab and not slides:
                k = presenca(t, ev["inicio"], ev["inicio"] + dur_ab, 0.5, 0.45)
                colar(frame, degrade_esquerda(), 0, 0, k)
                img = img_abertura(ev["numero"], ev["titulo"], ev.get("sub", ""))
                colar(frame, img, 110 - 120 * (1 - ease_out(tr / 0.5)), (A - img.shape[0]) / 2 - 40, k)
            k2 = presenca(t, ev["inicio"] + (0 if slides else dur_ab - 0.3), ev["fim"], 0.4, 0.3)
            if k2 > 0:
                colar(frame, img_etiqueta(ev["numero"], ev.get("curto", ev["titulo"])), 40, 34, k2)
        if not slides:
            y = 140
            for ev in self.ativos(t, "termo"):
                img, mg = img_termo(ev["termo"], ev.get("texto", ""))
                k = presenca(t, ev["inicio"], ev["fim"], 0.35, 0.25)
                dx = -(img.shape[1]) * (1 - ease_out((t - ev["inicio"]) / 0.35))
                colar(frame, img, 48 - mg + dx, y - mg, k)
                y += img.shape[0] - 2 * mg + 24
            for ev in cams:
                if ev["efeito"] in COM_DESENHO and not ev.get("sem_desenho"):
                    dur = max(0.4, ev["fim"] - ev["inicio"])
                    p = _clamp((t - ev["inicio"] - 0.1) / max(0.3, dur - 0.45))
                    k = presenca(t, ev["inicio"], ev["fim"], 0.3, 0.25)
                    colar(frame, desenho(ev["efeito"], p, t), L - 40 - 380, 34, k)
        self.legenda.desenhar(frame, t)
        return frame

    def sons(self):
        """Efeitos sonoros: whoosh na abertura e no slide, pop no termo, swish no efeito."""
        out = []
        for ev in self.eventos:
            if ev.get("sem_som"):
                continue
            t = ev["inicio"]
            if ev["tipo"] == "capitulo":
                out.append((t, "whoosh", -19))
            elif ev["tipo"] == "slide":
                out.append((t, "whoosh_sobe", -21))
            elif ev["tipo"] == "termo":
                out.append((t + 0.05, "pop", -20))
            elif ev["tipo"] == "camera":
                som = {"glitch": "impacto_seco", "vhs": "clique", "speedramp": "whoosh_sobe",
                       "reveal": "whoosh"}.get(ev["efeito"], "swish")
                out.append((t, som, -22))
        out.sort()
        limpos = []
        for s in out:
            if limpos and s[0] - limpos[-1][0] < 0.6:
                continue
            limpos.append(s)
        return limpos


# ---------------------------------------------------------------- render

def _pedaco(args):
    nome, q0, q1, saida, crf, preset = args
    aula = Aula(nome)
    p = pasta(nome)
    dec = subprocess.Popen(["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", f"{q0 / FPS:.6f}",
                            "-i", str(p / "corte.mp4"), "-frames:v", str(q1 - q0), "-an",
                            "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    enc = subprocess.Popen(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo",
                            "-pix_fmt", "rgb24", "-s", f"{L}x{A}", "-r", str(FPS), "-i", "-",
                            "-c:v", "libx264", "-preset", preset, "-crf", str(crf), "-pix_fmt", "yuv420p",
                            "-g", "60", "-threads", "2", "-video_track_timescale", "15360", str(saida)],
                           stdin=subprocess.PIPE)
    tam = L * A * 3
    ultimo = None
    for q in range(q0, q1):
        buf = dec.stdout.read(tam)
        if len(buf) < tam:
            if ultimo is None:
                break
            frame = ultimo.copy()           # o corte acabou 1 quadro antes: repete
        else:
            frame = np.frombuffer(buf, np.uint8).reshape(A, L, 3).copy()
            ultimo = frame
        frame = aula.quadro(frame, q / FPS)
        enc.stdin.write(np.ascontiguousarray(frame).tobytes())
    enc.stdin.close()
    dec.stdout.close()
    dec.wait()
    if enc.wait() != 0:
        raise RuntimeError(f"Falhou ao gravar o pedaço {q0}-{q1}")
    return saida


def _cortes_do_tempo(intervalos, D):
    out = []
    for a, b in intervalos:
        a, b = max(0.0, a), min(D, b)
        if b - a > 0.2:
            out.append((a, b))
    return out


def _audio(nome, intervalos, sons, tmp):
    """Voz do corte nos intervalos + efeitos sonoros, normalizado em -14 LUFS."""
    from . import sons as S
    from .render import _loudnorm_medir
    p = pasta(nome)
    bruto = tmp / "voz.wav"
    ffmpeg("-i", p / "corte.mp4", "-vn", "-ac", 2, "-ar", 48000, "-c:a", "pcm_s16le", bruto)
    import wave
    with wave.open(str(bruto), "rb") as f:
        voz = np.frombuffer(f.readframes(f.getnframes()), np.int16).reshape(-1, 2).astype(np.float32) / 32768
    partes, deslocar = [], 0.0
    for a, b in intervalos:
        x = voz[int(a * 48000):int(b * 48000)].copy()
        for t, tipo, db in sons:
            if a <= t < b:
                with wave.open(str(S.arquivo(tipo)), "rb") as f:
                    s = np.frombuffer(f.readframes(f.getnframes()), np.int16).reshape(-1, 2)
                s = s.astype(np.float32) / 32768 * (10 ** (db / 20))
                i0 = int((t - a) * 48000)
                n = min(len(s), len(x) - i0)
                if n > 0:
                    x[i0:i0 + n] += s[:n]
        if len(intervalos) > 1:
            n = int(0.012 * 48000)
            x[:n] *= np.linspace(0, 1, n)[:, None]
            x[-n:] *= np.linspace(1, 0, n)[:, None]
        partes.append(x)
    mix = np.clip(np.concatenate(partes), -1, 1)
    misturado = tmp / "mix.wav"
    with wave.open(str(misturado), "wb") as f:
        f.setnchannels(2)
        f.setsampwidth(2)
        f.setframerate(48000)
        f.writeframes((mix * 32767).astype(np.int16).tobytes())
    m = _loudnorm_medir(misturado)
    final = tmp / "som.m4a"
    ffmpeg("-i", misturado, "-af",
           f"loudnorm=I=-14:TP=-1:LRA=11:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
           f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:linear=true,"
           "aresample=48000", "-c:a", "aac", "-b:a", "192k", final)
    return final


def render(nome, intervalos=None, saida="aula.mp4", trabalhadores=3, crf=20, preset="medium"):
    """Desenha a aula (ou só os intervalos [a, b] do corte, juntos) e grava em trabalho/<nome>/saida."""
    import time
    t0 = time.time()
    p = pasta(nome)
    ed = ler_edicao(nome)
    preparar_slides(nome, ed)
    D = sondar(p / "corte.mp4")["duracao"]
    intervalos = _cortes_do_tempo(intervalos or [(0, D)], D)
    tmp = p / "render_aula"
    tmp.mkdir(exist_ok=True)
    for f in tmp.glob("*"):
        f.unlink()
    # pedaços de ~20 s (ou menos) pra dividir entre os processos
    tarefas = []
    for a, b in intervalos:
        q0, q1 = int(round(a * FPS)), int(round(b * FPS))
        passo = max(FPS * 8, min(FPS * 25, (q1 - q0) // max(1, trabalhadores)))
        q = q0
        while q < q1:
            fim = min(q1, q + passo)
            if q1 - fim < FPS * 2:
                fim = q1
            tarefas.append((nome, q, fim, str(tmp / f"v{len(tarefas):04d}.mp4"), crf, preset))
            q = fim
    with ProcessPoolExecutor(trabalhadores) as ex:
        partes = list(ex.map(_pedaco, tarefas))
    (tmp / "v.txt").write_text("".join(f"file '{x}'\n" for x in partes))
    ffmpeg("-f", "concat", "-safe", 0, "-i", tmp / "v.txt", "-c", "copy", tmp / "video.mp4")
    sons = Aula(nome).sons()
    som = _audio(nome, intervalos, sons, tmp)
    destino = p / saida
    ffmpeg("-i", tmp / "video.mp4", "-i", som, "-map", "0:v", "-map", "1:a", "-c", "copy",
           "-shortest", "-movflags", "+faststart", destino)
    for f in tmp.glob("*"):
        f.unlink()
    dur = sondar(destino)["duracao"]
    return destino, dur, time.time() - t0


def folha(nome, tempos, arquivo="aula.mp4"):
    """Folha de quadros 16:9 (3 colunas) pra conferir."""
    p = pasta(nome)
    ims = []
    for t in tempos:
        tmp = p / "_q.png"
        ffmpeg("-ss", f"{t:.3f}", "-i", p / arquivo, "-frames:v", 1, "-vf", "scale=640:360", tmp)
        im = Image.open(tmp).convert("RGB")
        d = ImageDraw.Draw(im)
        f = fonte("manrope", 26, 800)
        d.rounded_rectangle([8, 8, 16 + f.getlength(mmss(t)) + 16, 48], 8, fill=(0, 0, 0))
        d.text((20, 12), mmss(t), font=f, fill=(255, 255, 255))
        ims.append(im)
        tmp.unlink()
    col = 3
    lin = (len(ims) + col - 1) // col
    out = Image.new("RGB", (col * 640 + (col + 1) * 10, lin * 360 + (lin + 1) * 10), (24, 24, 24))
    for i, im in enumerate(ims):
        out.paste(im, (10 + (i % col) * 650, 10 + (i // col) * 370))
    arq = p / f"folha_{int(tempos[0] * 10)}.jpg"
    out.save(arq, quality=88)
    return arq


# ---------------------------------------------------------------- roteiro por palavra

def _mapa_tempo(segs):
    """Tempo do original -> tempo do corte."""
    inis, offs = [], []
    t = 0.0
    for s, e in segs:
        inis.append(s)
        offs.append(t)
        t += e - s

    def para_corte(x, lado="inicio"):
        i = bisect.bisect_right(inis, x) - 1
        if i < 0:
            return 0.0
        s, e = segs[i]
        if x < e:
            return offs[i] + (x - s)
        # caiu num pedaço que saiu: começo vai pro próximo trecho, fim fica no fim deste
        if lado == "inicio" and i + 1 < len(segs):
            return offs[i + 1]
        return offs[i] + (e - s)
    return para_corte, t


def ancorar(nome):
    """edicao.json → aula.roteiro (eventos presos às palavras, índices da transcrição original)
    vira aula.eventos (tempos no corte). Rode de novo depois de qualquer mudança no corte."""
    from .base import salvar_edicao
    p = pasta(nome)
    ed = ler_edicao(nome)
    ws = ler_json(p / "transcricao.json")
    para_corte, D = _mapa_tempo(ed["corte"]["segmentos"])
    cfg = ed.setdefault("aula", {})
    eventos = []
    for r in cfg.get("roteiro", []):
        ev = {k: v for k, v in r.items() if k not in ("de", "ate", "antes", "depois")}
        ini = para_corte(ws[r["de"]]["s"], "inicio") - r.get("antes", 0.1)
        fim = para_corte(ws[r.get("ate", r["de"])]["e"], "fim") + r.get("depois", 0.25)
        ev["inicio"], ev["fim"] = round(max(0.0, ini), 3), round(min(D, fim), 3)
        eventos.append(ev)
    # capítulo vai até o próximo
    caps = sorted([e for e in eventos if e["tipo"] == "capitulo"], key=lambda e: e["inicio"])
    for a, b in zip(caps, caps[1:] + [None]):
        a["fim"] = round(b["inicio"] - 0.15 if b else D, 3)
    # slide que começa junto com um capítulo espera a abertura do capítulo terminar
    for e in eventos:
        if e["tipo"] != "slide":
            continue
        for c in caps:
            ab = c.get("abertura", 3.2)
            if c["inicio"] - 0.5 <= e["inicio"] < c["inicio"] + ab and e["fim"] - (c["inicio"] + ab) >= 3:
                e["inicio"] = round(c["inicio"] + ab - 0.2, 3)
    # efeito de câmera não briga com slide
    slides = [(e["inicio"], e["fim"]) for e in eventos if e["tipo"] == "slide"]
    avisos, fora = [], []
    for e in eventos:
        if e["tipo"] != "camera":
            continue
        for a, b in slides:
            if a < e["fim"] and e["inicio"] < b:
                if e["inicio"] < a:           # o efeito termina quando o slide entra
                    e["fim"] = round(a, 3)
                else:                         # ou começa quando o slide sai
                    e["inicio"] = round(b, 3)
        if e["fim"] - e["inicio"] < 0.4:
            fora.append(e)
            avisos.append(f"efeito {e['efeito']} em {mmss(e['inicio'])} saiu (sem espaço entre slides)")
    eventos = [e for e in eventos if e not in fora]
    cfg["eventos"] = sorted(eventos, key=lambda e: e["inicio"])
    salvar_edicao(nome, ed)
    return len(eventos), avisos


def capitulos_youtube(nome):
    """Lista de capítulos pro texto do YouTube (0:00 obrigatório no primeiro)."""
    ed = ler_edicao(nome)
    caps = sorted([e for e in ed.get("aula", {}).get("eventos", []) if e["tipo"] == "capitulo"],
                  key=lambda e: e["inicio"])
    linhas = ["0:00 Abertura"]
    for c in caps:
        t = int(c["inicio"])
        linhas.append(f"{t // 60}:{t % 60:02d} {c['titulo']}")
    return "\n".join(linhas)
