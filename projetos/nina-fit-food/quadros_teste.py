"""Renderiza quadros soltos da montagem (pra conferir sem gerar o vídeo todo).
Uso: python quadros_teste.py saida.jpg t1 t2 ..."""
import sys

from PIL import Image, ImageDraw

import montagem as M

tempos = [float(x) for x in sys.argv[2:]]
L = M.montar_linha()
itens = M.camadas(L)
imgs = []
for t in tempos:
    obj, t0 = M.objeto_em(L, t)
    obj.abrir()
    tela = M.quadro(L, itens, t, {})
    obj.fechar()
    imgs.append(tela.convert("RGB").resize((360, 640)))
M.rostos.salvar()
cols = min(6, len(imgs))
linhas = (len(imgs) + cols - 1) // cols
folha = Image.new("RGB", (cols * 360, linhas * 664), "white")
d = ImageDraw.Draw(folha)
for k, (im, t) in enumerate(zip(imgs, tempos)):
    x, y = (k % cols) * 360, (k // cols) * 664
    folha.paste(im, (x, y + 24))
    d.text((x + 6, y + 4), f"{t:.2f}s", fill="black")
folha.save(sys.argv[1], quality=88)
print(sys.argv[1])
