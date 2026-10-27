"""Desenhos da aula (módulo 2, ajudante do visual_aula.py).

Paleta e fontes iguais aos slides, uma "Tela" com supersampling (desenha em 2x e reduz, pra ficar liso)
e os modelos de esquema. Tudo aqui é só PIL: devolve imagens RGB/RGBA. A conversão pra YUV e a montagem
do vídeo ficam no visual_aula.py.

Os modelos de esquema e o formato de "dados" de cada um estão documentados em ESQUEMAS_DOC (e no
docstring do visual_aula.py). Tempos ("t") são sempre em segundos da SAÍDA (mesma linha do tempo do
eventos.json). Item sem "t" já aparece aceso desde o começo.
"""
import functools
import math

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

# ---------------------------------------------------------------- identidade
AZUL_NOITE = (8, 11, 40)
CREME = (251, 247, 239)
LARANJA = (234, 85, 42)
TEXTO = (17, 20, 50)
CINZA = (110, 112, 130)
LILAS = (150, 128, 226)
MENTA = (64, 186, 152)
PELE = (246, 211, 186)
BOCHECHA = (240, 160, 150)

_INTER = "/usr/share/fonts/opentype/inter/"
FONTES = {
    "xbold": _INTER + "Inter-ExtraBold.otf",
    "bold": _INTER + "Inter-Bold.otf",
    "semi": _INTER + "Inter-SemiBold.otf",
    "medio": _INTER + "Inter-Medium.otf",
    "normal": _INTER + "Inter-Regular.otf",
    "mao": "/home/user/claude/recursos/fontes/Caveat-Variable.ttf",
}


@functools.lru_cache(maxsize=512)
def fonte(nome, tam):
    f = ImageFont.truetype(FONTES[nome], max(6, int(round(tam))))
    if nome == "mao":
        try:
            f.set_variation_by_name("Bold")
        except Exception:
            pass
    return f


def paleta(fundo="escuro"):
    if fundo == "claro":
        return dict(bg=CREME, fg=TEXTO, fraco=CINZA, apagado=(206, 200, 190), apagado_txt=(170, 166, 160),
                    cartao=(255, 255, 255), acento=LARANJA, sobre_acento=CREME, linha=(200, 194, 184))
    return dict(bg=AZUL_NOITE, fg=CREME, fraco=(168, 170, 200), apagado=(52, 56, 96), apagado_txt=(98, 102, 140),
                cartao=(24, 28, 66), acento=LARANJA, sobre_acento=CREME, linha=(70, 74, 112))


# ---------------------------------------------------------------- animação
def lim(x, a=0.0, b=1.0):
    return a if x < a else b if x > b else x


def suave(x):
    x = lim(x)
    return x * x * (3 - 2 * x)


def sai(x):  # ease-out cúbico
    x = lim(x)
    return 1 - (1 - x) ** 3


def vaivem(x):  # ease-in-out cúbico
    x = lim(x)
    return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2


def mola(x, s=1.9):  # ease-out-back (passa um pouco e volta)
    x = lim(x)
    return 1 + (s + 1) * (x - 1) ** 3 + s * (x - 1) ** 2


def mix(c1, c2, a):
    a = lim(a)
    return tuple(int(round(c1[i] + (c2[i] - c1[i]) * a)) for i in range(3))


def escurecer(c, k):
    return tuple(int(v * k) for v in c[:3])


def prog(t, ti, dur=0.45):
    """0 antes de ti, 1 depois de ti+dur. ti None = sempre 1."""
    if ti is None:
        return 1.0
    return lim((t - float(ti)) / dur)


# ---------------------------------------------------------------- texto
def medir(txt, nome, tam):
    return fonte(nome, tam).getlength(txt)


def quebrar(txt, nome, tam, largura):
    """Quebra em linhas que cabem na largura (respeita \\n)."""
    f = fonte(nome, tam)
    saida = []
    for par in str(txt).split("\n"):
        palavras = par.split()
        if not palavras:
            saida.append("")
            continue
        linha = palavras[0]
        for p in palavras[1:]:
            if f.getlength(linha + " " + p) <= largura:
                linha += " " + p
            else:
                saida.append(linha)
                linha = p
        saida.append(linha)
    return saida


def caber(txt, nome, tam, largura, max_linhas=2, tam_min=26):
    """Maior tamanho (<= tam, >= tam_min) em que o texto cabe em max_linhas. Devolve (tam, linhas)."""
    t = tam
    while t > tam_min:
        ls = quebrar(txt, nome, t, largura)
        if len(ls) <= max_linhas and all(medir(l, nome, t) <= largura for l in ls):
            return t, ls
        t -= 2
    return tam_min, quebrar(txt, nome, tam_min, largura)


# ---------------------------------------------------------------- tela
@functools.lru_cache(maxsize=4096)
def _mascara_texto(txt, nome, px, anchor):
    f = fonte(nome, px)
    bb = f.getbbox(txt, anchor=anchor)
    x0, y0 = int(math.floor(bb[0])) - 4, int(math.floor(bb[1])) - 4
    w, h = int(math.ceil(bb[2])) - x0 + 4, int(math.ceil(bb[3])) - y0 + 4
    masc = Image.new("L", (max(1, w), max(1, h)), 0)
    ImageDraw.Draw(masc).text((-x0, -y0), txt, font=f, fill=255, anchor=anchor)
    return masc, x0, y0


