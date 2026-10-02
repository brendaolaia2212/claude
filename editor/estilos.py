"""Desenho das legendas e dos ganchos, pelos nomes da lista de estilos."""
from PIL import Image, ImageDraw, ImageFilter

from .base import ZONA_X, cor, fonte, texto_escuro_sobre

LARG_MAX = ZONA_X[1] - ZONA_X[0]   # 800 px
BRANCO = (255, 255, 255, 255)
PRETO = (0, 0, 0, 255)
ESCURO = (22, 22, 22, 255)

LEGENDAS = {
    # nome: palavras por grupo, descrição
    "impacto": (3, "Anton, caixa alta, contorno preto, 1 a 3 palavras"),
    "caixa": (3, "Montserrat, caixa colorida atrás da palavra falada"),
    "gigante": (1, "Anton, uma palavra por vez, bem grande, sombra colorida"),
    "pulso": (3, "Montserrat, a palavra falada cresce e ganha cor"),
    "fita": (4, "Montserrat branca numa faixa preta inclinada"),
    "papelaria": (6, "Montserrat, contorno grosso, a frase vai se escrevendo"),
    "discreta": (9, "Montserrat fina, frase em até 2 linhas, faixa escura, sem animação"),
}
GANCHOS = {
    "manchete": "Anton caixa alta, segunda linha na cor de destaque",
    "tarjas": "cada linha numa tarja sólida, levemente inclinadas",
    "balao": "balão branco de conversa, como pergunta do público",
    "marcatexto": "texto escuro sobre faixas de marca-texto",
    "vidro": "painel escuro translúcido, texto branco, traço colorido",
}
NOMES_BONITOS = {"caixa": "Caixa na palavra", "gigante": "Palavra gigante", "balao": "Balão",
                 "marcatexto": "Marca-texto", "vidro": "Vidro escuro"}
APELIDOS = {"caixa na palavra": "caixa", "palavra gigante": "gigante", "marca-texto": "marcatexto",
            "vidro escuro": "vidro", "balão": "balao"}


def nome_estilo(n):
    n = (n or "").strip().lower()
    return APELIDOS.get(n, n)


def _medir(f, t, sw=0):
    l, tp, r, b = f.getbbox(t, stroke_width=sw)
    return r - l, l


def sombra(img, raio=18, deslocar=(0, 10), alfa=110):
    """Sombra suave por baixo de um elemento já desenhado."""
    m = 40
    base = Image.new("RGBA", (img.width + 2 * m, img.height + 2 * m), (0, 0, 0, 0))
    a = img.getchannel("A").point(lambda v: alfa if v > 20 else 0)
    s = Image.new("RGBA", img.size, (0, 0, 0, 255))
    s.putalpha(a)
    base.alpha_composite(s, (m + deslocar[0], m + deslocar[1]))
    base = base.filter(ImageFilter.GaussianBlur(raio))
    base.alpha_composite(img, (m, m))
    return base


def _linhas(palavras, fontes, larg_max, espaco, sw):
    """Quebra em linhas. Devolve [[(i, largura, deslocamento), ...], ...]."""
    linhas, atual, w_atual = [], [], 0
    for i, p in enumerate(palavras):
        w, l = _medir(fontes[i], p, sw)
        extra = w + (espaco if atual else 0)
        if atual and w_atual + extra > larg_max:
            linhas.append(atual)
            atual, w_atual = [], 0
            extra = w
        atual.append((i, w, l))
        w_atual += extra
    if atual:
        linhas.append(atual)
    return linhas


def _bloco_palavras(palavras, fontes, cores, sw, cor_sw, espaco, alinhar="centro",
                    caixas=None, larg_max=LARG_MAX, entrelinha=1.08, sombra_cor=None, sombra_d=0,
                    visivel=None, sem_contorno=()):
    """Desenha palavras com linha de base comum. caixas[i] = cor da caixa atrás da palavra i."""
    linhas = _linhas(palavras, fontes, larg_max, espaco, sw)
    asc = max(f.getmetrics()[0] for f in fontes)
    desc = max(f.getmetrics()[1] for f in fontes)
    alt_linha = int((asc + desc) * entrelinha)
    larg = max(sum(w for _, w, _ in ln) + espaco * (len(ln) - 1) for ln in linhas)
    pad = sw + 24 + sombra_d
    W, H = larg + 2 * pad, alt_linha * len(linhas) + 2 * pad
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    pos = []
    for k, ln in enumerate(linhas):
        lw = sum(w for _, w, _ in ln) + espaco * (len(ln) - 1)
        x = pad + ((larg - lw) / 2 if alinhar == "centro" else 0)
        base_y = pad + k * alt_linha + asc
        for i, w, l in ln:
            pos.append((i, x - l, base_y, w))
            x += w + espaco
    if caixas:
        for i, x, by, w in pos:
            if caixas.get(i) and (visivel is None or i in visivel):
                l, t, r, b = d.textbbox((x, by), palavras[i], font=fontes[i], anchor="ls")
                a, dsc = fontes[i].getmetrics()
                d.rounded_rectangle([l - 16, by - a * 0.8, r + 16, by + dsc * 0.7], radius=14, fill=caixas[i])
    for i, x, by, w in pos:
        if visivel is not None and i not in visivel:
            continue
        if sombra_cor:
            d.text((x + sombra_d, by + sombra_d), palavras[i], font=fontes[i], fill=sombra_cor,
                   anchor="ls", stroke_width=sw, stroke_fill=sombra_cor)
        d.text((x, by), palavras[i], font=fontes[i], fill=cores[i], anchor="ls",
               stroke_width=0 if i in sem_contorno else sw, stroke_fill=cor_sw)
    return img


