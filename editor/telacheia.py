"""Tela cheia de conteúdo com ela numa moldura pequena no canto (picture-in-picture).

edicao.json → "tela_cheia" (tempos no corte):
  {"imagem": "/caminho.png"  (ou "video": "/caminho.mp4"),
   "inicio": 12.0, "fim": 16.5,
   "de": 0.0,              # segundo do vídeo de conteúdo onde começa (opcional)
   "canto": "cima-dir",    # "cima-dir" (padrão) | "cima-esq" | "baixo-dir" | "baixo-esq"
   "moldura": 0.36}        # largura da moldura em fração de 1080 (padrão 0.36)
Opcionais:
  "entrada": "desliza" (padrão: o conteúdo entra pela direita em 0,25 s) | "sobe" | "corte" (seco)
  "recorte": [x0, y0, x1, y1]   só esse pedaço da imagem (em pixels dela), ex. uma seção do site
  "encaixe": "preencher" (padrão: ocupa tudo, corta as sobras) | "caber" (imagem inteira no
             fundo da cor da própria borda dela, bom pra print de site)
  "cor_fundo": "#F1E9DA"        fundo do "caber" (sem ela, a cor da borda da imagem)
  "rolar": true                 imagem comprida desce de cima até embaixo (em vez do zoom lento)
  "aperto": 0.75                quanto do quadro dela entra na moldura (menor = ela maior)
  "borda": "#FF6A00"            cor da borda da moldura
  "legenda_y": 1450             centro da legenda nesse trecho (ex. numa faixa lisa do conteúdo, sem placa)
  "legenda": false              sem legenda nesse trecho
  "placa": false                tira a placa escura translúcida que a legenda ganha nesse trecho

O conteúdo ocupa 1080x1920 (imagem parada ganha zoom lento 1,00→1,06). Ela aparece na moldura
9:16 com cantos arredondados, borda laranja e sombra, recortada pelo rosto, dentro da zona segura.
A moldura surge com escala 0,85→1 em 0,2 s; no fim volta pra ela em tela cheia com corte seco.
O som é sempre o dela. A legenda fica na altura de sempre e só sobe se a moldura estiver embaixo;
nesse trecho ela ganha uma placa escura translúcida (cor "fundo" do estilo) pra ler em cima de
print claro e cheio de texto (Fita e Discreta já têm faixa própria).
"""
import math
import subprocess

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from .base import ALTURA, FPS, LARGURA, cor, ease_out, quadros

ZONA = (60, 240, 1020, 1680)      # zona segura do Reels pra moldura (x0, y0, x1, y1)
TOPO = 250
BORDA, RAIO = 6, 28               # borda laranja e raio do vídeo dela
MARGEM = 48                       # espaço da sombra em volta da moldura
ENTRADA = 0.25                    # deslize do conteúdo
POP = 0.2                         # moldura: 0,85 → 1
ATRASO = 0.12                     # a moldura surge logo depois que o conteúdo começa a entrar
ZOOM_LENTO = 0.06
ROSTO_Y = 0.38                    # altura do centro do rosto dentro da moldura
LARANJA = "#FF6A00"


def _q(t):
    return round(t * FPS) / FPS


def _ease_io(p):
    p = min(1.0, max(0.0, p))
    return p * p * (3 - 2 * p)


def geometria(tc):
    """(x0, y0, largura, altura) da moldura por fora da borda, em pixels do vídeo."""
    fr = min(0.6, max(0.2, float(tc.get("moldura", 0.36))))
    wo = int(round(LARGURA * fr / 2)) * 2
    wi = wo - 2 * BORDA
    hi = int(round(wi * 16 / 9 / 2)) * 2
    ho = hi + 2 * BORDA
    canto = str(tc.get("canto", "cima-dir"))
    x0 = ZONA[0] if canto.endswith("esq") else ZONA[2] - wo
    y0 = ZONA[3] - ho if canto.startswith("baixo") else TOPO
    return x0, y0, wo, ho


