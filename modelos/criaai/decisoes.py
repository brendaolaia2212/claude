"""Cria Aí (criaai-1): correções de palavras, tempos refeitos e cortes do plano verificado.
Cada correção confere a palavra que está lá antes de trocar (índice errado = para tudo)."""
import json
import shutil
import sys
from pathlib import Path

P = Path("/home/user/claude/trabalho/criaai-1")
C = Path("/tmp/claude-0/-home-user-claude/9a8ce83d-651a-520e-8e0f-8249ec8620b1/scratchpad/criaai")
ws = json.loads((P / "transcricao.json").read_text())
if not (P / "transcricao_small.json").exists():
    shutil.copy(P / "transcricao.json", P / "transcricao_small.json")
plano = json.loads((C / "plano.json").read_text())
ruins = []
for c in plano["correcoes"]:
    i, antes, depois = c["i"], c["atual"], c["novo"]
    if ws[i]["w"] == depois:
        continue
    if ws[i]["w"] != antes:
        ruins.append((i, antes, ws[i]["w"]))
        continue
    ws[i]["w"] = depois
if ruins:
    sys.exit(f"Índice não bate: {ruins}")
# tempos refeitos (energia + segunda escuta)
TEMPOS = {783: ("No", 413.97, 414.24), 784: ("UGC", 414.24, 414.56), 785: ("Studio", 414.56, 415.05),
          786: ("entra", 415.05, 415.37), 1249: ("E", 646.78, 646.83)}
for i, (w, s, e) in TEMPOS.items():
    if ws[i]["w"].strip(" ,.").lower() not in (w.lower(), "studio", "estúdio", "entra", "e", "no", "ugc"):
        sys.exit(f"Tempo: índice {i} é {ws[i]['w']!r}, esperava {w!r}")
    ws[i]["s"], ws[i]["e"] = s, e
if ws[859]["w"].strip(" ,.").lower() == "tudo":
    ws[859]["s"] = 445.30
else:
    sys.exit(f"859 é {ws[859]['w']!r}")
if ws[93]["w"].strip(" ,.").lower() == "na":
    ws[93]["s"] = 94.40
(P / "transcricao.json").write_text(json.dumps(ws, ensure_ascii=False, indent=1))

ed = json.loads((P / "edicao.json").read_text())
ed["tirar_palavras"] = [[t["de"], t["ate"]] for t in plano["tirar"]]
ed["manter_palavras"] = [[218, 219]]
ed["estilo"] = {"legenda": "pulso", "gancho": "vidro", "cor": "#FF6A00", "fundo": "#0D2B3E", "zoom": False,
                "animacoes": "poucas", "sons": True}
(P / "edicao.json").write_text(json.dumps(ed, ensure_ascii=False, indent=2))
print("ok:", len(plano["correcoes"]), "correções,", len(TEMPOS) + 2, "tempos,", len(ed["tirar_palavras"]), "cortes")
