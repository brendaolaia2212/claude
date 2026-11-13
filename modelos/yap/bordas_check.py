"""Confere cada borda de corte que cai com som: de que lado está a palavra mantida, qual é a
palavra cortada vizinha, e como está a energia (dB) em volta da borda."""
import json
import sys

sys.path.insert(0, "/home/user/claude")
from editor.bordas import Energia

P = "/home/user/claude/trabalho/pacotes-ep2"
ed = json.load(open(f"{P}/edicao.json"))
ws = json.load(open(f"{P}/transcricao.json"))
en = Energia(f"{P}/voz16k.wav")
manter = set(ed["corte"]["palavras"])
segs = ed["corte"]["segmentos"]


def mm(t):
    return f"{int(t // 60)}:{t % 60:05.2f}"


def perfil(t):
    out = []
    for d in (-0.15, -0.10, -0.05, -0.02, 0.0, 0.02, 0.05, 0.10, 0.15):
        k = en.k(t + d)
        out.append(f"{en.db[k]:.0f}{'*' if en.som[k] else ''}")
    return " ".join(out)


for n, (s, e) in enumerate(segs):
    for t, lado in ((s, "início"), (e, "fim")):
        if not en.tem_som(t + (0.012 if lado == "início" else -0.012)):
            continue
        # palavras em volta da borda
        perto = [i for i, w in enumerate(ws) if w["e"] > t - 1.2 and w["s"] < t + 1.2]
        txt = " ".join((f"[{w['w']}]" if i in manter else f"({w['w']})") + f"{w['s']:.2f}-{w['e']:.2f}"
                       for i, w in ((i, ws[i]) for i in perto))
        dentro = [ws[i]["w"] for i in perto if i in manter and ws[i]["s"] + 0.03 < t < ws[i]["e"] - 0.03]
        print(f"{lado:6s} {mm(t)} ({t:.3f}) seg {n}  dB: {perfil(t)}")
        print(f"        {txt}")
        if dentro:
            print(f"        !!! borda dentro da palavra mantida: {dentro}")
