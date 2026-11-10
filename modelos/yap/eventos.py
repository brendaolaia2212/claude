"""Episódio 2: gancho, textos, emojis, carimbos, chuva, sons e efeitos de câmera, tudo preso
às palavras dela (busca pela frase, não por índice) -> edicao.json (tempos no corte)."""
import json
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, "/home/user/claude")
from editor.aula import _mapa_tempo
from editor.corte import _transcricao_do_corte

NOME = "pacotes-ep2"
P = Path("/home/user/claude/trabalho") / NOME
ed = json.loads((P / "edicao.json").read_text())
ws = json.loads((P / "transcricao.json").read_text())
manter = set(ed["corte"]["palavras"])
segs = ed["corte"]["segmentos"]
para, D = _mapa_tempo(segs)
rostos = [r for r in json.loads((P / "rosto.json").read_text()) if r["rosto"]]


def norm(t):
    t = unicodedata.normalize("NFD", t.lower())
    return re.sub(r"[^\w ]", "", "".join(c for c in t if unicodedata.category(c) != "Mn"))


NW = [norm(w["w"]) for w in ws]


def achar(frase, depois=0):
    """(primeira, última) palavra da frase, a partir do índice `depois`; só palavras mantidas."""
    alvo = norm(frase).split()
    for i in range(depois, len(ws)):
        if i not in manter or not NW[i] or NW[i].split()[0] != alvo[0]:
            continue
        toks, j = [], i
        while j < len(ws) and len(toks) < len(alvo):
            if j in manter and NW[j]:
                toks.extend(NW[j].split())
            j += 1
        if toks[:len(alvo)] == alvo:
            return i, j - 1
    sys.exit(f"Não achei no corte: {frase!r} (depois de {depois})")


def ini(i, antes=0.08):
    return round(max(0.0, para(ws[i]["s"], "inicio") - antes), 3)


def fim(i, depois=0.3):
    return round(min(D - 0.05, para(ws[i]["e"], "fim") + depois), 3)


def lado_do_rosto(t, preferir=None):
    """(x, y) pra um emoji ao lado do rosto, no lado com mais espaço."""
    r = min(rostos, key=lambda d: abs(d["t"] - t))["rosto"]
    cx, cy = r["x"] + r["w"] / 2, r["y"] + r["h"] * 0.45
    lado = preferir or ("dir" if cx < 540 else "esq")
    x = r["x"] + r["w"] + 175 if lado == "dir" else r["x"] - 175     # meio emoji + folga: não encosta no rosto
    return int(min(945, max(135, x))), int(min(1350, max(330, cy)))


A, FX, SX = [], [], []


def emoji(frase, e, dur=1.5, som="pop", db=-16, tam=230, depois=0, lado=None, antes=0.05, **k):
    i, _ = achar(frase, depois)
    t = ini(i, antes)
    x, y = lado_do_rosto(t, lado)
    a = {"tipo": "emoji", "emoji": e, "inicio": t, "fim": round(min(D - 0.3, t + dur), 3), "x": x, "y": y,
         "tam": tam, "som": som, "db": db}
    a.update(k)
    A.append(a)
    return i


def texto(frase_ini, frase_fim, t, depois=0, ate=0.7, **k):
    i0, _ = achar(frase_ini, depois)
    _, i1 = achar(frase_fim, i0)
    A.append(dict({"tipo": "texto", "texto": t, "inicio": ini(i0, 0.12), "fim": fim(i1, ate)}, **k))
    return i0


def chuva(frase, e, modo="sobe", dur=2.4, n=14, som="brilho", db=-19, depois=0, antes=0.05, **k):
    i, _ = achar(frase, depois)
    t = ini(i, antes)
    A.append(dict({"tipo": "chuva", "emoji": e, "modo": modo, "n": n, "inicio": t,
                   "fim": round(min(D - 0.3, t + dur), 3), "x": 540, "y": 960, "som": som, "db": db}, **k))
    return i


def carimbo(frase, txt, depois=0, ate=1.5, **k):
    i, j = achar(frase, depois)
    A.append(dict({"tipo": "carimbo", "texto": txt, "inicio": ini(i, 0.04), "fim": fim(j, ate)}, **k))
    return i


def zoom(frase, dur=1.0, escala=1.16, depois=0, antes=0.04, **k):
    i, _ = achar(frase, depois)
    t = ini(i, antes)
    FX.append(dict({"tipo": "zoom", "inicio": t, "fim": round(min(D, t + dur), 3), "escala": escala}, **k))
    return t


