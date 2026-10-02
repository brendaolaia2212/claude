"""Montagem final (ou de uma amostra) em cima do corte.mp4 aprovado."""
import json
import re

from PIL import Image

from . import animacoes, sons
from .base import (ALTURA, FPS, LARGURA, ZONA_Y, COR_PADRAO, ffmpeg, ler_edicao, ler_json,
                   pasta, quadros, rodar, sondar)
from .estilos import bloco_gancho
from .legenda import Camada, montar_camada
from .rosto import Rostos

ZOOM = 1.08


def _entre(intervalos):
    return "+".join(f"between(t,{a:.3f},{b:.3f})" for a, b in intervalos) or "0"


def _gancho(camada, ed, rostos, ini, D):
    g = ed.get("gancho")
    if not g or not g.get("texto"):
        return []
    g0, g1 = g.get("inicio", 0.0) - ini, g.get("fim", 2.8) - ini
    if g1 <= 0 or g0 >= D:
        return []
    estilo = ed["estilo"].get("gancho", "manchete")
    bloco = bloco_gancho(estilo, g["texto"], ed["estilo"].get("cor", COR_PADRAO))
    topo = 260
    zona = rostos.zona(g0 + ini, g1 + ini) if rostos else None
    if zona and topo + bloco.height > zona[1] - 20:
        caber = max(0.7, (zona[1] - 20 - topo) / bloco.height)
        bloco = bloco.resize((int(bloco.width * caber), int(bloco.height * caber)), Image.LANCZOS)
    x = (LARGURA - bloco.width) / 2
    escalas = [0.90, 0.933, 0.967]
    for k, e in enumerate(escalas):
        b = bloco.resize((int(bloco.width * e), int(bloco.height * e)), Image.LANCZOS)
        camada.colocar(b, (LARGURA - b.width) / 2, topo + (bloco.height - b.height) / 2,
                       g0 + k / FPS, g0 + (k + 1) / FPS)
    saida = 0.15
    camada.colocar(bloco, x, topo, g0 + len(escalas) / FPS, g1 - saida, chave="gancho")
    for k in range(4):
        a = 1 - (k + 1) / 5
        b = bloco.copy()
        b.putalpha(b.getchannel("A").point(lambda v: int(v * a)))
        camada.colocar(b, x, topo, g1 - saida + k * saida / 4, g1 - saida + (k + 1) * saida / 4)
    return [{"t": max(0.0, g0), "tipo": "whoosh", "db": -17}]


def _lista_animacoes(ed, dur_corte):
    lista = [dict(a) for a in ed.get("animacoes", [])]
    ch = ed.get("chamada")
    if ch and ch.get("texto"):
        d = float(ch.get("duracao", 1.8))
        lista.append({"tipo": "chamada", "texto": ch["texto"], "sub": ch.get("sub"),
                      "inicio": round(dur_corte - d, 3), "fim": round(dur_corte, 3)})
    return lista


