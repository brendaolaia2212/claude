"""Passa eventos_gravacao.json (tempo da gravação) pra eventos.json (tempo do vídeo cortado).

Todo campo de tempo (ini, fim, ate, t e t_*) em qualquer nível passa por saida_de().
Slide vai sempre inteiro no modo "cheia" (fora os "canto"): a letra fica legível e a Brenda
aparece numa moldura no alto, à direita.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import cortes_aula as C

PASTA = Path(__file__).resolve().parent.parent


def tempo(chave):
    return chave in ("ini", "fim", "ate", "t") or chave.startswith("t_")


def mapear(x):
    if isinstance(x, dict):
        return {k: (round(C.saida_de(v), 3) if tempo(k) and isinstance(v, (int, float)) else mapear(v))
                for k, v in x.items()}
    if isinstance(x, list):
        return [mapear(v) for v in x]
    return x


ev = json.loads((PASTA / "eventos_gravacao.json").read_text())
out = []
for e in ev:
    n = mapear(e)
    if n["fim"] - n["ini"] < 0.3:
        print("evento sumiu no corte:", e["tipo"], e["ini"])
        continue
    if n["tipo"] == "slide" and n.get("modo", "dividida") != "canto":
        # recorte e passeio cortavam colunas do slide no meio: vai o slide inteiro, com ela no alto à direita
        n["modo"], n["pip"] = "cheia", "sup_dir"
        n.pop("recorte", None)
        n.pop("passeio", None)
    out.append(n)
out.sort(key=lambda e: e["ini"])
(PASTA / "eventos.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
print(len(out), "eventos;", sum(1 for e in out if e.get("modo") == "cheia"), "slides em tela cheia")