def fx(tipo, frase, dur, depois=0, antes=0.03, **k):
    i, _ = achar(frase, depois)
    t = ini(i, antes)
    FX.append(dict({"tipo": tipo, "inicio": t, "fim": round(min(D, t + dur), 3)}, **k))
    return t


# ---------------- gancho ----------------
_, g1 = achar("pacotes da minha mãe")
ed["estilo"] = {"legenda": "yap", "gancho": "yap", "cor": "#FFFFFF", "zoom": True, "animacoes": "poucas",
                "sons": True}
ed["gancho"] = {"texto": "O que minha mãe comprou\nquando estava internada?", "sobre": "Episódio 2",
                "sub": "pacote 2 de 12", "inicio": 0.0, "fim": fim(g1, 0.55)}

# ---------------- começo: os comentários do episódio 1 ----------------
chuva("Vocês amaram abrir esse tanto", "❤️", n=12, db=-21)
zoom("Vocês amaram abrir esse tanto", 1.1, 1.14)
emoji("blusinhas t-shirt", "👕")
texto("blusinha nunca é demais", "blusinha nunca é demais", "blusinha nunca\né demais", fonte="kalam", tam=100)
emoji("espalhafatoso", "💃", som="boing", db=-19, dur=1.4)
texto("A minha mãe acabou chegando", "casa de muita gente", "a minha mãe\nacabou chegando\nna casa de muita gente",
      tam=100, som="plim", db=-22, ate=0.9)
emoji("entrevista dela na Ana Maria Braga", "📺", som="ding", db=-21)
zoom("entrevista dela na Ana Maria Braga", 1.2, 1.12)
emoji("numa caixa no fundo", "📦", lado=None)
emoji("sex shop", "🙈", som="boing", db=-17, antes=0.0)
zoom("sex shop", 1.1, 1.2)
texto("A gente vai descobrir realmente", "realmente junto", "a gente vai descobrir\nrealmente junto",
      fonte="kalam", tam=92)
carimbo("oferta relâmpago", "relâmpago", cheio=True, cor="#FACC15", emoji="⚡", som="kaching", db=-16, ate=0.9)
zoom("oferta relâmpago", 1.0, 1.15)
texto("esteve lá no velório", "de tanto que ela comprava", "até a entregadora\nesteve lá no velório",
      sub="de tanto que ela comprava", tam=100, som="ding", db=-21, ate=0.6)
texto("esse é o episódio 2", "compras da minha mãe", "Abrindo as compras\nda minha mãe", sobre="Episódio 2",
      tam=118, som="whoosh", db=-18, ate=1.3)

# ---------------- desafio ----------------
texto("Quero te fazer um desafio", "um desafio aqui", "desafio", tam=150, som="ding", db=-19, ate=0.5)
texto("me conte uma recordação boa", "recordação boa que você tem com ela",
      "me conte uma recordação\nboa que você tem com ela", fonte="kalam", tam=88, som="pop", db=-21, ate=0.6)
i12, _ = achar("os 12 dias abrindo pacote")
A.append({"tipo": "numero", "valor": "12", "rotulo": "dias abrindo pacote", "inicio": ini(i12 + 1, 0.15),
          "fim": fim(achar("dias abrindo pacote")[1], 0.9)})
emoji("cabeludo", "🤭", som="boing", db=-18, antes=0.0)
chuva("sinônimo de alegria", "✨", n=10, db=-23, dur=3.0)

# ---------------- o choro, a saudade ----------------
i_choro, _ = achar("não pensem que eu não choro")
_, i_casa = achar("até aqui na minha casa")
FX.append({"tipo": "dolly", "inicio": ini(i_choro, 0.1), "fim": fim(i_casa, 0.2), "escala": 1.10})
texto("E cadê minha mãe", "cadê minha mãe", "e cadê minha mãe?", fonte="instrument-italico", tam=110, som=None,
      ate=1.2)
texto("minha mãe era vida", "minha mãe era alegria", "minha mãe era vida,\nminha mãe era alegria", tam=100,
      som="brilho", db=-24, ate=1.0)

