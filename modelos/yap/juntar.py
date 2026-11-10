"""Junta as duas escutas do episódio 2.

Até INICIO_M fica a escuta do small (com filtro de voz, boa no falatório); dali pra frente
entra a do medium sem filtro de voz, que pegou as reações baixas no meio do barulho do
pacote ("É um babyliss!", "esse eu amei", "nossa, mãe"). Palavra do medium caída em
silêncio total (alucinação) sai. O original fica em transcricao_small.json.
"""
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, "/home/user/claude")
from editor.bordas import Energia

P = Path("/home/user/claude/trabalho/pacotes-ep2")
INICIO_M = float(sys.argv[1]) if len(sys.argv) > 1 else 418.0

if not (P / "transcricao_small.json").exists():
    shutil.copy(P / "transcricao.json", P / "transcricao_small.json")
S = json.loads((P / "transcricao_small.json").read_text())
M = json.loads((P / "transcricao_medium.json").read_text())
en = Energia(P / "voz16k.wav")

def tem_som(w):
    a, b = en.k(w["s"] - 0.05), en.k(w["e"] + 0.05)
    return bool(en.som[a:b + 1].any())

base = [w for w in S if w["s"] < INICIO_M]
novas, fora = [], []
for w in M:
    if w["s"] < INICIO_M - 0.05:
        continue
    (novas if tem_som(w) or w["p"] > 0.6 else fora).append(w)
# não deixa a primeira do medium encavalar na última do small
while novas and base and novas[0]["s"] < base[-1]["e"] - 0.05:
    novas.pop(0)
final = base + novas
(P / "transcricao.json").write_text(json.dumps(final, ensure_ascii=False, indent=1))
print(f"small até {INICIO_M}s: {len(base)} palavras; medium dali: {len(novas)}; descartadas: {len(fora)}")
for w in fora:
    print("  fora (silêncio):", w)
