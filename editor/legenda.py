"""Legenda no tempo: grupos de palavras, posição fora do rosto, camada de imagens."""
import re

from PIL import Image

from .base import ALTURA, FPS, LARGURA, ZONA_Y
from .estilos import LEGENDAS, bloco_legenda, nome_estilo

Y_PADRAO = 1180
MARGEM = 40


def grupos(palavras, estilo):
    """Agrupa 1 a N palavras, quebrando em pontuação e pausa."""
    maximo = LEGENDAS[nome_estilo(estilo)][0]
    out, atual = [], []
    for k, w in enumerate(palavras):
        if atual and (len(atual) >= maximo or w["s"] - atual[-1]["e"] > 0.3):
            out.append(atual)
            atual = []
        atual.append(w)
        if re.search(r"[.,;:?!…]$", w["w"]) and (maximo < 6 or re.search(r"[.?!…]$", w["w"])):
            out.append(atual)
            atual = []
    if atual:
        out.append(atual)
    return out


def _limpa(t):
    return t.strip().strip(",;:")


def estados(palavras, estilo, fim_video):
    """[(ini, fim, [palavras], ativa)] cobrindo a fala, sem buracos curtos."""
    gs = grupos(palavras, estilo)
    out = []
    for gi, g in enumerate(gs):
        prox = gs[gi + 1][0]["s"] if gi + 1 < len(gs) else fim_video
        fim_g = prox if prox - g[-1]["e"] < 0.5 else g[-1]["e"] + 0.25
        textos = [_limpa(w["w"]) for w in g]
        for k, w in enumerate(g):
            ini = w["s"] if k else g[0]["s"]
            fim = g[k + 1]["s"] if k + 1 < len(g) else fim_g
            if fim - ini > 0.01:
                out.append((ini, min(fim, fim_video), textos, k))
    return out


def posicao_y(bloco_h, zona_rosto, y_padrao=Y_PADRAO, bloqueios=()):
    """Centro vertical da legenda: padrão em ~1180, fora de olhos e boca e de animações na tela.
    None = não tem lugar livre (a legenda some nesse trecho)."""
    def livre(y, faixas):
        return all(y + bloco_h / 2 <= a - MARGEM / 2 or y - bloco_h / 2 >= b + MARGEM / 2 for a, b in faixas)

    candidatos = [y_padrao]
    if zona_rosto:
        _, z0, _, z1 = zona_rosto
        candidatos += [z1 + MARGEM + bloco_h / 2, z0 - MARGEM - bloco_h / 2]
    for a, b in bloqueios:
        candidatos += [b + MARGEM + bloco_h / 2, a - MARGEM - bloco_h / 2]
    rosto = [(zona_rosto[1], zona_rosto[3])] if zona_rosto else []
    dentro = [y for y in candidatos if ZONA_Y[0] + bloco_h / 2 <= y <= ZONA_Y[1] - bloco_h / 2]
    for y in sorted(dentro, key=lambda y: abs(y - y_padrao)):
        if livre(y, rosto + list(bloqueios)):
            return y
    if bloqueios:
        return None
    return min(max(y_padrao, ZONA_Y[0] + bloco_h / 2), ZONA_Y[1] - bloco_h / 2)


class Camada:
    """Sequência de imagens 1080x1920 com duração, virando um vídeo via concat."""

    def __init__(self, pasta_saida):
        self.pasta = pasta_saida
        self.pasta.mkdir(parents=True, exist_ok=True)
        for f in self.pasta.glob("*"):
            f.unlink()
        self.itens = []           # (arquivo, ini, fim)
        self.vazia = self.pasta / "vazia.png"
        Image.new("RGBA", (LARGURA, ALTURA), (0, 0, 0, 0)).save(self.vazia)
        self._cache = {}

    def colocar(self, img, x, y, ini, fim, chave=None):
        if fim - ini <= 0:
            return
        if chave and chave in self._cache:
            arq = self._cache[chave]
        else:
            tela = Image.new("RGBA", (LARGURA, ALTURA), (0, 0, 0, 0))
            tela.alpha_composite(img, (int(x), int(y)))
            arq = self.pasta / f"e{len(self.itens):05d}.png"
            tela.save(arq, compress_level=1)
            if chave:
                self._cache[chave] = arq
        self.itens.append((arq, ini, fim))

    def lista(self, duracao):
        """Escreve o roteiro do concat, com quadros inteiros e sem sobreposição."""
        q = lambda t: round(t * FPS) / FPS
        linhas, t = [], 0.0
        for arq, ini, fim in sorted(self.itens, key=lambda x: x[1]):
            ini, fim = max(q(ini), t), min(q(fim), duracao)
            if fim - ini < 1 / FPS:
                continue
            if ini > t:
                linhas.append((self.vazia, ini - t))
            linhas.append((arq, fim - ini))
            t = fim
        if t < duracao:
            linhas.append((self.vazia, duracao - t))
        txt = "ffconcat version 1.0\n"
        for arq, d in linhas:
            txt += f"file '{arq}'\nduration {d:.5f}\n"
        txt += f"file '{self.vazia}'\n"
        caminho = self.pasta / "lista.txt"
        caminho.write_text(txt)
        return caminho


def montar_camada(camada, palavras, estilo, destaque, rostos, fim_video, oculto=(), deslocar=0.0,
                  y_fixo=(), bloqueios=()):
    """Coloca a legenda inteira numa Camada. oculto = intervalos sem legenda;
    y_fixo = [(ini, fim, y)] pra trechos de tela dividida (legenda na emenda das metades);
    bloqueios = [(ini, fim, y0, y1)] faixas ocupadas por animações."""
    estilo = nome_estilo(estilo)
    revelar = estilo == "papelaria"
    for ini, fim, textos, ativa in estados(palavras, estilo, fim_video):
        for a, b in oculto:
            if ini < b and fim > a:
                if ini >= a:
                    ini = b
                if fim <= b:
                    fim = a
        if fim - ini < 0.04:
            continue
        bloco = bloco_legenda(estilo, textos, ativa, destaque, revelar=revelar)
        fixo = next((y for a, b, y in y_fixo if ini < b and fim > a), None)
        ocupado = [(y0, y1) for a, b, y0, y1 in bloqueios if ini < b and fim > a]
        y = fixo if fixo is not None else \
            posicao_y(bloco.height, rostos.zona(ini + deslocar, fim + deslocar) if rostos else None,
                      bloqueios=ocupado)
        if y is None:
            continue
        x = (LARGURA - bloco.width) / 2
        if estilo == "fita":
            x = 120
        camada.colocar(bloco, x, y - bloco.height / 2, ini, fim,
                       chave=(tuple(textos), ativa, int(y)))