class Tela:
    """Desenho em coordenadas lógicas, feito em 2x e reduzido no final (bordas lisas).

    fundo=None -> tela transparente (RGBA, pra sobrepor no vídeo)."""

    def __init__(self, w, h, fundo=None, ss=2):
        self.w, self.h, self.ss = int(w), int(h), ss
        self.transparente = fundo is None
        cor = (0, 0, 0, 0) if fundo is None else tuple(fundo[:3]) + (255,)
        self.img = Image.new("RGBA", (self.w * ss, self.h * ss), cor)
        self.d = ImageDraw.Draw(self.img)

    def _s(self, v):
        return int(round(v * self.ss))

    def _cx(self, caixa):
        return [self._s(v) for v in caixa]

    @staticmethod
    def _c(cor):
        return tuple(cor[:3]) + ((cor[3],) if len(cor) > 3 else (255,))

    # formas
    def ret(self, x0, y0, x1, y1, cor=None, raio=0, borda=None, larg=0):
        if x1 <= x0 or y1 <= y0:
            return
        kw = {}
        if cor is not None:
            kw["fill"] = self._c(cor)
        if borda is not None and larg > 0:
            kw["outline"] = self._c(borda)
            kw["width"] = max(1, self._s(larg))
        r = self._s(min(raio, (x1 - x0) / 2, (y1 - y0) / 2))
        self.d.rounded_rectangle(self._cx((x0, y0, x1, y1)), radius=r, **kw)

    def circ(self, cx, cy, r, cor=None, borda=None, larg=0):
        if r <= 0:
            return
        kw = {}
        if cor is not None:
            kw["fill"] = self._c(cor)
        if borda is not None and larg > 0:
            kw["outline"] = self._c(borda)
            kw["width"] = max(1, self._s(larg))
        self.d.ellipse(self._cx((cx - r, cy - r, cx + r, cy + r)), **kw)

    def poli(self, pts, cor):
        self.d.polygon([(self._s(x), self._s(y)) for x, y in pts], fill=self._c(cor))

    def linha(self, pts, cor, larg=4, pontas=True):
        p = [(self._s(x), self._s(y)) for x, y in pts]
        w = max(1, self._s(larg))
        self.d.line(p, fill=self._c(cor), width=w, joint="curve")
        if pontas:
            r = w / 2
            for x, y in (p[0], p[-1]):
                self.d.ellipse((x - r, y - r, x + r, y + r), fill=self._c(cor))

    def arco(self, cx, cy, r, a0, a1, cor, larg=4):
        self.d.arc(self._cx((cx - r, cy - r, cx + r, cy + r)), a0, a1, fill=self._c(cor), width=max(1, self._s(larg)))

    def seta(self, x0, y0, x1, y1, cor, larg=5, ponta=16, prog_=1.0):
        """Seta de (x0,y0) até (x1,y1); prog_ < 1 desenha só o começo (seta crescendo)."""
        if prog_ <= 0.01:
            return
        x1 = x0 + (x1 - x0) * prog_
        y1 = y0 + (y1 - y0) * prog_
        ang = math.atan2(y1 - y0, x1 - x0)
        comp = math.hypot(x1 - x0, y1 - y0)
        pt = min(ponta, comp * 0.6)
        bx, by = x1 - math.cos(ang) * pt * 0.8, y1 - math.sin(ang) * pt * 0.8
        self.linha([(x0, y0), (bx, by)], cor, larg)
        a1, a2 = ang + 2.5, ang - 2.5
        self.poli([(x1, y1), (x1 + math.cos(a1) * pt, y1 + math.sin(a1) * pt),
                   (x1 + math.cos(a2) * pt, y1 + math.sin(a2) * pt)], cor)

    def check(self, cx, cy, tam, cor, larg=5, prog_=1.0):
        """Check (✓) desenhado como traço; prog_ anima o traço."""
        pts = [(cx - tam * 0.42, cy + tam * 0.02), (cx - tam * 0.12, cy + tam * 0.32), (cx + tam * 0.45, cy - tam * 0.32)]
        l1 = math.dist(pts[0], pts[1])
        l2 = math.dist(pts[1], pts[2])
        alvo = (l1 + l2) * lim(prog_)
        if alvo <= 0.5:
            return
        if alvo <= l1:
            a = alvo / l1
            self.linha([pts[0], (pts[0][0] + (pts[1][0] - pts[0][0]) * a, pts[0][1] + (pts[1][1] - pts[0][1]) * a)], cor, larg)
        else:
            a = (alvo - l1) / l2
            self.linha([pts[0], pts[1], (pts[1][0] + (pts[2][0] - pts[1][0]) * a, pts[1][1] + (pts[2][1] - pts[1][1]) * a)], cor, larg)

    def xis(self, cx, cy, tam, cor, larg=5):
        h = tam * 0.32
        self.linha([(cx - h, cy - h), (cx + h, cy + h)], cor, larg)
        self.linha([(cx - h, cy + h), (cx + h, cy - h)], cor, larg)

    def sombra(self, x0, y0, x1, y1, raio=16, desfoque=16, opac=0.35, desloc=(0, 8), cor=(0, 0, 0)):
        s = self.ss
        m = int(desfoque * 3)
        w, h = int(x1 - x0) + 2 * m, int(y1 - y0) + 2 * m
        cam = Image.new("L", (w * s, h * s), 0)
        ImageDraw.Draw(cam).rounded_rectangle((m * s, m * s, (w - m) * s, (h - m) * s), radius=raio * s,
                                              fill=int(255 * opac))
        cam = cam.filter(ImageFilter.GaussianBlur(desfoque * s / 2))
        camada = Image.new("RGBA", cam.size, tuple(cor) + (0,))
        camada.putalpha(cam)
        self.img.alpha_composite(camada, (int((x0 - m + desloc[0]) * s), int((y0 - m + desloc[1]) * s)))

    def colar(self, im, x, y):
        """Cola uma imagem PIL (em coordenadas lógicas; é ampliada ss vezes)."""
        im = im.convert("RGBA")
        if self.ss != 1:
            im = im.resize((im.width * self.ss, im.height * self.ss), Image.LANCZOS)
        self.img.alpha_composite(im, (self._s(x), self._s(y)))

    # texto
    def texto(self, x, y, txt, nome, tam, cor, anchor="la"):
        """Texto com composição alfa correta (sem borda escura na tela transparente)."""
        if not txt:
            return
        masc, dx, dy = _mascara_texto(str(txt), nome, int(round(tam * self.ss)), anchor)
        alfa = cor[3] / 255 if len(cor) > 3 else 1.0
        if alfa < 1:
            masc = masc.point(lambda v: int(v * alfa))
        camada = Image.new("RGBA", masc.size, tuple(cor[:3]) + (0,))
        camada.putalpha(masc)
        X, Y = self._s(x), self._s(y)
        self.img.alpha_composite(camada, (X + dx, Y + dy))

    def bloco(self, x, y, linhas, nome, tam, cor, entre=1.22, alinhar="esq", largura=0):
        """Linhas de texto a partir do topo y. Devolve a altura usada."""
        alt = tam * entre
        for i, l in enumerate(linhas):
            yy = y + i * alt + alt / 2
            if alinhar == "centro":
                self.texto(x + largura / 2, yy, l, nome, tam, cor, anchor="mm")
            elif alinhar == "dir":
                self.texto(x + largura, yy, l, nome, tam, cor, anchor="rm")
            else:
                self.texto(x, yy, l, nome, tam, cor, anchor="lm")
        return alt * len(linhas)

    def final(self):
        """Imagem no tamanho lógico: RGB (com fundo) ou RGBA (transparente, alfa reto)."""
        if self.ss == 1:
            return self.img.convert("RGB") if not self.transparente else self.img
        if not self.transparente:
            a = cv2.resize(np.asarray(self.img), (self.w, self.h), interpolation=cv2.INTER_AREA)
            return Image.fromarray(np.ascontiguousarray(a[:, :, :3]))
        a = np.asarray(self.img).astype(np.float32)
        al = a[..., 3:4] / 255.0
        a[..., :3] *= al
        s = self.ss
        h, w = a.shape[0] // s, a.shape[1] // s
        a = a[:h * s, :w * s].reshape(h, s, w, s, 4).mean(axis=(1, 3))
        al = a[..., 3:4] / 255.0
        rgb = np.where(al > 0.002, a[..., :3] / np.maximum(al, 1e-6), 0)
        out = np.concatenate([np.clip(rgb, 0, 255), a[..., 3:4]], axis=2)
        return Image.fromarray(np.round(out).astype(np.uint8), "RGBA")