def _centro_rosto(rostos, t0, t1):
    cs = [d["rosto"] for d in rostos.dados if d["rosto"] and t0 - 0.5 <= d["t"] <= t1 + 0.5]
    if not cs:
        return rostos.centro()
    xs = sorted(c["x"] + c["w"] / 2 for c in cs)
    ys = sorted(c["y"] + c["h"] / 2 for c in cs)
    return xs[len(xs) // 2], ys[len(ys) // 2]


def _arredondado(w, h, r, fator=4):
    m = Image.new("L", (w * fator, h * fator), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, w * fator - 1, h * fator - 1), r * fator, fill=255)
    return m.resize((w, h), Image.LANCZOS)


def _enfeite(wo, ho, cor_borda):
    """Sombra + placa da borda (o vídeo dela entra por cima, BORDA px pra dentro)."""
    W, H = wo + 2 * MARGEM, ho + 2 * MARGEM
    sombra = Image.new("L", (W, H), 0)
    sombra.paste(_arredondado(wo, ho, RAIO + BORDA), (MARGEM, MARGEM + 12))
    sombra = sombra.filter(ImageFilter.GaussianBlur(18)).point(lambda v: int(v * 0.55))
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    img.putalpha(sombra)
    placa = Image.new("RGBA", (wo, ho), cor(cor_borda))
    placa.putalpha(_arredondado(wo, ho, RAIO + BORDA))
    img.alpha_composite(placa, (MARGEM, MARGEM))
    return img


def _cor_da_borda(im):
    a = np.asarray(im)
    borda = np.concatenate([a[0], a[-1], a[:, 0], a[:, -1]])
    return tuple(int(v) for v in np.median(borda, axis=0)[:3])


