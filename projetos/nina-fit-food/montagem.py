"""Vídeo da Nina Fit Food: abertura falada, história com fotos, reações e chamada pro Instagram.

Uso: python montagem.py [--ate SEG] [--de SEG] [--rapido] [--saida arquivo.mp4]
"""
import argparse
import json
import math
import subprocess
import wave

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import musica
from marca import (BRANCO, ESCURO, FPS, H, LILAS, PASTA, PRETO, ROXO, ROXO_CAIXA, ROXO_ESC, ROXO_VIVO,
                   VERDE, VERDE_CLARO, W, Particulas, balao, brilho, carimbo, cartao_nome, cartao_perfil,
                   colar, coracao, ease_back, ease_in, ease_in_out, ease_out, emoji, folha, fonte, fundo_roxo,
                   icone_camera, igreja, farol, lim, logo, mola, palavra, pilula, polaroid, recortar, rgba, sombra)

HD = PASTA / "hd"
FOTOS = PASTA / "fotos" / "recortes"
LOJA = "7649936307915692184"
SR = 48000


def hd(nome):
    return str(HD / f"{nome}.mov")


# =====================================================================
# Linha do tempo (tempos de saída em segundos)
# =====================================================================

ANCORA = 10.22          # início da história = tempo forte da música
FIM_CTA = 68.22         # cartão final começa aqui (acorde final)
DURACAO = 70.72


class Video:
    """Trecho de vídeo: fonte, ponto de entrada, duração e movimento de câmera."""

    def __init__(self, nome, ini, dur, zoom=(1.0, 1.0), foco=(540, 760), congelar=None, socos=(),
                 tremer=(), rapido=None):
        self.arq, self.ini, self.dur = hd(nome), ini, dur
        self.zoom, self.foco, self.congelar = zoom, foco, congelar
        self.socos, self.tremer = socos, tremer
        self.leitor = None

    def abrir(self):
        dur_fonte = self.dur if self.congelar is None else min(self.dur, self.congelar + 0.1)
        self.leitor = Leitor(self.arq, self.ini, dur_fonte)

    def fechar(self):
        if self.leitor:
            self.leitor.fechar()
            self.leitor = None

    def quadro(self, tl):
        if self.leitor is None:
            self.abrir()
        tq = tl if self.congelar is None else min(tl, self.congelar)
        img = self.leitor.quadro(int(round(tq * FPS)))
        z = self.zoom[0] + (self.zoom[1] - self.zoom[0]) * ease_in_out(tl / self.dur)
        for ts in self.socos:
            d = tl - ts
            if d >= 0:
                z += 0.07 * min(1.0, d / 0.07) * math.exp(-max(0.0, d - 0.07) * 3.0)
        dx = dy = 0.0
        for ts, amp in self.tremer:
            d = tl - ts
            if 0 <= d < 0.35:
                k = amp * (1 - d / 0.35)
                dx += k * math.sin(d * 97)
                dy += k * math.cos(d * 83)
        if abs(z - 1) > 0.002 or dx or dy:
            cx, cy = self.foco
            cw, ch = W / z, H / z
            x0 = min(max(cx - cw / 2 + dx, 0), W - cw)
            y0 = min(max(cy - ch / 2 + dy, 0), H - ch)
            img = img.resize((W, H), Image.BILINEAR, box=(x0, y0, x0 + cw, y0 + ch))
        return img.convert("RGBA")


