"""Vídeo da Nina Fit Food: abertura da Brenda, a história narrada com fotos, a reação de cada irmão que provou
o bolo e a chamada pro Instagram.

Uso: python montagem.py [--de SEG] [--ate SEG] [--rapido] [--saida arquivo.mp4]
Precisa de: hd/ (clipes em 1080x1920), proxy/ (áudio 16 kHz + transcrições), fotos/, narracao/ (narracao.py).
"""
import argparse
import json
import math
import re
import subprocess
import wave

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import musica
import narracao
import roteiro
import rostos
from legendas import legendas
from marca import (BRANCO, CREME, ESCURO, FPS, H, LILAS, PASTA, ROXO, ROXO_CAIXA, ROXO_ESC, ROXO_VIVO, VERDE,
                   VERDE_CLARO, W, Particulas, brilho, carimbo, cartao_perfil, colar, coracao, ease_back, ease_in,
                   ease_in_out, ease_out, emoji, farol, fonte, fundo_roxo, icone_camera, lim, logo, mola, palavra,
                   pilula, polaroid, recortar, rgba, selo_pib, sombra)

HD = PASTA / "hd"
FOTOS = PASTA / "fotos" / "recortes"
LOJA = "7649936307915692184"
SR = 48000


def hd(nome):
    return str(HD / f"{nome}.mov")


def quadro_inteiro(t):
    return round(t * FPS) / FPS


# =====================================================================
# O que aparece: trechos de vídeo e cenas desenhadas
# =====================================================================

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


class Video:
    """Trecho de um clipe: ponto de entrada, duração e movimento de câmera (zoom, soco, tremida, congelar)."""

    def __init__(self, nome, ini, dur, zoom=(1.0, 1.0), foco=(540, 760), congelar=None, socos=(), tremer=()):
        self.nome, self.arq, self.ini, self.dur = nome, hd(nome), ini, dur
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

    def janela(self, tl):
        """(x0, y0, largura, altura) do pedaço do quadro que aparece na tela em tl."""
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
        cw, ch = W / z, H / z
        cx, cy = self.foco
        return min(max(cx - cw / 2 + dx, 0), W - cw), min(max(cy - ch / 2 + dy, 0), H - ch), cw, ch

    def quadro(self, tl):
        if self.leitor is None:
            self.abrir()
        tq = tl if self.congelar is None else min(tl, self.congelar)
        img = self.leitor.quadro(int(round(tq * FPS)))
        x0, y0, cw, ch = self.janela(tl)
        if abs(cw - W) > 1 or x0 or y0:
            img = img.resize((W, H), Image.BILINEAR, box=(x0, y0, x0 + cw, y0 + ch))
        return img.convert("RGBA")

    def rostos(self, tl):
        """Rostos (olhos até boca) na tela em tl, já com o zoom do trecho."""
        tq = tl if self.congelar is None else min(tl, self.congelar)
        x0, y0, cw, ch = self.janela(tl)
        e = W / cw
        caixas = rostos.rostos(self.nome, round((self.ini + tq) * 4) / 4)
        return [((a - x0) * e, (b - y0) * e, (c - x0) * e, (d - y0) * e) for a, b, c, d in caixas]


class Cena:
    """Trecho desenhado (história, cartão final): desenhar(tl, quadro_do_fundo) -> imagem RGBA."""

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

    def rostos(self, tl):
        return self.base.rostos(tl) if self.base else []


# =====================================================================
# Texto que entra palavra por palavra (junto com a narração)
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

    def desenhar(self, tela, tl, t_in=0.0, t_out=None, passo=0.07, dur=0.38, sobe=46, tempos=None):
        """tempos: quando cada palavra entra (tempo da cena); sem eles, uma a cada 'passo' depois de t_in."""
        for im, cx, cy, k in self.itens:
            t0 = tempos[min(k, len(tempos) - 1)] - 0.04 if tempos else t_in + k * passo
            p = (tl - t0) / dur
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
    alfa = int(alfa)
    chave = (int(y0), int(y1), alfa, cor)
    if chave not in _FAIXAS:
        h = int(y1 - y0)
        m = h * 0.25
        a = np.array([alfa * min(1.0, i / m, (h - 1 - i) / m) for i in range(h)], np.float32)[:, None]
        camada = np.zeros((h, W, 4), np.uint8)
        camada[..., :3] = cor
        camada[..., 3] = np.repeat(a, W, axis=1).astype(np.uint8)
        _FAIXAS[chave] = Image.fromarray(camada, "RGBA")
    tela.alpha_composite(_FAIXAS[chave], (0, int(y0)))


# =====================================================================
# Fotos e câmera dentro da foto
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


def janela_camera(foto_rgb, cx, cy, s, jw, jh):
    """O que uma 'câmera' com centro (cx, cy) e zoom s vê da foto, no tamanho da janela."""
    w, h = jw / s, jh / s
    x0 = min(max(cx - w / 2, 0), foto_rgb.width - w)
    y0 = min(max(cy - h / 2, 0), foto_rgb.height - h)
    return foto_rgb.resize((jw, jh), Image.LANCZOS, box=(x0, y0, x0 + w, y0 + h)), (x0, y0)


def holofote(img, fx, fy, r, escuro=0.5, suave=110):
    """Escurece tudo fora do círculo do rosto em foco."""
    a = np.asarray(img).astype(np.float32)
    yy, xx = np.ogrid[0:img.height, 0:img.width]
    k = 1 - escuro * np.clip((np.sqrt((xx - fx) ** 2 + (yy - fy) ** 2) - r) / suave, 0, 1)
    return Image.fromarray((a * k[..., None]).clip(0, 255).astype(np.uint8))


class PolaroidCamera:
    """Polaroide com a foto vista por uma câmera (centro e zoom): dá pra aproximar e deslizar dentro da moldura."""

    def __init__(self, foto_rgb, jw, jh, borda=24, base=120):
        self.foto, self.jw, self.jh, self.borda = foto_rgb, jw, jh, borda
        vazio = Image.new("RGBA", (jw + 2 * borda, jh + borda + base), rgba(CREME))
        self.moldura = sombra(vazio, 18, (0, 14), 130)
        self.m = 18 * 2 + 14                      # margem que a sombra acrescenta em volta do cartão
        self.y_legenda = self.m + borda + jh + base / 2 - 4

    def quadro(self, cx, cy, s, foco=None, escuro=0.0):
        vista, (x0, y0) = janela_camera(self.foto, cx, cy, s, self.jw, self.jh)
        if foco and escuro > 0.01:
            fx, fy, fw = foco
            vista = holofote(vista, (fx - x0) * s, (fy - y0) * s, fw * s * 0.72, escuro)
        card = self.moldura.copy()
        card.paste(vista, (self.m + self.borda, self.m + self.borda))
        return card


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


# =====================================================================
# A história, narrada (cada cena sabe quando entra cada fala)
# =====================================================================

PART = Particulas()
F_TXT = fonte("montserrat", 64, 800)
F_TXT2 = fonte("montserrat", 58, 800)
F_GRANDE = fonte("anton", 150)
F_SCRIPT = fonte("caveat", 128, 700)
F_SCRIPT_M = fonte("caveat", 104, 700)
FALAS = narracao.falas()


def dur_fala(ch):
    return FALAS[ch]["duracao"]


def tempos_fala(ch, t0, de=0, ate=None):
    """Quando cada palavra da fala entra, em tempo da cena (a fala começa em t0)."""
    return [t0 + t for t in FALAS[ch]["inicios"][de:ate]]


def base_roxa(t_abs):
    tela = fundo_roxo().copy()
    PART.desenhar(tela, t_abs)
    return tela