def _ajustar(palavras, criar, tam, larg_max=LARG_MAX, linhas_max=2, minimo=0.6):
    """Diminui a fonte até caber em linhas_max linhas."""
    t = tam
    while True:
        img, n = criar(t)
        if n <= linhas_max or t <= tam * minimo:
            return img
        t *= 0.92


def bloco_legenda(estilo, palavras, ativa, destaque, revelar=False):
    """Uma 'foto' da legenda: grupo de palavras com a palavra falada (ativa) destacada."""
    estilo = nome_estilo(estilo)
    c = cor(destaque)
    n = len(palavras)

    if estilo == "impacto":
        ps = [p.upper() for p in palavras]
        f = fonte("anton", 90)
        cores = [c if i == ativa else BRANCO for i in range(n)]
        return _bloco_palavras(ps, [f] * n, cores, 8, PRETO, 22)

    if estilo == "caixa":
        f = fonte("montserrat", 68, 800)
        cores = [texto_escuro_sobre(c) if i == ativa else BRANCO for i in range(n)]
        return _bloco_palavras(palavras, [f] * n, cores, 4, PRETO, 26, caixas={ativa: c},
                               sem_contorno={ativa})

    if estilo == "gigante":
        p = palavras[ativa].upper()
        tam = 200
        while _medir(fonte("anton", tam), p, 5)[0] > LARG_MAX and tam > 90:
            tam -= 10
        return _bloco_palavras([p], [fonte("anton", tam)], [BRANCO], 5, PRETO, 0,
                               sombra_cor=c, sombra_d=12)

    if estilo == "pulso":
        f, fg = fonte("montserrat", 66, 800), fonte("montserrat", 66 * 1.25, 800)
        fontes = [fg if i == ativa else f for i in range(n)]
        cores = [c if i == ativa else BRANCO for i in range(n)]
        return _bloco_palavras(palavras, fontes, cores, 4, PRETO, 20)

    if estilo == "fita":
        f = fonte("montserrat", 60, 800)
        cores = [c if i == ativa else BRANCO for i in range(n)]
        txt = _bloco_palavras(palavras, [f] * n, cores, 0, PRETO, 18, alinhar="esquerda",
                              larg_max=LARG_MAX - 80)
        caixa = txt.getchannel("A").getbbox() or (0, 0, txt.width, txt.height)
        txt = txt.crop(caixa)
        fita = Image.new("RGBA", (txt.width + 64, txt.height + 40), (10, 10, 10, 240))
        fita.alpha_composite(txt, (32, 20))
        return fita.rotate(4, expand=True, resample=Image.BICUBIC)

    if estilo == "papelaria":
        f = fonte("montserrat", 70, 800)
        cores = [c if i == ativa else BRANCO for i in range(n)]
        return _bloco_palavras(palavras, [f] * n, cores, 10, ESCURO, 20,
                               visivel=set(range(ativa + 1)) if revelar else None)

    if estilo == "discreta":
        def criar(t):
            f = fonte("montserrat", t, 600)
            cores = [c if i == ativa else BRANCO for i in range(n)]
            linhas = _linhas(palavras, [f] * n, LARG_MAX - 60, 14, 0)
            return _bloco_palavras(palavras, [f] * n, cores, 0, PRETO, 14, larg_max=LARG_MAX - 60), len(linhas)
        txt = _ajustar(palavras, criar, 48)
        caixa = txt.getchannel("A").getbbox() or (0, 0, txt.width, txt.height)
        txt = txt.crop(caixa)
        faixa = Image.new("RGBA", (txt.width + 56, txt.height + 40), (0, 0, 0, 0))
        ImageDraw.Draw(faixa).rounded_rectangle([0, 0, faixa.width - 1, faixa.height - 1], 20,
                                                fill=(0, 0, 0, 150))
        faixa.alpha_composite(txt, (28, 20))
        return faixa

    raise SystemExit(f"Não conheço a legenda '{estilo}'. Opções: {', '.join(LEGENDAS)}")


def _recortar(img):
    caixa = img.getchannel("A").getbbox()
    return img.crop(caixa) if caixa else img