class Leitor:
    def __init__(self, arq, ini, dur):
        self.p = subprocess.Popen(["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", f"{ini:.3f}", "-i", arq,
                                   "-t", f"{dur + 0.25:.3f}", "-an", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                                  stdout=subprocess.PIPE, bufsize=W * H * 3 * 2)
        self.n, self.ultimo = -1, None

    def quadro(self, i):
        while self.n < i:
            b = self.p.stdout.read(W * H * 3)
            if len(b) < W * H * 3:
                break
            self.ultimo, self.n = b, self.n + 1
        return Image.frombuffer("RGB", (W, H), self.ultimo, "raw", "RGB", 0, 1)

    def fechar(self):
        self.p.stdout.close()
        self.p.kill()
        self.p.wait()


class Cena:
    """Trecho desenhado (história, cartão final): desenhar(tl) -> imagem RGBA."""

    def __init__(self, desenhar, dur, base=None):
        self.desenhar, self.dur, self.base = desenhar, dur, base

    def abrir(self):
        if self.base:
            self.base.abrir()

    def fechar(self):
        if self.base:
            self.base.fechar()

    def quadro(self, tl):
        return self.desenhar(tl, self.base.quadro(tl) if self.base else None)


# =====================================================================
# Texto animado palavra por palavra
# =====================================================================

class Texto:
    """Linhas de texto que entram palavra por palavra. linhas = [(texto, fonte, cor, contorno), ...]"""

    def __init__(self, linhas, cy, espaco=22, sombra_alfa=140, folga=0.28):
        blocos = []
        for txt, f, cor, contorno in linhas:
            ps = []
            for p_txt in txt.split():
                im = palavra(p_txt, f, cor, contorno, ESCURO)
                cx0, cy0, cx1, cy1 = im.getchannel("A").getbbox() or (0, 0, im.width, im.height)
                ps.append((im.crop((cx0, 0, cx1, im.height)), cy0, cy1))
            topo = min(p[1] for p in ps)
            base = max(p[2] for p in ps)
            larg = sum(p[0].width for p in ps) + espaco * (len(ps) - 1)
            blocos.append((ps, larg, topo, base, f.size * folga))
        total = sum(b[3] - b[2] for b in blocos) + sum(b[4] for b in blocos[:-1])
        y = cy - total / 2
        self.itens = []
        k = 0
        for ps, larg, topo, base, gap in blocos:
            x = (W - larg) / 2
            for im, _, _ in ps:
                img = sombra(im, 10, (0, 6), sombra_alfa) if sombra_alfa else im
                self.itens.append((img, x + im.width / 2, y - topo + im.height / 2, k))
                x += im.width + espaco
                k += 1
            y += (base - topo) + gap
        self.n = k

    def desenhar(self, tela, tl, t_in=0.0, t_out=None, passo=0.07, dur=0.38, sobe=46):
        for im, cx, cy, k in self.itens:
            p = (tl - t_in - k * passo) / dur
            if p <= 0:
                continue
            a = ease_out(p * 1.4)
            dy = sobe * (1 - ease_out(p))
            e = 0.86 + 0.14 * ease_back(p)
            if t_out is not None and tl > t_out:
                q = ease_in((tl - t_out) / 0.22)
                a *= 1 - q
                dy -= 40 * q
            colar(tela, im, cx, cy + dy, e, a)


_FAIXAS = {}


def faixa_escura(tela, y0, y1, alfa=150, cor=ROXO_ESC):
    """Faixa em degradê atrás de texto em cima de vídeo."""
    chave = (int(y0), int(y1), alfa, cor)
    if chave in _FAIXAS:
        tela.alpha_composite(_FAIXAS[chave], (0, int(y0)))
        return
    h = int(y1 - y0)
    a = np.zeros((h, 1), np.float32)
    m = h * 0.25
    for i in range(h):
        a[i] = alfa * min(1.0, i / m, (h - 1 - i) / m)
    camada = np.zeros((h, W, 4), np.uint8)
    camada[..., :3] = cor
    camada[..., 3] = a.astype(np.uint8)
    _FAIXAS[chave] = Image.fromarray(camada, "RGBA")
    tela.alpha_composite(_FAIXAS[chave], (0, int(y0)))


# =====================================================================
# Fotos
# =====================================================================

def foto(nome):
    return Image.open(FOTOS / nome).convert("RGB")


def recorte_proporcao(im, prop):
    """Recorta no centro pra proporção largura/altura = prop."""
    if im.width / im.height > prop:
        w = int(im.height * prop)
        x0 = (im.width - w) // 2
        return im.crop((x0, 0, x0 + w, im.height))
    h = int(im.width / prop)
    y0 = (im.height - h) // 2
    return im.crop((0, y0, im.width, y0 + h))


# =====================================================================
# Cenas da história (cada uma recebe tl = tempo local)
# =====================================================================

PART = Particulas()
F_TXT = fonte("montserrat", 64, 800)
F_TXT2 = fonte("montserrat", 58, 800)
F_GRANDE = fonte("anton", 150)
F_SCRIPT = fonte("caveat", 128, 700)
F_SCRIPT_M = fonte("caveat", 104, 700)


def base_roxa(t_abs):
    tela = fundo_roxo().copy()
    PART.desenhar(tela, t_abs)
    return tela


def cena_pib(t0):
    t1 = Texto([("Somos membros da", F_TXT, BRANCO, 0)], 420)
    t2 = Texto([("PIB GUARAPARI", F_GRANDE, BRANCO, 0)], 1340, espaco=34)
    foto_pib = FOTOS / "pib.jpg"
    pol = polaroid(foto("pib.jpg"), 760, 560) if foto_pib.exists() else None

    def desenhar(tl, _):
        tela = base_roxa(t0 + tl)
        if pol is not None:
            p = ease_back(tl / 0.5)
            colar(tela, pol, 540, 880, 0.8 + 0.2 * p, lim(tl / 0.25), giro=-3 * p)
        else:
            colar(tela, igreja(ease_in_out((tl - 0.05) / 1.5), 600), 540, 860)
        t1.desenhar(tela, tl, 0.15)
        t2.desenhar(tela, tl, 0.55, passo=0.12)
        if tl > 1.0:
            p = ease_out((tl - 1.0) / 0.4)
            dr = ImageDraw.Draw(tela)
            dr.rounded_rectangle([540 - 330 * p, 1440, 540 + 330 * p, 1452], 6, fill=rgba(VERDE))
        return tela
    return desenhar


def cena_grupo(t0):
    t1 = Texto([("Por ser uma igreja grande,", F_TXT2, BRANCO, 0),
                ("nos unimos em um", F_TXT2, BRANCO, 0)], 720)
    t2 = Texto([("pequeno grupo", F_SCRIPT, VERDE_CLARO, 0)], 960)
    ig = igreja(1.0, 300)

    def desenhar(tl, _):
        tela = base_roxa(t0 + tl)
        colar(tela, ig, 540, 380, 0.9 + 0.1 * ease_out(tl / 0.5), 0.55 * lim(tl / 0.3))
        t1.desenhar(tela, tl, 0.05, passo=0.06)
        t2.desenhar(tela, tl, 0.85, passo=0.15)
        # pontinhos que se juntam: o grupo se formando
        r = np.random.default_rng(5)
        p = ease_in_out((tl - 0.9) / 1.2)
        for i in range(14):
            ang = 2 * math.pi * i / 14
            x0, y0 = 540 + r.uniform(-420, 420), 1330 + r.uniform(-170, 170)
            x1, y1 = 540 + 120 * math.cos(ang), 1330 + 60 * math.sin(ang)
            x, y = x0 + (x1 - x0) * p, y0 + (y1 - y0) * p
            c = [LILAS, VERDE_CLARO, BRANCO][i % 3]
            colar(tela, coracao(46, c), x, y, 1.0, lim((tl - 0.6) / 0.3) * 0.95)
        return tela
    return desenhar


def cena_farol(t0):
    t1 = Texto([("que chamamos de", F_TXT, BRANCO, 0)], 330)
    t2 = Texto([("FAROL", fonte("anton", 200), BRANCO, 0)], 1440, espaco=30)

    def desenhar(tl, _):
        tela = base_roxa(t0 + tl)
        p = ease_back(tl / 0.55)
        colar(tela, farol(tl + 0.8, 560), 540, 860 + 120 * (1 - ease_out(tl / 0.5)), 0.85 + 0.15 * p,
              lim(tl / 0.25))
        t1.desenhar(tela, tl, 0.0)
        t2.desenhar(tela, tl, 0.45, passo=0.08)
        return tela
    return desenhar


def cena_fotos_farol(t0):
    specs = [  # (arquivo, proporção, largura, x, y, giro)
        ("04_farol_ano_novo.jpg", 4 / 3, 640, 330, 640, -7),
        ("05_farol_sofa_limpa.jpg", 16 / 9, 680, 690, 860, 6),
        ("06_farol_selfie.jpg", 16 / 10, 680, 360, 1120, 4),
        ("07_farol_19set.jpg", 4 / 3, 620, 715, 1320, -5),
        ("08_farol_restaurante.jpg", 3 / 4, 470, 560, 1010, -2),
    ]
    pols = []
    for arq, prop, larg, x, y, g in specs:
        im = recorte_proporcao(foto(arq), prop)
        pols.append((polaroid(im, larg, int((larg - 48) / prop), base=70), x, y, g))
    titulo = Texto([("Nossos encontros", F_SCRIPT_M, BRANCO, 0)], 300)

    def desenhar(tl, _):
        tela = base_roxa(t0 + tl)
        titulo.desenhar(tela, tl, 0.0, passo=0.1)
        for k, (pol, x, y, g) in enumerate(pols):
            tk = tl - 0.12 - 0.36 * k
            if tk <= 0:
                continue
            p = ease_out(tk / 0.32)
            e = 1.35 - 0.35 * p
            colar(tela, pol, x, y - 60 * (1 - p), e, lim(tk / 0.12), giro=g + 10 * (1 - p))
        return tela
    return desenhar


def cena_casal_chegou(t0):
    t1 = Texto([("Ano passado,", F_SCRIPT, VERDE_CLARO, 0)], 470)
    t2 = Texto([("um casal chegou", F_TXT, BRANCO, 0), ("pra fazer parte do", F_TXT, BRANCO, 0),
                ("nosso grupo", F_TXT, BRANCO, 0)], 760)

    def desenhar(tl, _):
        tela = base_roxa(t0 + tl)
        t1.desenhar(tela, tl, 0.0, passo=0.1)
        t2.desenhar(tela, tl, 0.35, passo=0.06)
        p = ease_in_out((tl - 0.5) / 1.0)
        enc = tl > 1.5
        for lado, cor in ((-1, LILAS), (1, VERDE_CLARO)):
            x = 540 + lado * (520 - 440 * p) + (0 if not enc else lado * 0)
            y = 1290 - 40 * math.sin(p * math.pi)
            e = 1.0 + (0.12 * math.sin((tl - 1.5) * 10) * math.exp(-(tl - 1.5) * 4) if enc else 0)
            colar(tela, coracao(150, cor), x, y, e, lim((tl - 0.4) / 0.2), giro=-lado * 12 * (1 - p))
        if enc:
            for i in range(6):
                a = 2 * math.pi * i / 6
                d = 60 + 160 * ease_out((tl - 1.5) / 0.5)
                colar(tela, brilho(54), 540 + d * math.cos(a), 1290 + d * math.sin(a), 1.0,
                      lim(1 - (tl - 1.7) / 0.5))
        return tela
    return desenhar


def cena_danilo_nina(t0):
    f_d = FOTOS / "danilo.jpg"
    f_n = FOTOS / "nina.jpg"
    c_d = cartao_nome("Danilo", "D", 410, giro=6, foto=foto("danilo.jpg") if f_d.exists() else None)
    c_n = cartao_nome("Nina", "N", 410, giro=-6, foto=foto("nina.jpg") if f_n.exists() else None)
    t1 = Texto([("Ele se chama", F_TXT2, BRANCO, 0)], 330)
    t2 = Texto([("e ela,", F_TXT2, BRANCO, 0)], 1500)

    def desenhar(tl, _):
        tela = base_roxa(t0 + tl)
        t1.desenhar(tela, tl, 0.0)
        p = ease_out((tl - 0.1) / 0.45)
        colar(tela, c_d, 300 - 500 * (1 - p), 880, 1.0, lim((tl - 0.1) / 0.15))
        t2.desenhar(tela, tl, 0.75)
        p2 = ease_out((tl - 0.95) / 0.45)
        colar(tela, c_n, 780 + 500 * (1 - p2), 1010, 1.0, lim((tl - 0.95) / 0.15))
        if tl > 1.5:
            q = tl - 1.5
            colar(tela, coracao(130, ROXO_VIVO), 545, 930, 0.3 + 0.7 * ease_back(q / 0.35), lim(q / 0.1))
            colar(tela, coracao(96, LILAS), 545, 930, 0.3 + 0.7 * ease_back(q / 0.35), lim(q / 0.1))
        return tela
    return desenhar


def cena_logo(t0):
    t1 = Texto([("E juntos, eles têm a", F_TXT, BRANCO, 0)], 560)
    lg = logo(780)
    lg_s = sombra(lg, 24, (0, 14), 120)
    mascara = lg.getchannel("A")

    def desenhar(tl, _):
        tela = base_roxa(t0 + tl)
        t1.desenhar(tela, tl, 0.0)
        q = tl - 0.5
        if q > 0:
            e = 0.55 + 0.45 * ease_back(q / 0.5, 2.2)
            img = lg_s
            if 0.45 < q < 1.15:      # brilho passando pelo logo
                s = (q - 0.45) / 0.7
                faixa = Image.new("L", lg.size, 0)
                x = int(-300 + (lg.width + 600) * s)
                ImageDraw.Draw(faixa).polygon([(x, 0), (x + 120, 0), (x - 80, lg.height), (x - 200, lg.height)],
                                              fill=170)
                faixa = faixa.filter(ImageFilter.GaussianBlur(30))
                from PIL import ImageChops
                faixa = ImageChops.multiply(faixa, mascara)
                bril = Image.new("RGBA", lg.size, (255, 255, 255, 0))
                bril.putalpha(faixa)
                img = lg_s.copy()
                m = (img.width - lg.width) // 2
                img.alpha_composite(bril, (m, (img.height - lg.height) // 2))
            colar(tela, img, 540, 1050, e, lim(q / 0.12))
            for i in range(7):
                a = 2 * math.pi * i / 7 + 0.4
                d = 330 + 70 * ease_out((q - 0.2) / 0.6)
                al = lim((q - 0.25) / 0.15) * lim(1 - (q - 1.0) / 0.4)
                colar(tela, brilho(46 + 16 * (i % 2)), 540 + d * math.cos(a), 1050 + 0.75 * d * math.sin(a),
                      0.7 + 0.3 * math.sin(q * 12 + i), al)
        return tela
    return desenhar


def cena_loja(t0, selo=False):
    pil = pilula("@ninafitfood", fonte("montserrat", 50, 800), icone=icone_camera(54))

    def desenhar(tl, quadro):
        tela = quadro
        q = tl - 0.12
        if selo and q > 0:
            colar(tela, pil, 540, 1430 + 40 * (1 - ease_out(q / 0.35)), 0.9 + 0.1 * ease_back(q / 0.35),
                  lim(q / 0.15))
        return tela
    return desenhar


def cena_lanchinho(t0):
    t1 = Texto([("No Farol, sempre", F_TXT, BRANCO, 0), ("levamos um", F_TXT, BRANCO, 0)], 330)
    t2 = Texto([("lanchinho", F_SCRIPT, VERDE_CLARO, 0)], 520)

    def desenhar(tl, quadro):
        tela = quadro
        faixa_escura(tela, 180, 660, 170)
        t1.desenhar(tela, tl, 0.0)
        t2.desenhar(tela, tl, 0.45, passo=0.1)
        return tela
    return desenhar


def cena_todos_nos(t0):
    im = recorte_proporcao(foto("04_farol_ano_novo.jpg"), 4 / 3)
    pol = polaroid(im, 900, int(852 * 3 / 4), base=80)
    t1 = Texto([("E todos nós...", F_SCRIPT, BRANCO, 0)], 420)

    def desenhar(tl, _):
        tela = base_roxa(t0 + tl)
        t1.desenhar(tela, tl, 0.0, passo=0.12)
        p = ease_out(tl / 0.35)
        colar(tela, pol, 540, 1020 + 80 * (1 - p), 1.15 - 0.15 * p + 0.03 * tl, lim(tl / 0.12),
              giro=-3 + 6 * (1 - p))
        return tela
    return desenhar


def cena_guarapari(t0):
    im = Image.open(PASTA / "fotos" / "03_guarapari.jpg").convert("RGB")
    e = H / im.height * 1.08
    grande = im.resize((int(im.width * e), int(im.height * e)), Image.LANCZOS)
    t1 = Texto([("e a cidade de", F_TXT, BRANCO, 0)], 330)
    t2 = Texto([("Guarapari", F_SCRIPT, VERDE_CLARO, 0)], 490)

    def desenhar(tl, _):
        p = ease_in_out(tl / 1.5)
        x0 = int((grande.width - W) * (0.62 - 0.22 * p))
        y0 = int((grande.height - H) * 0.5)
        tela = grande.crop((x0, y0, x0 + W, y0 + H)).convert("RGBA")
        faixa_escura(tela, 170, 640, 150)
        t1.desenhar(tela, tl, 0.0)
        t2.desenhar(tela, tl, 0.3, passo=0.1)
        return tela
    return desenhar


class Coracoes:
    """Corações subindo (determinístico)."""

    def __init__(self, n, t_ini, t_fim, area=(140, 940, 1300, 1700), semente=1, tam=(50, 110)):
        r = np.random.default_rng(semente)
        cores = [ROXO_VIVO, LILAS, VERDE_CLARO, BRANCO, (230, 120, 190)]
        self.cs = [dict(t=r.uniform(t_ini, t_fim), x=r.uniform(area[0], area[1]), y=r.uniform(area[2], area[3]),
                        tam=int(r.uniform(*tam)), v=r.uniform(260, 420), fase=r.uniform(0, 6.3),
                        cor=cores[i % len(cores)]) for i in range(n)]

    def desenhar(self, tela, t, vida=1.6, fim=None):
        if fim is not None and t >= fim:
            return
        sai = 1.0 if fim is None else lim((fim - t) / 0.25)
        for c in self.cs:
            d = t - c["t"]
            if 0 <= d < vida:
                y = c["y"] - c["v"] * d
                x = c["x"] + 34 * math.sin(d * 5 + c["fase"])
                e = 0.4 + 0.6 * ease_back(d / 0.3)
                a = lim(d / 0.1) * lim((vida - d) / 0.5) * sai
                colar(tela, coracao(c["tam"], c["cor"]), x, y, e, a, giro=12 * math.sin(d * 4 + c["fase"]))


def cena_apaixonados(t0):
    t1 = Texto([("nos tornamos", F_TXT, BRANCO, 0)], 290)
    t2 = Texto([("apaixonados", F_SCRIPT, VERDE_CLARO, 0)], 435)
    t3 = Texto([("pelas delícias que", F_TXT2, BRANCO, 0), ("a Nina prepara", F_TXT2, BRANCO, 0)], 640)
    cor = Coracoes(16, 0.4, 2.3, area=(150, 930, 1560, 1800), semente=4)

    def desenhar(tl, quadro):
        tela = quadro
        faixa_escura(tela, 160, 780, 165)
        t1.desenhar(tela, tl, 0.0)
        t2.desenhar(tela, tl, 0.25, passo=0.1)
        t3.desenhar(tela, tl, 0.7, passo=0.06)
        cor.desenhar(tela, tl, vida=1.25)
        return tela
    return desenhar


def cena_final(t0):
    t1 = Texto([("Só pedindo", F_TXT, BRANCO, 0)], 400)
    t2 = Texto([("lá na Nina!", F_SCRIPT, VERDE_CLARO, 0)], 540)
    lg = sombra(logo(640), 22, (0, 12), 110)
    pil = pilula("@ninafitfood", fonte("montserrat", 58, 800), icone=icone_camera(62), pad=(46, 24))
    t3 = Texto([("dicas e receitas no Instagram", fonte("montserrat", 40, 600), LILAS, 0)], 1500, sombra_alfa=0)

    def desenhar(tl, _):
        tela = base_roxa(t0 + tl)
        t1.desenhar(tela, tl, 0.0)
        t2.desenhar(tela, tl, 0.2, passo=0.1)
        p = tl - 0.3
        if p > 0:
            colar(tela, lg, 540, 930, 0.6 + 0.4 * ease_back(p / 0.45, 2.0), lim(p / 0.12))
        q = tl - 0.7
        if q > 0:
            pul = 1 + 0.035 * math.sin(max(0, q - 0.5) * 6)
            colar(tela, pil, 540, 1300 + 50 * (1 - ease_out(q / 0.35)), (0.85 + 0.15 * ease_back(q / 0.35)) * pul,
                  lim(q / 0.15))
        t3.desenhar(tela, tl, 1.0, passo=0.04)
        return tela
    return desenhar


# =====================================================================
# Legendas (fala) no estilo da marca: caixa roxa na palavra falada
# =====================================================================

F_LEG = fonte("montserrat", 62, 800)


def bloco_legenda(palavras, ativa):
    imgs = []
    for i, p in enumerate(palavras):
        if i == ativa:
            t = recortar(palavra(p, F_LEG, BRANCO))
            caixa = Image.new("RGBA", (t.width + 36, t.height + 28), (0, 0, 0, 0))
            ImageDraw.Draw(caixa).rounded_rectangle([0, 0, caixa.width - 1, caixa.height - 1], 16,
                                                    fill=rgba(ROXO_CAIXA))
            caixa.alpha_composite(t, (18, 14))
            imgs.append(caixa)
        else:
            imgs.append(recortar(palavra(p, F_LEG, BRANCO, 6, (20, 6, 20))))
    esp = 14
    linhas, atual, larg = [], [], 0
    for im in imgs:
        if atual and larg + esp + im.width > 860:
            linhas.append(atual)
            atual, larg = [], 0
        larg += (esp if atual else 0) + im.width
        atual.append(im)
    linhas.append(atual)
    lh = max(im.height for im in imgs)
    Wb = max(sum(i.width for i in l) + esp * (len(l) - 1) for l in linhas)
    Hb = lh * len(linhas) + 10 * (len(linhas) - 1)
    out = Image.new("RGBA", (Wb, Hb), (0, 0, 0, 0))
    y = 0
    for l in linhas:
        x = (Wb - (sum(i.width for i in l) + esp * (len(l) - 1))) // 2
        for im in l:
            out.alpha_composite(im, (x, y + (lh - im.height) // 2))
            x += im.width + esp
        y += lh + 10
    return sombra(out, 12, (0, 6), 120)


class Legendas:
    def __init__(self):
        self.grupos = []          # (ini, fim, [palavras], [tempos], y)
        self.cache = {}

    def adicionar(self, palavras, y=1290, maximo=3, trocas=None, limite=None):
        """palavras: [(texto, ini, fim)] em tempo de saída. limite: a legenda não passa desse tempo (corte)."""
        trocas = trocas or {}
        atual = []
        grupos = []
        for k, (w, s, e) in enumerate(palavras):
            w = trocas.get(w, w)
            if atual and (len(atual) >= maximo or s - atual[-1][2] > 0.35):
                grupos.append(atual)
                atual = []
            atual.append((w, s, e))
            if w.rstrip()[-1:] in ".,?!":
                grupos.append(atual)
                atual = []
        if atual:
            grupos.append(atual)
        for i, g in enumerate(grupos):
            prox = grupos[i + 1][0][1] if i + 1 < len(grupos) else g[-1][2] + 0.4
            fim = prox if prox - g[-1][2] < 0.6 else g[-1][2] + 0.3
            if limite is not None:
                fim = min(fim, limite)
            self.grupos.append((g[0][1], fim, [w for w, _, _ in g], [s for _, s, _ in g], y))

    def desenhar(self, tela, t, ocultar=()):
        for a, b in ocultar:
            if a <= t < b:
                return
        for ini, fim, ws, ts, y in self.grupos:
            if ini <= t < fim:
                ativa = max([i for i, s in enumerate(ts) if s <= t + 0.02] or [0])
                chave = (tuple(ws), ativa)
                if chave not in self.cache:
                    self.cache[chave] = bloco_legenda([w if w.endswith("...") else w.rstrip(",.") for w in ws], ativa)
                e = 0.9 + 0.1 * ease_back((t - ini) / 0.12)
                colar(tela, self.cache[chave], 540, y, e, lim((t - ini) / 0.05))
                return


# =====================================================================
# A montagem
# =====================================================================

CORRIGIR = {  # (fonte, início no whisper) -> (início, fim) conferidos na forma de onda
    ("IMG_6490", 17.36): (17.34, 17.48),
    ("IMG_6503", 50.50): (50.40, 50.86),
    ("IMG_6503", 53.44): (53.33, 53.60),
    ("IMG_6503", 53.98): (53.88, 54.20),
}


def palavras_de(nome, ini, fim, t0):
    """Palavras do whisper (modelo grande) dentro de [ini, fim] da fonte, em tempo de saída."""
    segs = json.load(open(PASTA / "proxy" / f"{nome}.large-v3.json"))
    out = []
    for s in segs:
        for w in s["w"]:
            c = CORRIGIR.get((nome, round(w["s"], 2)))
            if c:
                w = dict(w, s=c[0], e=c[1])
            meio = (w["s"] + w["e"]) / 2
            if ini - 0.02 <= meio <= fim + 0.02:
                out.append((w["w"].strip(), t0 + max(w["s"], ini) - ini, t0 + min(w["e"], fim) - ini))
    return out


def montar_linha():
    trechos = []          # (t0, objeto)
    audios = []           # dict(nome, ini, fim, t0, voz, ganho)
    leg = Legendas()
    t = 0.0

    def video(nome, ini, dur, audio=True, voz=False, legenda=False, y_leg=1290, trocas=None, **kw):
        nonlocal t
        v = Video(nome, ini, dur, **kw)
        trechos.append((t, v))
        if audio:
            audios.append(dict(nome=nome, ini=ini, fim=ini + dur, t0=t, voz=voz))
            if legenda:
                leg.adicionar(palavras_de(nome, ini, ini + dur, t), y_leg, trocas=trocas, limite=t + dur)
        t += dur
        return v

    def cena(fun, dur, base=None):
        nonlocal t
        trechos.append((t, Cena(fun(t), dur, base)))
        t += dur

    # ---------------- abertura ----------------
    video("IMG_6491", 5.30, 0.60, audio=False, zoom=(1.0, 1.08), foco=(540, 900))
    audios.append(dict(nome="IMG_6490", ini=0.24, fim=0.84, t0=0.0, voz=False))
    video("IMG_6490", 0.84, 2.72, voz=True, legenda=True, zoom=(1.0, 1.04), foco=(540, 700))
    video("IMG_6490", 12.44, 3.24, voz=True, legenda=True, zoom=(1.06, 1.0), foco=(540, 700))
    video("IMG_6490", 15.80, 1.70, voz=True, legenda=True, y_leg=1000, zoom=(1.0, 1.05), foco=(540, 700))
    video("IMG_6490", 18.00, 1.96, voz=True, legenda=True, y_leg=1000, zoom=(1.05, 1.0), foco=(540, 700))
    assert abs(t - ANCORA) < 0.01, t
    # ---------------- história ----------------
    cena(cena_pib, 2.5)
    cena(cena_grupo, 2.5)
    cena(cena_farol, 2.0)
    cena(cena_fotos_farol, 2.5)
    cena(cena_casal_chegou, 2.5)
    cena(cena_danilo_nina, 2.5)
    cena(cena_logo, 2.0)
    t_loja = t
    cena(cena_loja, 1.0, Video(LOJA, 1.00, 1.0, zoom=(1.0, 1.06), foco=(540, 600)))
    cena(lambda t0: cena_loja(t0, selo=True), 1.0, Video(LOJA, 38.00, 1.0, zoom=(1.04, 1.0), foco=(540, 900)))
    cena(cena_lanchinho, 2.0, Video("IMG_6499", 0.10, 2.0, zoom=(1.0, 1.06), foco=(600, 1100)))
    cena(cena_todos_nos, 1.5)
    cena(cena_guarapari, 1.5)
    cena(cena_apaixonados, 2.5, Video("IMG_6491", 6.40, 2.5, zoom=(1.0, 1.05), foco=(540, 1000)))
    t_reacts = t
    # ---------------- reações ----------------
    video("IMG_6500", 4.85, 1.25, zoom=(1.0, 1.04), foco=(540, 700))
    video("IMG_6500", 7.45, 1.25, zoom=(1.08, 1.12), foco=(560, 640))
    video("IMG_6500", 9.95, 1.00, zoom=(1.0, 1.0), foco=(540, 760), socos=(0.08,))
    video("IMG_6496", 10.62, 3.00, voz=True, legenda=True, zoom=(1.0, 1.06), foco=(540, 900))
    video("IMG_6497", 15.45, 1.00, zoom=(1.0, 1.04), foco=(540, 700), socos=(0.05,))
    video("IMG_6495", 43.30, 1.00, zoom=(1.08, 1.13), foco=(540, 760))
    video("IMG_6502", 4.80, 1.00, zoom=(1.05, 1.1), foco=(540, 760))
    video("IMG_6499", 11.60, 1.56, voz=True, legenda=True, zoom=(1.0, 1.04), foco=(560, 640))
    video("IMG_6499", 15.20, 2.44, voz=True, legenda=True, zoom=(1.06, 1.1), foco=(560, 640))
    video("IMG_6499", 24.20, 2.00, voz=True, legenda=True, zoom=(1.0, 1.05), foco=(560, 800))
    t_bolo = t
    video("IMG_6491", 1.30, 2.00, audio=False, zoom=(1.0, 1.08), foco=(540, 1000))
    audios.append(dict(nome="IMG_6499", ini=26.55, fim=28.53, t0=t_bolo, voz=True))
    t_aprov = t
    video("IMG_6494", 0.00, 3.00, voz=True, congelar=2.12, tremer=((2.05, 18),), zoom=(1.0, 1.06),
          foco=(540, 700))
    t_pecado = t
    video("IMG_6503", 24.05, 4.00, voz=True, legenda=True, y_leg=900, zoom=(1.0, 1.04), foco=(540, 700))
    # ---------------- chamada ----------------
    t_cta = t
    video("IMG_6503", 47.55, 3.33, voz=True, legenda=True, y_leg=470, zoom=(1.0, 1.05), foco=(540, 700))
    t_corte_bolo = t
    video("IMG_6495", 1.30, 1.64, audio=False, zoom=(1.0, 1.06), foco=(540, 1000))
    audios.append(dict(nome="IMG_6503", ini=51.98, fim=53.62, t0=t_corte_bolo, voz=True))
    leg.adicionar(palavras_de("IMG_6503", 51.98, 53.62, t_corte_bolo), 470, limite=t_corte_bolo + 1.64)
    video("IMG_6503", 53.84, 0.61, voz=True, legenda=True, y_leg=470, zoom=(1.06, 1.06), foco=(540, 700))
    video("IMG_6503", 55.00, 1.92, voz=True, legenda=True, y_leg=470, zoom=(1.0, 1.05), foco=(540, 700),
          trocas={"da": "da"})
    assert abs(t - FIM_CTA) < 0.02, t
    cena(cena_final, DURACAO - t)
    marcos = dict(loja=t_loja, reacts=t_reacts, bolo=t_bolo, aprov=t_aprov, pecado=t_pecado, cta=t_cta,
                  corte_bolo=t_corte_bolo)
    return trechos, audios, leg, marcos


# =====================================================================
# Camadas por cima (ganchos, animações das reações, chamada)
# =====================================================================

def camadas(marcos):
    R = marcos["reacts"]
    itens = []    # funções (tela, t) -> None

    # gancho dos primeiros segundos
    g1 = recortar(palavra("UMA PROPAGANDA", fonte("anton", 118), BRANCO, 8, ROXO_ESC))
    g2 = recortar(palavra("SEM FALAR NADA", fonte("anton", 118), VERDE_CLARO, 8, ROXO_ESC))
    g1, g2 = sombra(g1, 14, (0, 8), 150), sombra(g2, 14, (0, 8), 150)
    shh = emoji("🤫", 150)

    def gancho(tela, t):
        if t >= 3.0:
            return
        sai = lim((t - 2.75) / 0.25)
        for k, (im, y) in enumerate(((g1, 1110), (g2, 1250))):
            p = (t - 0.05 - 0.18 * k) / 0.32
            if p > 0:
                colar(tela, im, 540 + 600 * (1 - ease_out(p)) * (-1 if k == 0 else 1), y, 1.0,
                      lim(p * 2) * (1 - sai))
        q = t - 0.55
        if q > 0:
            colar(tela, shh, 540, 920, 0.4 + 0.6 * ease_back(q / 0.3), lim(q / 0.1) * (1 - sai),
                  giro=8 * math.sin(q * 6))
    itens.append(gancho)

    # "sem falar nada" (fala) -> emoji do silêncio pulando
    def silencio(tela, t):
        q = t - 5.62
        if 0 < q < 1.0:
            colar(tela, emoji("🤫", 170), 820, 560, 0.4 + 0.6 * ease_back(q / 0.25), lim(q / 0.08) * lim((1.0 - q) / 0.2),
                  giro=-10)
    itens.append(silencio)

    # prévia das reações quando ela fala "react"
    previas = []
    for nome, ts, giro, caixa in (("IMG_6500", 10.35, -8, (360, 370, 960, 1170)),
                                  ("IMG_6497", 16.0, 5, (200, 250, 800, 1050)),
                                  ("IMG_6502", 6.1, -4, (235, 255, 835, 1055))):
        fr = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", str(ts), "-i", hd(nome),
                             "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                            capture_output=True).stdout
        im = Image.frombuffer("RGB", (W, H), fr, "raw", "RGB", 0, 1)
        im = im.crop(caixa)
        previas.append((polaroid(im, 262, 312, borda=13, base=40), giro))

    def previa(tela, t):
        if not (7.5 <= t < 10.3):
            return
        for k, (pol, giro) in enumerate(previas):
            tk = t - 7.6 - 0.33 * k
            if tk <= 0:
                continue
            p = ease_back(tk / 0.35)
            sai = ease_in((t - 9.95) / 0.3)
            x = [250, 540, 830][k]
            colar(tela, pol, x, 1320 - 30 * (1 - p) + 700 * sai, 0.5 + 0.5 * p, lim(tk / 0.1), giro=giro)
    itens.append(previa)

    # entrada das reações: frase de transição
    tr1 = Texto([("Esse é o react de quem", F_TXT2, BRANCO, 0), ("come essas delícias...", F_TXT2, BRANCO, 0)], 292)
    tr2 = Texto([("e se apaixona!", F_SCRIPT, VERDE_CLARO, 0)], 290)

    def ponte(tela, t):
        q = t - R
        if 0 <= q < 1.27:
            faixa_escura(tela, 165, 405, 140)
            tr1.desenhar(tela, q, 0.0, t_out=1.05, passo=0.05)
        elif 1.27 <= q < 2.5:
            faixa_escura(tela, 165, 405, 140)
            tr2.desenhar(tela, q - 1.27, 0.0, t_out=1.0, passo=0.1)
    itens.append(ponte)

    cor_vo = Coracoes(9, R + 1.3, R + 2.4, area=(150, 400, 1150, 1450), semente=8)
    itens.append(lambda tela, t: cor_vo.desenhar(tela, t, fim=R + 3.45))

    def soquinho(tela, t):
        q = t - (R + 2.58)
        if 0 <= q < 0.9:
            for i in range(9):
                a = 2 * math.pi * i / 9
                d = 80 + 170 * ease_out(q / 0.5)
                colar(tela, brilho(60 if i % 2 else 44), 270 + d * math.cos(a), 640 + d * math.sin(a), 1.0,
                      lim(1 - (q - 0.4) / 0.5))
    itens.append(soquinho)

    # família: "1ª mordida"
    mordida = pilula("1ª MORDIDA", fonte("montserrat", 46, 900), fundo=VERDE, cor=ROXO_ESC)

    def primeira(tela, t):
        q = t - (R + 4.9)
        if 0 <= q < 1.58:
            colar(tela, mordida, 540, 420, 0.5 + 0.5 * ease_back(q / 0.3), lim(q / 0.1) * lim((1.58 - q) / 0.15),
                  giro=-4)
    itens.append(primeira)

    # rajada: três reações rápidas com emoji
    rajada = [(R + 6.5, "👍", 780, 470), (R + 7.5, "🥹", 860, 420), (R + 8.5, "😍", 850, 410)]

    def emojis(tela, t):
        for t0, ch, x, y in rajada:
            q = t - t0 - 0.12
            if 0 <= q < 0.88:
                colar(tela, emoji(ch, 190), x, y, 0.3 + 0.7 * ease_back(q / 0.25), lim(q / 0.06),
                      giro=10 * math.sin(q * 8))
    itens.append(emojis)
    cor_raj = Coracoes(12, R + 6.6, R + 9.3, area=(160, 920, 1350, 1550), semente=12, tam=(44, 90))
    itens.append(lambda tela, t: cor_raj.desenhar(tela, t, vida=1.2, fim=R + 9.45))

    # "assistindo um filme, comia um bolo todo"
    def filme(tela, t):
        for t0, ch, x in ((R + 10.45, "🎂", 230), (R + 11.72, "🍿", 860)):
            q = t - t0
            if 0 <= q < 1.0:
                colar(tela, emoji(ch, 150), x, 980, 0.3 + 0.7 * ease_back(q / 0.25), lim(q / 0.06) * lim((1 - q) / 0.2),
                      giro=8 * math.sin(q * 7))
    itens.append(filme)

    # "Já queremos bolo, Nina!" em balão de mensagem por cima do bolo
    bal = balao(["Já queremos bolo,", "Nina!"], fonte("montserrat", 60, 800))
    t_b = marcos["bolo"]

    def mensagem(tela, t):
        q = t - (t_b + 0.15)
        if 0 <= q < 1.85:
            colar(tela, bal, 540, 560 + 40 * (1 - ease_out(q / 0.3)), 0.7 + 0.3 * ease_back(q / 0.3),
                  lim(q / 0.1) * lim((1.85 - q) / 0.2))
            colar(tela, emoji("🎂", 104), 880, 400, 0.5 + 0.5 * ease_back((q - 0.3) / 0.3),
                  lim((q - 0.3) / 0.1) * lim((1.85 - q) / 0.2), giro=12)
    itens.append(mensagem)

    # "Aprovado, gente?" -> "APROVADÍSSIMO!"
    t_a = marcos["aprov"]
    perg = balao(["Aprovado, gente?"], fonte("montserrat", 56, 800), cauda="dir")
    selo = carimbo("APROVADÍSSIMO!", VERDE_CLARO, 120)

    def aprovado(tela, t):
        q = t - t_a
        if 0.05 <= q < 1.9:
            colar(tela, perg, 540, 420, 0.7 + 0.3 * ease_back((q - 0.05) / 0.3), lim((q - 0.05) / 0.1) *
                  lim((1.9 - q) / 0.2))
        s = t - (t_a + 2.02)
        if 0 <= s < 0.98:
            if s < 0.12:
                branco = Image.new("RGBA", (W, H), (255, 255, 255, int(150 * (1 - s / 0.12))))
                tela.alpha_composite(branco)
            if s < 0.18:
                e = 1.8 - 0.8 * ease_out(s / 0.18)
            elif s < 0.26:
                e = 0.97 + 0.03 * ((s - 0.18) / 0.08)
            else:
                e = 1.0
            colar(tela, selo, 540, 1150, e, lim(s / 0.05) * lim((0.98 - s) / 0.1))
    itens.append(aprovado)

    # "é um pecado" -> emoji entre os dois rostos
    t_p = marcos["pecado"]

    def pecado(tela, t):
        r = t - (t_p + 3.45)
        if 0 <= r < 0.55:
            colar(tela, emoji("😋", 160), 430, 470, 0.4 + 0.6 * ease_back(r / 0.25), lim(r / 0.06), giro=-8)
    itens.append(pecado)

    # marca d'água durante as reações
    marca = logo(170)

    def marca_dagua(tela, t):
        if R + 2.5 <= t < marcos["cta"]:
            colar(tela, marca, 160, 250, 1.0, 0.92 * lim((t - R - 2.5) / 0.3))
    itens.append(marca_dagua)

    # cartão do perfil + botão seguir
    t_c = marcos["cta"]
    perfil, botao = cartao_perfil(False)
    perfil_ok, _ = cartao_perfil(True)
    dedo = emoji("👆", 130)

    def chamada(tela, t):
        q = t - (t_c + 1.0)
        if q < 0 or t >= FIM_CTA:
            return
        p = ease_back(q / 0.4)
        cart = perfil if t < FIM_CTA - 0.9 else perfil_ok
        y = 1385 + 120 * (1 - ease_out(q / 0.4))
        colar(tela, cart, 540, y, 0.85 + 0.15 * p, lim(q / 0.12))
        tap = t - (FIM_CTA - 1.35)
        if 0 <= tap < 1.2:
            bx = 540 - perfil.width / 2 + botao[0]
            by = y - perfil.height / 2 + botao[1]
            ida = ease_out(tap / 0.35)
            colar(tela, dedo, bx + 40 + 160 * (1 - ida), by + 70 + 160 * (1 - ida), 1.0 - 0.1 * (0.35 < tap < 0.5),
                  lim(tap / 0.1) * lim((1.2 - tap) / 0.2))
            if tap > 0.45:
                r = ease_out((tap - 0.45) / 0.4)
                anel = Image.new("RGBA", (300, 300), (0, 0, 0, 0))
                ImageDraw.Draw(anel).ellipse([150 - 140 * r, 150 - 140 * r, 150 + 140 * r, 150 + 140 * r],
                                             outline=(255, 255, 255, int(230 * (1 - r))), width=8)
                colar(tela, anel, bx, by)
    itens.append(chamada)
    return itens


def sons_da_montagem(marcos):
    R, a = marcos["reacts"], marcos["aprov"]
    s = [
        (0.0, "whoosh", -14), (0.55, "pop", -16), (5.62, "shh", -16),
        (7.0, "pop", -18), (7.35, "pop", -18), (7.7, "pop", -18), (9.95, "whoosh", -18),
        # história
        (ANCORA, "whoosh_sobe", -16), (ANCORA + 0.6, "rabisco", -22),
        (ANCORA + 2.5, "whoosh", -18), (ANCORA + 5.0, "whoosh", -18), (ANCORA + 5.45, "brilho", -20),
    ]
    b4 = ANCORA + 7.0
    s += [(b4, "whoosh", -18)] + [(b4 + 0.12 + 0.36 * k, "obturador", -17) for k in range(5)]
    s += [(ANCORA + 9.5, "whoosh", -18), (ANCORA + 11.0, "pop", -16), (ANCORA + 12.0, "whoosh", -18),
          (ANCORA + 12.12, "swish", -18), (ANCORA + 12.97, "swish", -18), (ANCORA + 13.5, "pop", -15),
          (ANCORA + 14.5, "whoosh", -18), (ANCORA + 15.0, "brilho", -15),
          (marcos["loja"], "whoosh", -18), (marcos["loja"] + 0.25, "pop", -18),
          (ANCORA + 18.5, "whoosh", -18), (ANCORA + 20.5, "obturador", -16), (ANCORA + 22.0, "whoosh", -18),
          (ANCORA + 23.5, "whoosh_sobe", -19), (ANCORA + 24.0, "brilho", -20)]
    # reações
    s += [(R + 2.58, "impacto", -12), (R + 5.0, "pop", -15),
          (R + 6.5, "pop", -14), (R + 7.5, "pop", -14), (R + 8.5, "pop", -14),
          (R + 10.95, "pop", -16), (R + 11.95, "pop", -16),
          (marcos["bolo"] + 0.15, "ding", -14),
          (a + 0.05, "pop", -18), (a + 2.02, "impacto_seco", -9),
          (marcos["pecado"] + 3.45, "pop", -16),
          (marcos["cta"] + 1.0, "whoosh_sobe", -17), (FIM_CTA - 0.9, "clique", -12)]
    return s


# =====================================================================
# Transições nos cortes
# =====================================================================

def transicoes(marcos):
    """(tempo do corte, tipo)."""
    tr = [(0.60, "flash"), (ANCORA, "iris")]
    cortes_historia = [ANCORA + x for x in (2.5, 5.0, 7.0, 9.5, 12.0, 14.5, 16.5, 17.5, 18.5, 20.5, 22.0, 23.5)]
    tr += [(c, "chicote") for c in cortes_historia]
    R = marcos["reacts"]
    tr += [(R, "flash"), (R + 3.5, "chicote"), (R + 6.5, "flash"), (R + 7.5, "flash"), (R + 8.5, "flash"),
           (R + 9.5, "chicote"), (marcos["bolo"], "chicote"), (marcos["aprov"], "chicote"),
           (marcos["pecado"], "chicote"), (FIM_CTA, "iris")]
    return sorted(tr)


def borrar_horizontal(img, k=18):
    small = img.resize((max(1, W // k), H), Image.BILINEAR)
    return small.resize((W, H), Image.BILINEAR)


def aplicar_transicao(tela, t, tr, anterior):
    for tc, tipo in tr:
        d = t - tc
        if tipo == "flash" and 0 <= d < 0.12:
            tela.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, int(170 * (1 - d / 0.12)))))
        elif tipo == "chicote" and -0.07 <= d < 0.07:
            s = d / 0.07
            b = borrar_horizontal(tela)
            dx = int(-160 * s) if d >= 0 else int(-160 * s)
            m = Image.new("RGBA", (W, H))
            m.paste(b, (dx, 0))
            if dx > 0:
                m.paste(b.crop((0, 0, dx, H)).transpose(Image.FLIP_LEFT_RIGHT), (0, 0))
            elif dx < 0:
                m.paste(b.crop((W + dx, 0, W, H)).transpose(Image.FLIP_LEFT_RIGHT), (W + dx, 0))
            tela.paste(m, (0, 0))
        elif tipo == "iris" and 0 <= d < 0.45 and anterior.get(tc) is not None:
            r = 1150 * ease_in_out(d / 0.45)
            mascara = Image.new("L", (W, H), 0)
            ImageDraw.Draw(mascara).ellipse([540 - r, 960 - r, 540 + r, 960 + r], fill=255)
            base = anterior[tc].copy()
            base.paste(tela, (0, 0), mascara)
            tela.paste(base, (0, 0))
    return tela


# =====================================================================
# Áudio
# =====================================================================

def ler_audio(nome, ini, fim):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", f"{ini:.3f}", "-i", hd(nome),
                        "-t", f"{fim - ini:.3f}", "-vn", "-f", "f32le", "-ac", "2", "-ar", str(SR), "-"],
                       capture_output=True, check=True).stdout
    return np.frombuffer(r, np.float32).reshape(-1, 2).T.copy()


def som_extra(tipo):
    """Sons que não estão no editor: 'shh', 'brilho', 'obturador'."""
    rng = np.random.default_rng(len(tipo))
    if tipo == "shh":
        n = int(0.6 * SR)
        t = np.arange(n) / SR
        s = musica.filtro_fft(rng.uniform(-1, 1, n), lo=2500, hi=9000) * np.minimum(1, t / 0.08) * np.exp(-t * 3)
    elif tipo == "brilho":
        n = int(1.0 * SR)
        t = np.arange(n) / SR
        s = np.zeros(n)
        for k, f in enumerate([1568, 2093, 2637, 3136, 4186]):
            i = int(k * 0.05 * SR)
            tt = t[:n - i]
            s[i:] += np.sin(2 * np.pi * f * tt) * np.exp(-tt * 7) * 0.5
    elif tipo == "obturador":
        n = int(0.16 * SR)
        t = np.arange(n) / SR
        s = rng.uniform(-1, 1, n) * (np.exp(-t * 160) + 0.6 * np.exp(-np.maximum(0, t - 0.07) * 120) * (t > 0.07))
        s = musica.filtro_fft(s, lo=1500, hi=9000)
    else:
        import sys
        sys.path.insert(0, "/home/user/claude")
        from editor import sons
        with wave.open(str(sons.arquivo(tipo))) as w:
            a = np.frombuffer(w.readframes(w.getnframes()), np.int16).reshape(-1, 2).T.astype(np.float32) / 32768
        return a
    s = s / (np.abs(s).max() + 1e-9) * 0.89
    return np.vstack([s, s]).astype(np.float32)


def db(x):
    return 10 ** (x / 20)


def montar_audio(audios, marcos, saida):
    n = int(DURACAO * SR)
    voz = np.zeros((2, n), np.float32)
    atividade = np.zeros(n, np.float32)
    for a in audios:
        x = ler_audio(a["nome"], a["ini"], a["fim"])
        rms = 20 * np.log10(np.sqrt((x ** 2).mean()) + 1e-9)
        alvo = -19.0 if a["voz"] else -27.0
        g = db(max(-12, min(12, alvo - rms)))
        x = x * g
        f = int(0.012 * SR)
        x[:, :f] *= np.linspace(0, 1, f)
        x[:, -f:] *= np.linspace(1, 0, f)
        i = int(round(a["t0"] * SR))
        m = min(x.shape[1], n - i)
        voz[:, i:i + m] += x[:, :m]
        if a["voz"]:
            for w in json.load(open(PASTA / "proxy" / f"{a['nome']}.large-v3.json")):
                for p in w["w"]:
                    if a["ini"] <= (p["s"] + p["e"]) / 2 <= a["fim"]:
                        s0 = int((a["t0"] + p["s"] - a["ini"]) * SR)
                        s1 = int((a["t0"] + p["e"] - a["ini"]) * SR)
                        atividade[max(0, s0):max(0, min(n, s1))] = 1
    # música: volume por seção e abaixando quando tem fala
    secoes = [(0, ANCORA, "intro"), (ANCORA, marcos["reacts"], "historia"), (marcos["reacts"], marcos["cta"], "reacts"),
              (marcos["cta"], FIM_CTA, "cta"), (FIM_CTA, DURACAO + 1, "cta")]
    mus = musica.gerar(DURACAO, ANCORA, secoes[:-1], final_em=FIM_CTA)
    nivel = np.zeros(n, np.float32)
    for a_, b_, e in secoes:
        i0, i1 = int(a_ * SR), min(n, int(b_ * SR))
        nivel[i0:i1] = {"intro": -12, "historia": -4, "reacts": -9, "cta": -12}[e]
    nivel[int(FIM_CTA * SR):] = -3
    # suaviza a atividade de fala (ataque 80 ms, solta 350 ms)
    env = np.zeros(n, np.float32)
    v = 0.0
    passo = 240
    for i in range(0, n, passo):
        alvo = atividade[i:i + passo].max()
        v = v + (alvo - v) * (0.6 if alvo > v else 0.12)
        env[i:i + passo] = v
    duck = -9.0 * env
    ganho = db(nivel + duck)
    mus = mus[:, :n] * ganho
    sfx = np.zeros((2, n), np.float32)
    for t, tipo, nivel_db in sons_da_montagem(marcos):
        x = som_extra(tipo) * db(nivel_db + 1)
        i = int(round(t * SR))
        m = min(x.shape[1], n - i)
        if m > 0:
            sfx[:, i:i + m] += x[:, :m]
    mix = voz + mus + sfx
    with wave.open(str(saida), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        pico = np.abs(mix).max()
        if pico > 0.98:
            mix = mix / pico * 0.98
        w.writeframes((mix.T * 32767).astype(np.int16).tobytes())
    return saida


def normalizar(entrada, saida):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(entrada), "-af",
                        "loudnorm=I=-14:TP=-2:LRA=11:print_format=json", "-f", "null", "-"],
                       capture_output=True, text=True)
    import re
    m = json.loads(re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", r.stderr).group(0))
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(entrada), "-af",
                    f"loudnorm=I=-14:TP=-2:LRA=11:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
                    f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}"
                    ":linear=true,aresample=48000", "-ar", "48000", str(saida)], check=True)


