"""Animações 2D nos momentos fortes (motion). Cada uma vira um .mov com transparência."""
import math
import re
import subprocess

from PIL import Image, ImageDraw

from .base import (FPS, LARGURA, ZONA_X, ZONA_Y, cor, ease_out, fonte, quadros,
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


def _cartao(W, H, tema="escuro", raio=28):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    fundo = (18, 18, 22, 235) if tema == "escuro" else (255, 255, 255, 245)
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
    base = _cartao(W, H, tema)
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


def r_carimbo(a, c, dur):
    tinta = (220, 38, 38, 255) if a.get("vermelho") else c
    t = _texto(a["texto"].upper(), fonte("anton", 120), tinta)
    W, H = t.width + 90, t.height + 70
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(img).rounded_rectangle([6, 6, W - 7, H - 7], 18, outline=tinta, width=12)
    img.alpha_composite(t, (45, 35))
    img = img.rotate(8, expand=True, resample=Image.BICUBIC)
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
        _colar(tela, img, S / 2, S / 2, e, al * _alfa_saida(tt, dur))
        return tela
    return S, S, desenhar, [("impacto_seco", 0.12, -11)]


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


RECEITAS = {"impacto": r_impacto, "lista": r_lista, "passo": r_passo, "numero": r_numero,
            "notificacao": r_notificacao, "carimbo": r_carimbo, "destaque": r_destaque,
            "comentario": r_comentario, "barra": r_barra, "chamada": r_chamada}
POSICAO = {"impacto": "alto", "lista": "meio", "passo": "alto", "numero": "alto",
           "notificacao": "topo", "carimbo": "meio", "destaque": "ponto", "comentario": "baixo",
           "barra": "alto", "chamada": "meio"}


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
    if pref + H <= z0 or pref >= z1:
        return x, int(pref)
    cima, baixo = z0 - H - 20, z1 + 20
    opcoes = [y for y in (cima, baixo) if ZONA_Y[0] - 40 <= y and y + H <= ZONA_Y[1] + 40]
    if opcoes:
        return x, int(min(opcoes, key=lambda y: abs(y - pref)))
    return x, int(pref)


def renderizar(a, destaque, saida, zona_rosto=None):
    """Desenha a animação a 30 qps e grava um .mov com alfa. Devolve (x, y, sons, duração)."""
    tipo = a["tipo"]
    c = cor(a.get("cor") or destaque)
    parada = a["fim"] - a["inicio"]
    W, H, desenhar, sons = RECEITAS[tipo](a, c, parada)
    W += W % 2
    H += H % 2
    total = quadros(parada + SAIDA) if tipo != "chamada" else quadros(parada)
    proc = subprocess.Popen(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo",
                             "-pix_fmt", "rgba", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                             "-c:v", "qtrle", "-pix_fmt", "argb", str(saida)], stdin=subprocess.PIPE)
    for q in range(total):
        img = desenhar(q / FPS)
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
