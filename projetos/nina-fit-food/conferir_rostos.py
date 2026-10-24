"""Confere se alguma camada (texto, emoji, cartão) cobre olhos e boca. Usa os rostos detectados na linha do tempo."""
import json
import numpy as np
from PIL import Image
import montagem as M
from marca import PASTA, W, H

rostos = json.load(open(PASTA / "rostos_linha.json"))
trechos, audios, leg, marcos = M.montar_linha()
itens = M.camadas(marcos)
ocultar = [(0.0, 2.95), (marcos["bolo"], marcos["bolo"] + 2.0)]
problemas = []
for r in rostos:
    t = r["t"]
    caixas = [c for c in r["caixas"] if (c[2] - c[0]) > 120 and c[1] < 1500]   # ignora detecções pequenas/falsas
    if not caixas:
        continue
    for dt in (0.0, 0.1, 0.2):
        tt = t + dt
        tela = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        for f in itens:
            f(tela, tt)
        leg.desenhar(tela, tt, ocultar)
        a = np.asarray(tela.getchannel("A")) > 60
        for x0, y0, x1, y1 in caixas:
            x0, y0 = max(0, x0), max(0, y0)
            sub = a[y0:y1, x0:x1]
            if sub.size and sub.mean() > 0.03:
                problemas.append((round(tt, 2), r["fonte"], [x0, y0, x1, y1], round(float(sub.mean()), 3)))
for p in problemas:
    print(p)
print("total", len(problemas))