# =====================================================================
# Render
# =====================================================================

def render(de=0.0, ate=DURACAO, saida=None, rapido=False, so_audio=False):
    trechos, audios, leg, marcos = montar_linha()
    saida = saida or PASTA / "final.mp4"
    tmp = PASTA / "render"
    tmp.mkdir(exist_ok=True)
    audio_bruto = tmp / "audio_bruto.wav"
    audio_final = tmp / "audio_final.wav"
    montar_audio(audios, marcos, audio_bruto)
    normalizar(audio_bruto, audio_final)
    if so_audio:
        return audio_final
    itens = camadas(marcos)
    tr = transicoes(marcos)
    ocultar_leg = [(0.0, 2.95), (marcos["bolo"], marcos["bolo"] + 2.0)]
    video_tmp = tmp / "video.mp4"
    enc = subprocess.Popen(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                            "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-vf", "noise=alls=2:allf=t,format=yuv420p",
                            "-c:v", "libx264", "-preset", "veryfast" if rapido else "medium", "-crf", "20",
                            "-maxrate", "10M", "-bufsize", "20M", "-profile:v", "high", "-level", "4.1",
                            str(video_tmp)], stdin=subprocess.PIPE)
    anterior = {}
    cortes_iris = [tc for tc, tp in tr if tp == "iris"]
    q0, q1 = int(round(de * FPS)), int(round(ate * FPS))
    ativo = None
    for q in range(q0, q1):
        t = q / FPS
        idx = max(i for i, (t0, _) in enumerate(trechos) if t0 <= t + 1e-6)
        t0, obj = trechos[idx]
        if ativo is not obj:
            if ativo is not None:
                ativo.fechar()
            ativo = obj
            ativo.abrir()
        tela = obj.quadro(t - t0)
        for f in itens:
            f(tela, t)
        leg.desenhar(tela, t, ocultar_leg)
        tela = aplicar_transicao(tela, t, tr, anterior)
        for tc in cortes_iris:
            if tc - 1 / FPS - 1e-6 <= t < tc - 1e-6:
                anterior[tc] = tela.copy()
        enc.stdin.write(tela.convert("RGB").tobytes())
        if q % 150 == 0:
            print(f"  {t:5.1f}s", flush=True)
    if ativo is not None:
        ativo.fechar()
    enc.stdin.close()
    enc.wait()
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(video_tmp),
                    "-ss", f"{de:.3f}", "-t", f"{ate - de:.3f}", "-i", str(audio_final),
                    "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                    "-movflags", "+faststart", "-shortest", str(saida)], check=True)
    return saida


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--de", type=float, default=0.0)
    ap.add_argument("--ate", type=float, default=DURACAO)
    ap.add_argument("--saida")
    ap.add_argument("--rapido", action="store_true")
    ap.add_argument("--so-audio", action="store_true")
    a = ap.parse_args()
    import time
    ini = time.time()
    print(render(a.de, a.ate, a.saida, a.rapido, a.so_audio), f"{time.time() - ini:.0f}s")
