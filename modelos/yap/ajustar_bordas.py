"""Ajuste fino das emendas do episódio 2, conferidas uma a uma na energia do áudio.

Rodar depois de `planejar`. Cada ajuste: [borda que o planejar deu, borda nova] (tempo do
original). Borda nova sempre num vale (fim da palavra mantida já soou inteiro, a palavra
cortada ainda não começou). "tirar": pedaço que só tem o rabo de palavra cortada.
"""
import json
import math
import sys

sys.path.insert(0, "/home/user/claude")
from editor.bordas import Energia

FPS = 30
P = "/home/user/claude/trabalho/pacotes-ep2"
AJUSTES = {
    "mover": [
        [149.5333, 149.4667],   # "preparada" | (Então): corta no vale antes do "En"
        [193.3000, 193.2667],   # "encomendas" | (Eu fico): vale antes do "Eu"
        [259.6667, 260.3000],   # (Mas) | "Quero": o "s" do "mas" ia junto; começa no silêncio antes do "Quero"
        [275.2000, 275.3333],   # "causos": o "s" final ia ser comido; termina no vale depois dele
        [300.2333, 300.4333],   # (tinha) | "Então": o "a" esticado do "tinha" ia junto
        [394.9667, 395.0333],   # (pequenos) | "mas eu tô": vale antes do "mas"
        [402.0667, 402.1000],   # (pesado) | "esse aqui": vale antes do "esse"
        [418.8000, 418.7000],   # "caixa" ... barulho do saco: corta no vale
        [441.9000, 441.8333],   # "o que é?" | (É curler): termina antes do "É"
        [561.2667, 560.5000],   # volta com o modelador: o "aaah" dela fica inteiro
        [631.6333, 632.4000],   # "aprovado!": joinha e comemoração ficam até o fim
        [665.9333, 665.9000],   # "não imaginava" | (sempre): vale antes do "sempre"
        [706.9000, 706.8667],   # "compre": começa no silêncio, sem apagar o "c"
        [756.5667, 757.3333],   # fim: o sorriso dela depois do "episódio 2" fica (dá tempo do cartão final)
    ],
    "tirar": [151.8333],        # rabo do "lá" (Então, vamos lá) solto antes do "Mas"
}

ed = json.load(open(f"{P}/edicao.json"))
segs = [list(s) for s in ed["corte"]["segmentos"]]
fades = ed["corte"].get("fades") or [[0.01, 0.01] for _ in segs]
en = Energia(f"{P}/voz16k.wav")


def quadro(t):
    return round(round(t * FPS) / FPS, 4)


faltou = []
for velho, novo in AJUSTES["mover"]:
    achou = False
    for s in segs:
        for lado in (0, 1):
            if abs(s[lado] - velho) < 0.006:
                s[lado] = quadro(novo)
                achou = True
    if not achou:
        faltou.append(velho)
manter = [k for k, s in enumerate(segs) if not any(abs(s[0] - t) < 0.006 for t in AJUSTES["tirar"])]
if len(manter) != len(segs) - len(AJUSTES["tirar"]):
    faltou.append(("tirar", AJUSTES["tirar"]))
segs = [segs[k] for k in manter]
fades = [fades[k] for k in manter]
if faltou:
    sys.exit(f"Não achei estas bordas (o planejar mudou?): {faltou}")
for (a, b), (c, d) in zip(segs, segs[1:]):
    assert b <= c, f"emenda encavalada: {b} > {c}"
assert all(round((b - a) * FPS) >= 3 for a, b in segs)
# emenda com som: esmaece 40 ms (sem estalo); no silêncio, 10 ms
fades = [[0.04 if en.tem_som(a + 0.012) else 0.01, 0.04 if en.tem_som(b - 0.012) else 0.01] for a, b in segs]
ed["corte"]["segmentos"] = segs
ed["corte"]["fades"] = fades
ed["ajustes_bordas"] = AJUSTES
json.dump(ed, open(f"{P}/edicao.json", "w"), ensure_ascii=False, indent=2)
total = sum(b - a for a, b in segs)
print(f"{len(segs)} trechos, {int(total // 60)}:{total % 60:04.1f} de vídeo")
