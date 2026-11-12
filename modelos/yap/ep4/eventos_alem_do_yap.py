"""Episódio 4: além do yap. Fundo desfocado, luz no rosto, frases fortes grandes palavra por
palavra, foco na mão ao abrir o pacote, foto instantânea na revelação, aproximações e
exatamente os sons escolhidos (nada mais toca). Decisões de fala vêm do painel
(decisoes_painel.json, índices da transcricao.json) -> edicao.json (tempos no corte)."""
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, "/home/user/claude")
from editor.aula import _mapa_tempo
from editor.corte import _transcricao_do_corte
from editor.fx import centro_movimento

NOME = "ep4"
P = Path("/home/user/claude/trabalho") / NOME
S = Path("/tmp/claude-0/-home-user-claude/9a8ce83d-651a-520e-8e0f-8249ec8620b1/scratchpad/ep4")
ed = json.loads((P / "edicao.json").read_text())
ws = json.loads((P / "transcricao.json").read_text())
dec = json.loads((S / "decisoes_painel.json").read_text())
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


def corte_t(t_orig, lado="inicio"):
    return round(para(t_orig, lado), 3)


def emenda_depois(t):
    return next(e for e in emendas if e > t + 0.5)


def mantidas(de, ate):
    return [i for i in range(de, ate + 1) if i in manter and ws[i]["w"].strip()]


A, FX, SX, AVISOS = [], [], [], []

# ---------------- gancho (1º segundo) ----------------
g = dec["gancho"]
ed["estilo"] = {"legenda": "yap", "gancho": "yap", "cor": "#FFFFFF", "zoom": True, "animacoes": "poucas",
                "sons": True}
fim_gancho = max(5.2, fim(mantidas(0, 30)[min(14, len(mantidas(0, 30)) - 1)], 0.2))
ed["gancho"] = {"texto": g["texto"], "sobre": g.get("sobre") or "Episódio 4", "sub": g.get("sub", ""),
                "inicio": 0.0, "fim": round(min(fim_gancho, 6.5), 3)}
FX.append({"tipo": "dolly", "inicio": 0.0, "fim": emenda_depois(1.0), "escala": 1.08})

# ---------------- frases fortes: grandes, palavra por palavra ----------------
ocupado = [(0.0, ed["gancho"]["fim"])]
for f in sorted(dec["frases"], key=lambda f: f["de"]):
    ids = mantidas(f["de"], f["ate"])
    if len(ids) < 2:
        AVISOS.append(f"frase sem palavras no corte: {f['texto']}")
        continue
    t0 = ini(ids[0], 0.12)
    t1 = fim(ids[-1], 0.9)
    # se ela continua falando logo depois, a frase sai antes (a legenda comum não engole a fala)
    prox = next((j for j in range(ids[-1] + 1, len(ws)) if j in manter and ws[j]["w"].strip()), None)
    if prox is not None:
        t1 = round(min(t1, max(fim(ids[-1], 0.35), ini(prox, 0.0) - 0.02)), 3)
    # frase anterior colada: só a sobra do fim encosta -> a anterior sai um instante antes desta entrar
    if A and A[-1]["tipo"] == "frase" and A[-1]["fim"] > t0 and A[-1]["_fala_fim"] <= t0 + 0.15:
        t0 = round(max(t0, A[-1]["_fala_fim"]), 3)
        A[-1]["fim"] = round(max(A[-1]["_fala_fim"] + 0.05, t0 - 0.2), 3)  # a saída (0,2 s) termina quando a próxima entra
        t0 = round(max(t0, A[-1]["fim"]), 3)
        ocupado[-1] = (ocupado[-1][0], A[-1]["fim"])
    if any(t0 < b and t1 > a for a, b in ocupado):
        AVISOS.append(f"frase encavalada, saiu: {f['texto']}")
        continue
    TROCA = dec.get("trocas_frase", {})
    pal = [{"w": TROCA.get(str(i), ws[i]["w"].strip()), "t": round(max(0.0, para(ws[i]["s"], "inicio") - t0), 3)} for i in ids]
    dest = [k for k, i in enumerate(ids) if i in set(f.get("destaque", []))]
    A.append({"tipo": "frase", "palavras": pal, "destaques": dest, "quebras": f.get("quebras", []),
              "inicio": t0, "fim": t1, "som": None, "_fala_fim": fim(ids[-1], 0.0)})
    ocupado.append((t0, t1))