def cena_igreja(t0):
    """'Somos membros da PIB Guarapari. Uma igreja grande. Grande mesmo. Por isso, a gente se uniu num pequeno
    grupo...': foto da igreja cheia (a câmera vai abrindo), o símbolo da PIB no canto e os corações se juntando."""
    im = foto("pib.jpg")
    jw = 882
    cam = PolaroidCamera(im, jw, int(jw * im.height / im.width), base=56)
    s0 = jw / im.width
    T1 = 0.3
    T2 = T1 + dur_fala("pib") + 0.25
    T3 = T2 + dur_fala("grande") + 0.3
    dur = T3 + dur_fala("grupo") + 0.45
    a1 = Texto([("Somos membros da", F_TXT, BRANCO, 0)], 300)
    a2 = Texto([("PIB GUARAPARI", F_GRANDE, BRANCO, 0)], 1200, espaco=34)
    b1 = Texto([("Uma igreja grande.", F_TXT, BRANCO, 0), ("Grande mesmo.", F_SCRIPT, VERDE_CLARO, 0)], 320)
    c1 = Texto([("Por isso, a gente se uniu", F_TXT2, BRANCO, 0)], 1175)
    c2 = Texto([("num pequeno grupo...", F_SCRIPT, VERDE_CLARO, 0)], 1315)
    tp = tempos_fala("pib", T1)
    tg = tempos_fala("grande", T2)
    tu = tempos_fala("grupo", T3)

    def desenhar(tl, _):
        tela = base_roxa(t0 + tl)
        card = cam.quadro(im.width / 2, im.height / 2, s0 * (1.18 - 0.18 * ease_in_out(tl / dur)))
        q = tl - 0.05
        if q > 0:
            p = ease_out(q / 0.35)
            colar(tela, card, 540, 760 + 60 * (1 - p), 1.15 - 0.15 * p, lim(q / 0.12), giro=-2.5 + 6 * (1 - p))
        qs = tl - 0.4
        if qs > 0 and tl < T3 + 0.2:                     # símbolo da PIB no canto, com o barquinho balançando
            sai = ease_in((tl - T3) / 0.2)
            colar(tela, selo_pib(4.5 * math.sin(2 * math.pi * tl / 1.5), 210), 165, 505,
                  (0.5 + 0.5 * ease_back(qs / 0.4, 2.2)) * (1 - 0.6 * sai), lim(qs / 0.1) * (1 - sai), giro=-8)
        a1.desenhar(tela, tl, t_out=T2 - 0.15, tempos=tp[:3])
        a2.desenhar(tela, tl, t_out=T3 - 0.15, tempos=tp[3:])
        p = ease_out((tl - tp[3] - 0.3) / 0.4) * (1 - ease_in((tl - T3 + 0.15) / 0.22))
        if p > 0.01:
            ImageDraw.Draw(tela).rounded_rectangle([540 - 330 * p, 1300, 540 + 330 * p, 1312], 6, fill=rgba(VERDE))
        b1.desenhar(tela, tl, t_out=dur - 0.25, tempos=tg)
        c1.desenhar(tela, tl, tempos=tu[:6])
        c2.desenhar(tela, tl, tempos=tu[6:])
        r = np.random.default_rng(5)                    # coraçõezinhos que se juntam: o grupo se formando
        t_g = tu[7]
        p = ease_in_out((tl - t_g) / 1.0)
        for i in range(14):
            ang = 2 * math.pi * i / 14
            x0, y0 = 540 + r.uniform(-420, 420), 1455 + r.uniform(-60, 60)
            x1, y1 = 540 + 105 * math.cos(ang), 1455 + 30 * math.sin(ang)
            colar(tela, coracao(38, [LILAS, VERDE_CLARO, BRANCO][i % 3]), x0 + (x1 - x0) * p, y0 + (y1 - y0) * p,
                  1.0, lim((tl - t_g + 0.3) / 0.3) * 0.95)
        return tela
    return desenhar, dur, [("pib", T1), ("grande", T2), ("grupo", T3)]


def cena_farol(t0):
    T = 0.2
    dur = T + dur_fala("farol") + 0.6
    t1 = Texto([("que a gente chama de", F_TXT, BRANCO, 0)], 330)
    t2 = Texto([("FAROL", fonte("anton", 200), BRANCO, 0)], 1440, espaco=30)
    tf = tempos_fala("farol", T)

    def desenhar(tl, _):
        tela = base_roxa(t0 + tl)
        p = ease_back(tl / 0.55)
        colar(tela, farol(tl + 0.8, 560), 540, 860 + 120 * (1 - ease_out(tl / 0.5)), 0.85 + 0.15 * p, lim(tl / 0.25))
        t1.desenhar(tela, tl, tempos=tf[:5])
        t2.desenhar(tela, tl, tempos=tf[5:])
        return tela
    return desenhar, dur, [("farol", T)]


def cena_encontros(t0):
    T = 0.15
    dur = max(2.5, T + dur_fala("encontros") + 0.6)
    specs = [  # (arquivo, proporção, largura, x, y, giro)
        ("04_farol_ano_novo.jpg", 4 / 3, 640, 330, 660, -7),
        ("05_farol_sofa_limpa.jpg", 16 / 9, 680, 690, 880, 6),
        ("06_farol_selfie.jpg", 16 / 10, 680, 360, 1140, 4),
        ("07_farol_19set.jpg", 4 / 3, 620, 715, 1340, -5),
        ("08_farol_restaurante.jpg", 3 / 4, 470, 560, 1030, -2),
    ]
    pols = []
    for arq, prop, larg, x, y, g in specs:
        im = recorte_proporcao(foto(arq), prop)
        pols.append((polaroid(im, larg, int((larg - 48) / prop), base=70), x, y, g))
    titulo = Texto([("Esses são os nossos", F_TXT2, BRANCO, 0), ("encontros", F_SCRIPT_M, VERDE_CLARO, 0)], 300)
    te = tempos_fala("encontros", T)

    def desenhar(tl, _):
        tela = base_roxa(t0 + tl)
        for k, (pol, x, y, g) in enumerate(pols):
            tk = tl - 0.1 - 0.36 * k
            if tk <= 0:
                continue
            p = ease_out(tk / 0.32)
            colar(tela, pol, x, y - 60 * (1 - p), 1.35 - 0.35 * p, lim(tk / 0.12), giro=g + 10 * (1 - p))
        titulo.desenhar(tela, tl, tempos=te)
        return tela
    return desenhar, dur, [("encontros", T)]


# rostos na foto da loja (coordenadas do recorte): centro x, centro y, largura do rosto
ROSTO_LOJA = {"danilo": (491, 333, 189), "nina": (654, 463, 159)}


