"""Identidade da Nina Fit Food no vídeo: cores, fontes e desenhos (Pillow)."""
import math
import sys
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

RAIZ = Path("/home/user/claude")
sys.path.insert(0, str(RAIZ))
from editor.base import fonte  # noqa: E402

PASTA = RAIZ / "trabalho" / "nina"
W, H, FPS = 1080, 1920, 30

ROXO = (74, 30, 72)
ROXO_ESC = (36, 11, 36)
ROXO_VIVO = (122, 52, 118)
ROXO_CAIXA = (128, 58, 124)
LILAS = (226, 204, 234)
VERDE = (178, 182, 104)
VERDE_CLARO = (220, 226, 150)
BRANCO = (255, 255, 255)
CREME = (253, 249, 251)
PRETO = (0, 0, 0)
ESCURO = (40, 22, 40)


def rgba(c, a=255):
    return tuple(c[:3]) + (int(a),)


# ---------- curvas de tempo ----------

def lim(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def ease_out(p):
    p = lim(p)
    return 1 - (1 - p) ** 3


def ease_in(p):
    p = lim(p)
    return p ** 3


def ease_in_out(p):
    p = lim(p)
    return 4 * p ** 3 if p < 0.5 else 1 - (-2 * p + 2) ** 3 / 2


def ease_back(p, s=1.9):
    """Passa um pouco do ponto e volta (efeito de 'pulo')."""
    p = lim(p)
    return 1 + (s + 1) * (p - 1) ** 3 + s * (p - 1) ** 2


def mola(p, freq=3.2, amort=6.0):
    """Mola amortecida: 0 -> 1 com balanço."""
    p = max(0.0, p)
    return 1 - math.exp(-amort * p) * math.cos(freq * 2 * math.pi * p)


# ---------- texto ----------

def palavra(txt, f, cor=BRANCO, contorno=0, cor_contorno=PRETO):
    """Uma palavra com linha de base fixa (todas as palavras da mesma fonte ficam alinhadas)."""
    asc, desc = f.getmetrics()
    pad = contorno + 8
    larg = int(math.ceil(f.getlength(txt))) + 2 * pad
    im = Image.new("RGBA", (larg, asc + desc + 2 * pad), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((pad, pad + asc), txt, font=f, fill=rgba(cor), anchor="ls",
                            stroke_width=contorno, stroke_fill=rgba(cor_contorno))
    return im


def recortar(im):
    c = im.getchannel("A").getbbox()
    return im.crop(c) if c else im


def sombra(img, raio=16, desl=(0, 10), alfa=120, cor=(0, 0, 0)):
    m = raio * 2 + max(abs(desl[0]), abs(desl[1]))
    base = Image.new("RGBA", (img.width + 2 * m, img.height + 2 * m), (0, 0, 0, 0))
    a = img.getchannel("A").point(lambda v: alfa * v // 255)
    s = Image.new("RGBA", img.size, rgba(cor))
    s.putalpha(a)
    base.alpha_composite(s, (m + desl[0], m + desl[1]))
    base = base.filter(ImageFilter.GaussianBlur(raio))
    base.alpha_composite(img, (m, m))
    return base


def texto(txt, f, cor=BRANCO, contorno=0, cor_contorno=PRETO, sombra_alfa=0):
    im = recortar(palavra(txt, f, cor, contorno, cor_contorno))
    return sombra(im, 10, (0, 6), sombra_alfa) if sombra_alfa else im


def pilula(txt, f, fundo=ROXO_VIVO, cor=BRANCO, pad=(40, 20), icone=None, sombra_alfa=110):
    t = recortar(palavra(txt, f, cor))
    iw = icone.width + 18 if icone else 0
    w, h = t.width + iw + 2 * pad[0], max(t.height, icone.height if icone else 0) + 2 * pad[1]
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(im).rounded_rectangle([0, 0, w - 1, h - 1], h // 2, fill=rgba(fundo))
    if icone:
        im.alpha_composite(icone, (pad[0], (h - icone.height) // 2))
    im.alpha_composite(t, (pad[0] + iw, (h - t.height) // 2))
    return sombra(im, 14, (0, 8), sombra_alfa) if sombra_alfa else im


@lru_cache(maxsize=64)
def emoji(ch, tam):
    f = ImageFont.truetype("/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf", 109)
    im = Image.new("RGBA", (220, 220), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((30, 30), ch, font=f, embedded_color=True)
    im = recortar(im)
    e = tam / max(im.size)
    return im.resize((max(1, int(im.width * e)), max(1, int(im.height * e))), Image.LANCZOS)


# ---------- colar com escala, giro e transparência ----------

def colar(tela, img, cx, cy, escala=1.0, alfa=1.0, giro=0.0):
    if escala <= 0.01 or alfa <= 0.004:
        return
    if abs(escala - 1) > 0.003:
        img = img.resize((max(1, int(img.width * escala)), max(1, int(img.height * escala))), Image.BICUBIC)
    if abs(giro) > 0.05:
        img = img.rotate(giro, expand=True, resample=Image.BICUBIC)
    if alfa < 0.996:
        img = img.copy()
        img.putalpha(img.getchannel("A").point(lambda v: int(v * alfa)))
    x, y = int(round(cx - img.width / 2)), int(round(cy - img.height / 2))
    if x >= tela.width or y >= tela.height or x + img.width <= 0 or y + img.height <= 0:
        return
    sx, sy = max(0, -x), max(0, -y)
    if sx or sy or x + img.width > tela.width or y + img.height > tela.height:
        img = img.crop((sx, sy, min(img.width, tela.width - x), min(img.height, tela.height - y)))
        x, y = x + sx, y + sy
    tela.alpha_composite(img, (x, y))


# ---------- formas ----------

def _aa(desenhar, w, h, k=3):
    """Desenha em tamanho maior e reduz: bordas lisas."""
    big = Image.new("RGBA", (w * k, h * k), (0, 0, 0, 0))
    desenhar(ImageDraw.Draw(big), k)
    return big.resize((w, h), Image.LANCZOS)


@lru_cache(maxsize=64)
def coracao(tam, cor, alfa=255):
    def d(dr, k):
        pts = []
        for i in range(120):
            t = 2 * math.pi * i / 120
            x = 16 * math.sin(t) ** 3
            y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
            pts.append(((x + 17) / 34 * tam * k, (17 - y) / 34 * tam * k))
        dr.polygon(pts, fill=rgba(cor, alfa))
    return _aa(d, tam, tam)


@lru_cache(maxsize=32)
def brilho(tam, cor=BRANCO):
    """Estrelinha de 4 pontas com halo."""
    def d(dr, k):
        c = tam * k / 2
        r1, r2 = tam * k / 2, tam * k / 9
        pts = []
        for i in range(8):
            a = math.pi / 4 * i - math.pi / 2
            r = r1 if i % 2 == 0 else r2
            pts.append((c + r * math.cos(a), c + r * math.sin(a)))
        dr.polygon(pts, fill=rgba(cor))
    im = _aa(d, tam, tam)
    halo = im.filter(ImageFilter.GaussianBlur(tam / 8))
    out = Image.new("RGBA", im.size, (0, 0, 0, 0))
    out.alpha_composite(halo)
    out.alpha_composite(halo)
    out.alpha_composite(im)
    return out


@lru_cache(maxsize=16)
def folha(tam, cor=VERDE, alfa=255):
    """Folhinha (como as do logo): duas curvas e uma nervura."""
    def d(dr, k):
        L = tam * k
        pts = []
        for i in range(61):
            t = i / 60
            pts.append((L * t, L / 2 - math.sin(math.pi * t) * L * 0.30 * (1 - 0.25 * t)))
        for i in range(60, -1, -1):
            t = i / 60
            pts.append((L * t, L / 2 + math.sin(math.pi * t) * L * 0.30 * (1 - 0.25 * t)))
        dr.polygon(pts, fill=rgba(cor, alfa))
        dr.line([(L * 0.08, L / 2), (L * 0.85, L / 2)], fill=rgba(ROXO, int(alfa * 0.45)), width=max(1, int(L / 40)))
    return _aa(d, tam, tam)


def caminho_parcial(dr, caminhos, p, cor, largura):
    """Desenha os caminhos (listas de pontos) até a fração p do comprimento total."""
    comps = []
    for c in caminhos:
        comps.append([math.dist(c[i], c[i + 1]) for i in range(len(c) - 1)])
    total = sum(sum(x) for x in comps)
    resta = p * total
    for c, cs in zip(caminhos, comps):
        if resta <= 0:
            break
        pts = [c[0]]
        for i, L in enumerate(cs):
            if resta >= L:
                pts.append(c[i + 1])
                resta -= L
            else:
                f = resta / L if L else 0
                pts.append((c[i][0] + (c[i + 1][0] - c[i][0]) * f, c[i][1] + (c[i + 1][1] - c[i][1]) * f))
                resta = 0
                break
        if len(pts) > 1:
            dr.line(pts, fill=cor, width=largura, joint="curve")
            r = largura / 2
            for q in (pts[0], pts[-1]):
                dr.ellipse([q[0] - r, q[1] - r, q[0] + r, q[1] + r], fill=cor)


def arco(cx, cy, r, a0, a1, n=24):
    return [(cx + r * math.cos(math.radians(a0 + (a1 - a0) * i / n)),
             cy + r * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]


def igreja(p, tam=620, cor=BRANCO):
    """Igreja em traço que vai se desenhando (p de 0 a 1)."""
    k = 2
    S = tam * k / 600

    def P(pts):
        return [(x * S, y * S) for x, y in pts]
    porta = [(262, 560), (262, 482)] + arco(300, 482, 38, 180, 360)[1:] + [(338, 560)]
    caminhos = [
        P([(30, 560), (570, 560)]),
        P([(110, 560), (110, 330), (300, 196), (490, 330), (490, 560)]),
        P([(262, 228), (262, 140), (300, 100), (338, 140), (338, 228)]),
        P([(300, 100), (300, 36)]), P([(276, 60), (324, 60)]),
        P(porta),
        P(arco(300, 300, 30, -90, 270, 36)),
        P([(160, 520), (160, 430)] + arco(185, 430, 25, 180, 360)[1:] + [(210, 520), (160, 520)]),
        P([(390, 520), (390, 430)] + arco(415, 430, 25, 180, 360)[1:] + [(440, 520), (390, 520)]),
    ]
    big = Image.new("RGBA", (tam * k, tam * k), (0, 0, 0, 0))
    dr = ImageDraw.Draw(big)
    if p > 0.85:
        a = int(200 * lim((p - 0.85) / 0.15))
        dr.polygon(P(porta), fill=rgba(VERDE, a))
    caminho_parcial(dr, caminhos, lim(p / 0.9), rgba(cor), int(10 * k * tam / 600))
    return big.resize((tam, tam), Image.LANCZOS)


def farol(t, tam=560):
    """Farol com a luz girando. t em segundos (pro giro)."""
    k = 2
    w, h = tam * k, int(tam * 1.5) * k
    s = w / 500
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    dr = ImageDraw.Draw(im)
    cx, ly = 250 * s, 250 * s
    # luz girando (dois fachos)
    ang = (t * 140) % 360
    for d in (0, 180):
        a = math.radians(ang + d)
        larg = abs(math.cos(a))
        comp = 520 * s
        abertura = 16 + 10 * larg
        dirx = 1 if math.cos(a) >= 0 else -1
        p1 = (cx + dirx * comp * (0.35 + 0.65 * larg), ly - abertura * s * 2.2)
        p2 = (cx + dirx * comp * (0.35 + 0.65 * larg), ly + abertura * s * 2.2)
        facho = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        ImageDraw.Draw(facho).polygon([(cx, ly - 6 * s), p1, p2, (cx, ly + 6 * s)],
                                      fill=(255, 246, 200, int(70 + 80 * larg)))
        facho = facho.filter(ImageFilter.GaussianBlur(10 * s))
        im.alpha_composite(facho)
    # torre listrada (trapézio)
    base_y, topo_y = 690 * s, 300 * s
    def x_em(y, lado):
        f = (y - topo_y) / (base_y - topo_y)
        meia = (45 + (80 - 45) * f) * s
        return cx + lado * meia
    faixas = 6
    for i in range(faixas):
        y0 = topo_y + (base_y - topo_y) * i / faixas
        y1 = topo_y + (base_y - topo_y) * (i + 1) / faixas
        cor = BRANCO if i % 2 == 0 else ROXO_VIVO
        dr.polygon([(x_em(y0, -1), y0), (x_em(y0, 1), y0), (x_em(y1, 1), y1), (x_em(y1, -1), y1)], fill=rgba(cor))
    # janelinha e porta
    dr.rounded_rectangle([cx - 14 * s, 430 * s, cx + 14 * s, 470 * s], 8 * s, fill=rgba(ROXO_ESC))
    dr.rounded_rectangle([cx - 22 * s, 630 * s, cx + 22 * s, base_y], 10 * s, fill=rgba(ROXO_ESC))
    # varanda, sala da luz e telhado
    dr.rounded_rectangle([cx - 66 * s, 286 * s, cx + 66 * s, 304 * s], 6 * s, fill=rgba(ROXO_ESC))
    pulso = 0.75 + 0.25 * math.sin(t * 9)
    dr.rounded_rectangle([cx - 38 * s, 214 * s, cx + 38 * s, 288 * s], 10 * s,
                         fill=(255, 238, 170, 255), outline=rgba(ROXO_ESC), width=int(8 * s))
    brilho_luz = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(brilho_luz).ellipse([cx - 70 * s, ly - 70 * s, cx + 70 * s, ly + 70 * s],
                                       fill=(255, 240, 180, int(150 * pulso)))
    im.alpha_composite(brilho_luz.filter(ImageFilter.GaussianBlur(26 * s)))
    dr = ImageDraw.Draw(im)
    dr.polygon([(cx - 52 * s, 218 * s), (cx + 52 * s, 218 * s), (cx, 150 * s)], fill=rgba(ROXO_VIVO))
    dr.ellipse([cx - 10 * s, 136 * s, cx + 10 * s, 156 * s], fill=rgba(VERDE))
    # pedra e ondas
    dr.rounded_rectangle([cx - 150 * s, base_y - 4 * s, cx + 150 * s, base_y + 40 * s], 20 * s, fill=rgba(ROXO_ESC))
    for j, yy in enumerate((base_y + 70 * s, base_y + 110 * s)):
        pts = [(x * s, yy + 10 * s * math.sin(x / 26 + t * 4 + j * 1.7)) for x in range(20, 481, 6)]
        dr.line(pts, fill=(255, 255, 255, 170 - 50 * j), width=int(7 * s), joint="curve")
    return im.resize((w // k, h // k), Image.LANCZOS)


def carimbo(txt, cor=VERDE, tam=118, giro=-8):
    f = fonte("anton", tam)
    t = recortar(palavra(txt, f, rgba(cor)))
    W_, H_ = t.width + 100, t.height + 70
    im = Image.new("RGBA", (W_, H_), (0, 0, 0, 0))
    dr = ImageDraw.Draw(im)
    dr.rounded_rectangle([6, 6, W_ - 7, H_ - 7], 22, outline=rgba(cor), width=12)
    dr.rounded_rectangle([22, 22, W_ - 23, H_ - 23], 14, outline=rgba(cor, 150), width=3)
    im.alpha_composite(t, ((W_ - t.width) // 2, (H_ - t.height) // 2))
    # textura de tinta: alguns furinhos
    r = np.random.default_rng(len(txt))
    a = np.asarray(im.getchannel("A")).astype(np.float32)
    ruido = r.random(a.shape)
    a[ruido < 0.03] *= 0.35
    m = Image.fromarray(a.astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.8))
    im.putalpha(m)
    fundo = Image.new("RGBA", im.size, (255, 255, 255, 0))
    fundo.alpha_composite(im)
    return sombra(fundo.rotate(-giro, expand=True, resample=Image.BICUBIC), 10, (0, 6), 90)


def balao(linhas, f, fundo=BRANCO, cor=ESCURO, cauda="esq", larg_min=0):
    ts = [recortar(palavra(l, f, cor)) for l in linhas]
    lh = max(t.height for t in ts)
    w = max(max(t.width for t in ts) + 90, larg_min)
    h = lh * len(ts) + 22 * (len(ts) - 1) + 70
    im = Image.new("RGBA", (w, h + 40), (0, 0, 0, 0))
    dr = ImageDraw.Draw(im)
    dr.rounded_rectangle([0, 0, w - 1, h - 1], 42, fill=rgba(fundo))
    if cauda == "esq":
        dr.polygon([(70, h - 4), (140, h - 4), (60, h + 36)], fill=rgba(fundo))
    else:
        dr.polygon([(w - 140, h - 4), (w - 70, h - 4), (w - 60, h + 36)], fill=rgba(fundo))
    y = 35
    for t in ts:
        im.alpha_composite(t, ((w - t.width) // 2, y + (lh - t.height) // 2))
        y += lh + 22
    return sombra(im, 16, (0, 10), 110)


def icone_camera(tam, cor=BRANCO):
    def d(dr, k):
        s = tam * k
        lw = max(2, int(s / 11))
        dr.rounded_rectangle([lw / 2, lw / 2, s - lw / 2, s - lw / 2], s * 0.28, outline=rgba(cor), width=lw)
        r = s * 0.22
        dr.ellipse([s / 2 - r, s / 2 - r, s / 2 + r, s / 2 + r], outline=rgba(cor), width=lw)
        q = s * 0.06
        dr.ellipse([s * 0.74 - q, s * 0.26 - q, s * 0.74 + q, s * 0.26 + q], fill=rgba(cor))
    return _aa(d, tam, tam)


@lru_cache(maxsize=4)
def logo(larg):
    im = Image.open(PASTA / "assets" / "logo_nina.png").convert("RGBA")
    return im.resize((larg, int(im.height * larg / im.width)), Image.LANCZOS)


def polaroid(foto, larg, alt_foto=None, borda=24, base=96, legenda=None, f_legenda=None):
    """Foto com moldura branca de polaroide. alt_foto: recorta a foto nessa altura."""
    fw = larg - 2 * borda
    fh = alt_foto or int(foto.height * fw / foto.width)
    e = max(fw / foto.width, fh / foto.height)
    f2 = foto.resize((int(foto.width * e + 0.5), int(foto.height * e + 0.5)), Image.LANCZOS)
    x0, y0 = (f2.width - fw) // 2, (f2.height - fh) // 2
    f2 = f2.crop((x0, y0, x0 + fw, y0 + fh))
    card = Image.new("RGBA", (larg, fh + borda + base), rgba(CREME))
    card.paste(f2.convert("RGB"), (borda, borda))
    if legenda:
        f_legenda = f_legenda or fonte("caveat", 64, 700)
        t = recortar(palavra(legenda, f_legenda, ROXO))
        card.alpha_composite(t, ((larg - t.width) // 2, fh + borda + (base - t.height) // 2))
    return sombra(card, 18, (0, 14), 130)


def cartao_nome(nome, inicial, larg=400, giro=0, foto=None):
    """Cartão de 'polaroide' com a inicial (ou a foto, quando ela mandar)."""
    borda, base = 24, 110
    fw = larg - 2 * borda
    card = Image.new("RGBA", (larg, fw + borda + base), rgba(CREME))
    if foto is not None:
        e = max(fw / foto.width, fw / foto.height)
        f2 = foto.resize((int(foto.width * e + 0.5), int(foto.height * e + 0.5)), Image.LANCZOS)
        x0, y0 = (f2.width - fw) // 2, (f2.height - fw) // 2
        card.paste(f2.crop((x0, y0, x0 + fw, y0 + fw)).convert("RGB"), (borda, borda))
    else:
        g = Image.new("RGBA", (fw, fw))
        a = np.linspace(0, 1, fw)[:, None]
        arr = np.zeros((fw, fw, 4), np.uint8)
        for c in range(3):
            arr[..., c] = (ROXO_VIVO[c] * (1 - a) + ROXO[c] * a).astype(np.uint8)
        arr[..., 3] = 255
        g = Image.fromarray(arr, "RGBA")
        letra = recortar(palavra(inicial, fonte("caveat", int(fw * 0.78), 700), BRANCO))
        g.alpha_composite(letra, ((fw - letra.width) // 2, (fw - letra.height) // 2 - 6))
        fl = folha(70, VERDE).rotate(35, expand=True, resample=Image.BICUBIC)
        g.alpha_composite(fl, (fw - fl.width - 26, 22))
        card.alpha_composite(g, (borda, borda))
    t = recortar(palavra(nome, fonte("caveat", 92, 700), ROXO))
    card.alpha_composite(t, ((larg - t.width) // 2, fw + borda + (base - t.height) // 2 - 4))
    out = sombra(card, 18, (0, 14), 130)
    return out.rotate(giro, expand=True, resample=Image.BICUBIC) if giro else out


def cartao_perfil(seguindo=False, larg=860):
    """Cartão genérico de perfil (sem marca de rede social) com o botão Seguir."""
    h = 300
    im = Image.new("RGBA", (larg, h), (0, 0, 0, 0))
    dr = ImageDraw.Draw(im)
    dr.rounded_rectangle([0, 0, larg - 1, h - 1], 44, fill=rgba(BRANCO))
    # avatar
    av = 190
    cx, cy = 40 + av // 2, h // 2
    dr.ellipse([cx - av // 2 - 7, cy - av // 2 - 7, cx + av // 2 + 7, cy + av // 2 + 7], fill=rgba(VERDE))
    dr.ellipse([cx - av // 2, cy - av // 2, cx + av // 2, cy + av // 2], fill=rgba(ROXO))
    lg = logo(150)
    im.alpha_composite(lg, (cx - lg.width // 2, cy - lg.height // 2))
    # textos
    x = 40 + av + 40
    t1 = recortar(palavra("@ninafitfood", fonte("montserrat", 54, 800), ESCURO))
    t2 = recortar(palavra("Nina Fit Food", fonte("montserrat", 36, 500), (120, 110, 120)))
    im.alpha_composite(t1, (x, 52))
    im.alpha_composite(t2, (x, 52 + t1.height + 14))
    # botão
    bw, bh = larg - x - 40, 78
    by = h - bh - 40
    if seguindo:
        dr.rounded_rectangle([x, by, x + bw, by + bh], 20, fill=(236, 230, 238, 255))
        t_ = recortar(palavra("Seguindo", fonte("montserrat", 38, 800), ESCURO))
        tb = Image.new("RGBA", (t_.width + 52, max(t_.height, 34)), (0, 0, 0, 0))
        tb.alpha_composite(t_, (0, (tb.height - t_.height) // 2))
        cy_ = tb.height / 2
        ImageDraw.Draw(tb).line([(t_.width + 16, cy_), (t_.width + 27, cy_ + 11), (t_.width + 46, cy_ - 12)],
                                fill=rgba(ROXO_VIVO), width=7, joint="curve")
    else:
        dr.rounded_rectangle([x, by, x + bw, by + bh], 20, fill=rgba(ROXO_VIVO))
        tb = recortar(palavra("Seguir", fonte("montserrat", 38, 800), BRANCO))
    im.alpha_composite(tb, (x + (bw - tb.width) // 2, by + (bh - tb.height) // 2))
    return sombra(im, 22, (0, 14), 130), (x + bw // 2, by + bh // 2)


@lru_cache(maxsize=2)
def fundo_roxo():
    """Fundo da história: roxo profundo com luz no alto e cantos escuros."""
    y, x = np.mgrid[0:H, 0:W].astype(np.float32)
    d = np.sqrt(((x - W / 2) / W) ** 2 + ((y - H * 0.38) / (H * 0.75)) ** 2)
    f = np.clip(d / 0.75, 0, 1) ** 1.3
    arr = np.zeros((H, W, 3), np.float32)
    for c in range(3):
        arr[..., c] = ROXO_VIVO[c] * (1 - f) + ROXO_ESC[c] * f
    return Image.fromarray(arr.clip(0, 255).astype(np.uint8), "RGB").convert("RGBA")


class Particulas:
    """Folhinhas e bolinhas de luz flutuando (determinístico por semente)."""

    def __init__(self, n_folhas=7, n_luzes=9, semente=3):
        r = np.random.default_rng(semente)
        self.folhas = [dict(x=r.uniform(60, W - 60), y=r.uniform(-200, H), tam=int(r.uniform(46, 96)),
                            v=r.uniform(30, 70), giro0=r.uniform(0, 360), vg=r.uniform(-40, 40),
                            fase=r.uniform(0, 6.28), alfa=int(r.uniform(90, 170))) for _ in range(n_folhas)]
        self.luzes = [dict(x=r.uniform(0, W), y=r.uniform(0, H), r=r.uniform(40, 120), v=r.uniform(8, 25),
                           fase=r.uniform(0, 6.28), cor=[LILAS, VERDE_CLARO, BRANCO][i % 3])
                      for i in range(n_luzes)]
        self._luz_img = {}

    def desenhar(self, tela, t):
        for l in self.luzes:
            rr = int(l["r"])
            if rr not in self._luz_img:
                im = Image.new("RGBA", (rr * 4, rr * 4), (0, 0, 0, 0))
                ImageDraw.Draw(im).ellipse([rr, rr, rr * 3, rr * 3], fill=(255, 255, 255, 255))
                self._luz_img[rr] = im.filter(ImageFilter.GaussianBlur(rr / 2.2))
            im = self._luz_img[rr]
            a = 0.10 + 0.06 * math.sin(t * 0.9 + l["fase"])
            cor = Image.new("RGBA", im.size, rgba(l["cor"]))
            cor.putalpha(im.getchannel("A").point(lambda v: int(v * a)))
            y = (l["y"] - l["v"] * t) % (H + 300) - 150
            colar(tela, cor, l["x"] + 30 * math.sin(t * 0.5 + l["fase"]), y)
        for f in self.folhas:
            y = (f["y"] + f["v"] * t) % (H + 300) - 150
            x = f["x"] + 40 * math.sin(t * 0.8 + f["fase"])
            colar(tela, folha(f["tam"], VERDE, f["alfa"]), x, y, giro=f["giro0"] + f["vg"] * t)
