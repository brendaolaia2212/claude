"""Coisas comuns: caminhos, ffmpeg, fontes, cores e o arquivo de edição."""
import json
import os
import re
import subprocess
import unicodedata
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
TRABALHO = RAIZ / "trabalho"
RECURSOS = RAIZ / "recursos"
FONTES = RECURSOS / "fontes"
MODELO_ROSTO = RECURSOS / "modelos" / "face_detection_yunet_2023mar.onnx"
PERFIL = RAIZ / "perfil"

LARGURA, ALTURA, FPS = 1080, 1920, 30
# Zona segura do Reels: todo texto aqui dentro.
ZONA_X = (140, 940)
ZONA_Y = (230, 1530)

COR_PADRAO = "#FFC400"
CORES = {
    "amarelo": "#FFC400", "rosa": "#FF4FA3", "rosa claro": "#FFB3D1", "pink": "#FF2E88",
    "azul": "#2F80FF", "azul bebe": "#9FD3FF", "azul bebê": "#9FD3FF", "verde": "#2ECC71",
    "verde limao": "#B6FF3B", "verde limão": "#B6FF3B", "laranja": "#FF8A1F", "vermelho": "#FF3B3B",
    "roxo": "#8E5CFF", "lilas": "#C9A7FF", "lilás": "#C9A7FF", "branco": "#FFFFFF",
    "dourado": "#D4AF37", "nude": "#E8C4A8", "bege": "#E9D8C0", "vinho": "#8E1F3A",
    "champagne": "#F1DDBF", "terracota": "#C8643B", "preto": "#111111",
}


def rodar(cmd, capturar=False, checar=True):
    """Roda um comando. Em erro, mostra o fim do stderr pra facilitar o conserto."""
    r = subprocess.run(cmd, capture_output=True, text=True)
    if checar and r.returncode != 0:
        fim = "\n".join(r.stderr.strip().splitlines()[-25:])
        raise RuntimeError(f"Falhou: {' '.join(map(str, cmd[:6]))} ...\n{fim}")
    return r.stdout if capturar else r


def ffmpeg(*args):
    return rodar(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *map(str, args)])


def sondar(arquivo):
    """Duração, tamanho já girado, fps, se tem som e taxa de bits."""
    out = rodar(["ffprobe", "-v", "error", "-print_format", "json", "-show_streams",
                 "-show_format", str(arquivo)], capturar=True)
    info = json.loads(out)
    v = next((s for s in info["streams"] if s["codec_type"] == "video"), None)
    a = next((s for s in info["streams"] if s["codec_type"] == "audio"), None)
    dur = float(info["format"].get("duration", 0))
    res = {"duracao": dur, "tem_som": a is not None,
           "bitrate": int(info["format"].get("bit_rate", 0) or 0)}
    if v:
        w, h = int(v["width"]), int(v["height"])
        rot = 0
        for sd in v.get("side_data_list", []):
            if "rotation" in sd:
                rot = int(sd["rotation"])
        if "rotate" in v.get("tags", {}):
            rot = int(v["tags"]["rotate"])
        if abs(rot) % 180 == 90:
            w, h = h, w
        num, den = (v.get("avg_frame_rate") or "30/1").split("/")
        res.update(largura=w, altura=h, fps=float(num) / float(den or 1) if float(den or 1) else 30.0,
                   vertical=h >= w)
    return res


def fonte(nome, tamanho, peso=800):
    from PIL import ImageFont
    arq = {"anton": "Anton-Regular.ttf", "montserrat": "Montserrat-Variable.ttf",
           "caveat": "Caveat-Variable.ttf"}[nome]
    f = ImageFont.truetype(str(FONTES / arq), int(round(tamanho)))
    if nome != "anton":
        try:
            f.set_variation_by_axes([peso])
        except Exception:
            pass
    return f


def cor(valor, alfa=255):
    """'amarelo', '#FFC400' ou 'FFC400' -> (r, g, b, a)."""
    if isinstance(valor, (tuple, list)):
        return tuple(valor[:3]) + (alfa,)
    v = CORES.get(str(valor).strip().lower(), str(valor).strip())
    v = v.lstrip("#")
    if not re.fullmatch(r"[0-9a-fA-F]{6}", v):
        raise ValueError(f"Cor que não entendi: {valor}")
    return (int(v[0:2], 16), int(v[2:4], 16), int(v[4:6], 16), alfa)


def texto_escuro_sobre(c):
    """Escolhe preto ou branco pra ler bem em cima da cor c."""
    r, g, b = c[:3]
    lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
    return (17, 17, 17, 255) if lum > 140 else (255, 255, 255, 255)


def sem_acento(t):
    t = unicodedata.normalize("NFD", t.lower())
    t = "".join(ch for ch in t if unicodedata.category(ch) != "Mn")
    return re.sub(r"[^a-z0-9 ]+", "", t).strip()


def pasta(nome):
    p = TRABALHO / nome
    if not p.exists():
        raise SystemExit(f"Não achei o vídeo '{nome}'. Os que existem: "
                         + ", ".join(sorted(x.name for x in TRABALHO.glob('*') if x.is_dir())))
    return p


def ler_edicao(nome):
    return json.loads((pasta(nome) / "edicao.json").read_text())


def salvar_edicao(nome, dados):
    (pasta(nome) / "edicao.json").write_text(json.dumps(dados, ensure_ascii=False, indent=2))


def ler_json(caminho, padrao=None):
    caminho = Path(caminho)
    return json.loads(caminho.read_text()) if caminho.exists() else padrao


def registrar(nome, linha):
    """Memória do vídeo: uma linha por decisão."""
    with open(pasta(nome) / "estado.md", "a") as f:
        f.write(f"- {datetime.now():%d/%m %H:%M} · {linha}\n")


def mmss(t):
    t = max(0.0, t)
    return f"{int(t // 60)}:{t % 60:04.1f}"


def ease_out(p):
    p = min(1.0, max(0.0, p))
    return 1 - (1 - p) ** 3


def quadros(segundos):
    return int(round(segundos * FPS))