for a in A:
    a.pop("_fala_fim", None)

# ---------------- cartões leves (comentários dela) ----------------
for c in dec.get("cartoes_leves", []):
    ids = mantidas(c["de"], c["ate"])
    if not ids:
        continue
    t0, t1 = ini(ids[0], 0.12), fim(ids[-1], 0.7)
    if c.get("fim_max") == "antes_foco_mao":
        VIS0 = json.loads((S / "visual.json").read_text())
        t1 = min(t1, corte_t(VIS0["foco_mao"][0]["de"]) - 0.15)
    if any(t0 < b and t1 > a for a, b in ocupado):
        AVISOS.append(f"cartão encavalado, saiu: {c['texto']}")
        continue
    A.append({"tipo": "texto", "texto": c["texto"], "fonte": "kalam", "tam": 96, "som": None, "inicio": t0, "fim": t1})
    ocupado.append((t0, t1))

# ---------------- abrir o pacote: foco na mão (suspense) e revelação ----------------
VIS = json.loads((S / "visual.json").read_text())
for z in VIS["foco_mao"]:
    t0, t1 = corte_t(z["de"]), corte_t(z["ate"], "fim")
    if t1 - t0 < 1.0:
        continue
    e_ = emenda_depois(t0)
    t1 = e_ if e_ - t1 < 0.5 else min(t1, e_)          # vai até a emenda: sem voltar ao quadro aberto antes do corte
    centro = centro_movimento(NOME, t0, t1)
    FX.append({"tipo": "dolly", "inicio": t0, "fim": t1, "escala": z.get("escala", 1.32), "centro": centro})
for r in VIS.get("revelacao", []):
    t = corte_t(r["t"])
    FX.append({"tipo": "flash", "inicio": t, "fim": round(t + 0.3, 3), "forca": 0.28})
for pol in VIS.get("polaroid", []):
    t0 = corte_t(pol["t"])
    img = S / f"polaroid_{pol['t']}.png"
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", str(pol["t_foto"]), "-i",
                    str(P / "original.mp4"), "-frames:v", "1", str(img)], check=True)
    A.append({"tipo": "polaroid", "imagem": str(img), "recorte": pol["recorte"], "legenda": pol["legenda"],
              "largura": pol.get("largura", 440), "giro": pol.get("giro", -6), "x": pol["x"], "y": pol["y"],
              "inicio": t0, "fim": round(t0 + pol.get("dur", 3.2), 3), "som": None})

# ---------------- aproximações ----------------
for r in dec.get("reacoes_zoom", []):
    ids = mantidas(r["de"], r["ate"])
    if not ids:
        continue
    t0 = ini(ids[0], 0.04)
    if any(e["inicio"] - 0.3 < t0 < e["fim"] + 0.3 for e in FX if e["tipo"] in ("dolly", "zoom")):
        continue
    FX.append({"tipo": "zoom", "inicio": t0, "fim": round(min(D, t0 + 1.3), 3), "escala": 1.10,
               "entrada": 0.3, "saida": 0.35})
for r in dec.get("emocao_lenta", []):
    ids = mantidas(r["de"], r["ate"])
    if not ids:
        continue
    t = ini(ids[0], 0.0)
    t_fim = fim(ids[-1], 0.2)
    while t < t_fim - 3:
        e = min(emenda_depois(t), D)
        if e - t >= 5 and not any(x["inicio"] < e and x["fim"] > t for x in FX if x["tipo"] in ("dolly", "zoom")):
            FX.append({"tipo": "dolly", "inicio": round(t + 0.15, 3), "fim": e, "escala": 1.06})
        t = e

# ---------------- próximo episódio ----------------
pr = dec.get("proximo")
if pr:
    ids = mantidas(pr["de"], pr["ate"])
    t0 = ini(ids[0], 0.15)
    A.append({"tipo": "texto", "texto": pr["texto"], "sobre": pr.get("sobre"), "tam": 128, "som": None,
              "inicio": t0, "fim": round(min(D - 0.05, t0 + 4.8), 3)})

