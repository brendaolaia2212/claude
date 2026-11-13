"""Cria Aí (criaai-1): edição tech a partir do plano verificado (plano.json, índices da transcricao.json)
-> edicao.json (tempos no corte). Gancho no 1º segundo, troca de enquadramento a cada frase, frases fortes
em letra grande (Archivo, destaque laranja), animações só onde ajudam, telas do site com ela na moldura
do canto, 6 sons, trilha baixinha, sem chamada de venda, sem desfoque de fundo."""
import json
import sys
from pathlib import Path

sys.path.insert(0, "/home/user/claude")
from editor.aula import _mapa_tempo
from editor.corte import _transcricao_do_corte

NOME = "criaai-1"
P = Path("/home/user/claude/trabalho") / NOME
T = P / "telas"
C = Path("/tmp/claude-0/-home-user-claude/9a8ce83d-651a-520e-8e0f-8249ec8620b1/scratchpad/criaai")
ed = json.loads((P / "edicao.json").read_text())
ws = json.loads((P / "transcricao.json").read_text())
plano = json.loads((C / "plano.json").read_text())
manter = set(ed["corte"]["palavras"])
segs = ed["corte"]["segmentos"]
para, D = _mapa_tempo(segs)
emendas, _acc = [0.0], 0.0
for _s, _e in segs:
    _acc += _e - _s
    emendas.append(round(_acc, 4))


def ini(i, antes=0.08):
    return round(max(0.0, para(ws[i]["s"], "inicio") - antes), 3)


def fim(i, depois=0.3):
    return round(min(D - 0.05, para(ws[i]["e"], "fim") + depois), 3)


def mantidas(de, ate):
    return [i for i in range(de, ate + 1) if i in manter and ws[i]["w"].strip()]


def prox(i):
    return next((j for j in range(i + 1, len(ws)) if j in manter and ws[j]["w"].strip()), None)


A, FX, SX, AV = [], [], [], []
ed.pop("fundo", None)            # sem desfoque de fundo (ela não gosta)
ed.pop("chamada", None)          # sem chamada de venda no fim

# ---------------- gancho ----------------
g = plano["gancho"]
ed["gancho"] = {"texto": g["texto"], "inicio": 0.0, "fim": 3.4, "y": 1450, "escala": 1.3}
ed["estilo"].update({"gancho": "manchete", "legenda_y": 1520})
ocupado = [(0.0, 3.4)]

# ---------------- telas cheias (ela na moldura do canto) ----------------
TC = []


def tela(arquivo, t0, t1, canto, entrada="desliza", moldura=0.30):
    TC.append({"video": str(T / arquivo), "de": 0.0, "inicio": round(t0, 3), "fim": round(t1, 3), "canto": canto,
               "moldura": moldura, "entrada": entrada})


for tl in plano["telas"]:
    ids = mantidas(tl["de"], tl["ate"])
    t0, t1 = ini(ids[0], 0.1), fim(ids[-1], 0.2)
    e_ = next((e for e in emendas if e > t0 + 0.3), None)
    if tl["assunto"] == "ferramenta_massa" and tl["de"] == 565:
        tela("letreiro_ferramenta_massa_curta_b_anim.mp4", t0, t1, "cima-dir")
    elif tl["assunto"] == "pov":
        tela("letreiro_pov_studio_anim.mp4", t0, t0 + 1.7, "cima-dir")
        tela("site_pov_studio.mp4", t0 + 1.7, t1, "baixo-dir", entrada="corte")
    elif tl["assunto"] == "ugc":
        tela("letreiro_ugc_studio_anim.mp4", t0, t0 + 1.7, "cima-dir")
        tela("site_ugc_studio.mp4", t0 + 1.7, t1, "baixo-dir", entrada="corte")
    elif tl["assunto"] == "motion":
        tela("site_motion.mp4", t0, t1, "baixo-dir")
    else:
        tela("site_lote_passos.mp4", t0, t1, "baixo-dir")
    ocupado.append((t0, t1))

# ---------------- animações que ajudam a entender ----------------
def ok(t0, t1, o):
    if any(t0 < b and t1 > a for a, b in ocupado):
        AV.append(f"encavalado, saiu: {o}")
        return False
    ocupado.append((t0, t1))
    return True


AN = [
    {"tipo": "numero", "valor": "+700", "rotulo": "cards de imagem e vídeos", "de": 266, "ate": 274},
    {"tipo": "lista", "tema": "escuro", "titulo": "Separados por nicho", "de": 285, "ate": 302, "depois": 0.8,
     "itens": [("Roupa, mobiliário", 289), ("POV, UGC", 291), ("Prompts para gerar em elementos", 297),
               ("Prompts para gerar em frames", 302)]},
    {"tipo": "passo", "de": 343, "ate": 360, "passos": [("Copia no Cria Aí!", 344), ("Cola no Flow", 348), ("Gera", 356)]},
    {"tipo": "numero", "valor": "+20", "rotulo": "aulas de apoio", "de": 435, "ate": 441},
    {"tipo": "lista", "tema": "escuro", "titulo": "Minerador de produtos da Shopee", "de": 453, "ate": 484,
     "itens": [("Os produtos mais vendidos", 460), ("As comissões mais altas", 464),
               ("Quanto cada anúncio paga de comissão", 468), ("Quanto vendeu nos últimos 30 dias", 478)]},
    {"tipo": "lista", "tema": "escuro", "titulo": "Quem faz o trabalho pesado", "de": 995, "ate": 1025,
     "itens": [("Cria Aí!: manualmente", 1011), ("Ferramentas: de maneira automática", 1024)]},
]
for an in AN:
    ids = mantidas(an["de"], an["ate"])
    t0, t1 = ini(ids[0], 0.1), fim(ids[-1], an.get("depois", 0.5))
    if not ok(t0, t1, an["tipo"]):
        continue
    x = {"tipo": an["tipo"], "inicio": t0, "fim": t1, "y": 1250 if an["tipo"] == "lista" else 1200,
         "escala": {"lista": 1.8, "numero": 1.5, "passo": 1.6}[an["tipo"]]}
    # explicação: fundo azul da marca, ela na moldura do canto (o rosto dela fica livre)
    TC.append({"imagem": str(T / "fundo_explicacao.png"), "inicio": round(t0 - 0.05, 3), "fim": round(t1, 3),
               "canto": "cima-dir", "moldura": 0.32, "entrada": "desliza"})
    if an["tipo"] == "numero":
        x.update(valor=an["valor"], rotulo=an["rotulo"])
    elif an["tipo"] == "lista":
        x.update(titulo=an["titulo"], tema=an["tema"], itens=[{"texto": tx, "t": ini(i, 0.05)} for tx, i in an["itens"]])
    elif an["tipo"] == "passo":
        x.update(passos=[{"nome": nm, "t": ini(i, 0.05)} for nm, i in an["passos"]])
    A.append(x)

