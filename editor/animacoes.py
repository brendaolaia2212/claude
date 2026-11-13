"""Animações 2D nos momentos fortes (motion). Cada uma vira um .mov com transparência."""
import math
import re
import subprocess

from PIL import Image, ImageDraw

from .base import (FPS, LARGURA, ZONA_X, ZONA_Y, cor, cor_painel, ease_out, fonte, quadros,
                   texto_escuro_sobre)
from .estilos import BRANCO, ESCURO, PRETO, _bloco_palavras, _medir, _recortar, sombra

ENTRADA, SAIDA = 0.3, 0.2
TIPOS = ["impacto", "lista", "passo", "numero", "notificacao", "carimbo", "destaque",
         "comentario", "barra", "chamada"]


def _colar(tela, img, cx, cy, escala=1.0, alfa=1.0):
    if escala <= 0.01 or alfa <= 0.01:
        return
    if abs(escala - 1) > 0.005:
        img = img.resize((max(1, int(img.width * escala)), max(1, int(img.height * escala))),
                         Image.BICUBIC)
    if alfa < 0.999:
        a = img.getchannel("A").point(lambda v: int(v * alfa))
        img = img.copy()
        img.putalpha(a)
    tela.alpha_composite(img, (int(cx - img.width / 2), int(cy - img.height / 2)))


def _alfa_saida(t, dur):
    return 1.0 - min(1.0, max(0.0, (t - dur) / SAIDA))


def _cartao(W, H, tema="escuro", raio=28, cor_fundo=None):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    fundo = cor_painel(cor_fundo, (18, 18, 22), 235) if tema == "escuro" else (255, 255, 255, 245)
    ImageDraw.Draw(img).rounded_rectangle([0, 0, W - 1, H - 1], raio, fill=fundo)
    return img


def _texto(t, f, c, sw=0, csw=PRETO):
    return _recortar(_bloco_palavras([t], [f], [c], sw, csw, 0, larg_max=5000, entrelinha=1.0))


def _texto_quebrado(t, f, c, larg):
    ps = t.split()
    return _recortar(_bloco_palavras(ps, [f] * len(ps), [c] * len(ps), 0, PRETO, 14,
                                     alinhar="esquerda", larg_max=larg))


# ---------- receitas: cada uma devolve (largura, altura, desenhar(t) -> Image, sons) ----------

def r_impacto(a, c, dur):
    txt = a["texto"].upper()
    tam = 190
    while _medir(fonte("anton", tam), txt, 8)[0] > ZONA_X[1] - ZONA_X[0] and tam > 80:
        tam -= 10
    img = sombra(_texto(txt, fonte("anton", tam), c, 8, PRETO), 14, (0, 8), 120)
    W, H = int(img.width * 1.15), int(img.height * 1.15)

    def desenhar(t):
        tela = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        if t < 0.15:
            e = 0.6 + 0.48 * ease_out(t / 0.15)
        elif t < 0.3:
            e = 1.08 - 0.08 * ease_out((t - 0.15) / 0.15)
        else:
            e = 1.0
        q = int(t * FPS) - int(0.3 * FPS)
        dx = [3, -2, 2][q] if 0 <= q < 3 else 0
        _colar(tela, img, W / 2 + dx, H / 2, e, min(1, t / 0.08) * _alfa_saida(t, dur))
        return tela
    return W, H, desenhar, [("impacto", 0.0, -11)]


def r_lista(a, c, dur):
    tema = a.get("tema", "escuro")
    cor_txt = BRANCO if tema == "escuro" else ESCURO
    f = fonte("montserrat", 50, 800)
    itens = a["itens"][:4]
    W = ZONA_X[1] - ZONA_X[0]
    linhas = [_texto_quebrado(i["texto"], f, cor_txt, W - 170) for i in itens]
    titulo = _texto(a["titulo"], fonte("montserrat", 40, 700), c) if a.get("titulo") else None
    topo = 44 + (titulo.height + 26 if titulo else 0)
    alturas = [max(70, l.height) for l in linhas]
    H = topo + sum(alturas) + 30 * (len(linhas) - 1) + 44
    base = _cartao(W, H, tema, cor_fundo=a.get("fundo"))
    if titulo:
        base.alpha_composite(titulo, (48, 40))
    tempos = [i["t"] - a["inicio"] for i in itens]
    M = 40

    def desenhar(t):
        tela = Image.new("RGBA", (W + 2 * M, H + 2 * M), (0, 0, 0, 0))
        card = base.copy()
        d = ImageDraw.Draw(card)
        y = topo
        for k, l in enumerate(linhas):
            dt = t - tempos[k] + 0.1
            if dt > 0:
                p = ease_out(dt / 0.2)
                x = 130 - 40 * (1 - p)
                camada = Image.new("RGBA", card.size, (0, 0, 0, 0))
                _colar(camada, l, x + l.width / 2, y + alturas[k] / 2, 1, p)
                card.alpha_composite(camada)
                cx, cy, r = 72, y + alturas[k] / 2, 26
                arco = min(1.0, dt / 0.2) * 360
                d.arc([cx - r, cy - r, cx + r, cy + r], -90, -90 + arco, fill=c, width=7)
                if dt > 0.2:
                    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=c)
                    ck = texto_escuro_sobre(c)
                    d.line([(cx - 12, cy + 1), (cx - 3, cy + 10), (cx + 13, cy - 9)], fill=ck, width=7)
            y += alturas[k] + 30
        p = ease_out(t / ENTRADA)
        _colar(tela, sombra(card, 16, (0, 10), 90), (W + 2 * M) / 2, (H + 2 * M) / 2 + 30 * (1 - p),
               1, p * _alfa_saida(t, dur))
        return tela
    sons = [("pop", max(0.0, tk), -17) for tk in tempos]
    return W + 2 * M, H + 2 * M, desenhar, sons