def render_parte(nome, ini, fim, saida, rapido=False):
    p = pasta(nome)
    ed = ler_edicao(nome)
    est = ed.get("estilo", {})
    destaque = est.get("cor", COR_PADRAO)
    corte = p / "corte.mp4"
    dur_corte = sondar(corte)["duracao"]
    fim = min(fim, dur_corte)
    D = fim - ini
    rostos = Rostos(nome)
    tmp = p / "render"
    tmp.mkdir(exist_ok=True)

    entradas = (["-ss", f"{ini:.3f}"] if ini > 0 else []) + \
        (["-t", f"{D + 0.05:.3f}"] if fim < dur_corte - 0.01 else []) + ["-i", str(corte)]
    filtros, n_in, sfx = [], 1, []
    atual = "[0:v]"

    # zoom nos cortes: alterna 1,00 e 1,08 a cada emenda, centrado no rosto
    if est.get("zoom", True):
        emendas = [0.0] + ler_json(p / "emendas.json", []) + [dur_corte]
        trechos = [(emendas[k] - ini, emendas[k + 1] - ini) for k in range(1, len(emendas) - 1, 2)]
        trechos = [(max(0, a), min(D, b)) for a, b in trechos if b > 0 and a < D]
        if trechos:
            cx, cy = rostos.centro()
            W2, H2 = int(LARGURA * ZOOM) // 2 * 2, int(ALTURA * ZOOM) // 2 * 2
            x = min(max(cx * ZOOM - LARGURA / 2, 0), W2 - LARGURA)
            y = min(max(cy * ZOOM - ALTURA / 2, 0), H2 - ALTURA)
            filtros.append(f"{atual}split[za][zb];[zb]scale={W2}:{H2},crop={LARGURA}:{ALTURA}:{x:.0f}:{y:.0f}[zz];"
                           f"[za][zz]overlay=0:0:enable='{_entre(trechos)}'[vz]")
            atual = "[vz]"

    # tela dividida: imagem em cima, pessoa embaixo recortada pelo rosto
    y_fixo, oculto = [], [(a - ini, b - ini) for a, b in ed.get("legenda_oculta", [])]
    for k, td in enumerate(ed.get("tela_dividida", [])):
        a, b = td["inicio"] - ini, td["fim"] - ini
        if b <= 0 or a >= D:
            continue
        entradas += ["-loop", "1", "-t", f"{D:.3f}", "-i", td["imagem"]]
        _, cy = rostos.centro()
        fy = min(max(cy - ALTURA / 4, 0), ALTURA / 2)
        filtros.append(f"[{n_in}:v]scale={LARGURA}:{ALTURA // 2}:force_original_aspect_ratio=increase,"
                       f"crop={LARGURA}:{ALTURA // 2},setsar=1,format=yuv420p[top{k}];"
                       f"{atual}split[sa{k}][sb{k}];[sb{k}]crop={LARGURA}:{ALTURA // 2}:0:{fy:.0f}[bot{k}];"
                       f"[top{k}][bot{k}]vstack[ss{k}];"
                       f"[sa{k}][ss{k}]overlay=0:0:enable='between(t,{a:.3f},{b:.3f})'[vs{k}]")
        atual = f"[vs{k}]"
        n_in += 1
        y_fixo.append((a, b, ALTURA / 2))
        sfx.append({"t": max(0.0, a), "tipo": "pop", "db": -17})

    # animações (gravadas antes, pra saber onde ficam e esconder a legenda se cobrirem a faixa)
    anims, bloqueios = [], []
    for k, a in enumerate(_lista_animacoes(ed, dur_corte)):
        if a["inicio"] < ini - 0.05 or a["inicio"] >= fim:
            continue
        mov = tmp / f"anim{k:02d}.mov"
        x, y, W, H, sons_a, dur_a = animacoes.renderizar(a, destaque, mov, rostos.zona(a["inicio"], a["fim"]))
        t0 = a["inicio"] - ini
        anims.append((mov, x, y, t0, min(D, t0 + dur_a)))
        if a["tipo"] != "chamada":
            bloqueios.append((t0, t0 + dur_a, y, y + H))
        else:
            oculto.append((t0, D))
        sfx += [{"t": t0 + ts, "tipo": tipo, "db": db} for tipo, ts, db in sons_a]

    # legenda e gancho: camadas de imagens com duração
    palavras = [dict(w, s=w["s"] - ini, e=w["e"] - ini)
                for w in ler_json(p / "transcricao_corte.json", []) if w["e"] > ini and w["s"] < fim]
    if est.get("legenda", "impacto") != "nenhuma":
        cam = Camada(tmp / "legenda")
        montar_camada(cam, palavras, est.get("legenda", "impacto"), destaque, rostos, D,
                      oculto=oculto, deslocar=ini, y_fixo=y_fixo, bloqueios=bloqueios)
        entradas += ["-f", "concat", "-safe", "0", "-i", str(cam.lista(D))]
        filtros.append(f"{atual}[{n_in}:v]overlay=0:0:format=auto[vl]")
        atual, n_in = "[vl]", n_in + 1
    camg = Camada(tmp / "gancho")
    sfx += _gancho(camg, ed, rostos, ini, D)
    if camg.itens:
        entradas += ["-f", "concat", "-safe", "0", "-i", str(camg.lista(D))]
        filtros.append(f"{atual}[{n_in}:v]overlay=0:0:format=auto[vg]")
        atual, n_in = "[vg]", n_in + 1

    for k, (mov, x, y, t0, t1) in enumerate(anims):
        entradas += ["-i", str(mov)]
        filtros.append(f"[{n_in}:v]setpts=PTS-STARTPTS+{max(t0, 0):.3f}/TB[a{k}];"
                       f"{atual}[a{k}]overlay={x}:{y}:eof_action=pass:format=auto:"
                       f"enable='between(t,{max(t0, 0):.3f},{t1:.3f})'[va{k}]")
        atual, n_in = f"[va{k}]", n_in + 1

    filtros.append(f"{atual}format=yuv420p[vout]")
    script = tmp / "filtros.txt"
    script.write_text(";\n".join(filtros))
    video = tmp / "video.mp4"
    ffmpeg(*entradas, "-filter_complex_script", script, "-map", "[vout]", "-an",
           "-c:v", "libx264", "-preset", "veryfast" if rapido else "medium", "-crf", 20,
           "-r", FPS, "-frames:v", quadros(D), video)

    if est.get("sons", True) is False:
        sfx = []
    sfx = sons.espalhar([s for s in ed.get("sons_extra", []) if ini <= s["t"] < fim] + sfx)
    audio = _audio(nome, ed, corte, ini, D, sfx, tmp)
    ffmpeg("-i", video, "-i", audio, "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac",
           "-b:a", "192k", "-movflags", "+faststart", saida)
    return saida


