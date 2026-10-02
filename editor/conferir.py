"""Conferências: frases que a Meta reprova, quadros do vídeo, duração e mostruário de estilos."""
import re

from PIL import Image, ImageDraw

from .base import (ALTURA, LARGURA, ZONA_X, ZONA_Y, COR_PADRAO, ffmpeg, fonte, ler_edicao,
                   ler_json, mmss, pasta, sondar)
from .estilos import GANCHOS, LEGENDAS, NOMES_BONITOS, bloco_gancho, bloco_legenda

ALERTAS = [
    (r"r\$\s?\d|\d+\s?(mil|reais|k)\b.*\b(ganh|fatur|lucr|renda)|\b(ganh|fatur|lucr)\w*\b.*\d+\s?(mil|reais)",
     "valor em dinheiro ligado a ganho"),
    (r"\bem \d+ (dias|semanas|horas)\b|\bem (dois|três|tres|sete|trinta) dias\b", "promessa de prazo (\"em X dias\")"),
    (r"\bgarantid[oa]s?\b", "\"garantido\""),
    (r"\brenda extra de\b", "\"renda extra de\""),
    (r"\bfi(que|car) ric[oa]\b", "\"fique rico\""),
    (r"\bsem esfor[cç]o\b", "\"sem esforço\""),
    (r"\bantes e depois\b.*\b(dinheiro|reais|renda|ganho)", "antes e depois de dinheiro"),
    (r"\bvoc[eê] que (ganha pouco|est[aá] (endividad|gord|acima do peso|deprimid|sozinh)|é (pobre|gord|feia))",
     "aponta característica da pessoa"),
    (r"\b(cura|curou|curar)\b.*\b(depress|ansiedad|doen)", "promessa de cura"),
    (r"\b(perd[ae]|elimin[ae]|emagre[cç]a)\w* \d+ ?(kg|quilos)\b.*\bem \d+", "emagrecimento com prazo"),
]


def frases_meta(nome):
    """Procura na fala e nos textos da tela. Devolve [(tempo, trecho, motivo)]."""
    p = pasta(nome)
    ed = ler_edicao(nome)
    palavras = ler_json(p / "transcricao_corte.json", [])
    achados = []
    janela = 14
    for i in range(0, max(1, len(palavras)), 7):
        trecho = " ".join(w["w"] for w in palavras[i:i + janela])
        for padrao, motivo in ALERTAS:
            if re.search(padrao, trecho.lower()):
                achados.append((palavras[i]["s"], trecho, motivo))
    telas = []
    if ed.get("gancho", {}).get("texto"):
        telas.append((ed["gancho"].get("inicio", 0), ed["gancho"]["texto"].replace("\n", " ")))
    for a in ed.get("animacoes", []):
        t = " ".join(str(a.get(k, "")) for k in ("texto", "titulo", "valor", "rotulo"))
        t += " ".join(i.get("texto", "") for i in a.get("itens", []))
        telas.append((a["inicio"], t))
    if ed.get("chamada", {}) and ed["chamada"].get("texto"):
        telas.append((None, ed["chamada"]["texto"]))
    for t, txt in telas:
        for padrao, motivo in ALERTAS:
            if re.search(padrao, txt.lower()):
                achados.append((t, f"(na tela) {txt}", motivo))
    vistos, out = set(), []
    for t, trecho, motivo in achados:
        chave = (motivo, round(t or -1))
        if chave not in vistos:
            vistos.add(chave)
            out.append((t, trecho, motivo))
    return out