def r_passo(a, c, dur):
    passos = a["passos"]
    f = fonte("montserrat", 46, 800)
    pilulas = []
    for k, p in enumerate(passos):
        t = _texto(f"PASSO {k + 1} · {p['nome'].upper()}", f, texto_escuro_sobre(c))
        img = Image.new("RGBA", (t.width + 70, t.height + 44), (0, 0, 0, 0))
        ImageDraw.Draw(img).rounded_rectangle([0, 0, img.width - 1, img.height - 1], img.height // 2, fill=c)
        img.alpha_composite(t, (35, 22))
        pilulas.append(sombra(img, 12, (0, 6), 90))
    W = max(p.width for p in pilulas)
    H = max(p.height for p in pilulas) + 80
    tempos = [p["t"] - a["inicio"] for p in passos]

    def desenhar(t):
        tela = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        k = max([i for i, tk in enumerate(tempos) if t >= tk - 0.1] or [0])
        dt = t - tempos[k] + 0.1
        p = ease_out(dt / 0.25)
        _colar(tela, pilulas[k], W / 2, H / 2 - 60 * (1 - p), 1, p * _alfa_saida(t, dur))
        return tela
    return W, H, desenhar, [("swish", max(0.0, tk), -17) for tk in tempos]


def _formatar_numero(modelo, valor):
    digitos = re.sub(r"\D", "", modelo)
    s = str(int(valor)).zfill(len(digitos) if digitos.startswith("0") else 1)
    if "." in modelo and len(s) > 3:
        s = f"{int(valor):,}".replace(",", ".")
    return re.sub(r"[\d.]+", s, modelo, count=1)


def r_numero(a, c, dur):
    modelo = str(a["valor"])
    alvo = int(re.sub(r"\D", "", modelo) or 0)
    fn, fr = fonte("anton", 230), fonte("montserrat", 50, 800)
    maior = _texto(_formatar_numero(modelo, alvo), fn, c, 8, PRETO)
    rot = _texto(a.get("rotulo", "").upper(), fr, BRANCO, 5, PRETO) if a.get("rotulo") else None
    W = max(maior.width, rot.width if rot else 0) + 120
    H = maior.height + (rot.height + 30 if rot else 0) + 100

    def desenhar(t):
        tela = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        v = alvo * ease_out(t / 0.8)
        num = _texto(_formatar_numero(modelo, round(v)), fn, c, 8, PRETO)
        al = min(1, t / 0.12) * _alfa_saida(t, dur)
        _colar(tela, sombra(num, 12, (0, 8), 110), W / 2, 50 + maior.height / 2 + 40, 1, al)
        if rot:
            _colar(tela, rot, W / 2, H - 50 - rot.height / 2, 1, al)
        return tela
    return W, H, desenhar, [("tique", 0.0, -20), ("pop", 0.8, -16)]


def r_notificacao(a, c, dur):
    W = ZONA_X[1] - ZONA_X[0]
    ft, fx = fonte("montserrat", 40, 800), fonte("montserrat", 36, 500)
    tit = _texto(a.get("titulo", "Nova mensagem"), ft, ESCURO)
    txt = _texto_quebrado(a.get("texto", ""), fx, (70, 70, 75, 255), W - 190) if a.get("texto") else None
    H = 60 + tit.height + (txt.height + 14 if txt else 0) + 40
    card = _cartao(W, max(H, 150), "claro", 32)
    d = ImageDraw.Draw(card)
    d.ellipse([34, 34, 114, 114], fill=c)
    letra = _texto((a.get("icone") or a.get("titulo", "N"))[0].upper(), fonte("montserrat", 44, 900),
                   texto_escuro_sobre(c))
    card.alpha_composite(letra, (74 - letra.width // 2, 74 - letra.height // 2))
    card.alpha_composite(tit, (140, 44))
    if txt:
        card.alpha_composite(txt, (140, 44 + tit.height + 14))
    card = sombra(card, 18, (0, 10), 100)
    H2 = card.height + 260

    def desenhar(t):
        tela = Image.new("RGBA", (card.width, H2), (0, 0, 0, 0))
        p = ease_out(t / 0.35)
        sai = max(0.0, (t - dur) / SAIDA)
        y = -card.height / 2 + (260 + card.height / 2) * p - 260 * sai
        _colar(tela, card, card.width / 2, y + card.height / 2 - 0, 1, 1 - sai * 0.5)
        return tela
    return card.width, H2, desenhar, [("ding", 0.25, -14)]


EMOJI_FONTE = "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"


def _emoji(e, tam):
    """Emoji colorido (Noto Color Emoji) no tamanho pedido."""
    from PIL import ImageFont
    f = ImageFont.truetype(EMOJI_FONTE, 109)
    img = Image.new("RGBA", (150, 150), (0, 0, 0, 0))
    ImageDraw.Draw(img).text((8, 8), e, font=f, embedded_color=True)
    img = img.crop(img.getchannel("A").getbbox() or (0, 0, 150, 150))
    k = tam / max(img.size)
    return img.resize((max(1, int(img.width * k)), max(1, int(img.height * k))), Image.LANCZOS)


def r_carimbo(a, c, dur):
    """Carimbo. cheio=True: selo preenchido na cor (texto branco), com emoji opcional
    ao lado e um som próprio por cima da batida (ex.: APROVADO verde + "aprovado")."""
    tinta = (220, 38, 38, 255) if a.get("vermelho") else c
    if a.get("cheio"):
        t = _texto(a["texto"].upper(), fonte("anton", 118), texto_escuro_sobre(tinta))
        emo = _emoji(a["emoji"], 120) if a.get("emoji") else None
        W = t.width + 100 + (emo.width + 26 if emo else 0)
        H = max(t.height, emo.height if emo else 0) + 64
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(img).rounded_rectangle([0, 0, W - 1, H - 1], 26, fill=tinta)
        ImageDraw.Draw(img).rounded_rectangle([10, 10, W - 11, H - 11], 20, outline=(255, 255, 255, 230), width=6)
        x = 50
        if emo:
            img.alpha_composite(emo, (x, (H - emo.height) // 2))
            x += emo.width + 26
        img.alpha_composite(t, (x, (H - t.height) // 2))
        img = sombra(img, 18, (0, 10), 140)
    else:
        t = _texto(a["texto"].upper(), fonte("anton", 120), tinta)
        W, H = t.width + 90, t.height + 70
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(img).rounded_rectangle([6, 6, W - 7, H - 7], 18, outline=tinta, width=12)
        img.alpha_composite(t, (45, 35))
    img = img.rotate(a.get("giro", 8), expand=True, resample=Image.BICUBIC)
    S = int(max(img.size) * 1.7)

    def desenhar(tt):
        tela = Image.new("RGBA", (S, S), (0, 0, 0, 0))
        if tt < 0.18:
            e = 1.6 - 0.6 * ease_out(tt / 0.18)
            al = min(1, tt / 0.06)
        elif tt < 0.24:
            e, al = 1.05, 1
        else:
            e, al = 1.0, 1
        q = int(tt * FPS) - int(0.18 * FPS)
        dx, dy = ([(6, -4), (-5, 3), (3, -2), (-2, 1)][q] if 0 <= q < 4 else (0, 0))
        _colar(tela, img, S / 2 + dx, S / 2 + dy, e, al * _alfa_saida(tt, dur))
        return tela
    sons = [("impacto_seco", 0.12, -11)]
    if a.get("som"):
        sons.append((a["som"], 0.16, a.get("db", -13), True))
    return S, S, desenhar, sons


def r_destaque(a, c, dur):
    r = int(a.get("raio", 130))
    seta = a.get("forma") == "seta"
    W = H = 2 * r + 80

    def desenhar(t):
        tela = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(tela)
        p = ease_out(t / 0.4)
        al = int(255 * _alfa_saida(t, dur))
        cc = c[:3] + (al,)
        if seta:
            x0, y0, x1, y1 = 30, H - 30, W / 2 + r * 0.25, H / 2 + r * 0.25
            xe, ye = x0 + (x1 - x0) * p, y0 + (y1 - y0) * p
            d.line([(x0, y0), (xe, ye)], fill=cc, width=10)
            if p > 0.95:
                ang = math.atan2(y1 - y0, x1 - x0)
                for s in (2.5, -2.5):
                    d.line([(x1, y1), (x1 - 46 * math.cos(ang + s / 4), y1 - 46 * math.sin(ang + s / 4))],
                           fill=cc, width=10)
        else:
            caixa = [40, 40 + r * 0.12, W - 40, H - 40 - r * 0.12]
            d.arc(caixa, -100, -100 + 370 * p, fill=cc, width=10)
        return tela
    return W, H, desenhar, [("rabisco", 0.0, -17)]


def r_comentario(a, c, dur):
    W = ZONA_X[1] - ZONA_X[0]
    f = fonte("montserrat", 46, 700)
    texto = a["texto"]
    H = 150
    digitar = len(texto) * 0.05

    def desenhar(t):
        card = _cartao(W, H, "claro", H // 2)
        d = ImageDraw.Draw(card)
        n = int(max(0.0, t - 0.25) / 0.05)
        vis = texto[:n]
        if vis:
            tx = _texto(vis, f, ESCURO)
            card.alpha_composite(tx, (60, H // 2 - tx.height // 2))
            cur = 60 + tx.width + 6
        else:
            ph = _texto("Adicione um comentário...", fonte("montserrat", 40, 500), (150, 150, 155, 255))
            card.alpha_composite(ph, (60, H // 2 - ph.height // 2))
            cur = 60
        if int(t * 2) % 2 == 0 and n < len(texto):
            d.line([(cur, H // 2 - 28), (cur, H // 2 + 28)], fill=ESCURO, width=4)
        fim = 0.25 + digitar
        pisca = fim < t < fim + 0.6 and int((t - fim) * 8) % 2 == 0
        bc = c if (pisca or t >= fim + 0.6) else (200, 200, 205, 255)
        d.ellipse([W - 130, 25, W - 30, 125], fill=bc)
        d.polygon([(W - 98, 52), (W - 98, 98), (W - 56, 75)], fill=texto_escuro_sobre(bc))
        tela = Image.new("RGBA", (W + 80, H + 80), (0, 0, 0, 0))
        p = ease_out(t / ENTRADA)
        _colar(tela, sombra(card, 14, (0, 8), 90), (W + 80) / 2, (H + 80) / 2 + 40 * (1 - p), 1,
               p * _alfa_saida(t, dur))
        return tela
    return W + 80, H + 80, desenhar, [("teclado", 0.25, -19), ("clique", 0.25 + digitar + 0.6, -15)]


def r_barra(a, c, dur):
    W = ZONA_X[1] - ZONA_X[0]
    rot = _texto(a.get("rotulo", "").upper(), fonte("montserrat", 46, 800), BRANCO, 4, PRETO)
    ate = float(a.get("ate", 100)) / 100
    H = rot.height + 140

    def desenhar(t):
        tela = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(tela)
        al = min(1, t / 0.12) * _alfa_saida(t, dur)
        tela.alpha_composite(rot, ((W - rot.width) // 2, 10))
        y0 = rot.height + 50
        d.rounded_rectangle([0, y0, W - 1, y0 + 56], 28, fill=(255, 255, 255, 70), outline=BRANCO, width=4)
        p = ease_out(max(0.0, t - 0.1) / 0.6) * ate
        if p > 0.02:
            d.rounded_rectangle([6, y0 + 6, 6 + (W - 13) * p, y0 + 50], 22, fill=c)
        if al < 1:
            tela.putalpha(tela.getchannel("A").point(lambda v: int(v * al)))
        return tela
    return W, H, desenhar, [("whoosh_sobe", 0.05, -17)]


def r_emoji(a, c, dur):
    """Emoji que pula na tela: cresce passando do ponto, balança e flutua um pouquinho."""
    img = _emoji(a["emoji"], a.get("tam", 240))
    W = H = int(max(img.size) * 1.6)
    giro = a.get("giro", 10)

    def desenhar(t):
        tela = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        if t < 0.12:
            e = 1.25 * ease_out(t / 0.12)
        elif t < 0.22:
            e = 1.25 - 0.32 * ease_out((t - 0.12) / 0.1)
        elif t < 0.32:
            e = 0.93 + 0.07 * ease_out((t - 0.22) / 0.1)
        else:
            e = 1.0 + 0.03 * math.sin((t - 0.32) * 5)
        ang = giro * math.sin(t * 9) * math.exp(-t * 2.2)
        b = img.rotate(ang, expand=True, resample=Image.BICUBIC) if abs(ang) > 0.3 else img
        _colar(tela, b, W / 2, H / 2 - 14 * min(1, t / max(0.5, dur)), e, _alfa_saida(t, dur))
        return tela
    som = a.get("som", "pop")
    return W, H, desenhar, ([(som, 0.0, a.get("db", -15))] if som else [])


def r_chuva(a, c, dur):
    """Chuva de emoji pela tela inteira: "sobe" (corações subindo), "cai" ou "explode"
    (estouro a partir de um ponto)."""
    import random
    rnd = random.Random(a.get("semente", 7))
    n = a.get("n", 14)
    modo = a.get("modo", "sobe")
    base = _emoji(a["emoji"], 150)
    W, H = LARGURA, 1920
    cx, cy = a.get("cx", W / 2), a.get("cy", H * 0.55)
    ps = []
    for _ in range(n):
        tam = rnd.uniform(0.45, 1.0)
        img = base.resize((int(base.width * tam), int(base.height * tam)), Image.LANCZOS)
        if modo == "explode":
            ang = rnd.uniform(0, 2 * math.pi)
            v = rnd.uniform(700, 1300)
            ps.append((img, cx, cy, v * math.cos(ang), v * math.sin(ang) - 500, rnd.uniform(0, 0.12)))
        else:
            x = rnd.uniform(80, W - 80)
            y0 = H + 120 if modo == "sobe" else -120
            v = rnd.uniform(650, 1100) * (-1 if modo == "sobe" else 1)
            ps.append((img, x, y0, rnd.uniform(-40, 40), v, rnd.uniform(0, 0.6)))

    def desenhar(t):
        tela = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        for img, x0, y0, vx, vy, atraso in ps:
            tt = t - atraso
            if tt <= 0:
                continue
            if modo == "explode":
                x, y = x0 + vx * tt, y0 + vy * tt + 900 * tt * tt
                al = max(0.0, 1 - tt / 1.2)
            else:
                x, y = x0 + vx * tt + 30 * math.sin(tt * 4 + x0), y0 + vy * tt
                al = 1.0
            _colar(tela, img, x, y, 1.0, al * _alfa_saida(t, dur))
        return tela
    som = a.get("som", "brilho")
    return W, H, desenhar, ([(som, 0.0, a.get("db", -17))] if som else [])


def r_texto(a, c, dur):
    """Texto no estilo yap: serifa elegante (ou manuscrita), branco, sombra suave.
    a: texto (\\n quebra), fonte ("instrument", "instrument-italico", "kalam"), tam,
    sobre (linha manuscrita acima), sub (linha manuscrita abaixo), som."""
    from .estilos import _empilhar, _quebrar_simples
    larg = ZONA_X[1] - ZONA_X[0]
    nome_f = a.get("fonte", "instrument")
    tam = a.get("tam", 104)
    linhas = [l.strip() for l in a["texto"].split("\n") if l.strip()]
    f = fonte(nome_f, tam)
    while tam > 56 and any(_medir(f, l)[0] > larg for l in linhas) and len(linhas) > 1:
        tam -= 6
        f = fonte(nome_f, tam)
    partes = []
    if a.get("sobre"):
        partes.append(_texto(a["sobre"], fonte("kalam", 56), BRANCO))
    for l in linhas:
        for q in _quebrar_simples(l, f, larg):
            partes.append(_texto(q, f, BRANCO))
    if a.get("sub"):
        fk = fonte("kalam", 50)
        for q in _quebrar_simples(a["sub"], fk, larg - 40):
            partes.append(_texto(q, fk, BRANCO))
    from .estilos import halo
    img = halo(_empilhar(partes, 6))
    W, H = int(img.width * 1.1), int((img.height + 40) * 1.1)
    pulo = a.get("pulo", True)

    def desenhar(t):
        tela = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        p = ease_out(t / 0.4)
        if pulo:   # entra crescendo, passa um tiquinho do tamanho e assenta
            e = 0.86 + 0.2 * ease_out(t / 0.18) if t < 0.18 else 1.06 - 0.06 * ease_out((t - 0.18) / 0.16)
        else:
            e = 1.0
        _colar(tela, img, W / 2, H / 2 + 24 * (1 - p), e, min(1, t / 0.12) * _alfa_saida(t, dur))
        return tela
    som = a.get("som", "pop")
    return W, H, desenhar, ([(som, 0.0, a.get("db", -20))] if som else [])


def r_chamada(a, c, dur):
    W = ZONA_X[1] - ZONA_X[0]
    t = _texto_quebrado(a["texto"], fonte("montserrat", 58, 800), texto_escuro_sobre(c), W - 120)
    sub = _texto_quebrado(a["sub"], fonte("montserrat", 38, 600), texto_escuro_sobre(c), W - 120) \
        if a.get("sub") else None
    H = t.height + (sub.height + 18 if sub else 0) + 110
    card = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(card).rounded_rectangle([0, 0, W - 1, H - 1], 32, fill=c)
    card.alpha_composite(t, ((W - t.width) // 2, 55))
    if sub:
        card.alpha_composite(sub, ((W - sub.width) // 2, 55 + t.height + 18))
    card = sombra(card, 18, (0, 10), 110)

    def desenhar(tt):
        tela = Image.new("RGBA", card.size, (0, 0, 0, 0))
        p = ease_out(tt / ENTRADA)
        _colar(tela, card, card.width / 2, card.height / 2, 0.85 + 0.15 * p, p)
        return tela
    return card.width, card.height, desenhar, [("ding", 0.05, -15)]


def r_frase(a, c, dur):
    """Frase forte dela, em letras grandes, palavra por palavra no tempo da fala.

    a: palavras = [{"w": "palavra", "t": segundos desde o início}], tam (padrão 132),
    fonte ("instrument" | "archivo" | ...), fonte_destaque (padrão "instrument-italico"), destaques = [índices] (na cor de
    destaque), cor_ativa (a palavra recém-dita brilha um instante), som (padrão nenhum)."""
    from .estilos import halo
    larg = ZONA_X[1] - ZONA_X[0]
    pal = [dict(p) for p in a["palavras"] if p["w"].strip()]
    destaques = set(a.get("destaques", []))
    nome_f = a.get("fonte", "instrument")
    acento = cor(a.get("cor_destaque", "#F6D7A7"))
    tam = int(a.get("tam", 132))

    quebras = set(a.get("quebras", []))        # índice da palavra que abre cada linha nova

    def palavra(t, ff, cor_, fontes):
        """Palavra numa caixa de altura fixa (mesma linha de base pra todas): sem 'que' flutuando."""
        asc = max(x.getmetrics()[0] for x in fontes)
        desc = max(x.getmetrics()[1] for x in fontes)
        w = int(ff.getlength(t)) + 24
        im = Image.new("RGBA", (w, asc + desc + 8), (0, 0, 0, 0))
        ImageDraw.Draw(im).text((12, 4 + asc - ff.getmetrics()[0]), t, font=ff, fill=cor_)
        bb = im.getbbox()
        return im.crop((bb[0], 0, bb[2], im.height)) if bb else im

    def montar(tam):
        f, fi = fonte(nome_f, tam), fonte(a.get("fonte_destaque", "instrument-italico"), tam)
        esp = int(tam * 0.26)
        imgs = []
        for k, p in enumerate(pal):
            ff = fi if k in destaques else f
            t = p["w"]
            imgs.append((palavra(t, ff, acento if k in destaques else BRANCO, (f, fi)), ff))
        # quebra gulosa e depois equilibra (sem palavra sozinha na última linha)
        linhas, atual, w_at = [], [], 0
        for k, (im, _) in enumerate(imgs):
            w = im.width + (esp if atual else 0)
            if atual and (w_at + w > larg or k in quebras):
                linhas.append(atual)
                atual, w_at = [k], im.width
            else:
                atual.append(k)
                w_at += w
        if atual:
            linhas.append(atual)
        if not quebras and len(linhas) >= 2 and len(linhas[-1]) == 1 and len(linhas[-2]) > 2:
            linhas[-1].insert(0, linhas[-2].pop())
        return imgs, linhas, esp

    while True:
        imgs, linhas, esp = montar(tam)
        if len(linhas) <= 4 or tam <= 84:
            break
        tam -= 8
    alt_l = int(tam * 1.08)
    pad = 60
    W = larg + 2 * pad
    H = alt_l * len(linhas) + 2 * pad
    pos = {}
    for li, ks in enumerate(linhas):
        wl = sum(imgs[k][0].width for k in ks) + esp * (len(ks) - 1)
        x = pad + (larg - wl) / 2
        for k in ks:
            im = imgs[k][0]
            pos[k] = (x + im.width / 2, pad + li * alt_l + alt_l / 2)
            x += im.width + esp
    # cada palavra com o halo escuro do yap (legível em fundo claro)
    prontas = []
    for im, _ in imgs:
        tela = Image.new("RGBA", (im.width + 80, im.height + 80), (0, 0, 0, 0))
        tela.alpha_composite(im, (40, 40))
        prontas.append(halo(tela))
    ativa_c = cor(a.get("cor_ativa", "#FFE8C2"))
    brilho = []
    for k, (im, _) in enumerate(imgs):
        if k in destaques:
            brilho.append(None)
            continue
        b = Image.new("RGBA", (im.width + 80, im.height + 80), (0, 0, 0, 0))
        b.alpha_composite(palavra(pal[k]["w"], imgs[k][1], ativa_c, (fonte(nome_f, tam), fonte(a.get("fonte_destaque", "instrument-italico"), tam))), (40, 40))
        brilho.append(b)
    tempos = [max(0.0, p["t"]) for p in pal]

    def desenhar(t):
        tela = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        sai = _alfa_saida(t, dur)
        for k in range(len(pal)):
            dt = t - tempos[k]
            if dt < 0:
                continue
            p = ease_out(min(1.0, dt / 0.16))
            cx, cy = pos[k]
            _colar(tela, prontas[k], cx, cy + 22 * (1 - p), 0.92 + 0.08 * p, p * sai)
            if brilho[k] is not None and dt < 0.45:
                _colar(tela, brilho[k], cx, cy + 22 * (1 - p), 0.92 + 0.08 * p, (1 - dt / 0.45) * p * sai)
        return tela
    som = a.get("som")
    return W, H, desenhar, ([(som, 0.0, a.get("db", -18))] if som else [])


def r_polaroid(a, c, dur):
    """Foto instantânea de um momento do vídeo (a revelação do produto): moldura branca,
    legenda manuscrita, cai girando de leve, fica e sai. a: imagem (caminho), recorte
    [x0, y0, x1, y1] no quadro, legenda, giro, largura (px da foto), som (padrão nenhum)."""
    import random
    foto = Image.open(a["imagem"]).convert("RGB")
    if a.get("recorte"):
        foto = foto.crop(tuple(int(v) for v in a["recorte"]))
    lw = int(a.get("largura", 520))
    foto = foto.resize((lw, int(foto.height * lw / foto.width)), Image.LANCZOS)
    borda, base = int(lw * 0.06), int(lw * 0.24)
    card = Image.new("RGBA", (foto.width + 2 * borda, foto.height + borda + base), (250, 248, 244, 255))
    card.paste(foto, (borda, borda))
    if a.get("legenda"):
        t = _texto(a["legenda"], fonte("kalam", int(base * 0.42)), (40, 36, 34, 255))
        if t.width > card.width - 2 * borda:
            t = t.resize((card.width - 2 * borda, int(t.height * (card.width - 2 * borda) / t.width)), Image.LANCZOS)
        card.alpha_composite(t, ((card.width - t.width) // 2, foto.height + borda + (base - t.height) // 2))
    giro = float(a.get("giro", -6))
    card = sombra(card, 18, (0, 10), 120)
    W = H = int(max(card.width, card.height) * 1.25)

    def desenhar(t):
        tela = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        p = ease_out(min(1.0, t / 0.35))
        ang = giro * (0.4 + 0.6 * p) + (1 - p) * 12
        im = card.rotate(ang, expand=True, resample=Image.BICUBIC)
        _colar(tela, im, W / 2, H / 2 - 60 * (1 - p), 1.15 - 0.15 * p, min(1.0, t / 0.12) * _alfa_saida(t, dur))
        return tela
    som = a.get("som")
    return W, H, desenhar, ([(som, 0.0, a.get("db", -16))] if som else [])


RECEITAS = {"impacto": r_impacto, "lista": r_lista, "passo": r_passo, "numero": r_numero,
            "notificacao": r_notificacao, "carimbo": r_carimbo, "destaque": r_destaque,
            "comentario": r_comentario, "barra": r_barra, "chamada": r_chamada, "texto": r_texto,
            "emoji": r_emoji, "chuva": r_chuva, "frase": r_frase, "polaroid": r_polaroid}
POSICAO = {"impacto": "alto", "lista": "meio", "passo": "alto", "numero": "alto",
           "notificacao": "topo", "carimbo": "meio", "destaque": "ponto", "comentario": "baixo",
           "barra": "alto", "chamada": "meio", "texto": "meio", "emoji": "ponto", "chuva": "ponto", "frase": "meio", "polaroid": "ponto"}


def posicionar(tipo, W, H, a, zona_rosto):
    """(x, y) do canto da animação: dentro da zona segura e fora do rosto quando der."""
    if POSICAO[tipo] == "ponto":
        return int(a["x"] - W / 2), int(a["y"] - H / 2)
    x = (LARGURA - W) // 2
    if "y" in a:
        return x, int(a["y"] - H / 2)
    pref = {"topo": ZONA_Y[0] - 260 + 20, "alto": ZONA_Y[0] + 30,
            "meio": 960 - H // 2, "baixo": ZONA_Y[1] - H - 40}[POSICAO[tipo]]
    if POSICAO[tipo] == "topo" or not zona_rosto:
        return x, int(pref)
    _, z0, _, z1 = zona_rosto
    folga = 50 if tipo == "frase" else 20
    if pref + H <= z0 - folga or pref >= z1 + folga:
        return x, int(pref)
    cima, baixo = z0 - H - folga, z1 + folga
    opcoes = [y for y in (cima, baixo) if ZONA_Y[0] - 40 <= y and y + H <= ZONA_Y[1] + 40]
    if opcoes:
        return x, int(min(opcoes, key=lambda y: abs(y - pref)))
    return x, int(pref)


def renderizar(a, destaque, saida, zona_rosto=None, fundo=None):
    """Desenha a animação a 30 qps e grava um .mov com alfa. Devolve (x, y, sons, duração).
    fundo = cor dos cartões escuros (a animação pode trazer a sua em a["fundo"])."""
    a = dict(a, fundo=a.get("fundo") or fundo)
    tipo = a["tipo"]
    c = cor(a.get("cor") or destaque)
    parada = a["fim"] - a["inicio"]
    W, H, desenhar, sons = RECEITAS[tipo](a, c, parada)
    esc = float(a.get("escala", 1.0))       # maior (ex.: lista sozinha numa tela de explicação)
    W0, H0 = W, H
    if esc != 1.0:
        esc = min(esc, 1000 / W)
        W, H = int(W * esc), int(H * esc)
    W += W % 2
    H += H % 2
    total = quadros(parada + SAIDA) if tipo != "chamada" else quadros(parada)
    proc = subprocess.Popen(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo",
                             "-pix_fmt", "rgba", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                             "-c:v", "qtrle", "-pix_fmt", "argb", str(saida)], stdin=subprocess.PIPE)
    for q in range(total):
        img = desenhar(q / FPS)
        if esc != 1.0:
            if img.size != (W0, H0):
                base = Image.new("RGBA", (W0, H0), (0, 0, 0, 0))
                base.alpha_composite(img.crop((0, 0, min(W0, img.width), min(H0, img.height))))
                img = base
            img = img.resize((W, H), Image.LANCZOS)
        if img.size != (W, H):
            fundo = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            fundo.alpha_composite(img.crop((0, 0, min(W, img.width), min(H, img.height))))
            img = fundo
        proc.stdin.write(img.tobytes())
    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError(f"Falhou ao gravar a animação {tipo}")
    x, y = posicionar(tipo, W, H, a, zona_rosto)
    return x, y, W, H, sons, total / FPS


# ---------- achar os momentos na fala ----------

ENUM = r"\b(primeir[oa]|segund[oa]|terceir[oa]|quart[oa]|passo \d|tr[eê]s coisas|duas coisas|quatro coisas)\b"
NUMEROS = {"dois": 2, "duas": 2, "três": 3, "tres": 3, "quatro": 4, "cinco": 5, "seis": 6, "sete": 7,
           "oito": 8, "nove": 9, "dez": 10, "quinze": 15, "vinte": 20, "trinta": 30, "cem": 100, "mil": 1000}
UNIDADES = r"(minutos?|segundos?|horas?|dias?|semanas?|meses|anos?|quilos?|kg|vídeos?|videos?|vezes|pessoas|%|por cento)"
GATILHOS = [
    (r"\b(chegou|nova mensagem|notifica[cç][aã]o|recebi uma mensagem|vendeu|nova venda)\b", "notificacao"),
    (r"\b(pronto|aprovad[oa]|feito|decidi|resolvido)\b", "carimbo"),
    (r"\b(olha isso|olha aqui|esse aqui|essa aqui|repara)\b", "destaque"),
    (r"\bcomenta\b", "comentario"),
]


def sugerir(palavras, ritmo="medias", inicio_livre=0.5, fim_video=None):
    """Candidatos de animação a partir da fala do corte. A IA revisa antes de mostrar."""
    if ritmo == "nenhuma":
        return []
    gap = {"poucas": 12.0, "medias": 6.0, "muitas": 3.5}.get(ritmo, 6.0)
    texto = [w["w"] for w in palavras]
    norm = [re.sub(r"[^\wçãõáéíóúâêô%]", "", t.lower()) for t in texto]
    achados = []
    for i, w in enumerate(norm):
        trecho = " ".join(norm[i:i + 4])
        if re.match(ENUM, trecho):
            achados.append((palavras[i]["s"], "lista", i))
            continue
        val = int(w) if w.isdigit() else NUMEROS.get(w)
        if val is not None and i + 1 < len(norm) and re.match(UNIDADES, norm[i + 1]):
            achados.append((palavras[i]["s"], "numero", i))
            continue
        for padrao, tipo in GATILHOS:
            if re.match(padrao, trecho):
                achados.append((palavras[i]["s"], tipo, i))
                break
    out, ultimo = [], -999.0
    for t, tipo, i in sorted(achados):
        if t < inicio_livre or t - ultimo < gap:
            continue
        a = {"tipo": tipo, "inicio": round(max(0.0, t - 0.1), 2), "fim": round(t + 2.0, 2),
             "fala": " ".join(texto[max(0, i - 3):i + 6])}
        if tipo == "numero":
            a.update(valor=norm[i] if norm[i].isdigit() else str(NUMEROS[norm[i]]), rotulo=norm[i + 1])
        elif tipo == "lista":
            a.update(itens=[{"texto": "...", "t": round(t, 2)}], fim=round(t + 5.0, 2))
        elif tipo == "carimbo":
            a.update(texto=norm[i].upper())
        elif tipo == "comentario":
            a.update(texto=(texto[i + 1] if i + 1 < len(texto) else "").strip(".,!?").upper())
        elif tipo == "notificacao":
            a.update(titulo="Nova mensagem", texto="...")
        elif tipo == "destaque":
            a.update(x=540, y=900)
        if fim_video:
            a["fim"] = min(a["fim"], fim_video - 0.3)
        out.append(a)
        ultimo = t
    return out