def cena_casal(t0):
    """'Até que, no ano passado, um casal chegou pra fazer parte do grupo.' (foto dos dois), 'Ele se chama Danilo.'
    (a câmera chega no rosto dele), 'E ela, Nina.' (desliza até ela) e a selfie dos dois caindo por cima."""
    loja = foto("casal_loja.jpg")
    cam = PolaroidCamera(loja, 752, 820)
    f_nome = fonte("caveat", 92, 700)
    nomes = {k: recortar(palavra(k, f_nome, ROXO)) for k in ("Danilo", "Nina")}
    T_CASAL = 0.15
    T_ZOOM = T_CASAL + dur_fala("casal") + 0.15
    D_ZOOM, D_PAN = 0.5, 0.35
    T_DANILO = T_ZOOM + 0.05
    T_PAN = T_DANILO + dur_fala("danilo") + 0.2
    T_NINA = T_PAN + 0.05
    T_SELFIE = T_NINA + dur_fala("nina") + 0.35
    dur = T_SELFIE + 1.15
    td = tempos_fala("danilo", T_DANILO)
    tn = tempos_fala("nina", T_NINA)
    pos = {"casal": (513, 560, 820 / 1120)}            # os dois inteiros, sem o canto dos ícones
    for quem, s in (("danilo", 1.7), ("nina", 1.9)):
        fx, fy, _ = ROSTO_LOJA[quem]
        pos[quem] = (fx, fy + 0.06 * 820 / s, s)
    a1 = Texto([("Até que, no ano passado,", fonte("caveat", 94, 700), VERDE_CLARO, 0)], 260)   # cabe na zona segura
    a2 = Texto([("um casal chegou pra fazer", F_TXT2, BRANCO, 0), ("parte do grupo", F_TXT2, BRANCO, 0)], 450)
    b1 = Texto([("Ele se chama", F_TXT2, BRANCO, 0)], 330)
    b2 = Texto([("e ela,", F_TXT2, BRANCO, 0)], 330)
    tc = tempos_fala("casal", T_CASAL)
    selfie = polaroid(foto("casal_praia.jpg"), 728, 850, base=110, legenda="Danilo e Nina",
                      f_legenda=fonte("caveat", 84, 700))
    cor_chegou = [Coracoes(5, 0.7, 1.5, area=area, semente=30 + k, tam=(40, 70))
                  for k, area in enumerate(((150, 215, 1150, 1400), (865, 930, 1150, 1400)))]
    cor_selfie = [Coracoes(6, T_SELFIE + 0.05, T_SELFIE + 0.7, area=area, semente=21 + k, tam=(48, 84))
                  for k, area in enumerate(((125, 200, 1150, 1450), (880, 955, 1150, 1450)))]

    def ir(a, b, p, zoom_log=False):
        s = math.exp(math.log(a[2]) + (math.log(b[2]) - math.log(a[2])) * p) if zoom_log else a[2] + (b[2] - a[2]) * p
        return a[0] + (b[0] - a[0]) * p, a[1] + (b[1] - a[1]) * p, s

    def camera(tl):
        casal = pos["casal"]
        if tl < T_ZOOM:
            return casal[0], casal[1], casal[2] * (1 + 0.02 * tl), None, 0.0
        danilo = pos["danilo"]
        if tl < T_PAN:
            p = ease_in_out((tl - T_ZOOM) / D_ZOOM)
            cx, cy, s = ir((casal[0], casal[1], casal[2] * (1 + 0.02 * T_ZOOM)), danilo, p, zoom_log=True)
            return cx, cy, s * (1 + 0.04 * max(0.0, tl - T_ZOOM - D_ZOOM)), ROSTO_LOJA["danilo"], 0.5 * p
        p = ease_in_out((tl - T_PAN) / D_PAN)
        cx, cy, s = ir((danilo[0], danilo[1], danilo[2] * (1 + 0.04 * (T_PAN - T_ZOOM - D_ZOOM))), pos["nina"], p)
        foco = tuple(a + (b - a) * p for a, b in zip(ROSTO_LOJA["danilo"], ROSTO_LOJA["nina"]))
        return (cx, cy, s * (1 + 0.04 * max(0.0, tl - T_PAN - D_PAN)), foco,
                0.5 * (1 - ease_in((tl - T_SELFIE) / 0.3)))

    def desenhar(tl, _):
        tela = base_roxa(t0 + tl)
        cx, cy, s, foco, escuro = camera(tl)
        card = cam.quadro(cx, cy, s, foco, escuro)
        xl, yl = card.width / 2, cam.y_legenda
        if tl < T_ZOOM + 0.2:                            # coraçãozinho na legenda enquanto ainda não tem nome
            colar(card, coracao(54, ROXO_VIVO), xl, yl, 1.0, lim((tl - 0.3) / 0.2) * lim((T_ZOOM + 0.2 - tl) / 0.2))
        q1 = (tl - td[-1] + 0.05) / 0.3
        colar(card, nomes["Danilo"], xl, yl, 0.7 + 0.3 * ease_back(q1), lim(q1 * 3) * lim((T_PAN + 0.12 - tl) / 0.12))
        q2 = (tl - tn[-1] + 0.05) / 0.3
        colar(card, nomes["Nina"], xl, yl, 0.7 + 0.3 * ease_back(q2), lim(q2 * 3))
        g = ease_in_out((tl - T_ZOOM) / D_ZOOM)
        q = tl - 0.05
        if q > 0:
            p = ease_out(q / 0.3)
            colar(tela, card, 540, 1050 - 90 * g + 50 * (1 - p), (0.84 + 0.16 * g) * (1.1 - 0.1 * p), lim(q / 0.12),
                  giro=-1.5)
        a1.desenhar(tela, tl, t_out=T_ZOOM - 0.1, tempos=tc[:5])
        a2.desenhar(tela, tl, t_out=T_ZOOM - 0.1, tempos=tc[5:])
        for c in cor_chegou:                              # somem antes da câmera entrar nos rostos
            c.desenhar(tela, tl, vida=1.0, fim=T_ZOOM + 0.05)
        b1.desenhar(tela, tl, t_out=T_PAN - 0.05, tempos=td[:3])
        b2.desenhar(tela, tl, t_out=T_SELFIE - 0.1, tempos=tn[:2])
        qs = tl - T_SELFIE
        if qs > 0:
            p = ease_out(qs / 0.3)
            colar(tela, selfie, 540, 985 - 50 * (1 - p), 1.3 - 0.3 * p, lim(qs / 0.1), giro=-3 + 11 * (1 - p))
            for c in cor_selfie:
                c.desenhar(tela, tl, vida=1.0)
        return tela
    return desenhar, dur, [("casal", T_CASAL), ("danilo", T_DANILO), ("nina", T_NINA)]