# ---------------- frases fortes em letra grande ----------------
for f in sorted(plano["palavras_grandes"], key=lambda f: f["de"]):
    ids = mantidas(f["de"], f["ate"])
    if len(ids) < 2:
        continue
    t0, t1 = ini(ids[0], 0.12), fim(ids[-1], 0.9)
    pj = prox(ids[-1])
    if pj is not None:
        t1 = round(min(t1, max(fim(ids[-1], 0.35), ini(pj, 0.0) - 0.02)), 3)
    if not ok(t0, t1, f["texto"]):
        continue
    pal = [{"w": ws[i]["w"].strip(), "t": round(max(0.0, para(ws[i]["s"], "inicio") - t0), 3)} for i in ids]
    dest = [k for k, i in enumerate(ids) if i in set(f.get("destaque", []))]
    A.append({"tipo": "frase", "palavras": pal, "destaques": dest, "inicio": t0, "fim": t1, "som": None,
              "fonte": "archivo", "fonte_destaque": "archivo", "cor_destaque": "#FF6A00", "tam": 96, "y": 1490})

# ---------------- troca de enquadramento a cada frase ----------------
frases_fala, atual = [], []
ordem = [i for i in sorted(manter) if ws[i]["w"].strip()]
for k, i in enumerate(ordem):
    atual.append(i)
    nxt = ordem[k + 1] if k + 1 < len(ordem) else None
    pausa = (para(ws[nxt]["s"], "inicio") - para(ws[i]["e"], "fim")) if nxt is not None else 9
    if ws[i]["w"].strip()[-1] in ".?!" or pausa > 0.45:
        frases_fala.append(atual)
        atual = []
if atual:
    frases_fala.append(atual)
CICLO = [1.0, 1.13, 1.0, 1.07]
blocos, b0 = [], None
for fr in frases_fala:
    t0 = ini(fr[0], 0.06)
    if blocos and t0 - blocos[-1][0] < 1.6:       # frase curtinha: fica no mesmo enquadramento
        continue
    blocos.append([t0])
for k, b in enumerate(blocos):
    t0 = b[0]
    t1 = blocos[k + 1][0] if k + 1 < len(blocos) else D
    esc = CICLO[k % len(CICLO)]
    if esc > 1.0:
        FX.append({"tipo": "enquadrar", "inicio": round(t0, 3), "fim": round(t1, 3), "escala": esc})

# ---------------- só 6 sons ----------------
for s_ in plano["sons"]:
    i = s_["indice"]
    if i not in manter:
        i = next((j for j in range(i, i + 10) if j in manter), None)
        if i is None:
            continue
    antes = 0.15 if s_["tipo"].startswith("whoosh") else 0.0
    SX.append({"t": ini(i, antes), "tipo": s_["tipo"], "db": -22 if s_["tipo"].startswith("whoosh") else -20, "junto": True})
ed["sons_so_extras"] = True

# ---------------- trilha baixinha ----------------
ed["trilha"] = {"arquivo": "/home/user/claude/recursos/trilhas/tech_suave.wav", "abaixo_db": 24}

ed["tela_cheia"] = sorted(TC, key=lambda t: t["inicio"])
A.sort(key=lambda a: a["inicio"])
FX.sort(key=lambda e: e["inicio"])
ed["animacoes"] = A
ed["fx"] = FX
ed["sons_extra"] = sorted(SX, key=lambda s: s["t"])
_oc = sorted([[a["inicio"], a["fim"]] for a in A if a["tipo"] == "frase"] + [[0.0, ed["gancho"]["fim"]]])
ed["legenda_oculta"] = _oc
(P / "edicao.json").write_text(json.dumps(ed, ensure_ascii=False, indent=2))
_transcricao_do_corte(NOME, segs)


def mm(x):
    return f"{int(x // 60)}:{x % 60:05.2f}"


print("corte", mm(D))
for t in ed["tela_cheia"]:
    print(f"{mm(t['inicio'])}-{mm(t['fim'])} TELA  {Path(t.get('video') or t['imagem']).name} {t['canto']} {t['entrada']}")
for a in A:
    txt = a.get("titulo") or a.get("valor") or " ".join(p["w"] for p in a.get("palavras", [])) or ""
    print(f"{mm(a['inicio'])}-{mm(a['fim'])} {a['tipo']:7s} {txt[:70]}")
print(len(FX), "trocas de enquadramento;", len(SX), "sons:", [(mm(s['t']), s['tipo']) for s in ed["sons_extra"]])
for a in AV:
    print("AVISO:", a)