# ---------------- abrindo o pacote ----------------
emoji("vamos abrir o pacote de hoje", "📦", antes=0.0)
zoom("vamos abrir o pacote de hoje", 1.0, 1.12)
i_pes = emoji("pesadaço", "🏋️", som="impacto_seco", db=-15, antes=0.02)
fx("tremor", "pesadaço", 0.6, forca=14)
# rufar de tambor: a batida (1,6 s depois do começo) cai quando a caixa sai do saco
caixa_sai = para(429.0, "inicio")
SX.append({"t": round(caixa_sai - 1.6, 3), "tipo": "tambor", "db": -14, "junto": True})
FX.append({"tipo": "flash", "inicio": round(caixa_sai, 3), "fim": round(caixa_sai + 0.3, 3), "forca": 0.55})
SX.append({"t": round(caixa_sai + 0.02, 3), "tipo": "brilho", "db": -20, "junto": True})
# "É um babyliss do TikTok Shop!"
i_bab = chuva("É um babyliss", "✨", modo="explode", n=18, db=-16, dur=1.8, cy=1050)
t_bab = ini(i_bab, 0.05)
FX.append({"tipo": "flash", "inicio": t_bab, "fim": round(t_bab + 0.3, 3), "forca": 0.6})
FX.append({"tipo": "zoom", "inicio": t_bab, "fim": round(t_bab + 1.8, 3), "escala": 1.14, "centro": "meio"})
emoji("TikTok Shop", "🛍️", dur=1.3, depois=i_bab)
emoji("você vai ficar pra mim", "💖", som="brilho", db=-20)
emoji("Não acredito", "😱", som="impacto", db=-17, antes=0.0, lado="esq")   # o modelador está do outro lado
fx("tremor", "Não acredito", 0.5, forca=12)
zoom("Para com isso", 1.6, 1.15)
emoji("Esse eu amei", "🤩", som="pop", db=-15, antes=0.0)
zoom("Esse eu amei", 1.0, 1.16)
texto("Isso era a cara dela", "Isso era a cara dela", "isso era\na cara dela", fonte="kalam", tam=104, som="plim",
      db=-21, ate=0.6)
# "eu vou pegar ali pra vocês" -> sai do quadro -> volta com as escovas
_, i_pegar = achar("eu vou pegar ali pra vocês")
i_como, _ = achar("Como se não bastasse")
seg_volta = next(s for s, e in segs if s <= ws[i_como]["s"] < e)    # emenda: ela entra no quadro
volta = round(para(seg_volta, "inicio"), 3)
SX.append({"t": round(volta - 1.85, 3), "tipo": "suspense", "db": -21})   # sobe até ela sair e voltar
SX.append({"t": round(volta - 0.15, 3), "tipo": "whoosh", "db": -17, "junto": True})
FX.append({"tipo": "flash", "inicio": round(volta, 3), "fim": round(volta + 0.25, 3), "forca": 0.45})
zoom("Como se não bastasse", 1.2, 1.14)
emoji("essa tá quebrada", "❌", som="reprovado", db=-16, lado="esq")
emoji("essa daqui é meio ruim", "😬", som="boing", db=-19, lado="dir")
emoji("a pranchinha dá para usar", "✅", som="plim", db=-17, lado="esq")
emoji("essa daqui é a que eu tenho usado", "💖", som="brilho", db=-20, lado="dir")
SX.append({"t": round(para(560.5, "inicio") + 0.02, 3), "tipo": "whoosh_sobe", "db": -18, "junto": True})
texto("agora temos o Hair Curler", "Hair Curler", "Hair Curler", sobre="agora temos o", tam=124, som="pop",
      db=-17, ate=0.8)
emoji("live no TikTok", "📱")
emoji("campeão de venda", "🏆", som="kaching", db=-16)
fx("pulso", "campeão de venda", 0.35, forca=0.07)
emoji("A t-shirt eu já tenho", "🎁")
emoji("vou ficar pra mim com esse", "🙌", som="brilho", db=-20)
zoom("vou ficar pra mim com esse", 1.0, 1.14)

# ---------------- veredito 1: "Mãe, esse tá aprovado!" ----------------
i_apr = carimbo("aprovado", "aprovado", cheio=True, cor="#22C55E", emoji="✅", som="aprovado", db=-11,
                giro=-8, ate=1.7)