def folha_de_quadros(video, tempos, saida, rotulos=None, colunas=3):
    """Vários quadros numa imagem só, com o tempo escrito embaixo de cada um."""
    tmp = saida.parent / "_q.png"
    larg, alt = 360, 640
    imgs = []
    for k, t in enumerate(tempos):
        ffmpeg("-ss", f"{t:.3f}", "-i", video, "-frames:v", 1, "-vf", f"scale={larg}:{alt}", tmp)
        img = Image.open(tmp).convert("RGB")
        d = ImageDraw.Draw(img)
        txt = rotulos[k] if rotulos else mmss(t)
        d.rounded_rectangle([8, alt - 54, 8 + 22 * len(txt) + 20, alt - 10], 10, fill=(0, 0, 0))
        d.text((18, alt - 50), txt, font=fonte("montserrat", 30, 700), fill=(255, 255, 255))
        imgs.append(img)
    tmp.unlink(missing_ok=True)
    linhas = (len(imgs) + colunas - 1) // colunas
    folha = Image.new("RGB", (colunas * larg + (colunas + 1) * 12, linhas * alt + (linhas + 1) * 12), (24, 24, 24))
    for k, img in enumerate(imgs):
        folha.paste(img, (12 + (k % colunas) * (larg + 12), 12 + (k // colunas) * (alt + 12)))
    folha.save(saida, quality=88)
    return saida


def olhar_final(nome, arquivo="final.mp4"):
    p = pasta(nome)
    v = p / arquivo
    dur = sondar(v)["duracao"]
    dur_corte = sondar(p / "corte.mp4")["duracao"]
    tempos = [dur * k / 7 for k in range(1, 7)]
    folha = folha_de_quadros(v, tempos, p / f"conferencia_{v.stem}.jpg")
    return {"duracao": dur, "duracao_corte": dur_corte, "bate": abs(dur - dur_corte) < 0.1,
            "folha": folha}


def mostruario(nome, tipo="legenda", t=None, cor=None, opcoes=None, texto=None):
    """Um quadro do vídeo com cada opção de estilo, lado a lado, pra escolher pelo nome."""
    p = pasta(nome)
    ed = ler_edicao(nome)
    destaque = cor or ed.get("estilo", {}).get("cor", COR_PADRAO)
    video = p / ("corte.mp4" if (p / "corte.mp4").exists() else "original")
    if not video.exists():
        video = ed["original"]
    dur = sondar(video)["duracao"]
    t = min(t if t is not None else dur * 0.3, dur - 0.1)
    tmp = p / "_frame.png"
    ffmpeg("-ss", f"{t:.3f}", "-i", video, "-frames:v", 1, "-vf",
           f"scale={LARGURA}:{ALTURA}:force_original_aspect_ratio=increase,crop={LARGURA}:{ALTURA}", tmp)
    quadro = Image.open(tmp).convert("RGBA")
    tmp.unlink()
    nomes = opcoes or list(LEGENDAS if tipo == "legenda" else GANCHOS)
    palavras = ler_json(p / "transcricao_corte.json", []) or ler_json(p / "transcricao.json", [])
    if tipo == "legenda":
        perto = [w["w"] for w in palavras if w["s"] >= t][:3] or ["sua", "frase", "aqui"]
    gtexto = texto or (ed.get("gancho", {}).get("texto") or "O gancho escrito\naparece aqui")
    paineis = []
    for n in nomes:
        img = quadro.copy()
        if tipo == "legenda":
            b = bloco_legenda(n, perto, min(1, len(perto) - 1), destaque)
            img.alpha_composite(b, ((LARGURA - b.width) // 2 if n != "fita" else 120, 1180 - b.height // 2))
        else:
            b = bloco_gancho(n, gtexto, destaque)
            img.alpha_composite(b, ((LARGURA - b.width) // 2, 260))
        img = img.convert("RGB").resize((360, 640))
        d = ImageDraw.Draw(img)
        rot = NOMES_BONITOS.get(n, n.capitalize())
        f = fonte("montserrat", 30, 800)
        d.rounded_rectangle([8, 8, 8 + d.textlength(rot, font=f) + 24, 56], 10, fill=(0, 0, 0))
        d.text((20, 12), rot, font=f, fill=(255, 255, 255))
        paineis.append(img)
    col = min(4, len(paineis))
    linhas = (len(paineis) + col - 1) // col
    folha = Image.new("RGB", (col * 372 + 12, linhas * 652 + 12), (24, 24, 24))
    for k, img in enumerate(paineis):
        folha.paste(img, (12 + (k % col) * 372, 12 + (k // col) * 652))
    saida = p / f"mostruario_{tipo}.jpg"
    folha.save(saida, quality=88)
    return saida