def _loudnorm_medir(arquivo, filtro_antes=""):
    r = rodar(["ffmpeg", "-hide_banner", "-i", str(arquivo), "-af",
               f"{filtro_antes}loudnorm=I=-14:TP=-1:LRA=11:print_format=json", "-f", "null", "-"])
    return json.loads(re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", r.stderr).group(0))


def _audio(nome, ed, corte, ini, D, sfx, tmp):
    voz = tmp / "voz.wav"
    ffmpeg("-ss", f"{ini:.3f}", "-t", f"{D:.3f}", "-i", corte, "-vn", "-ac", 2, "-ar", 48000, voz)
    entradas, filtros, mix = ["-i", str(voz)], [], ["[0:a]"]
    n = 1
    trilha = ed.get("trilha")
    if trilha and trilha.get("arquivo"):
        voz_i = float(_loudnorm_medir(voz)["input_i"])
        alvo = max(-60, voz_i - float(trilha.get("abaixo_db", 22)))
        entradas += ["-stream_loop", "-1", "-i", trilha["arquivo"]]
        filtros.append(f"[0:a]asplit[vz][sc];[{n}:a]atrim=0:{D:.3f},aresample=48000,"
                       f"aformat=channel_layouts=stereo,loudnorm=I={alvo:.1f}:TP=-6,apad,atrim=0:{D:.3f}[mus];"
                       f"[mus][sc]sidechaincompress=threshold=0.03:ratio=5:attack=15:release=350[md]")
        mix = ["[vz]", "[md]"]
        n += 1
    for k, s in enumerate(sfx):
        entradas += ["-i", str(sons.arquivo(s["tipo"]))]
        ms = int(max(0.0, s["t"]) * 1000)
        filtros.append(f"[{n}:a]volume={s['db'] + 1:.1f}dB,adelay={ms}|{ms},apad,atrim=0:{D:.3f}[s{k}]")
        mix.append(f"[s{k}]")
        n += 1
    if len(mix) > 1:
        filtros.append(f"{''.join(mix)}amix=inputs={len(mix)}:normalize=0:duration=first,"
                       f"atrim=0:{D:.3f}[mix]")
    else:
        filtros.append(f"[0:a]apad,atrim=0:{D:.3f}[mix]")
    script = tmp / "audio.txt"
    script.write_text(";\n".join(filtros))
    misturado = tmp / "mix.wav"
    ffmpeg(*entradas, "-filter_complex_script", script, "-map", "[mix]", "-ar", 48000, misturado)
    m = _loudnorm_medir(misturado)
    final = tmp / "audio_final.wav"
    ffmpeg("-i", misturado, "-af",
           f"loudnorm=I=-14:TP=-1:LRA=11:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
           f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}:"
           f"linear=true,aresample=48000,apad,atrim=0:{D:.3f}", "-ar", 48000, final)
    return final


def _juntar(partes, saida, tmp):
    lista = tmp / "partes.txt"
    lista.write_text("".join(f"file '{x}'\n" for x in partes))
    ffmpeg("-f", "concat", "-safe", 0, "-i", lista, "-c", "copy", "-movflags", "+faststart", saida)


def janelas_amostra(nome):
    """Primeiros 8-10 s + 4 s em volta da 1ª animação e da 1ª tela dividida, se caírem depois."""
    p = pasta(nome)
    ed = ler_edicao(nome)
    dur = sondar(p / "corte.mp4")["duracao"]
    js = [(0.0, min(10.0, dur))]
    anims = sorted(ed.get("animacoes", []), key=lambda a: a["inicio"])
    if anims and anims[0]["inicio"] > 9.0:
        a = anims[0]
        js.append((max(0, a["inicio"] - 0.6), min(dur, max(a["inicio"] + 3.4, min(a["fim"] + 0.4, a["inicio"] + 6)))))
    tds = sorted(ed.get("tela_dividida", []), key=lambda t: t["inicio"])
    if tds and tds[0]["inicio"] > 9.0:
        js.append((max(0, tds[0]["inicio"] - 1), min(dur, tds[0]["inicio"] + 3)))
    js.sort()
    unidas = []
    for a, b in js:
        if unidas and a <= unidas[-1][1] + 0.5:
            unidas[-1] = (unidas[-1][0], max(unidas[-1][1], b))
        else:
            unidas.append((a, b))
    return unidas


def amostra(nome):
    p = pasta(nome)
    js = janelas_amostra(nome)
    partes = []
    for k, (a, b) in enumerate(js):
        partes.append(render_parte(nome, a, b, p / "render" / f"amostra{k}.mp4", rapido=True))
    saida = p / "amostra.mp4"
    if len(partes) == 1:
        partes[0].replace(saida)
    else:
        _juntar(partes, saida, p / "render")
    return saida, js


def completo(nome):
    p = pasta(nome)
    dur = sondar(p / "corte.mp4")["duracao"]
    return render_parte(nome, 0.0, dur, p / "final.mp4")