t_apr = ini(i_apr, 0.04)
FX.append({"tipo": "flash", "inicio": round(t_apr + 0.12, 3), "fim": round(t_apr + 0.4, 3), "forca": 0.4})
FX.append({"tipo": "tremor", "inicio": round(t_apr + 0.12, 3), "fim": round(t_apr + 0.6, 3), "forca": 12})
chuva("Mãe arrasou na comprinha", "❤️", n=16, db=-19, dur=2.6, antes=0.16)   # começa antes: o texto fica por cima
texto("Mãe arrasou na comprinha", "arrasou na comprinha", "Mãe, arrasou\nna comprinha", fonte="instrument-italico",
      tam=112, som=None, ate=1.0)
i_viva, _ = achar("se a minha mãe estivesse viva")
_, i_link = achar("lá no link dela o meu")
FX.append({"tipo": "dolly", "inicio": ini(i_viva, 0.1), "fim": fim(i_link, 0.2), "escala": 1.08})
emoji("tá muito em alta nas lives", "📈", depois=i_viva)
emoji("fiz vídeo de IA dele", "🎥")
emoji("eu jurava que ia ser alguma coisa de casa", "🏠", depois=i_viva)
emoji("mais um babyliss", "😂", som="boing", db=-18)
zoom("mais um babyliss", 1.0, 1.16)
emoji("muito viralizado", "🔥")
texto("isso é a cara dela", "isso é a cara dela", "isso é\na cara dela", depois=i_viva, fonte="kalam", tam=104,
      som="plim", db=-21, ate=0.6)

# ---------------- veredito 2: "Então… Comprinha aprovada!" ----------------
i_ent, _ = achar("Então Comprinha aprovada")
SX.append({"t": ini(i_ent, 0.05), "tipo": "whoosh_sobe", "db": -18})
i_apr2 = carimbo("aprovada", "aprovada", depois=i_ent, cheio=True, cor="#22C55E", emoji="✅", som="aprovado",
                 db=-10, giro=8, ate=1.6)
t2 = ini(i_apr2, 0.04)
chuva("aprovada", "🎉", modo="explode", n=20, som=None, dur=2.0, depois=i_ent, cy=980)
FX.append({"tipo": "flash", "inicio": round(t2 + 0.12, 3), "fim": round(t2 + 0.45, 3), "forca": 0.55})
FX.append({"tipo": "tremor", "inicio": round(t2 + 0.12, 3), "fim": round(t2 + 0.7, 3), "forca": 16})
i_lk, _ = achar("quiser o link eu mando", i_apr2)
A.append({"tipo": "comentario", "texto": "LINK", "inicio": ini(i_lk, 0.1), "fim": round(ini(i_lk, 0.1) + 2.8, 3)})
emoji("sou especialista em inteligência artificial", "🤖")
emoji("posto só besteira aqui", "😅", som="boing", db=-19)

# ---------------- final ----------------
texto("não esquece de deixar o comentário", "lembrança que você tem da minha mãe",
      "deixa nos comentários\na lembrança que você\ntem da minha mãe", fonte="kalam", tam=86, som="ding", db=-20,
      ate=0.5)
i_ate, _ = achar("até amanhã pessoal")
A.append({"tipo": "texto", "texto": "Pacote 3 de 12", "sobre": "amanhã a gente volta", "sub": "Episódio 3",
          "tam": 120, "som": "whoosh", "db": -19, "inicio": ini(i_ate, 0.1), "fim": round(D - 0.05, 3)})

# ---------------- grava ----------------
A.sort(key=lambda a: a["inicio"])
FX.sort(key=lambda e: e["inicio"])
ed["animacoes"] = A
ed["fx"] = FX
ed["sons_extra"] = sorted(SX, key=lambda s: s["t"])
# a legenda some quando o mesmo texto (ou um carimbo, ou o número) já está na tela
ed["legenda_oculta"] = ([[a["inicio"], a["fim"]] for a in A if a["tipo"] in ("texto", "carimbo", "numero")]
                        + [[0.0, ed["gancho"]["fim"]]])
ed.pop("chamada", None)
(P / "edicao.json").write_text(json.dumps(ed, ensure_ascii=False, indent=2))
_transcricao_do_corte(NOME, segs)


def mm(t):
    return f"{int(t // 60)}:{t % 60:05.2f}"


print("duração do corte", mm(D), "| gancho até", ed["gancho"]["fim"])
for a in A:
    print(f"{mm(a['inicio'])}-{mm(a['fim'])} {a['tipo']:10s} "
          f"{(a.get('texto') or a.get('emoji') or a.get('valor') or '').replace(chr(10), ' / ')[:46]}")
print(len(A), "elementos,", len(FX), "efeitos de câmera,", len(SX), "sons extras")
