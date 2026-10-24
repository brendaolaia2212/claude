"""Prepara as fotos e o logo da Nina Fit Food a partir dos anexos que a Brenda mandou.

Uso: python preparar_fotos.py <pasta com os anexos>
Os anexos chegam com nomes aleatórios: copie cada um pro nome abaixo antes de rodar.
  01_tapete_insta.png  print do Instagram da Nina (tapete na porta da loja)
  02_logo.jpg          foto do logo (fundo roxo)
  03_guarapari.jpg     foto da cidade
  04..08_farol_*.png   prints das fotos do Farol
Opcionais (entram no lugar das iniciais/desenho): recortes/danilo.jpg, recortes/nina.jpg, recortes/pib.jpg
"""
import shutil
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageFilter

from marca import PASTA

FOTOS = PASTA / "fotos"
RECORTES = FOTOS / "recortes"

# área da foto dentro de cada print de tela (x0, y0, x1, y1), medida nos prints de 1320x2868
CORTES = {
    "04_farol_ano_novo.png": (0, 849, 1320, 2015),
    "05_farol_sofa.png": (0, 1083, 1320, 1785),
    "06_farol_selfie.png": (0, 1062, 1307, 1804),
    "08_farol_restaurante.png": (0, 552, 1320, 2312),
    "07_farol_19set.png": (0, 930, 1320, 1938),
    "01_tapete_insta.png": (0, 509, 1320, 1828),
}


def recortar_prints():
    RECORTES.mkdir(parents=True, exist_ok=True)
    for arq, caixa in CORTES.items():
        Image.open(FOTOS / arq).convert("RGB").crop(caixa).save(RECORTES / arq.replace(".png", ".jpg"), quality=95)
    # tira o "1/3" do Instagram de cima da foto do sofá
    img = cv2.imread(str(RECORTES / "05_farol_sofa.jpg"))
    mascara = np.zeros(img.shape[:2], np.uint8)
    cv2.rectangle(mascara, (1150, 25), (1295, 110), 255, -1)
    cv2.imwrite(str(RECORTES / "05_farol_sofa_limpa.jpg"), cv2.inpaint(img, mascara, 9, cv2.INPAINT_TELEA),
                [cv2.IMWRITE_JPEG_QUALITY, 95])
    # tapete: corta a borda direita (onde ficavam o "1/7" e o ícone de som)
    Image.open(RECORTES / "01_tapete_insta.jpg").crop((0, 0, 1150, 1319)).save(RECORTES / "01_tapete.jpg", quality=95)


def extrair_logo():
    """Logo em PNG transparente: letras brancas e folhas verdes, sem o fundo roxo."""
    src = Image.open(FOTOS / "02_logo.jpg").convert("RGB")
    K = 5
    a = np.asarray(src.resize((src.width * K, src.height * K), Image.BICUBIC)).astype(float)
    R, G, B = a[..., 0], a[..., 1], a[..., 2]

    def ss(x, lo, hi):
        t = np.clip((x - lo) / (hi - lo), 0, 1)
        return t * t * (3 - 2 * t)
    yy, xx = np.mgrid[0:R.shape[0], 0:R.shape[1]]
    mn = np.minimum(np.minimum(R, G), B)
    branco = ss(mn, 115, 185)
    fit = (yy >= 170 * K) & (yy <= 210 * K) & (xx >= 170 * K) & (xx <= 345 * K)   # "FIT FOOD" é fininho
    branco[fit] = ss(mn[fit], 92, 150)
    verde = ss(G - B, 22, 48) * ss(G, 95, 135)
    fora = ((xx >= 322 * K) & (yy <= 82 * K)) | (yy >= 221 * K)                  # alfinete e @ cortado
    branco[fora] = 0
    verde[fora] = 0

    def suavizar(m, raio, lo=0.32, hi=0.68):
        im = Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(raio))
        return ss(np.asarray(im).astype(float) / 255, lo, hi)
    branco = np.where(fit, suavizar(branco, K * 0.35, 0.25, 0.6), suavizar(branco, K * 0.55))
    verde = suavizar(verde, K * 1.1, 0.4, 0.62)
    alfa = np.maximum(branco, verde)
    mix = verde / np.maximum(alfa, 1e-6)
    cor = np.full(alfa.shape + (3,), 255.0) * (1 - mix[..., None]) + np.array((178, 182, 104)) * mix[..., None]
    img = Image.fromarray(np.dstack([cor, alfa * 255]).clip(0, 255).astype(np.uint8), "RGBA")
    (PASTA / "assets").mkdir(parents=True, exist_ok=True)
    img.crop(img.getchannel("A").getbbox()).save(PASTA / "assets" / "logo_nina.png")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        FOTOS.mkdir(parents=True, exist_ok=True)
        for f in Path(sys.argv[1]).glob("*"):
            if f.name[:2].isdigit():
                shutil.copy2(f, FOTOS / f.name)
    recortar_prints()
    extrair_logo()
    print("fotos e logo prontos")
