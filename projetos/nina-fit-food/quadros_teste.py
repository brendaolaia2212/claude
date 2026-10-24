"""Renderiza quadros soltos da montagem (pra conferir sem gerar o vídeo todo)."""
import sys
from PIL import Image
import montagem as M

tempos = [float(x) for x in sys.argv[2:]]
trechos, audios, leg, marcos = M.montar_linha()
itens = M.camadas(marcos)
tr = M.transicoes(marcos)
ocultar = [(0.0, 2.95), (marcos["bolo"], marcos["bolo"] + 2.0)]
imgs = []
for t in tempos:
    idx = max(i for i, (t0, _) in enumerate(trechos) if t0 <= t + 1e-6)
    t0, obj = trechos[idx]
    obj.abrir()
    tela = obj.quadro(t - t0)
    obj.fechar()
    for f in itens:
        f(tela, t)
    leg.desenhar(tela, t, ocultar)
    tela = M.aplicar_transicao(tela, t, tr, {})
    imgs.append(tela.convert("RGB").resize((360, 640)))
cols = min(6, len(imgs))
linhas = (len(imgs) + cols - 1) // cols
folha = Image.new("RGB", (cols * 360, linhas * 664), "white")
from PIL import ImageDraw
d = ImageDraw.Draw(folha)
for k, (im, t) in enumerate(zip(imgs, tempos)):
    x, y = (k % cols) * 360, (k // cols) * 664
    folha.paste(im, (x, y + 24))
    d.text((x + 6, y + 4), f"{t:.2f}s", fill="black")
folha.save(sys.argv[1], quality=88)
print(sys.argv[1], marcos)
