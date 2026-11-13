"""Legenda elegante: maiúscula só no começo de frase e em nome próprio (o small capitaliza no
meio da frase). Mexe só no texto, os índices e tempos ficam."""
import json, sys
from pathlib import Path
P = Path("/home/user/claude/trabalho/video-11nov")
ws = json.loads((P / "transcricao.json").read_text())
manter = set(json.loads((P / "edicao.json").read_text())["corte"]["palavras"])
PROPRIOS = {"brenda", "shopee", "tiktok", "shop", "deus", "ia", "cria"}
anterior = "."
mudou = 0
for i, w in enumerate(ws):
    t = w["w"]
    if not t:
        continue
    base = t.strip("¿¡\"“”'").lower().rstrip(".,!?…;:")
    if anterior[-1:] in ".!?…":
        novo = t[:1].upper() + t[1:]
    elif base in PROPRIOS:
        novo = t
    else:
        novo = t[:1].lower() + t[1:]
    if novo != t:
        w["w"] = novo
        mudou += 1
    if i in manter:
        anterior = novo
(P / "transcricao.json").write_text(json.dumps(ws, ensure_ascii=False, indent=1))
print("palavras ajustadas:", mudou)
