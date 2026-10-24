"""Confere se alguma camada por cima do vídeo (legenda, emoji, número da reação, carimbo, cartão do perfil) cobre
olhos e boca de alguém. Passa pela linha do tempo a cada 0,2 s com os rostos de rostos.py.
Os trechos desenhados da história ficam de fora (lá o texto faz parte da cena). Uso: python conferir_rostos.py
"""
import numpy as np
from PIL import Image

import montagem as M
from marca import W, H

L = M.montar_linha()
itens = M.camadas(L)
problemas = []
for t in np.arange(0.0, L.marcos["fim"], 0.2):
    obj, t0 = M.objeto_em(L, t)
    if isinstance(obj, M.Cena):
        continue
    caixas = [c for c in obj.rostos(t - t0) if c[2] - c[0] > 120]   # rosto pequeno lá no fundo não conta
    if not caixas:
        continue
    tela = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    for f in itens:
        f(tela, t)
    L.leg.desenhar(tela, t)
    a = np.asarray(tela.getchannel("A")) > 60
    for x0, y0, x1, y1 in caixas:
        sub = a[max(0, int(y0)):max(0, int(y1)), max(0, int(x0)):max(0, int(x1))]
        if sub.size and sub.mean() > 0.03:
            problemas.append((round(float(t), 2), obj.nome, [int(v) for v in (x0, y0, x1, y1)], round(float(sub.mean()), 3)))
M.rostos.salvar()
for p in problemas:
    print(p)
print("total", len(problemas))