def bloco_gancho(estilo, texto, destaque):
    """Gancho escrito do começo. texto com até 2 linhas (quebre com \\n)."""
    estilo = nome_estilo(estilo)
    c = cor(destaque)
    linhas = [l.strip() for l in texto.split("\n") if l.strip()][:3]

    if estilo == "manchete":
        tam = 110
        while max(_medir(fonte("anton", tam), l.upper(), 9)[0] for l in linhas) > LARG_MAX and tam > 60:
            tam -= 6
        f = fonte("anton", tam)
        partes = [_bloco_palavras([l.upper()], [f], [c if k == 1 else BRANCO], 9, PRETO, 0,
                                  larg_max=4000, entrelinha=1.0) for k, l in enumerate(linhas)]
        return _empilhar([_recortar(p) for p in partes], 6)

    if estilo == "tarjas":
        tam = 70
        while max(_medir(fonte("montserrat", tam, 900), l.upper())[0] for l in linhas) > LARG_MAX - 70 and tam > 40:
            tam -= 4
        f = fonte("montserrat", tam, 900)
        partes = []
        for k, l in enumerate(linhas):
            fundo = BRANCO if k % 2 == 0 else c
            t = _recortar(_bloco_palavras([l.upper()], [f], [texto_escuro_sobre(fundo)], 0, PRETO, 0,
                                          larg_max=4000))
            tarja = Image.new("RGBA", (t.width + 56, t.height + 36), fundo)
            tarja.alpha_composite(t, (28, 18))
            partes.append(sombra(tarja.rotate(2 if k % 2 == 0 else -1.5, expand=True,
                                              resample=Image.BICUBIC), 12, (0, 6), 90))
        return _empilhar(partes, -70)

    if estilo == "balao":
        def criar(t):
            f = fonte("montserrat", t, 800)
            ps = " ".join(linhas).split()
            n = len(_linhas(ps, [f] * len(ps), LARG_MAX - 90, 16, 0))
            return _bloco_palavras(ps, [f] * len(ps), [ESCURO] * len(ps), 0, PRETO, 16,
                                   larg_max=LARG_MAX - 90), n
        t = _recortar(_ajustar(linhas, criar, 64, linhas_max=3))
        W, H = t.width + 80, t.height + 64
        balao = Image.new("RGBA", (W, H + 34), (0, 0, 0, 0))
        d = ImageDraw.Draw(balao)
        d.rounded_rectangle([0, 0, W - 1, H - 1], 36, fill=BRANCO)
        d.polygon([(60, H - 2), (130, H - 2), (54, H + 32)], fill=BRANCO)
        balao.alpha_composite(t, (40, 32))
        return sombra(balao, 16, (0, 8), 100)

    if estilo == "marcatexto":
        tam = 74
        while max(_medir(fonte("montserrat", tam, 900), l)[0] for l in linhas) > LARG_MAX - 40 and tam > 40:
            tam -= 4
        f = fonte("montserrat", tam, 900)
        partes = []
        for k, l in enumerate(linhas):
            t = _recortar(_bloco_palavras([l], [f], [ESCURO], 0, PRETO, 0, larg_max=4000))
            W, H = t.width + 40, t.height + 30
            faixa = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            d = ImageDraw.Draw(faixa)
            inc = 6 if k % 2 == 0 else -5
            d.polygon([(4, 8 + inc), (W - 2, 4), (W - 6, H - 6 - inc), (0, H - 2)], fill=c[:3] + (235,))
            faixa.alpha_composite(t, (20, 15))
            partes.append(faixa)
        return _empilhar(partes, 4)

    if estilo == "vidro":
        def criar(t):
            f = fonte("montserrat", t, 800)
            ps = " ".join(linhas).split()
            n = len(_linhas(ps, [f] * len(ps), LARG_MAX - 110, 16, 0))
            return _bloco_palavras(ps, [f] * len(ps), [BRANCO] * len(ps), 0, PRETO, 16,
                                   larg_max=LARG_MAX - 110), n
        t = _recortar(_ajustar(linhas, criar, 68, linhas_max=3))
        W, H = t.width + 100, t.height + 110
        painel = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(painel)
        d.rounded_rectangle([0, 0, W - 1, H - 1], 30, fill=(14, 14, 18, 185),
                            outline=(255, 255, 255, 40), width=2)
        d.rounded_rectangle([50, 34, 170, 44], 5, fill=c)
        painel.alpha_composite(t, (50, 72))
        return sombra(painel, 18, (0, 10), 90)

    raise SystemExit(f"Não conheço o gancho '{estilo}'. Opções: {', '.join(GANCHOS)}")


def _empilhar(partes, espaco):
    W = max(p.width for p in partes)
    H = sum(p.height for p in partes) + espaco * (len(partes) - 1)
    img = Image.new("RGBA", (W, max(1, H)), (0, 0, 0, 0))
    y = 0
    for p in partes:
        img.alpha_composite(p, ((W - p.width) // 2, max(0, y)))
        y += p.height + espaco
    return img