def _base_imagem(tc):
    im = Image.open(tc["imagem"]).convert("RGB")
    if tc.get("recorte"):
        im = im.crop(tuple(int(v) for v in tc["recorte"]))
    iw, ih = im.size
    if tc.get("rolar"):
        return im.resize((LARGURA, max(ALTURA, round(ih * LARGURA / iw))), Image.LANCZOS)
    if tc.get("encaixe") == "caber":
        s = min(LARGURA / iw, ALTURA / ih)
        peq = im.resize((max(1, round(iw * s)), max(1, round(ih * s))), Image.LANCZOS)
        fundo = cor(tc["cor_fundo"])[:3] if tc.get("cor_fundo") else _cor_da_borda(im)
        base = Image.new("RGB", (LARGURA, ALTURA), fundo)
        base.paste(peq, ((LARGURA - peq.width) // 2, (ALTURA - peq.height) // 2))
        return base
    s = max(LARGURA / iw, ALTURA / ih)
    big = im.resize((max(LARGURA, round(iw * s)), max(ALTURA, round(ih * s))), Image.LANCZOS)
    x, y = (big.width - LARGURA) // 2, (big.height - ALTURA) // 2
    return big.crop((x, y, x + LARGURA, y + ALTURA))


def _clipe_imagem(tc, saida, t0, n, dur, rapido):
    """Imagem parada vira um clipe 1080x1920 de n quadros, começando t0 s depois do início
    (zoom lento ou rolagem com movimento em subpixel, sem tremer)."""
    import cv2
    arr = np.ascontiguousarray(np.asarray(_base_imagem(tc)))
    enc = subprocess.Popen(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo",
                            "-pix_fmt", "rgb24", "-s", f"{LARGURA}x{ALTURA}", "-r", str(FPS), "-i", "-",
                            "-c:v", "libx264", "-preset", "ultrafast" if rapido else "veryfast", "-crf", "14",
                            "-pix_fmt", "yuv420p", "-g", str(FPS), str(saida)], stdin=subprocess.PIPE)
    for q in range(n):
        p = min(1.0, (t0 + q / FPS) / max(dur, 1e-3))
        if tc.get("rolar"):
            dy = (arr.shape[0] - ALTURA) * _ease_io(p)
            s0 = min(int(dy), arr.shape[0] - ALTURA)
            fatia = arr[s0:s0 + ALTURA + 1]
            M = np.float32([[1, 0, 0], [0, 1, -(dy - s0)]])
            quadro = cv2.warpAffine(fatia, M, (LARGURA, ALTURA), flags=cv2.INTER_LINEAR,
                                    borderMode=cv2.BORDER_REPLICATE)
        else:
            M = cv2.getRotationMatrix2D((LARGURA / 2, ALTURA / 2), 0, 1 + ZOOM_LENTO * p)
            quadro = cv2.warpAffine(arr, M, (LARGURA, ALTURA), flags=cv2.INTER_CUBIC,
                                    borderMode=cv2.BORDER_REFLECT)
        enc.stdin.write(np.ascontiguousarray(quadro).tobytes())
    enc.stdin.close()
    if enc.wait() != 0:
        raise RuntimeError(f"Falhou ao preparar a imagem da tela cheia: {tc['imagem']}")
    return saida


def montar(ed, ini, D, corte, rostos, tmp, entradas, filtros, n_in, atual, rapido=False):
    """Põe as telas cheias do trecho [ini, ini+D] no grafo do render (mexe em entradas e filtros).
    Devolve (atual, n_in, y_fixo, sfx): y_fixo = [(a, b, y0, y1, placa)] faixa da moldura pra legenda
    (ou (a, b, y) com legenda_y)."""
    y_fixo, sfx = [], []
    h = 0.5 / FPS
    # com -ss os quadros do corte caem em off + n/FPS dentro do pedaço (ini nem sempre cai num quadro)
    off = math.ceil(ini * FPS - 1e-6) / FPS - ini

    def g(t):
        return off + round((t - off) * FPS) / FPS
    for k, tc in enumerate(ed.get("tela_cheia", [])):
        if not (tc.get("imagem") or tc.get("video")):
            continue
        i0, i1 = _q(float(tc["inicio"])), _q(float(tc["fim"]))
        a, b = g(i0 - ini), min(g(i1 - ini), D)        # na grade de quadros deste pedaço
        a0 = max(a, off)                       # onde começa dentro deste pedaço
        if b - a0 < 1 / FPS:
            continue
        dur = b - a0
        entrada = tc.get("entrada", "desliza")

        # 1) o conteúdo, 1080x1920, com o tempo já no lugar
        if tc.get("imagem"):
            clipe = tmp / f"tela_cheia{k:02d}.mp4"
            _clipe_imagem(tc, clipe, a0 - a, quadros(dur) + 2, i1 - i0, rapido)
            entradas += ["-i", str(clipe)]
        else:
            de = float(tc.get("de", 0.0)) + (a0 - a)
            entradas += ["-ss", f"{de:.3f}", "-t", f"{dur + 0.1:.3f}", "-i", str(tc["video"])]
        nc = n_in
        n_in += 1
        filtros.append(f"[{nc}:v]setpts=PTS-STARTPTS,fps={FPS},scale={LARGURA}:{ALTURA}:"
                       f"force_original_aspect_ratio=increase,crop={LARGURA}:{ALTURA},setsar=1,"
                       f"format=yuv420p,setpts=PTS+{a0:.4f}/TB[tc{k}]")
        # o deslize conta de um quadro antes: o 1º quadro do trecho já mostra o conteúdo entrando
        s0 = a - 1 / FPS
        mov = f"if(lt(t,{s0 + ENTRADA:.4f}),{{L}}*pow(1-(t-({s0:.4f}))/{ENTRADA},3),0)"
        x = f"'{mov.format(L=LARGURA)}'" if entrada == "desliza" else "0"
        y = f"'{mov.format(L=ALTURA)}'" if entrada == "sobe" else "0"
        filtros.append(f"{atual}[tc{k}]overlay=x={x}:y={y}:enable='between(t,{a0 - h:.4f},{b - h:.4f})'[tv{k}]")
        atual = f"[tv{k}]"
        if a >= 0:
            sfx.append({"t": a, "tipo": "pop" if entrada == "corte" else "swish", "db": -17})

        # 2) ela na moldura do canto: entrada própria do corte (só o trecho), recortada pelo rosto
        x0, y0, wo, ho = geometria(tc)
        if tc.get("legenda") is False:
            pass                                         # sem legenda: render.py põe o trecho em "oculto"
        elif tc.get("legenda_y"):
            y_fixo.append((a0, b, float(tc["legenda_y"])))   # centro da legenda escolhido a dedo
        else:
            y_fixo.append((a0, b, y0 - BORDA, y0 + ho + 26, tc.get("placa", True) is not False))
        am = g(a + (0.0 if entrada == "corte" else ATRASO))
        am0 = max(am, off)
        if b - am0 < 1 / FPS:
            continue
        wi, hi = wo - 2 * BORDA, ho - 2 * BORDA
        aperto = min(1.0, max(0.4, float(tc.get("aperto", 0.75))))
        cw = int(round(LARGURA * aperto / 2)) * 2
        ch = min(ALTURA, int(round(cw * 16 / 9 / 2)) * 2)
        fx, fy = _centro_rosto(rostos, i0, i1)
        cx = min(max(fx - cw / 2, 0), LARGURA - cw)
        cy = min(max(fy - ROSTO_Y * ch, 0), ALTURA - ch)
        enfeite, mascara = tmp / f"tela_cheia{k:02d}_moldura.png", tmp / f"tela_cheia{k:02d}_mascara.png"
        _enfeite(wo, ho, tc.get("borda", LARANJA)).save(enfeite)
        _arredondado(wi, hi, RAIO).save(mascara)
        td = f"{b - am0 + 0.1:.3f}"
        entradas += ["-ss", f"{ini + am0 - 0.25 / FPS:.4f}", "-t", td, "-i", str(corte),
                     "-loop", "1", "-framerate", str(FPS), "-t", td, "-i", str(enfeite),
                     "-loop", "1", "-framerate", str(FPS), "-t", td, "-i", str(mascara)]
        nh, nd, nm = n_in, n_in + 1, n_in + 2
        n_in += 3

        # entrada da moldura: 0,85 → 1 com freio (quadro a quadro), depois parada até o fim
        passos = []
        nq = max(1, int(round(POP * FPS)))
        for j in range(nq):
            e = 0.85 + 0.15 * ease_out(j / nq)
            if e >= 0.99:
                break
            passos.append((am + j / FPS, e))
        t_cheia = am + len(passos) / FPS
        passos = [(t, e) for t, e in passos if t >= off - h]
        Cw, Ch = wo + 2 * MARGEM, ho + 2 * MARGEM
        mx, my = x0 + wo / 2, y0 + ho / 2
        ramos = "".join(f"[pp{k}_{j}]" for j in range(len(passos) + 1))
        filtros.append(f"[{nh}:v]setpts=PTS-STARTPTS,crop={cw}:{ch}:{cx:.0f}:{cy:.0f},scale={wi}:{hi},"
                       f"setsar=1,format=yuva420p[hv{k}];"
                       f"[{nm}:v]format=gray,setpts=PTS-STARTPTS[hm{k}];"
                       f"[hv{k}][hm{k}]alphamerge[ha{k}];"
                       f"[{nd}:v]format=rgba,setpts=PTS-STARTPTS[hd{k}];"
                       f"[hd{k}][ha{k}]overlay={MARGEM + BORDA}:{MARGEM + BORDA}:format=rgb:shortest=1,"
                       f"setpts=PTS+{am0:.4f}/TB" + (f",split={len(passos) + 1}{ramos}" if passos else f"[pp{k}_0]"))
        for j, (t, e) in enumerate(passos):
            w2, h2 = int(round(Cw * e / 2)) * 2, int(round(Ch * e / 2)) * 2
            # o trim fica folgado (meio quadro antes, quase um depois): o fim arredonda pro quadro
            # seguinte e o quadro t nunca se perde; o enable é que escolhe o quadro exato
            filtros.append(f"[pp{k}_{j}]trim=start={t - h:.4f}:end={t + 1.8 * h:.4f},scale={w2}:{h2}[pq{k}_{j}];"
                           f"{atual}[pq{k}_{j}]overlay={mx - w2 / 2:.0f}:{my - h2 / 2:.0f}:format=auto:"
                           f"enable='between(t,{t - h:.4f},{t + h:.4f})'[pv{k}_{j}]")
            atual = f"[pv{k}_{j}]"
        filtros.append(f"{atual}[pp{k}_{len(passos)}]overlay={x0 - MARGEM}:{y0 - MARGEM}:format=auto:"
                       f"enable='between(t,{max(t_cheia, off) - h:.4f},{b - h:.4f})'[pw{k}]")
        atual = f"[pw{k}]"
    return atual, n_in, y_fixo, sfx