# ---------------------------------------------------------------- peças comuns
M = 44  # margem do painel


def cabecalho(tl, pal, titulo, W, y_traco=46):
    """Traço laranja curto + título (como nos slides). Devolve o y onde o conteúdo começa."""
    if not titulo:
        return 48
    tl.ret(M, y_traco, M + 56, y_traco + 5, pal["acento"], raio=2)
    tam, linhas = caber(titulo, "bold", 36, W - 2 * M, max_linhas=2, tam_min=28)
    y = y_traco + 20
    y += tl.bloco(M, y, linhas, "bold", tam, pal["fg"], entre=1.18)
    return y + 26


def _itens(lista):
    out = []
    for it in lista or []:
        if isinstance(it, str):
            out.append({"txt": it, "t": None})
        else:
            d = dict(it)
            d["txt"] = d.get("txt", d.get("texto", ""))
            d.setdefault("t", None)
            out.append(d)
    return out


def icone(tl, nome, cx, cy, r, pal, fundo=CREME, cor=LARANJA):
    """Ícone simples numa bolinha. nomes: video, celular, carrinho, coracao, dinheiro, olho, estrela,
    lupa, check, sobe, sacola, nenhum."""
    if not nome or nome == "nenhum":
        return
    tl.circ(cx, cy, r, fundo)
    k = r / 26.0
    if nome == "video":
        tl.ret(cx - 15 * k, cy - 11 * k, cx + 15 * k, cy + 11 * k, cor, raio=4 * k)
        tl.poli([(cx - 4 * k, cy - 6 * k), (cx - 4 * k, cy + 6 * k), (cx + 7 * k, cy)], fundo)
    elif nome == "celular":
        tl.ret(cx - 9 * k, cy - 16 * k, cx + 9 * k, cy + 16 * k, None, raio=4 * k, borda=cor, larg=3.5 * k)
        tl.circ(cx, cy + 11 * k, 2 * k, cor)
    elif nome == "carrinho":
        tl.linha([(cx - 17 * k, cy - 12 * k), (cx - 11 * k, cy - 12 * k), (cx - 6 * k, cy + 5 * k), (cx + 12 * k, cy + 5 * k),
                  (cx + 15 * k, cy - 6 * k), (cx - 9 * k, cy - 6 * k)], cor, 3.5 * k)
        tl.circ(cx - 4 * k, cy + 12 * k, 3.2 * k, cor)
        tl.circ(cx + 10 * k, cy + 12 * k, 3.2 * k, cor)
    elif nome == "sacola":
        tl.ret(cx - 13 * k, cy - 6 * k, cx + 13 * k, cy + 15 * k, cor, raio=3 * k)
        tl.arco(cx, cy - 6 * k, 7 * k, 180, 360, cor, 3.5 * k)
    elif nome == "coracao":
        tl.circ(cx - 6.5 * k, cy - 4 * k, 8 * k, cor)
        tl.circ(cx + 6.5 * k, cy - 4 * k, 8 * k, cor)
        tl.poli([(cx - 14 * k, cy - 1 * k), (cx + 14 * k, cy - 1 * k), (cx, cy + 15 * k)], cor)
    elif nome == "dinheiro":
        tl.texto(cx, cy + 1 * k, "R$", "xbold", 19 * k, cor, anchor="mm")
    elif nome == "olho":
        tl.d.ellipse(tl._cx((cx - 17 * k, cy - 10 * k, cx + 17 * k, cy + 10 * k)), fill=tl._c(cor))
        tl.circ(cx, cy, 6.5 * k, fundo)
        tl.circ(cx, cy, 3.2 * k, TEXTO)
    elif nome == "estrela":
        pts = []
        for i in range(10):
            a = -math.pi / 2 + i * math.pi / 5
            rr = (16 if i % 2 == 0 else 7) * k
            pts.append((cx + math.cos(a) * rr, cy + math.sin(a) * rr))
        tl.poli(pts, cor)
    elif nome == "lupa":
        tl.circ(cx - 3 * k, cy - 3 * k, 9 * k, None, borda=cor, larg=4 * k)
        tl.linha([(cx + 4 * k, cy + 4 * k), (cx + 13 * k, cy + 13 * k)], cor, 5 * k)
    elif nome == "check":
        tl.check(cx, cy, 30 * k, cor, 5 * k)
    elif nome == "sobe":
        tl.linha([(cx - 14 * k, cy + 10 * k), (cx - 4 * k, cy), (cx + 2 * k, cy + 5 * k), (cx + 13 * k, cy - 9 * k)], cor, 4 * k)
        tl.poli([(cx + 15 * k, cy - 12 * k), (cx + 5 * k, cy - 11 * k), (cx + 14 * k, cy - 2 * k)], cor)
    else:
        tl.texto(cx, cy, str(nome)[:2], "bold", 18 * k, cor, anchor="mm")