def cena_logo(t0):
    T = 0.15
    dur = T + dur_fala("juntos") + 0.55
    t1 = Texto([("E juntos, eles têm a", F_TXT, BRANCO, 0)], 560)
    tj = tempos_fala("juntos", T)
    t_logo = tj[5] - 0.05
    lg = logo(780)
    lg_s = sombra(lg, 24, (0, 14), 120)
    mascara = lg.getchannel("A")

    def desenhar(tl, _):
        from PIL import ImageChops
        tela = base_roxa(t0 + tl)
        t1.desenhar(tela, tl, tempos=tj[:5])
        q = tl - t_logo
        if q > 0:
            e = 0.55 + 0.45 * ease_back(q / 0.5, 2.2)
            img = lg_s
            if 0.45 < q < 1.15:      # brilho passando pelo logo
                s = (q - 0.45) / 0.7
                faixa = Image.new("L", lg.size, 0)
                x = int(-300 + (lg.width + 600) * s)
                ImageDraw.Draw(faixa).polygon([(x, 0), (x + 120, 0), (x - 80, lg.height), (x - 200, lg.height)],
                                              fill=170)
                faixa = ImageChops.multiply(faixa.filter(ImageFilter.GaussianBlur(30)), mascara)
                bril = Image.new("RGBA", lg.size, (255, 255, 255, 0))
                bril.putalpha(faixa)
                img = lg_s.copy()
                img.alpha_composite(bril, ((img.width - lg.width) // 2, (img.height - lg.height) // 2))
            colar(tela, img, 540, 1050, e, lim(q / 0.12))
            for i in range(7):
                a = 2 * math.pi * i / 7 + 0.4
                d = 330 + 70 * ease_out((q - 0.2) / 0.6)
                al = lim((q - 0.25) / 0.15) * lim(1 - (q - 1.0) / 0.4)
                colar(tela, brilho(46 + 16 * (i % 2)), 540 + d * math.cos(a), 1050 + 0.75 * d * math.sin(a),
                      0.7 + 0.3 * math.sin(q * 12 + i), al)
        return tela
    return desenhar, dur, [("juntos", T)]


def cena_loja(selo=False):
    pil = pilula("@ninafitfood", fonte("montserrat", 50, 800), icone=icone_camera(54))

    def fabrica(t0):
        def desenhar(tl, quadro):
            q = tl - 0.12
            if selo and q > 0:
                colar(quadro, pil, 540, 1430 + 40 * (1 - ease_out(q / 0.35)), 0.9 + 0.1 * ease_back(q / 0.35),
                      lim(q / 0.15))
            return quadro
        return desenhar, 1.0, []
    return fabrica


def cena_lanchinho(t0):
    T = 0.1
    dur = T + dur_fala("lanchinho") + 0.4
    t1 = Texto([("No Farol, a gente", F_TXT, BRANCO, 0), ("sempre leva um", F_TXT, BRANCO, 0)], 320)
    t2 = Texto([("lanchinho", F_SCRIPT, VERDE_CLARO, 0)], 530)
    tl_ = tempos_fala("lanchinho", T)

    def desenhar(tl, quadro):
        faixa_escura(quadro, 170, 680, 170)
        t1.desenhar(quadro, tl, tempos=tl_[:7])
        t2.desenhar(quadro, tl, tempos=tl_[7:])
        return quadro
    return desenhar, dur, [("lanchinho", T)]


def cena_todos(t0):
    T = 0.1
    dur = max(1.4, T + dur_fala("todos") + 0.45)
    im = recorte_proporcao(foto("04_farol_ano_novo.jpg"), 4 / 3)
    pol = polaroid(im, 900, int(852 * 3 / 4), base=80)
    t1 = Texto([("E todos nós...", F_SCRIPT, BRANCO, 0)], 420)
    tt = tempos_fala("todos", T)

    def desenhar(tl, _):
        tela = base_roxa(t0 + tl)
        t1.desenhar(tela, tl, tempos=tt)
        p = ease_out(tl / 0.35)
        colar(tela, pol, 540, 1020 + 80 * (1 - p), 1.15 - 0.15 * p + 0.03 * tl, lim(tl / 0.12), giro=-3 + 6 * (1 - p))
        return tela
    return desenhar, dur, [("todos", T)]


def cena_guarapari(t0):
    T = 0.1
    dur = T + dur_fala("cidade") + 0.6
    im = Image.open(PASTA / "fotos" / "03_guarapari.jpg").convert("RGB")
    e = H / im.height * 1.08
    grande = im.resize((int(im.width * e), int(im.height * e)), Image.LANCZOS)
    t1 = Texto([("e a cidade de", F_TXT, BRANCO, 0)], 330)
    t2 = Texto([("Guarapari", fonte("caveat", 150, 700), VERDE_CLARO, 0)], 500)
    tc = tempos_fala("cidade", T)
    pino = emoji("📍", 110)
    x_pino = 540 - t2.itens[0][0].width / 2 - 55          # logo à esquerda do nome

    def desenhar(tl, _):
        p = ease_in_out(tl / dur)
        x0 = int((grande.width - W) * (0.62 - 0.22 * p))
        y0 = int((grande.height - H) * 0.5)
        tela = grande.crop((x0, y0, x0 + W, y0 + H)).convert("RGBA")
        faixa_escura(tela, 170, 660, 150)
        t1.desenhar(tela, tl, tempos=tc[:4])
        t2.desenhar(tela, tl, tempos=tc[4:])
        q = tl - tc[4] - 0.25
        if q > 0:                                          # pino de localização caindo ao lado do nome
            colar(tela, pino, x_pino, 480 - 320 * (1 - mola(q / 0.7)), 1.0, lim(q / 0.08))
        return tela
    return desenhar, dur, [("cidade", T)]


def cena_apaixonados(t0):
    T = 0.1
    dur = T + dur_fala("apaixonados") + 0.45
    t1 = Texto([("nos tornamos", F_TXT, BRANCO, 0)], 290)
    t2 = Texto([("apaixonados", F_SCRIPT, VERDE_CLARO, 0)], 435)
    t3 = Texto([("pelas delícias que", F_TXT2, BRANCO, 0), ("a Nina prepara", F_TXT2, BRANCO, 0)], 640)
    ta = tempos_fala("apaixonados", T)
    cor = Coracoes(16, ta[2], ta[2] + 1.9, area=(150, 930, 1560, 1800), semente=4)

    def desenhar(tl, quadro):
        faixa_escura(quadro, 160, 780, 165)
        t1.desenhar(quadro, tl, tempos=ta[:2])
        t2.desenhar(quadro, tl, tempos=ta[2:3])
        t3.desenhar(quadro, tl, tempos=ta[3:])
        cor.desenhar(quadro, tl, vida=1.25)
        return quadro
    return desenhar, dur, [("apaixonados", T)]


def cena_reacao(t0):
    T = 0.1
    dur = T + dur_fala("reacao") + 0.35
    t1 = Texto([("E esse vídeo mostra a", F_TXT2, BRANCO, 0), ("reação de quem come", F_TXT2, BRANCO, 0),
                ("essas delícias...", F_TXT2, BRANCO, 0)], 400)
    t2 = Texto([("e se apaixona!", F_SCRIPT, VERDE_CLARO, 0)], 1450)
    tr = tempos_fala("reacao", T)
    cor = [Coracoes(5, tr[11], tr[11] + 1.0, area=area, semente=9 + k)       # sobem pelos lados, longe do texto
           for k, area in enumerate(((120, 230, 1500, 1800), (850, 960, 1500, 1800)))]

    def desenhar(tl, quadro):
        faixa_escura(quadro, 200, 640, 150)
        t1.desenhar(quadro, tl, tempos=tr[:11])
        faixa_escura(quadro, 1330, 1580, 130 * lim((tl - tr[11] + 0.2) / 0.2))
        t2.desenhar(quadro, tl, tempos=tr[11:])
        for c in cor:
            c.desenhar(quadro, tl, vida=1.2)
        return quadro
    return desenhar, dur, [("reacao", T)]


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
    return desenhar, 2.5, []


# =====================================================================
# Legendas das falas: caixa roxa na palavra falada, longe dos rostos
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
        if atual and larg + esp + im.width > 800:          # zona segura: x de 140 a 940
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


def cruza(caixa, rosto, folga=24):
    x0, y0, x1, y1 = caixa
    a, b, c, d = rosto
    return not (x1 < a - folga or x0 > c + folga or y1 < b - folga or y0 > d + folga)


class Legendas:
    def __init__(self):
        self.pendentes = []       # (ini, fim, [palavras], [inícios], objeto, t0 do objeto, largura, altura)
        self.grupos = []          # (ini, fim, [palavras], [inícios], y, largura, altura), depois de posicionar()
        self.cache = {}

    def adicionar(self, palavras, obj, t_obj, maximo=3):
        """palavras: [(texto, ini, fim)] em tempo de saída; obj/t_obj: o trecho (pra achar os rostos)."""
        atual, grupos = [], []
        for w, s, e in palavras:
            if atual and (len(atual) >= maximo or s - atual[-1][2] > 0.35):
                grupos.append(atual)
                atual = []
            atual.append((w, s, e))
            if w.rstrip()[-1:] in ".,?!":
                grupos.append(atual)
                atual = []
        if atual:
            grupos.append(atual)
        fim_trecho = t_obj + obj.dur
        for i, g in enumerate(grupos):
            prox = grupos[i + 1][0][1] if i + 1 < len(grupos) else g[-1][2] + 0.4
            fim = min(prox if prox - g[-1][2] < 0.6 else g[-1][2] + 0.3, fim_trecho)
            ini = max(g[0][1], t_obj)
            if fim - ini < 0.05:
                continue
            ws = [w if w.endswith("...") else w.rstrip(",.") for w, _, _ in g]
            larg = max(bloco_legenda(ws, i).width for i in range(len(ws)))
            self.pendentes.append((ini, fim, ws, [s for _, s, _ in g], obj, t_obj, larg, bloco_legenda(ws, 0).height))

    def posicionar(self, ocupados):
        """Altura de cada grupo: a primeira opção que não encosta em rosto nenhum nem nas áreas ocupadas
        (carimbo, cartão do perfil, título, contagem) enquanto o grupo está na tela.
        ocupados: [(início, fim, caixa, tipo)] em tempo de saída."""
        self.grupos = []
        for ini, fim, ws, ts, obj, t_obj, larg, altura in self.pendentes:
            # o carimbo é a resposta da pergunta da legenda: quando ele bate, a legenda sai
            fim = min([fim] + [a for a, b, caixa, tipo in ocupados if tipo == "selo" and ini + 0.6 < a < fim])
            rs = []
            for t in np.linspace(ini, fim, 4):
                rs += obj.rostos(t - t_obj)
            rs += [caixa for a, b, caixa, tipo in ocupados if a < fim and ini < b]
            y = next((y for y in (1290, 1440, 1020, 470, 330)
                      if not any(cruza((100, y - altura / 2, 980, y + altura / 2), r) for r in rs)), 1290)
            self.grupos.append((ini, fim, ws, ts, y, larg, altura))

    def caixas(self, t0, t1):
        """Onde ficam as legendas que aparecem entre t0 e t1 (pra emoji e número não caírem em cima)."""
        return [(540 - larg / 2, y - altura / 2, 540 + larg / 2, y + altura / 2)
                for ini, fim, ws, ts, y, larg, altura in self.grupos if ini < t1 and t0 < fim and fim > 2.95]

    def desenhar(self, tela, t):
        if t < 2.95:                                     # o gancho do começo ocupa o lugar da legenda
            return
        for ini, fim, ws, ts, y, _, _ in self.grupos:
            if ini <= t < fim:
                ativa = max([i for i, s in enumerate(ts) if s <= t + 0.02] or [0])
                chave = (tuple(ws), ativa)
                if chave not in self.cache:
                    self.cache[chave] = bloco_legenda(ws, ativa)
                e = 0.9 + 0.1 * ease_back((t - ini) / 0.12)
                colar(tela, self.cache[chave], 540, y, e, lim((t - ini) / 0.05))
                return


# =====================================================================
# A linha do tempo
# =====================================================================

class Linha:
    def __init__(self):
        self.t = 0.0
        self.trechos = []         # (t0, objeto)
        self.audios = []          # dict(nome, ini, fim, t0, voz, sem_som)
        self.narr = []            # (t, chave da fala)
        self.adesivos = []        # (t, tipo, parâmetros, objeto, t0 do objeto)
        self.cortes = []          # (t, tipo de transição)
        self.unidades = []        # (t, número, quem)
        self.leg = Legendas()
        self.marcos = {}

    def video(self, nome, a, b, op=None):
        op = op or {}
        dur = quadro_inteiro(b - a)
        v = Video(nome, a, dur, op.get("zoom", (1.0, 1.0)), op.get("foco", (540, 760)), op.get("congelar"),
                  op.get("socos", ()), op.get("tremer", ()))
        t0 = self.t
        self.trechos.append((t0, v))
        if op.get("audio", True):
            self.audios.append(dict(nome=nome, ini=a, fim=a + dur, t0=t0, voz=op.get("voz", False),
                                    sem_som=op.get("sem_som")))
        if op.get("texto") and op.get("legenda", True):
            ate = op.get("legenda_ate", a + dur)
            ws = [(w, t0 + s - a, t0 + e - a) for w, s, e in legendas(nome, a, a + dur, op["texto"], op.get("tempos"))
                  if s < ate]
            self.leg.adicionar(ws, v, t0)
        for ts, tipo, par in op.get("adesivos", []):
            self.adesivos.append((t0 + ts - a, tipo, par, v, t0))
        self.t += dur
        return v

    def cena(self, fabrica, base=None):
        t0 = self.t
        desenhar, dur, falas = fabrica(t0)
        dur = quadro_inteiro(dur)
        if base is not None:
            base.dur = dur
        self.trechos.append((t0, Cena(desenhar, dur, base)))
        self.narr += [(t0 + t, ch) for ch, t in falas]
        self.t += dur
        return t0


def montar_linha():
    L = Linha()
    # ---------------- abertura: o bolo e a Brenda explicando ----------------
    L.video("IMG_6491", 5.30, 5.90, dict(audio=False, zoom=(1.0, 1.08), foco=(540, 900)))
    L.audios.append(dict(nome="IMG_6490", ini=0.07, fim=0.67, t0=0.0, voz=False))
    L.cortes.append((L.t, "flash"))
    for nome, a, b, op in roteiro.abertura():
        L.video(nome, a, b, op)
    L.marcos["historia"] = L.t
    # ---------------- história, narrada ----------------
    L.cortes.append((L.t, "iris"))
    for fab, base in [(cena_igreja, None), (cena_farol, None), (cena_encontros, None), (cena_casal, None),
                      (cena_logo, None), (cena_loja(), Video(LOJA, 1.00, 1.0, (1.0, 1.06), (540, 600))),
                      (cena_loja(True), Video(LOJA, 38.00, 1.0, (1.04, 1.0), (540, 900))),
                      (cena_lanchinho, Video("IMG_6499", 0.10, 2.8, (1.0, 1.05), (600, 1100))),
                      (cena_todos, None), (cena_guarapari, None),
                      (cena_apaixonados, Video("IMG_6491", 6.40, 3.5, (1.0, 1.05), (540, 1000))),
                      (cena_reacao, Video("IMG_6491", 1.30, 4.0, (1.0, 1.06), (540, 1000)))]:
        t0 = L.cena(fab, base)
        if t0 > L.marcos["historia"] + 0.01:
            L.cortes.append((t0, "chicote"))
        if base is not None and base.nome == LOJA and "loja" not in L.marcos:
            L.marcos["loja"] = t0
    L.marcos["reacoes"] = L.t
    # ---------------- as reações, uma pessoa de cada vez ----------------
    clipe_anterior = None
    for n, (quem, trechos) in enumerate(roteiro.reacoes(), 1):
        L.unidades.append((L.t, n, quem))
        L.cortes.append((L.t, "chicote" if trechos[0][0] == clipe_anterior else "flash"))
        for nome, a, b, op in trechos:
            L.video(nome, a, b, op)
        clipe_anterior = trechos[-1][0]
    # ---------------- as confeiteiras e a chamada ----------------
    L.marcos["final"] = L.t
    L.unidades.append((L.t, len(roteiro.reacoes()) + 1, "confeiteiras"))
    L.cortes.append((L.t, "chicote"))
    for nome, a, b, op in roteiro.final():
        L.video(nome, a, b, op)
    L.marcos["cartao"] = L.t
    L.cortes.append((L.t, "iris"))
    L.cena(cena_final)
    L.marcos["fim"] = L.t
    L.ocupados = areas_ocupadas(L)
    L.leg.posicionar(L.ocupados)
    return L


CARTAO_Y, CARTAO_LARG = 1370, 800                    # cartão do perfil dentro da zona segura
PREVIA_Y = 1360                                      # as três prévias da abertura, idem


def carimbo_seguro(txt):
    """Carimbo de no máximo 800 px de largura (zona segura)."""
    im = carimbo(txt, VERDE_CLARO, 120)
    return im if im.width <= 800 else carimbo(txt, VERDE_CLARO, int(120 * 800 / im.width))


def areas_ocupadas(L):
    """[(início, fim, caixa, tipo)] de carimbo, cartão do perfil, título, contagem e prévias: legenda e emoji
    desviam deles."""
    t_react = next(s for g in L.leg.pendentes for w, s in zip(g[2], g[3]) if w.startswith("react"))
    out = [(t_react - 0.1, L.marcos["historia"], (130, PREVIA_Y - 160, 950, PREVIA_Y + 160), "previa")]
    for ta, tipo, par, obj, t_obj in L.adesivos:
        fim_obj = t_obj + obj.dur
        if tipo == "selo":
            im = carimbo_seguro(par["txt"])
            out.append((ta, fim_obj, (540 - im.width / 2, par["y"] - im.height / 2,
                                      540 + im.width / 2, par["y"] + im.height / 2), tipo))
        elif tipo == "perfil":                         # o cartão sobe 120 px até parar em CARTAO_Y
            im, _ = cartao_perfil(False, CARTAO_LARG)
            out.append((ta, L.marcos["cartao"], (540 - im.width / 2, CARTAO_Y - im.height / 2,
                                                 540 + im.width / 2, CARTAO_Y + 120 + im.height / 2), tipo))
        elif tipo == "titulo":
            out.append((ta, min(ta + 3.0, fim_obj), (100, 1200, 980, 1460), tipo))
        elif tipo == "numero":
            out.append((ta, min(ta + 0.55, fim_obj), (380, 190, 700, 510), tipo))
    return out


# =====================================================================
# Por cima: gancho, prévia, número de cada reação, adesivos, perfil
# =====================================================================

def chip_react(n):
    """'REACT #n': o número num círculo verde e a palavra numa pílula roxa."""
    num = recortar(palavra(f"#{n}", fonte("anton", 64), ROXO_ESC))
    txt = recortar(palavra("REACT", fonte("montserrat", 46, 900), BRANCO))
    d = 112
    w = d + txt.width + 70
    im = Image.new("RGBA", (w, d), (0, 0, 0, 0))
    dr = ImageDraw.Draw(im)
    dr.rounded_rectangle([d // 2, 10, w - 1, d - 11], (d - 20) // 2, fill=rgba(ROXO_VIVO))
    dr.ellipse([0, 0, d - 1, d - 1], fill=rgba(VERDE_CLARO))
    im.alpha_composite(num, ((d - num.width) // 2, (d - num.height) // 2))
    im.alpha_composite(txt, (d + 22, (d - txt.height) // 2))
    return sombra(im, 14, (0, 8), 120)


def lugar_livre(L, t0, t1, w, h, opcoes, extra=()):
    """Primeira posição (centro) cuja caixa w x h não encosta em rosto nem nas áreas 'extra' de t0 a t1.
    Os rostos vêm do trecho que está na tela em cada instante (t0 a t1 pode passar por mais de um corte)."""
    rs = []
    for t in np.linspace(t0, t1, max(4, int((t1 - t0) / 0.25) + 1)):
        obj, t_obj = objeto_em(L, t)
        rs += obj.rostos(t - t_obj)
    rs += list(extra)
    # a primeira sem nada no caminho; se nenhuma estiver livre, a que encosta em menos coisas
    batidas = [sum(cruza((x - w / 2, y - h / 2, x + w / 2, y + h / 2), r, 16) for r in rs) for x, y in opcoes]
    return opcoes[batidas.index(min(batidas))]


def objeto_em(L, t):
    i = max(i for i, (t0, _) in enumerate(L.trechos) if t0 <= t + 1e-6)
    return L.trechos[i][1], L.trechos[i][0]


def camadas(L):
    itens = []
    R0, C = L.marcos["reacoes"], L.marcos["cartao"]

    # gancho dos primeiros segundos
    g1 = sombra(recortar(palavra("UMA PROPAGANDA", fonte("anton", 118), BRANCO, 8, ROXO_ESC)), 14, (0, 8), 150)
    g2 = sombra(recortar(palavra("SEM FALAR NADA", fonte("anton", 118), VERDE_CLARO, 8, ROXO_ESC)), 14, (0, 8), 150)
    shh = emoji("🤫", 150)

    def gancho(tela, t):
        if t >= 3.0:
            return
        sai = lim((t - 2.75) / 0.25)
        for k, (im, y) in enumerate(((g1, 1110), (g2, 1250))):
            p = (t - 0.05 - 0.18 * k) / 0.32
            if p > 0:
                colar(tela, im, 540 + 600 * (1 - ease_out(p)) * (-1 if k == 0 else 1), y, 1.0, lim(p * 2) * (1 - sai))
        q = t - 0.55
        if q > 0:
            colar(tela, shh, 540, 920, 0.4 + 0.6 * ease_back(q / 0.3), lim(q / 0.1) * (1 - sai), giro=8 * math.sin(q * 6))
    itens.append(gancho)

    # prévia de três reações quando a Brenda fala "react"
    t_react = next(s for g in L.leg.grupos for w, s in zip(g[2], g[3]) if w.startswith("react"))
    previas = []
    for nome, ts, giro, caixa in (("IMG_6500", 10.35, -8, (360, 370, 960, 1170)),
                                  ("IMG_6497", 16.0, 5, (200, 250, 800, 1050)),
                                  ("IMG_6502", 6.1, -4, (235, 255, 835, 1055))):
        fr = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", str(ts), "-i", hd(nome),
                             "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
        im = Image.frombuffer("RGB", (W, H), fr, "raw", "RGB", 0, 1).crop(caixa)
        previas.append((polaroid(im, 236, 281, borda=12, base=36), giro))
    H0 = L.marcos["historia"]

    def previa(tela, t):
        if not (t_react - 0.1 <= t < H0):
            return
        for k, (pol, giro) in enumerate(previas):
            tk = t - t_react - 0.33 * k
            if tk <= 0:
                continue
            p = ease_back(tk / 0.35)
            sai = ease_in((t - (H0 - 0.35)) / 0.3)
            colar(tela, pol, [280, 540, 800][k], PREVIA_Y - 30 * (1 - p) + 700 * sai, 0.5 + 0.5 * p, lim(tk / 0.1),
                  giro=giro)
    itens.append(previa)

    # logo da Nina no canto durante as reações
    marca = logo(170)
    MARCA = (145, 255, 315, 355)

    def marca_dagua(tela, t):
        if R0 + 0.3 <= t < C:
            # some aos poucos quando um rosto passa por baixo (a câmera vira e a pessoa cai no canto)
            livre = 1.0
            for d in (-0.4, -0.3, -0.2, -0.1, 0.0, 0.1, 0.2, 0.3, 0.4):
                tt = min(max(t + d, R0), C - 0.01)
                obj, t_obj = objeto_em(L, tt)
                if any(cruza(MARCA, r, 16) for r in obj.rostos(tt - t_obj)):
                    livre = min(livre, abs(d) / 0.4)
            colar(tela, marca, 230, 305, 1.0, 0.92 * lim((t - R0 - 0.3) / 0.3) * livre)
    itens.append(marca_dagua)

    def ocupado(t0, t1):
        """Legendas e áreas fixas (carimbo, cartão, título, contagem) na tela entre t0 e t1."""
        return L.leg.caixas(t0, t1) + [cx for a, b, cx, _ in L.ocupados if a < t1 and t0 < b]

    # número de cada reação (a pílula visível, sem a sombra, fica dentro da zona segura nas quatro posições)
    chips = []
    for t0, n, quem in L.unidades:
        im = chip_react(n)
        x, y = lugar_livre(L, t0 + 0.02, t0 + 2.0, im.width, im.height,
                           [(560, 290), (740, 290), (560, 1470), (740, 1470)], extra=[MARCA] + ocupado(t0, t0 + 2.0))
        chips.append((t0, im, x, y))
    caixas_chips = [(t0 + 0.12, t0 + 2.02, (x - im.width / 2, y - im.height / 2, x + im.width / 2, y + im.height / 2))
                    for t0, im, x, y in chips]

    def numeros(tela, t):
        for t0, im, x, y in chips:
            q = t - t0 - 0.12
            if 0 <= q < 1.9:
                colar(tela, im, x, y - 50 * (1 - ease_out(q / 0.3)), 0.6 + 0.4 * ease_back(q / 0.3),
                      lim(q / 0.1) * lim((1.9 - q) / 0.25))
    itens.append(numeros)

    # adesivos de cada trecho (emoji, brilhos, corações, contagem, carimbo, flash, título, perfil)
    perfil, botao = cartao_perfil(False, CARTAO_LARG)
    perfil_ok, _ = cartao_perfil(True, CARTAO_LARG)
    dedo = emoji("👆", 130)
    preparados = []
    for k, (ta, tipo, par, obj, t_obj) in enumerate(L.adesivos):
        fim_obj = t_obj + obj.dur
        if tipo == "emoji":
            im = emoji(par["ch"], par.get("tam", 150))
            fim = min(ta + 1.1, fim_obj)
            x, y = lugar_livre(L, ta, fim - 0.01, im.width, im.height,
                               [(par["x"], par["y"]), (W - par["x"], par["y"]), (par["x"], 1450), (W - par["x"], 1450)],
                               extra=ocupado(ta, fim) + [cx for a, b, cx in caixas_chips if a < fim and ta < b])
            preparados.append(("emoji", ta, fim, dict(im=im, x=x, y=y)))
        elif tipo == "brilhos":
            preparados.append(("brilhos", ta, min(ta + 0.9, fim_obj), par))
        elif tipo == "coracoes":
            preparados.append(("coracoes", ta, min(ta + 1.4, fim_obj),
                               dict(c=Coracoes(8, ta, ta + 0.7, area=par["area"], semente=40 + k, tam=(44, 80)))))
        elif tipo == "numero":
            im = sombra(recortar(palavra(par["txt"], fonte("anton", 230), BRANCO, 10, ROXO_ESC)), 14, (0, 8), 150)
            preparados.append(("numero", ta, min(ta + 0.55, fim_obj), dict(im=im)))
        elif tipo == "selo":
            preparados.append(("selo", ta, fim_obj - 0.02, dict(im=carimbo_seguro(par["txt"]), y=par["y"])))
        elif tipo == "flash":
            preparados.append(("flash", ta, ta + 0.14, {}))
        elif tipo == "titulo":
            im = Texto([(par["linhas"][0], fonte("montserrat", 60, 900), BRANCO, 0),
                        (par["linhas"][1], fonte("anton", 150), VERDE_CLARO, 0)], 1330)
            preparados.append(("titulo", ta, min(ta + 3.0, fim_obj), dict(texto=im)))
        elif tipo == "perfil":
            preparados.append(("perfil", ta, C, {}))

    def adesivos(tela, t):
        for tipo, a, b, par in preparados:
            if not (a <= t < b):
                continue
            q = t - a
            if tipo == "emoji":
                colar(tela, par["im"], par["x"], par["y"], 0.3 + 0.7 * ease_back(q / 0.25), lim(q / 0.06) * lim((b - t) / 0.2),
                      giro=9 * math.sin(q * 7))
            elif tipo == "brilhos":
                cx, cy = par["x"], par["y"]
                for i in range(9):
                    ang = 2 * math.pi * i / 9 + 0.3
                    d = 50 + 150 * ease_out(q / 0.5)
                    colar(tela, brilho(58 if i % 2 else 42), cx + d * math.cos(ang), cy + d * math.sin(ang), 1.0,
                          lim(1 - (q - 0.4) / 0.5))
            elif tipo == "coracoes":
                par["c"].desenhar(tela, t, vida=1.1, fim=b)
            elif tipo == "numero":
                colar(tela, par["im"], 540, 350, 0.5 + 0.6 * ease_back(q / 0.18), lim(q / 0.05) * lim((b - t) / 0.12))
            elif tipo == "selo":
                if q < 0.12:
                    tela.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, int(150 * (1 - q / 0.12)))))
                e = 1.8 - 0.8 * ease_out(q / 0.18) if q < 0.18 else (0.97 + 0.03 * lim((q - 0.18) / 0.08))
                colar(tela, par["im"], 540, par["y"], e, lim(q / 0.05) * lim((b - t) / 0.08))
            elif tipo == "flash":
                tela.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, int(190 * (1 - q / 0.14)))))
            elif tipo == "titulo":
                par["texto"].desenhar(tela, q, 0.0, t_out=(b - a) - 0.25, passo=0.12)
            elif tipo == "perfil":
                p = ease_back(q / 0.4)
                card = perfil if t < b - 0.9 else perfil_ok
                y = CARTAO_Y + 120 * (1 - ease_out(q / 0.4))
                colar(tela, card, 540, y, 0.85 + 0.15 * p, lim(q / 0.12))
                tap = t - (b - 1.35)
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
    itens.append(adesivos)
    return itens


def sons(L):
    """(t, tipo, dB) de todos os efeitos."""
    H0, R0, C = L.marcos["historia"], L.marcos["reacoes"], L.marcos["cartao"]
    s = [(0.0, "whoosh", -14), (0.55, "pop", -16)]
    t_react = next(s_ for g in L.leg.grupos for w, s_ in zip(g[2], g[3]) if w.startswith("react"))
    s += [(t_react + 0.33 * k, "pop", -18) for k in range(3)]
    s += [(t, "whoosh" if tipo != "iris" else "whoosh_sobe", -18) for t, tipo in L.cortes if H0 - 0.01 <= t < R0]
    s += [(H0 + 0.45, "pop", -17)]                       # símbolo da PIB
    for t, ch in L.narr:                                 # um toque em momentos da história
        if ch == "encontros":
            s += [(t - 0.05 + 0.36 * k, "obturador", -18) for k in range(5)]
        elif ch in ("danilo", "nina"):
            s += [(t + FALAS[ch]["inicios"][-1], "swish", -19)]
        elif ch == "juntos":
            s += [(t + FALAS[ch]["inicios"][5], "brilho", -17)]
        elif ch == "todos":
            s += [(t, "obturador", -17)]
        elif ch == "cidade":
            s += [(t + FALAS[ch]["inicios"][4] + 0.35, "pop", -17)]
        elif ch == "apaixonados":
            s += [(t + FALAS[ch]["inicios"][2], "brilho", -19)]
    for t0, n, quem in L.unidades:
        s += [(t0 + 0.12, "pop", -16)]
    for ta, tipo, par, obj, t_obj in L.adesivos:
        s += {"emoji": [(ta, "pop", -17)], "brilhos": [(ta, "brilho", -16)], "numero": [(ta, "tique", -14)],
              "selo": [(ta, "impacto_seco", -9)], "flash": [(ta, "obturador", -13)], "titulo": [(ta, "whoosh", -16)],
              "perfil": [(ta, "whoosh_sobe", -17), (C - 0.9, "clique", -12)]}.get(tipo, [])
    s += [(C, "brilho", -15)]
    return s


# =====================================================================
# Transições
# =====================================================================

def borrar_horizontal(img, k=18):
    small = img.resize((max(1, W // k), H), Image.BILINEAR)
    return small.resize((W, H), Image.BILINEAR)


def aplicar_transicao(tela, t, cortes, anterior):
    for tc, tipo in cortes:
        d = t - tc
        if tipo == "flash" and 0 <= d < 0.12:
            tela.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, int(170 * (1 - d / 0.12)))))
        elif tipo == "chicote" and -0.07 <= d < 0.07:
            s = d / 0.07
            b = borrar_horizontal(tela)
            dx = int(-160 * s)
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


def ler_wav(arq):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(arq), "-f", "f32le", "-ac", "2",
                        "-ar", str(SR), "-"], capture_output=True, check=True).stdout
    return np.frombuffer(r, np.float32).reshape(-1, 2).T.copy()