# ---------------- movimento extra (revisão) ----------------
for mv in dec.get("fx_mover", []):
    for x in FX:
        if abs(x["inicio"] - mv["de"]) < 0.1:
            x["fim"] = round(x["fim"] + mv["para"] - x["inicio"], 3)
            x["inicio"] = mv["para"]
for x in dec.get("fx_extra", []):
    FX.append({k: v for k, v in x.items() if k != "por_que"})

# ---------------- planos longos sem movimento: aproximação lenta até o corte ----------------
for a_, b_ in zip(emendas, emendas[1:]):
    if b_ - a_ >= 5 and not any(x["inicio"] < b_ - 0.3 and x["fim"] > a_ + 0.3 for x in FX if x["tipo"] == "dolly"):
        FX.append({"tipo": "dolly", "inicio": round(a_, 3), "fim": round(b_, 3), "escala": 1.05 if b_ - a_ > 9 else 1.04})

# ---------------- só os 6 sons escolhidos (nada mais toca) ----------------
sg = dec.get("som_gancho")
if sg:
    SX.append({"t": 0.0, "tipo": sg["tipo"], "db": sg.get("db", -20), "junto": True})
for st in dec.get("sons_tempo", []):
    SX.append({"t": corte_t(st["t_orig"]), "tipo": st["tipo"], "db": st.get("db", -20), "junto": True})
for s_ in dec["sons"]:
    i = s_["indice"]
    if i not in manter:
        viz = [j for j in range(i, min(len(ws), i + 12)) if j in manter]
        if not viz:
            AVISOS.append(f"som sem palavra no corte: {s_}")
            continue
        i = viz[0]
    antes = 0.15 if s_["tipo"].startswith("whoosh") else 0.0
    SX.append({"t": ini(i, antes), "tipo": s_["tipo"], "db": s_.get("db", -18), "junto": True})
ed["sons_so_extras"] = True

# ---------------- final ----------------
ed["fundo"] = {"desfoque": 18, "escurecer": 0.86, "dessaturar": 0.18, "luz_rosto": 0.16,
               "sem_desfoque": [[next(e for e in emendas if abs(e - 152.37) < 0.1), 154.6]], "teto_fora": [[169.4, 171.6], [199.3, 203.3]]}
A.sort(key=lambda a: a["inicio"])
for x in FX:                     # movimento que termina numa emenda acaba 1 quadro antes (não vaza no plano seguinte)
    for e_ in emendas:
        if abs(x["fim"] - e_) < 0.02:
            x["fim"] = round(e_ - 0.005, 4)
FX.sort(key=lambda e: e["inicio"])
ed["animacoes"] = A
ed["fx"] = FX
ed["sons_extra"] = sorted(SX, key=lambda s: s["t"])
_oc = sorted([[a["inicio"], a["fim"]] for a in A if a["tipo"] in ("frase", "texto")] + [[0.0, ed["gancho"]["fim"]]])
_jun = []
for a_, b_ in _oc:               # frases coladas: um intervalo só (a legenda comum não pisca entre elas)
    if _jun and a_ - _jun[-1][1] < 0.35:
        _jun[-1][1] = max(_jun[-1][1], b_)
    else:
        _jun.append([a_, b_])
ed["legenda_oculta"] = _jun
ed.pop("chamada", None)
(P / "edicao.json").write_text(json.dumps(ed, ensure_ascii=False, indent=2))
_transcricao_do_corte(NOME, segs)


def mm(x):
    return f"{int(x // 60)}:{x % 60:05.2f}"


print("corte", mm(D), "| gancho até", ed["gancho"]["fim"])
for a in A:
    txt = a.get("texto") or " ".join(p["w"] for p in a.get("palavras", [])) or a.get("legenda", "")
    print(f"{mm(a['inicio'])}-{mm(a['fim'])} {a['tipo']:8s} {txt.replace(chr(10), ' / ')[:70]}")
for e in FX:
    print(f"   fx {e['tipo']:6s} {mm(e['inicio'])}-{mm(e['fim'])} {e.get('escala', e.get('forca', ''))} {e.get('centro', '')}")
for s in ed["sons_extra"]:
    print(f"   som {s['tipo']:10s} {mm(s['t'])}")
for a in AVISOS:
    print("AVISO:", a)
print(len(A), "elementos,", len(FX), "efeitos,", len(SX), "sons")