CORES_PERSONAGEM = {"maria": LARANJA, "joana": LILAS, "serafina": MENTA}
CABELOS = {"maria": (92, 56, 40), "joana": (40, 30, 38), "serafina": (196, 120, 58)}
_PAL_EXTRA = [(232, 170, 60), (90, 150, 230), (220, 100, 150), (120, 190, 90)]


def cor_personagem(nome):
    k = str(nome).strip().lower()
    if k in CORES_PERSONAGEM:
        return CORES_PERSONAGEM[k], CABELOS[k]
    h = sum(ord(c) for c in k)
    return _PAL_EXTRA[h % len(_PAL_EXTRA)], [(70, 45, 35), (40, 30, 38), (150, 95, 50)][h % 3]


def boneco(tl, cx, pe, s, cor, cabelo, pal, acenando=0.0):
    """Bonequinho simples (cabeça redonda + corpo) com os pés em y=pe, escala s."""
    corpo_h, corpo_w = 84 * s, 70 * s
    ombro = pe - corpo_h
    hy = ombro - 36 * s
    braco = escurecer(cor, 0.82)
    # braços
    ang = 0.5 + acenando * 0.9
    for lado in (-1, 1):
        x0 = cx + lado * corpo_w * 0.38
        y0 = ombro + 16 * s
        a = ang if lado == 1 else 0.5
        x1 = x0 + lado * math.sin(a) * 46 * s
        y1 = y0 + math.cos(a) * 46 * s if lado == -1 or acenando <= 0 else y0 - math.sin(acenando * 1.2) * 40 * s + 20 * s
        tl.linha([(x0, y0), (x1, y1)], braco, 11 * s)
        tl.circ(x1, y1, 7.5 * s, PELE)
    # corpo (vestidinho)
    tl.poli([(cx - corpo_w * 0.34, ombro + 6 * s), (cx + corpo_w * 0.34, ombro + 6 * s),
             (cx + corpo_w * 0.56, pe - 10 * s), (cx - corpo_w * 0.56, pe - 10 * s)], cor)
    tl.ret(cx - corpo_w * 0.56, pe - 22 * s, cx + corpo_w * 0.56, pe, cor, raio=10 * s)
    tl.ret(cx - corpo_w * 0.36, ombro, cx + corpo_w * 0.36, ombro + 30 * s, cor, raio=14 * s)
    # pernas
    for lado in (-1, 1):
        tl.linha([(cx + lado * 14 * s, pe), (cx + lado * 14 * s, pe + 18 * s)], escurecer(cor, 0.6), 9 * s, pontas=False)
    # cabelo atrás + cabeça
    tl.ret(cx - 40 * s, hy - 40 * s, cx + 40 * s, hy + 40 * s, cabelo, raio=36 * s)
    tl.circ(cx, hy, 31 * s, PELE)
    tl.d.chord(tl._cx((cx - 33 * s, hy - 37 * s, cx + 33 * s, hy + 12 * s)), 180, 360, fill=tl._c(cabelo))
    tl.circ(cx - 11 * s, hy + 3 * s, 3.6 * s, TEXTO)
    tl.circ(cx + 11 * s, hy + 3 * s, 3.6 * s, TEXTO)
    tl.circ(cx - 19 * s, hy + 12 * s, 5 * s, BOCHECHA)
    tl.circ(cx + 19 * s, hy + 12 * s, 5 * s, BOCHECHA)
    tl.arco(cx, hy + 7 * s, 10 * s, 25, 155, TEXTO, 3 * s)
    return hy  # centro da cabeça


# ---------------------------------------------------------------- modelos de esquema
ESQUEMAS_DOC = """
Modelos de "esquema" e o formato de "dados" (t = segundos da SAÍDA; item sem t aparece desde o início).
Campos comuns: "titulo": str (opcional, com o traço laranja em cima, como nos slides).
No evento: "fundo": "escuro" (padrão, azul-noite como os slides) | "claro" (creme).

fluxo      {"titulo", "passos": [{"txt": "TESTAR", "t": 61.2, "sub": "opcional"}, ...], "nota": str, "t_nota": float}
           Passos numerados em coluna com setas; cada passo fica apagado e ACENDE no seu t (o atual ganha fundo).
comparacao {"titulo", "esq": {"titulo": "SEM ESTRATÉGIA", "t": float, "itens": [{"txt", "t"}, ...]},
                      "dir": {"titulo": "COM ESTRATÉGIA", "t": float, "itens": [...]}}
           Duas colunas; esquerda com ✗ (cinza), direita com ✓ (laranja). Itens entram no seu t.
ciclo      {"titulo", "etapas": [{"txt", "t"}, ...], "centro": "texto opcional no meio"}
           Etapas em círculo, setas entre elas e um pontinho laranja girando.
funil      {"titulo", "etapas": [{"txt": "ALCANCE", "sub": "opcional", "t"}, ...]}
           Camadas de cima (larga) pra baixo (estreita), caindo no seu t.
analogia   {"titulo", "personagens": [{"nome": "Maria", "acao": "publica o vídeo", "icone": "video", "t"}, ...],
            "setas": ["vê o vídeo", ...]  (opcional: texto em cima de cada seta entre personagens)}
           Bonequinhos (Maria laranja, Joana lilás, Serafina verde; outro nome ganha cor própria) com balão de
           ícone. ícones: video, celular, carrinho, sacola, coracao, dinheiro, olho, estrela, lupa, check, sobe, nenhum.
           Até 3 por linha (4 a 6 viram 2 linhas). Entram no seu t; a seta até ele cresce junto.
equivale   {"titulo", "pares": [{"a": "GMV", "b": "valor vendido", "t"}, ...], "rotulo_a": "no slide",
            "rotulo_b": "quer dizer"}
           "palavra do slide = palavra que ela falou". 1 par fica grande; até 4 pares empilhados.
lista      {"titulo", "itens": [{"txt", "t"}, ...]}   checklist: cada item entra e o ✓ se desenha.
numero     {"valor": "4 de 5", "rotulo": "vídeos vendendo todo dia", "t": float, "contar": false, "titulo"}
           Número grande com rótulo (só número que ela falou). "contar": true conta de 0 até o valor (se for inteiro).
"""