def som_extra(tipo):
    """Sons que não estão no editor: 'shh', 'brilho', 'obturador'. Os outros vêm do editor."""
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
        from editor import sons as sons_editor
        with wave.open(str(sons_editor.arquivo(tipo))) as w:
            return np.frombuffer(w.readframes(w.getnframes()), np.int16).reshape(-1, 2).T.astype(np.float32) / 32768
    s = s / (np.abs(s).max() + 1e-9) * 0.89
    return np.vstack([s, s]).astype(np.float32)


def db(x):
    return 10 ** (x / 20)


def nivelar(x, alvo):
    rms = 20 * np.log10(np.sqrt((x ** 2).mean()) + 1e-9)
    return x * db(max(-12, min(12, alvo - rms)))


def colocar(buf, x, t, fade=0.015):
    x = x.copy()
    f = min(int(fade * SR), x.shape[1] // 2)
    if f > 0:
        x[:, :f] *= np.linspace(0, 1, f)
        x[:, -f:] *= np.linspace(1, 0, f)
    i = int(round(t * SR))
    m = min(x.shape[1], buf.shape[1] - i)
    if m > 0 and i >= 0:
        buf[:, i:i + m] += x[:, :m]


def montar_audio(L, saida):
    n = int(L.marcos["fim"] * SR)
    voz = np.zeros((2, n), np.float32)
    atividade = np.zeros(n, np.float32)
    for a in L.audios:
        x = ler_audio(a["nome"], a["ini"], a["fim"])
        if a.get("sem_som"):
            s0, s1 = (int((v - a["ini"]) * SR) for v in a["sem_som"])
            x[:, max(0, s0):max(0, s1)] = 0
        colocar(voz, nivelar(x, -19.0 if a["voz"] else -27.0), a["t0"])
        if a["voz"]:
            atividade[int(a["t0"] * SR):int((a["t0"] + a["fim"] - a["ini"]) * SR)] = 1
    for t, ch in L.narr:
        x = nivelar(ler_wav(narracao.SAIDA / f"{ch}.wav"), -18.5)
        colocar(voz, x, t, fade=0.005)
        atividade[int(t * SR):int((t + x.shape[1] / SR) * SR)] = 1
    # música: volume por parte e abaixando quando tem fala
    H0, R0, F, C = L.marcos["historia"], L.marcos["reacoes"], L.marcos["final"], L.marcos["cartao"]
    secoes = [(0, H0, "intro"), (H0, R0, "historia"), (R0, F, "reacts"), (F, C, "cta")]
    mus = musica.gerar(L.marcos["fim"], H0, secoes, final_em=C)
    nivel = np.zeros(n, np.float32)
    for a_, b_, e in secoes:
        nivel[int(a_ * SR):min(n, int(b_ * SR))] = {"intro": -12, "historia": -8, "reacts": -9, "cta": -12}[e]
    nivel[int(C * SR):] = -3
    env = np.zeros(n, np.float32)
    v = 0.0
    passo = 240
    for i in range(0, n, passo):
        alvo = atividade[i:i + passo].max()
        v = v + (alvo - v) * (0.6 if alvo > v else 0.12)
        env[i:i + passo] = v
    mus = mus[:, :n] * db(nivel - 10.0 * env)
    sfx = np.zeros((2, n), np.float32)
    for t, tipo, nivel_db in sons(L):
        colocar(sfx, som_extra(tipo) * db(nivel_db + 1), t, fade=0.002)
    mix = voz + mus + sfx
    pico = np.abs(mix).max()
    if pico > 0.98:
        mix = mix / pico * 0.98
    with wave.open(str(saida), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((mix.T * 32767).astype(np.int16).tobytes())
    return saida


def normalizar(entrada, saida):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(entrada), "-af",
                        "loudnorm=I=-14:TP=-2:LRA=11:print_format=json", "-f", "null", "-"],
                       capture_output=True, text=True)
    m = json.loads(re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", r.stderr).group(0))
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(entrada), "-af",
                    f"loudnorm=I=-14:TP=-2:LRA=11:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
                    f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}"
                    ":linear=true,aresample=48000", "-ar", "48000", str(saida)], check=True)


