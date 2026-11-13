"""Junta as duas escutas: small (com filtro de voz) fora da janela [A, B], medium (sem filtro,
pega as reações no meio do barulho do pacote) dentro. Original guardado em transcricao_small.json."""
import json, shutil, sys
from pathlib import Path
sys.path.insert(0, "/home/user/claude")
from editor.bordas import Energia

P = Path("/home/user/claude/trabalho/video-11nov")
A, B = float(sys.argv[1]), float(sys.argv[2])
if not (P / "transcricao_small.json").exists():
    shutil.copy(P / "transcricao.json", P / "transcricao_small.json")
S = json.loads((P / "transcricao_small.json").read_text())
M = json.loads((P / "transcricao_medium.json").read_text())
en = Energia(P / "voz16k.wav")
tem_som = lambda w: bool(en.som[en.k(w["s"] - 0.05):en.k(w["e"] + 0.05) + 1].any())
antes = [w for w in S if w["s"] < A]
meio = [w for w in M if A <= w["s"] < B and (tem_som(w) or w["p"] > 0.6)]
depois = [w for w in S if w["s"] >= B]
fora = [w for w in M if A <= w["s"] < B and not (tem_som(w) or w["p"] > 0.6)]
final = antes + meio + depois
(P / "transcricao.json").write_text(json.dumps(final, ensure_ascii=False, indent=1))
print(f"small: {len(antes)} + medium: {len(meio)} + small: {len(depois)} = {len(final)}; descartadas {len(fora)}")