def _chave(marcos, t, extra=()):
    return tuple(int(round(prog(t, m) * 12)) for m in marcos) + tuple(extra)


class Esquema:
    """Desenha um modelo de esquema no tamanho W x H. Uso: e.chave(t) pra cache, e.desenhar(t) -> PIL RGB."""

    dinamico = False

    def __init__(self, modelo, dados, W, H, fundo="escuro"):
        self.modelo, self.d, self.W, self.H = modelo, dict(dados or {}), int(W), int(H)
        self.pal = paleta(fundo)
        f = getattr(self, "_m_" + modelo, None)
        if f is None:
            raise ValueError("modelo de esquema desconhecido: %s" % modelo)
        self._f = f
        self.marcos = self._marcos()

    def _marcos(self):
        d, m = self.d, []
        for k in ("passos", "etapas", "itens", "pares", "personagens"):
            for it in _itens(d.get(k)) if k != "pares" and k != "personagens" else d.get(k, []):
                m.append(it.get("t") if isinstance(it, dict) else None)
        for lado in ("esq", "dir"):
            if lado in d:
                m.append(d[lado].get("t"))
                m += [it["t"] for it in _itens(d[lado].get("itens"))]
        m += [d.get("t"), d.get("t_nota")]
        if self.modelo == "numero" and d.get("t") is not None:
            m += [d["t"] + 0.3, d["t"] + 0.6]
        if self.modelo == "lista":
            m += [it["t"] + 0.35 for it in _itens(d.get("itens")) if it["t"] is not None]
        if self.modelo == "equivale":
            m += [p.get("t") + 0.35 for p in d.get("pares", []) if p.get("t") is not None]
        return [x for x in m if x is not None]

    def chave(self, t):
        extra = ()
        if self.modelo == "ciclo":
            extra = (int((t % 4.0) / 4.0 * 72),)
        elif self.modelo == "analogia":
            extra = (int((t % 1.6) / 1.6 * 24),)
        elif self.modelo == "numero" and self.d.get("contar"):
            extra = (int(round(prog(t, self.d.get("t"), 0.9) * 30)),)
        return _chave(self.marcos, t, extra)

    def desenhar(self, t):
        tl = Tela(self.W, self.H, self.pal["bg"])
        self._f(tl, t)
        return tl.final()

    # ---- fluxo
    def _m_fluxo(self, tl, t):
        d, pal, W, H = self.d, self.pal, self.W, self.H
        y0 = cabecalho(tl, pal, d.get("titulo"), W)
        passos = _itens(d.get("passos"))
        n = max(1, len(passos))
        nota = d.get("nota")
        fim = H - 34 - (78 if nota else 0)
        row = min(150, (fim - y0) / n)
        r = max(18, min(32, row * 0.3))
        cx = M + r + 4
        tx = cx + r + 26
        larg_txt = W - tx - M
        tem_t = [p for p in passos if p["t"] is not None]
        atual = None
        if len(tem_t) > 1:
            ja = [i for i, p in enumerate(passos) if p["t"] is not None and t >= p["t"]]
            atual = ja[-1] if ja else None
        y_top = y0 + max(0, (fim - y0 - row * n) / 2)
        cys = [y_top + row * (i + 0.5) for i in range(n)]
        for i, p in enumerate(passos):
            cy = cys[i]
            pr = prog(t, p["t"])
            if i == atual:
                a = 0.10 * suave((t - p["t"]) / 0.3)
                tl.ret(M - 14, cy - row / 2 + 6, W - M + 14, cy + row / 2 - 6, mix(pal["bg"], pal["fg"], a), raio=18)
            if i > 0:
                ya, yb = cys[i - 1] + r + 9, cy - r - 9
                if yb - ya > 8:
                    tl.linha([(cx, ya), (cx, yb)], pal["apagado"], 3)
                    if pr > 0:
                        tl.seta(cx, ya, cx, yb, pal["acento"], larg=4, ponta=12, prog_=sai(pr))
            s = 1 + 0.22 * math.sin(math.pi * pr) if 0 < pr < 1 else 1
            rr = r * s
            if pr <= 0:
                tl.circ(cx, cy, r, pal["bg"], borda=pal["apagado"], larg=3)
                tl.texto(cx, cy, str(i + 1), "bold", r * 0.95, pal["apagado_txt"], anchor="mm")
            else:
                tl.circ(cx, cy, rr, mix(pal["apagado"], pal["acento"], suave(pr * 1.6)))
                tl.texto(cx, cy, str(i + 1), "bold", r * 0.95 * s, mix(pal["apagado_txt"], CREME, pr), anchor="mm")
            cor_t = mix(pal["apagado_txt"], pal["fg"], suave(pr))
            dx = -10 * (1 - sai(pr)) if p["t"] is not None and pr < 1 else 0
            sub = p.get("sub")
            tam, linhas = caber(p["txt"], "bold", 35, larg_txt, 2, 26)
            alt = tam * 1.18 * len(linhas) + (32 if sub else 0)
            yy = cy - alt / 2
            yy += tl.bloco(tx + dx, yy, linhas, "bold", tam, cor_t, entre=1.18)
            if sub:
                tl.texto(tx + dx, yy + 16, sub, "normal", 26, mix(pal["apagado_txt"], pal["fraco"], suave(pr)), anchor="lm")
        if nota:
            pn = prog(t, d.get("t_nota"))
            if pn > 0:
                tam, linhas = caber(nota, "mao", 40, W - 2 * M, 2, 30)
                tl.bloco(M, H - 34 - 70 + 8 * (1 - sai(pn)), linhas, "mao", tam, mix(pal["bg"], pal["acento"], pn),
                         entre=1.0, alinhar="centro", largura=W - 2 * M)

    # ---- comparacao
    def _m_comparacao(self, tl, t):
        d, pal, W, H = self.d, self.pal, self.W, self.H
        y0 = cabecalho(tl, pal, d.get("titulo"), W)
        gap = 22
        cw = (W - 2 * M - gap) / 2
        tam_it = 26
        for f in range(34, 25, -2):
            ok = True
            for lado in ("esq", "dir"):
                col = d.get(lado, {})
                th, lt = caber(col.get("titulo", ""), "xbold", 30, cw - 36, 2, 24)
                h = 24 + th * 1.15 * len(lt) + 34
                for it in _itens(col.get("itens")):
                    h += len(quebrar(it["txt"], "medio", f, cw - 36 - 40)) * f * 1.2 + 18
                if h > H - 36 - y0 - 10:
                    ok = False
            if ok:
                tam_it = f
                break
        for k, lado in enumerate(("esq", "dir")):
            col = d.get(lado, {})
            x0 = M + k * (cw + gap)
            pc = prog(t, col.get("t"))
            if pc <= 0:
                continue
            bom = lado == "dir"
            fundo_c = mix(pal["bg"], pal["cartao"], pc)
            dy = 14 * (1 - sai(pc))
            tl.ret(x0, y0 + dy, x0 + cw, H - 36 + dy, fundo_c, raio=20,
                   borda=mix(pal["bg"], pal["acento"] if bom else pal["linha"], pc), larg=3 if bom else 2)
            cor_tit = pal["acento"] if bom else pal["fraco"]
            tam, linhas = caber(col.get("titulo", ""), "xbold", 30, cw - 36, 2, 24)
            y = y0 + 24 + dy
            y += tl.bloco(x0 + 18, y, linhas, "xbold", tam, mix(pal["bg"], cor_tit, pc), entre=1.15,
                          alinhar="centro", largura=cw - 36)
            tl.ret(x0 + cw / 2 - 24, y + 10 + dy * 0, x0 + cw / 2 + 24, y + 14, mix(pal["bg"], cor_tit, pc), raio=2)
            y += 34
            for it in _itens(col.get("itens")):
                pi = prog(t, it["t"]) * pc
                if pi <= 0:
                    continue
                tam, linhas = tam_it, quebrar(it["txt"], "medio", tam_it, cw - 36 - 40)
                ox = 12 * (1 - sai(pi))
                ic = y + tam * 0.62
                if bom:
                    tl.circ(x0 + 32 + ox, ic, 14, mix(fundo_c, pal["acento"], pi))
                    tl.check(x0 + 32 + ox, ic, 18, mix(fundo_c, CREME, pi), 3.4)
                else:
                    tl.circ(x0 + 32 + ox, ic, 14, mix(fundo_c, pal["apagado"], pi))
                    tl.xis(x0 + 32 + ox, ic, 22, mix(fundo_c, pal["fraco"], pi), 3.2)
                h = tl.bloco(x0 + 56 + ox, y, linhas, "medio", tam, mix(fundo_c, pal["fg"], pi), entre=1.2)
                y += h + 18

    # ---- ciclo
    def _m_ciclo(self, tl, t):
        d, pal, W, H = self.d, self.pal, self.W, self.H
        y0 = cabecalho(tl, pal, d.get("titulo"), W)
        etapas = _itens(d.get("etapas"))
        n = max(2, len(etapas))
        cxc = W / 2
        cyc = y0 + (H - 30 - y0) / 2
        R = min(W / 2 - M - 78, (H - 30 - y0) / 2 - 48)
        angs = [-math.pi / 2 + 2 * math.pi * i / n for i in range(n)]
        acesos = [prog(t, e["t"]) for e in etapas]
        # anel
        tl.circ(cxc, cyc, R, None, borda=pal["apagado"], larg=4)
        for i in range(len(etapas)):
            j = (i + 1) % len(etapas)
            p = min(acesos[i], acesos[j])
            if p > 0:
                a0 = math.degrees(angs[i]) + 360 / n * 0.2
                a1 = a0 + (360 / n * 0.6) * sai(p)
                tl.arco(cxc, cyc, R, a0, a1, pal["acento"], 6)
            # ponta da seta no meio do arco
            am = angs[i] + (2 * math.pi / n) * 0.62
            px, py = cxc + R * math.cos(am), cyc + R * math.sin(am)
            tg = am + math.pi / 2
            cor = pal["acento"] if p >= 1 else pal["apagado"]
            tl.poli([(px + math.cos(tg) * 13, py + math.sin(tg) * 13),
                     (px + math.cos(tg + 2.4) * 12, py + math.sin(tg + 2.4) * 12),
                     (px + math.cos(tg - 2.4) * 12, py + math.sin(tg - 2.4) * 12)], cor)
        # pontinho girando
        if any(a > 0 for a in acesos) or not etapas:
            a = -math.pi / 2 + 2 * math.pi * ((t % 4.0) / 4.0)
            tl.circ(cxc + R * math.cos(a), cyc + R * math.sin(a), 10, pal["acento"], borda=CREME, larg=3)
        if d.get("centro"):
            tam, linhas = caber(d["centro"], "mao", 40, R * 1.3, 3, 30)
            h = tam * 1.05 * len(linhas)
            tl.bloco(cxc - R * 0.65, cyc - h / 2, linhas, "mao", tam, pal["fraco"], entre=1.05, alinhar="centro",
                     largura=R * 1.3)
        for i, e in enumerate(etapas):
            p = acesos[i]
            x, y = cxc + R * math.cos(angs[i]), cyc + R * math.sin(angs[i])
            tam, linhas = caber(e["txt"], "bold", 28, 210, 2, 26)
            tw = max(medir(l, "bold", tam) for l in linhas) + 40
            th = tam * 1.2 * len(linhas) + 26
            x = min(max(x, 16 + tw / 2 + 4), W - 16 - tw / 2 - 4)
            s = 1 + 0.15 * math.sin(math.pi * p) if 0 < p < 1 else 1
            tw, th = tw * s, th * s
            fill = mix(pal["cartao"], pal["acento"], suave(p))
            tl.ret(x - tw / 2, y - th / 2, x + tw / 2, y + th / 2, fill, raio=th / 2 if len(linhas) == 1 else 18,
                   borda=mix(pal["apagado"], pal["acento"], p), larg=2)
            tl.bloco(x - tw / 2, y - tam * 1.2 * len(linhas) * s / 2, linhas, "bold", tam * s,
                     mix(pal["apagado_txt"], CREME if pal["bg"] == AZUL_NOITE or p > 0.5 else pal["fg"], p),
                     entre=1.2, alinhar="centro", largura=tw)

    # ---- funil
    def _m_funil(self, tl, t):
        d, pal, W, H = self.d, self.pal, self.W, self.H
        y0 = cabecalho(tl, pal, d.get("titulo"), W)
        etapas = _itens(d.get("etapas"))
        n = max(1, len(etapas))
        topo_w, base_w = W - 2 * M, 250
        gap = 10
        alt_total = H - 40 - y0
        h = min(112, (alt_total - gap * (n - 1)) / n)
        ytop = y0 + (alt_total - (h * n + gap * (n - 1))) / 2
        tot = h * n + gap * (n - 1)
        def larg(y):
            return topo_w + (base_w - topo_w) * ((y - ytop) / tot)
        for i, e in enumerate(etapas):
            p = prog(t, e["t"])
            if p <= 0:
                continue
            ya = ytop + i * (h + gap)
            yb = ya + h
            dy = -22 * (1 - sai(p))
            wa, wb = larg(ya), larg(yb)
            cor = mix(LARANJA, (120, 40, 40), i / max(1, n) * 0.55)
            cor = mix(pal["bg"], cor, suave(p))
            tl.poli([(W / 2 - wa / 2, ya + dy), (W / 2 + wa / 2, ya + dy), (W / 2 + wb / 2, yb + dy), (W / 2 - wb / 2, yb + dy)], cor)
            sub = e.get("sub")
            tam, linhas = caber(e["txt"], "xbold", 32, wb - 40, 1, 24)
            cy = (ya + yb) / 2 + dy
            if sub and h >= 84:
                tl.texto(W / 2, cy - 14, linhas[0], "xbold", tam, mix(cor, CREME, p), anchor="mm")
                tam2, l2 = caber(sub, "medio", 26, wb - 30, 1, 22)
                tl.texto(W / 2, cy + 20, l2[0], "medio", tam2, mix(cor, (255, 236, 225), p), anchor="mm")
            else:
                tl.texto(W / 2, cy, linhas[0], "xbold", tam, mix(cor, CREME, p), anchor="mm")

    # ---- analogia
    def _m_analogia(self, tl, t):
        """Personagens em coluna (de cima pra baixo), cada um com nome e ação ao lado; seta entre eles."""
        d, pal, W, H = self.d, self.pal, self.W, self.H
        y0 = cabecalho(tl, pal, d.get("titulo"), W)
        pers = d.get("personagens", [])
        n = max(1, len(pers))
        setas = d.get("setas", [])
        gap_h = 58 if n <= 3 else 34
        area = H - 26 - y0
        row_h = (area - (n - 1) * gap_h) / n
        s = min(1.12, row_h / 186)
        cx = M + 64 * s + 4
        tx = M + 150 * s + 22
        larg_txt = W - M - tx
        tops = [y0 + i * (row_h + gap_h) for i in range(n)]
        for i in range(n - 1):
            p = prog(t, pers[i + 1].get("t"), 0.55)
            if p <= 0:
                continue
            ya, yb = tops[i] + row_h - 6, tops[i + 1] + 8
            xa = tx + 16
            tl.seta(xa, ya, xa, yb, pal["acento"], larg=5, ponta=15, prog_=sai(p))
            if i < len(setas) and setas[i]:
                tam, ls = caber(setas[i], "mao", 34, larg_txt - 44, 1, 28)
                tl.texto(xa + 26, (ya + yb) / 2, ls[0], "mao", tam, mix(pal["bg"], pal["fraco"], p), anchor="lm")
        for i, ps in enumerate(pers):
            p = prog(t, ps.get("t"), 0.5)
            if p <= 0:
                continue
            top = tops[i]
            pe = top + row_h - 20 * s
            cor, cabelo = cor_personagem(ps.get("nome", ""))
            bob = 3.5 * math.sin(2 * math.pi * (t / 1.6 + i * 0.37)) * s
            esc = s * (0.4 + 0.6 * mola(p))
            hy = boneco(tl, cx, pe + bob, esc, cor, cabelo, pal)
            ic = ps.get("icone")
            if ic and ic != "nenhum":
                ir = 27 * s
                ix, iy = cx + 54 * s, hy - 34 * s + bob * 0.5
                tl.circ(ix - 20 * s, iy + 22 * s, 5 * s, CREME)
                icone(tl, ic, ix, iy, ir * (0.5 + 0.5 * mola(p)), pal)
            dx = 14 * (1 - sai(p))
            acao = ps.get("acao")
            tam, ls = caber(acao or "", "medio", 31, larg_txt, 2, 26) if acao else (31, [])
            nome_h = 50
            bloco_h = nome_h + tam * 1.18 * len(ls)
            yc = top + row_h / 2 - bloco_h / 2
            tl.texto(tx + dx, yc + nome_h / 2, ps.get("nome", ""), "mao", 50, mix(pal["bg"], cor, p), anchor="lm")
            if ls:
                tl.bloco(tx + dx, yc + nome_h, ls, "medio", tam, mix(pal["bg"], pal["fg"], p), entre=1.18)

    # ---- equivale
    def _m_equivale(self, tl, t):
        d, pal, W, H = self.d, self.pal, self.W, self.H
        y0 = cabecalho(tl, pal, d.get("titulo"), W)
        pares = d.get("pares", [])
        n = max(1, len(pares))
        grande = n == 1
        k = 1.35 if grande else 1.0
        wa = (W - 2 * M) * 0.38
        weq = 64 * k
        wb = W - 2 * M - wa - weq
        row = (128 if not grande else 200)
        tot = row * n + 50
        ytop = y0 + max(0, (H - 30 - y0 - tot) / 2)
        p_lab = max([prog(t, p.get("t")) for p in pares] or [1])
        cl = mix(pal["bg"], pal["fraco"], p_lab)
        tl.texto(M + wa / 2, ytop + 18, d.get("rotulo_a", "no slide"), "mao", 36, cl, anchor="mm")
        tl.texto(M + wa + weq + wb / 2, ytop + 18, d.get("rotulo_b", "quer dizer"), "mao", 36, cl, anchor="mm")
        y = ytop + 50
        for pr_ in pares:
            ti = pr_.get("t")
            p1 = prog(t, ti)
            p2 = prog(t, None if ti is None else ti + 0.35)
            hh = row - 26
            cy = y + hh / 2
            if p1 > 0:
                s = 0.85 + 0.15 * mola(p1)
                tam, ls = caber(pr_.get("a", ""), "xbold", 40 * k, wa - 30, 2, 26)
                bw, bh = wa * s, hh * s
                tl.ret(M + wa / 2 - bw / 2, cy - bh / 2, M + wa / 2 + bw / 2, cy + bh / 2, mix(pal["bg"], CREME, p1), raio=20,
                       borda=mix(pal["bg"], pal["linha"], p1) if pal["bg"] == CREME else None, larg=2)
                tl.bloco(M + 15, cy - tam * 1.12 * len(ls) / 2, ls, "xbold", tam * s, mix(pal["bg"], TEXTO, p1),
                         entre=1.12, alinhar="centro", largura=wa - 30)
            if p2 > 0:
                tl.texto(M + wa + weq / 2, cy, "=", "xbold", 64 * k * (0.6 + 0.4 * mola(p2)), mix(pal["bg"], pal["acento"], p2),
                         anchor="mm")
                dx = 30 * (1 - sai(p2))
                tam, ls = caber(pr_.get("b", ""), "bold", 34 * k, wb - 34, 3, 26)
                x0 = M + wa + weq + dx
                tl.ret(x0, cy - hh / 2, x0 + wb, cy + hh / 2, mix(pal["bg"], pal["acento"], p2), raio=20)
                tl.bloco(x0 + 17, cy - tam * 1.15 * len(ls) / 2, ls, "bold", tam, mix(pal["acento"], CREME, p2),
                         entre=1.15, alinhar="centro", largura=wb - 34)
            y += row

    # ---- lista
    def _m_lista(self, tl, t):
        d, pal, W, H = self.d, self.pal, self.W, self.H
        y0 = cabecalho(tl, pal, d.get("titulo"), W)
        itens = _itens(d.get("itens"))
        tam = 36
        larg = W - 2 * M - 60
        while True:
            esp = tam * 0.9
            blocos = [quebrar(it["txt"], "medio", tam, larg) for it in itens]
            tot = sum(len(b) * tam * 1.22 + esp for b in blocos) - esp
            if tot <= H - 40 - y0 or tam <= 26:
                break
            tam -= 2
        y = y0 + max(0, (H - 40 - y0 - tot) / 2 * 0.7)
        for it, ls in zip(itens, blocos):
            p = prog(t, it["t"], 0.4)
            pc = prog(t, None if it["t"] is None else it["t"] + 0.3, 0.4)
            h = len(ls) * tam * 1.22
            if p > 0:
                dx = 16 * (1 - sai(p))
                cy = y + tam * 0.61
                bx = M + 18 + dx
                b = 15 + tam * 0.06
                tl.ret(bx - b, cy - b, bx + b, cy + b, mix(pal["bg"], pal["acento"], pc),
                       raio=7, borda=mix(pal["bg"], pal["acento"], p), larg=3)
                tl.check(bx, cy + 1, b * 1.4, CREME, 4, prog_=pc)
                tl.bloco(M + 60 + dx, y, ls, "medio", tam, mix(pal["bg"], pal["fg"], p), entre=1.22)
            y += h + esp

    # ---- numero
    def _m_numero(self, tl, t):
        d, pal, W, H = self.d, self.pal, self.W, self.H
        y0 = cabecalho(tl, pal, d.get("titulo"), W)
        ti = d.get("t")
        p = prog(t, ti, 0.5)
        valor = str(d.get("valor", ""))
        if d.get("contar") and valor.strip().isdigit():
            pc = prog(t, ti, 0.9)
            valor = str(int(round(int(valor) * sai(pc))))
        tam = 190
        while medir(valor, "xbold", tam) > W - 2 * M and tam > 60:
            tam -= 6
        cy = y0 + (H - y0) * 0.36
        if p > 0:
            s = 0.6 + 0.4 * mola(p)
            if 0 < p < 1:
                for k in range(10):
                    a = 2 * math.pi * k / 10 + 0.3
                    r0, r1 = tam * 0.62 + 50 * p, tam * 0.62 + 50 * p + 26 * (1 - p)
                    tl.linha([(W / 2 + math.cos(a) * r0 * 1.4, cy + math.sin(a) * r0),
                              (W / 2 + math.cos(a) * r1 * 1.4, cy + math.sin(a) * r1)], mix(pal["bg"], pal["acento"], 1 - p), 5)
            tl.texto(W / 2, cy, valor, "xbold", tam * s, mix(pal["bg"], pal["acento"], suave(p * 1.5)), anchor="mm")
        p2 = prog(t, None if ti is None else ti + 0.3, 0.45)
        if p2 > 0:
            yl = cy + tam * 0.55 + 16
            tl.ret(W / 2 - 36, yl, W / 2 + 36, yl + 5, mix(pal["bg"], pal["acento"], p2), raio=2)
            tam2, ls = caber(d.get("rotulo", ""), "bold", 38, W - 2 * M, 3, 26)
            tl.bloco(M, yl + 26 + 10 * (1 - sai(p2)), ls, "bold", tam2, mix(pal["bg"], pal["fg"], p2), entre=1.2,
                     alinhar="centro", largura=W - 2 * M)