# =====================================================================
# Render
# =====================================================================

def quadro(L, itens, t, anterior):
    obj, t0 = objeto_em(L, t)
    tela = obj.quadro(t - t0)
    for f in itens:
        f(tela, t)
    L.leg.desenhar(tela, t)
    return aplicar_transicao(tela, t, L.cortes, anterior)


def render(de=0.0, ate=None, saida=None, rapido=False):
    L = montar_linha()
    ate = min(ate or L.marcos["fim"], L.marcos["fim"])
    saida = saida or PASTA / "final.mp4"
    tmp = PASTA / "render"
    tmp.mkdir(exist_ok=True)
    montar_audio(L, tmp / "audio_bruto.wav")
    normalizar(tmp / "audio_bruto.wav", tmp / "audio_final.wav")
    itens = camadas(L)
    rostos.salvar()
    video_tmp = tmp / "video.mp4"
    enc = subprocess.Popen(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                            "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-vf", "noise=alls=2:allf=t,format=yuv420p",
                            "-c:v", "libx264", "-preset", "veryfast" if rapido else "medium", "-crf", "20",
                            "-maxrate", "10M", "-bufsize", "20M", "-profile:v", "high", "-level", "4.1",
                            str(video_tmp)], stdin=subprocess.PIPE)
    anterior = {}
    cortes_iris = [tc for tc, tp in L.cortes if tp == "iris"]
    ativo = None
    for q in range(int(round(de * FPS)), int(round(ate * FPS))):
        t = q / FPS
        obj, _ = objeto_em(L, t)
        if ativo is not obj:
            if ativo is not None:
                ativo.fechar()
            ativo = obj
            ativo.abrir()
        tela = quadro(L, itens, t, anterior)
        for tc in cortes_iris:
            if tc - 1 / FPS - 1e-6 <= t < tc - 1e-6:
                anterior[tc] = tela.copy()
        enc.stdin.write(tela.convert("RGB").tobytes())
        if q % 300 == 0:
            print(f"  {t:5.1f}s", flush=True)
    if ativo is not None:
        ativo.fechar()
    enc.stdin.close()
    enc.wait()
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(video_tmp),
                    "-ss", f"{de:.3f}", "-t", f"{ate - de:.3f}", "-i", str(tmp / "audio_final.wav"),
                    "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                    "-movflags", "+faststart", "-shortest", str(saida)], check=True)
    return saida


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--de", type=float, default=0.0)
    ap.add_argument("--ate", type=float)
    ap.add_argument("--saida")
    ap.add_argument("--rapido", action="store_true")
    a = ap.parse_args()
    import time
    ini = time.time()
    print(render(a.de, a.ate, a.saida, a.rapido), f"{time.time() - ini:.0f}s")
