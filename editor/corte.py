"""Plano de corte (pausas, tomadas repetidas, muletas) e montagem do corte.mp4."""
import difflib
import json
import math
import re
from concurrent.futures import ThreadPoolExecutor

from .base import (FPS, ALTURA, LARGURA, ffmpeg, ler_edicao, ler_json, mmss, pasta,
                   salvar_edicao, sem_acento, sondar)

PAUSA_MAX = 0.25          # silêncio maior que isso entre palavras sai
FOLGA_ANTES, FOLGA_DEPOIS = 0.06, 0.10
MULETAS = {"hum", "hmm", "hm", "ahn", "ah", "eh", "ehh", "ee", "eee", "aa", "aaa", "uh", "uhm", "ã"}


def _frases(palavras):
    """Quebra a fala em frases: pausa longa ou pontuação final."""
    frases, atual = [], []
    for i, w in enumerate(palavras):
        if atual and (w["s"] - atual[-1]["e"] > 0.45):
            frases.append(atual)
            atual = []
        atual.append(dict(w, i=i))
        if re.search(r"[.?!…]$", w["w"]):
            frases.append(atual)
            atual = []
    if atual:
        frases.append(atual)
    return frases


def _toks(frase):
    return [t for t in (sem_acento(w["w"]) for w in frase) if t]


def _muletas(palavras):
    fora = set()
    for i, w in enumerate(palavras):
        t = sem_acento(w["w"])
        if t in MULETAS:
            fora.add(i)
        if t == "tipo" and i + 1 < len(palavras) and sem_acento(palavras[i + 1]["w"]) == "assim":
            antes = w["s"] - palavras[i - 1]["e"] if i else 1
            depois = palavras[i + 2]["s"] - palavras[i + 1]["e"] if i + 2 < len(palavras) else 1
            if antes > 0.3 and depois > 0.3:
                fora |= {i, i + 1}
    return fora


def _tomadas(frases):
    """Tomadas repetidas: fica a última. Devolve (índices de frases que saem, dúvidas)."""
    fora, duvidas = set(), []
    for i, a in enumerate(frases):
        ta = _toks(a)
        if not ta:
            continue
        for j in range(i + 1, min(i + 4, len(frases))):
            tb = _toks(frases[j])
            if not tb:
                continue
            n = min(len(ta), len(tb), 5)
            inicio_igual = n >= 3 and sum(x == y for x, y in zip(ta[:n], tb[:n])) >= n - (n == 5)
            abandonada = len(ta) <= 2 and tb[:len(ta)] == ta and j == i + 1
            if not (inicio_igual or abandonada):
                continue
            sim = difflib.SequenceMatcher(None, ta, tb[:len(ta) + 1]).ratio()
            limite = 0.85 if len(ta) >= 8 else 0.7
            if abandonada or len(ta) < len(tb) * 0.6 or sim >= limite:
                fora.add(i)
            else:
                duvidas.append((i, j))
            break
    return fora, duvidas


def _juntar_trechos(manter, palavras, silencios, duracao):
    """Palavras mantidas -> trechos [ini, fim] com folga e sem pausa longa."""
    trechos = []
    for i in manter:
        w = palavras[i]
        if trechos and trechos[-1][2] == i - 1 and w["s"] - trechos[-1][1] <= PAUSA_MAX:
            trechos[-1][1], trechos[-1][2] = w["e"], i
        else:
            trechos.append([w["s"], w["e"], i, i])
    res = []
    for s, e, ult, pri in trechos:
        ant = palavras[pri - 1]["e"] if pri > 0 else 0.0
        prox = palavras[ult + 1]["s"] if ult + 1 < len(palavras) else duracao
        # o whisper costuma esticar o fim da palavra pra dentro do silêncio
        for a, b in silencios:
            if a < e < b and a > s:
                e = a
            if a < s < b and b < e:
                s = b
        s = max(s - FOLGA_ANTES, ant, 0.0)
        e = min(e + FOLGA_DEPOIS, prox, duracao)
        # silêncio longo inteiro dentro do trecho: divide
        partes, ini = [], s
        for a, b in silencios:
            if ini + 0.1 < a and b < e - 0.1 and b - a > PAUSA_MAX + 0.1:
                partes.append([ini, a + FOLGA_DEPOIS])
                ini = b - FOLGA_ANTES
        partes.append([ini, e])
        res.extend(partes)
    unidos = []
    for s, e in res:
        if unidos and s <= unidos[-1][1] + 0.02:
            unidos[-1][1] = max(unidos[-1][1], e)
        else:
            unidos.append([s, e])
    return _quantizar(unidos)


def _quantizar(trechos, perto=False):
    """Cada trecho com duração em quadros inteiros: voz e imagem nunca escorregam.

    perto=False: o começo arredonda pra trás e o fim pra frente (sem bordas pelo som,
    nunca come o começo nem o fim da palavra). perto=True: quadro mais perto (as bordas
    pelo som já têm folga; arredondar pra fora poderia entrar no respiro seguinte)."""
    out = []
    for s, e in trechos:
        a = round(s * FPS) if perto else math.floor(s * FPS + 1e-6)
        b = round(e * FPS) if perto else math.ceil(e * FPS - 1e-6)
        if out and a <= round(out[-1][1] * FPS):
            a = round(out[-1][1] * FPS)
        if b - a >= 3:
            out.append([round(a / FPS, 4), round(b / FPS, 4)])
    return out


def planejar(nome):
    p = pasta(nome)
    ed = ler_edicao(nome)
    palavras = ler_json(p / "transcricao.json")
    if not palavras:
        raise SystemExit("Não ouvi fala nenhuma nesse vídeo.")
    sil = ler_json(p / "silencios.json", [])
    dur = sondar(ed["original"])["duracao"]

    frases = _frases(palavras)
    frases_fora, duvidas = _tomadas(frases)
    mul = _muletas(palavras)
    fora = set(mul)
    for k in frases_fora:
        fora |= {w["i"] for w in frases[k]}
    # decisões feitas lendo a fala (índices de palavra, intervalos fechados)
    for a, b in ed.get("tirar_palavras", []):
        fora |= set(range(a, b + 1))
    for a, b in ed.get("manter_palavras", []):
        fora -= set(range(a, b + 1))
    manter = [i for i in range(len(palavras)) if i not in fora]
    en = _energia(nome)
    if en:
        from .bordas import conferir, trechos_por_energia
        trechos = _quantizar(trechos_por_energia(manter, palavras, en, dur, PAUSA_MAX), perto=True)
        arriscados = conferir(trechos, en)
        # borda que cai com som (fala emendada): emenda mais macia, sem estalo
        fades = [[0.04 if en.tem_som(s + 0.012) else 0.01, 0.04 if en.tem_som(e - 0.012) else 0.01]
                 for s, e in trechos]
    else:
        trechos = _juntar_trechos(manter, palavras, sil, dur)
        arriscados, fades = [], None

    pausas = sum(1 for a, b in zip(trechos, trechos[1:]) if b[0] - a[1] > PAUSA_MAX)
    final = sum(e - s for s, e in trechos)
    longas = [w for w in palavras if w["e"] - w["s"] > 1.2]
    ed["corte"] = {"segmentos": trechos, "palavras": manter}
    if fades:
        ed["corte"]["fades"] = fades
    salvar_edicao(nome, ed)

    linhas = [f"Tirei {pausas} pausa(s), {len(frases_fora)} frase(s) repetida(s) ou abandonada(s)"
              f" e {len(mul)} muleta(s) (hum, ahn).",
              f"O vídeo foi de {mmss(dur)} pra {mmss(final)}."]
    if frases_fora:
        linhas.append("Saíram: " + " | ".join(
            f"{mmss(frases[k][0]['s'])} \"{' '.join(w['w'] for w in frases[k])}\"" for k in sorted(frases_fora)))
    for i, j in duvidas:
        linhas.append(f"Conferir (mantive as duas, parece repetição de propósito): "
                      f"{mmss(frases[i][0]['s'])} e {mmss(frases[j][0]['s'])}")
    for w in longas:
        linhas.append(f"Atenção: \"{w['w']}\" em {mmss(w['s'])} dura {w['e'] - w['s']:.1f}s, "
                      "pode ter frase repetida escondida. Vale ouvir.")
    if en:
        linhas.append(f"Bordas pelo som: {2 * len(trechos)} pontas de corte, "
                      f"{len(arriscados)} caem com som (fala emendada).")
        for t, lado in arriscados[:15]:
            linhas.append(f"  Conferir borda ({lado}) em {mmss(t)} do original")
    return "\n".join(linhas)


def _energia(nome):
    """Energia do áudio (voz16k.wav que o transcrever deixa) pras bordas dos cortes."""
    from .bordas import Energia
    p = pasta(nome)
    wav = p / "voz16k.wav"
    if not wav.exists():
        ed = ler_edicao(nome)
        if not sondar(ed["original"])["tem_som"]:
            return None
        ffmpeg("-i", ed["original"], "-vn", "-ac", 1, "-ar", 16000, "-c:a", "pcm_s16le", wav)
    return Energia(wav)


def corte_para_original(segmentos):
    """Lista (ini_corte, fim_corte, ini_original) de cada trecho."""
    out, t = [], 0.0
    for s, e in segmentos:
        out.append((t, t + (e - s), s))
        t += e - s
    return out


def tirar(nome, ini, fim):
    """Tira do corte o intervalo [ini, fim] (tempo do corte que a pessoa viu)."""
    ed = ler_edicao(nome)
    novos = []
    for a, b, s in corte_para_original(ed["corte"]["segmentos"]):
        e = s + (b - a)
        oi, of = s + max(0, ini - a), s + min(b - a, fim - a)
        if of <= s or oi >= e or fim <= a or ini >= b:
            novos.append([s, e])
            continue
        if oi > s:
            novos.append([s, oi])
        if of < e:
            novos.append([of, e])
    ed["corte"]["segmentos"] = _quantizar(novos)
    ed["corte"].pop("fades", None)
    salvar_edicao(nome, ed)
    return sum(e - s for s, e in ed["corte"]["segmentos"])


def tamanho(ed):
    """(largura, altura) do vídeo editado: em pé (padrão) ou 16:9 pro YouTube."""
    return (1920, 1080) if ed.get("formato") == "16:9" else (LARGURA, ALTURA)


def _filtro_video(info, ed=None):
    L, A = tamanho(ed or {})
    return (f"scale={L}:{A}:force_original_aspect_ratio=increase,"
            f"crop={L}:{A},fps={FPS},setsar=1,format=yuv420p")


def _extrair(args):
    """Um trecho: vídeo .mp4 (sem som) e som .wav separados, os dois com a mesma duração exata."""
    i, (s, e), original, saida, vf, tem_som, (fi, fo) = args
    n = int(round((e - s) * FPS))
    d = n / FPS
    entrada = ["-ss", f"{s:.4f}", "-t", f"{d + 0.2:.4f}", "-i", original]
    ffmpeg(*entrada, "-map", "0:v:0", "-vf", vf, "-frames:v", n, "-an",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-g", "30",
           "-video_track_timescale", "15360", f"{saida}.mp4")
    if tem_som:
        af = (f"aresample=48000,aformat=channel_layouts=stereo,afade=t=in:d={fi},"
              f"apad,atrim=end_sample={int(round(d * 48000))},afade=t=out:st={d - fo:.5f}:d={fo}")
        ffmpeg(*entrada, "-map", "0:a:0", "-af", af, "-c:a", "pcm_s16le", "-ar", 48000, f"{saida}.wav")
    else:
        ffmpeg("-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-t", f"{d:.5f}",
               "-c:a", "pcm_s16le", f"{saida}.wav")
    return saida


def montar(nome):
    """Monta o corte.mp4 numa passada só: lê o original uma vez e fica com os quadros
    dos trechos (rápido mesmo com centenas de cortes); o som é cortado à parte, com
    emenda macia em cada corte."""
    import wave

    import numpy as np

    p = pasta(nome)
    ed = ler_edicao(nome)
    info = sondar(ed["original"])
    segs = ed["corte"]["segmentos"]
    tmp = p / "trechos"
    tmp.mkdir(exist_ok=True)
    for f in tmp.glob("*"):
        f.unlink()
    L, A = tamanho(ed)
    quadros = [(int(round(s * FPS)), int(round(e * FPS))) for s, e in segs]
    expr = "+".join(f"between(n\\,{a}\\,{b - 1})" for a, b in quadros)
    (tmp / "filtro.txt").write_text(
        f"fps={FPS},select={expr},setpts=N/{FPS}/TB,"
        f"scale={L}:{A}:force_original_aspect_ratio=increase,crop={L}:{A},setsar=1,format=yuv420p")
    ffmpeg("-i", ed["original"], "-map", "0:v:0", "-filter_script:v", tmp / "filtro.txt", "-an",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-g", "30", "-fps_mode", "passthrough",
           "-video_track_timescale", "15360", tmp / "video.mp4")
    total = sum(b - a for a, b in quadros)
    sr = 48000
    fades = ed["corte"].get("fades") or []
    if len(fades) != len(segs):
        fades = [[0.01, 0.01]] * len(segs)
    if info["tem_som"]:
        bruto = tmp / "som_original.wav"
        ffmpeg("-i", ed["original"], "-map", "0:a:0", "-vn", "-ac", 2, "-ar", sr, "-c:a", "pcm_s16le", bruto)
        with wave.open(str(bruto), "rb") as f:
            som = np.frombuffer(f.readframes(f.getnframes()), np.int16).reshape(-1, 2)
        partes = []
        for (a, b), (fi, fo) in zip(quadros, fades):
            i0, n = a * sr // FPS, (b - a) * sr // FPS
            x = som[i0:i0 + n].astype(np.float32)
            if len(x) < n:
                x = np.concatenate([x, np.zeros((n - len(x), 2), np.float32)])
            ni, no = max(1, int(fi * sr)), max(1, int(fo * sr))
            x[:ni] *= np.linspace(0, 1, ni)[:, None]
            x[-no:] *= np.linspace(1, 0, no)[:, None]
            partes.append(x)
        mix = np.concatenate(partes).clip(-32768, 32767).astype(np.int16)
        bruto.unlink()
    else:
        mix = np.zeros((total * sr // FPS, 2), np.int16)
    with wave.open(str(tmp / "audio.wav"), "wb") as f:
        f.setnchannels(2)
        f.setsampwidth(2)
        f.setframerate(sr)
        f.writeframes(mix.tobytes())
    ffmpeg("-i", tmp / "video.mp4", "-i", tmp / "audio.wav", "-map", "0:v", "-map", "1:a",
           "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", p / "corte.mp4")
    _transcricao_do_corte(nome, segs)
    for f in tmp.glob("*"):
        f.unlink()
    return sondar(p / "corte.mp4")["duracao"]


def montar_por_trechos(nome):
    """Jeito antigo (um ffmpeg por trecho). Fica pra comparar, se precisar."""
    p = pasta(nome)
    ed = ler_edicao(nome)
    info = sondar(ed["original"])
    segs = ed["corte"]["segmentos"]
    tmp = p / "trechos"
    tmp.mkdir(exist_ok=True)
    for f in tmp.glob("*"):
        f.unlink()
    vf = _filtro_video(info, ed)
    fades = ed["corte"].get("fades") or [[0.01, 0.01]] * len(segs)
    if len(fades) != len(segs):
        fades = [[0.01, 0.01]] * len(segs)
    tarefas = [(i, sg, ed["original"], str(tmp / f"t{i:04d}"), vf, info["tem_som"], tuple(fades[i]))
               for i, sg in enumerate(segs)]
    with ThreadPoolExecutor(2) as ex:
        bases = list(ex.map(_extrair, tarefas))
    (tmp / "v.txt").write_text("".join(f"file '{b}.mp4'\n" for b in bases))
    (tmp / "a.txt").write_text("".join(f"file '{b}.wav'\n" for b in bases))
    ffmpeg("-f", "concat", "-safe", 0, "-i", tmp / "v.txt", "-c", "copy", tmp / "video.mp4")
    ffmpeg("-f", "concat", "-safe", 0, "-i", tmp / "a.txt", "-c", "copy", tmp / "audio.wav")
    ffmpeg("-i", tmp / "video.mp4", "-i", tmp / "audio.wav", "-map", "0:v", "-map", "1:a",
           "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", p / "corte.mp4")
    _transcricao_do_corte(nome, segs)
    for f in tmp.glob("*"):
        f.unlink()
    return sondar(p / "corte.mp4")["duracao"]


def _transcricao_do_corte(nome, segs):
    p = pasta(nome)
    palavras = ler_json(p / "transcricao.json", [])
    manter = set(ler_edicao(nome)["corte"].get("palavras", range(len(palavras))))
    mapa = corte_para_original(segs)
    out = []
    for i, w in enumerate(palavras):
        if i not in manter:
            continue
        # o trecho com maior sobreposição fica com a palavra (o whisper erra as bordas)
        melhor, sob = None, 0.0
        for a, b, s in mapa:
            e = s + (b - a)
            o = min(e, w["e"]) - max(s, w["s"])
            if o > sob:
                melhor, sob = (a, b, s), o
        if melhor and sob >= min(0.06, 0.3 * (w["e"] - w["s"])):
            a, b, s = melhor
            out.append({"w": w["w"], "s": round(max(a, a + w["s"] - s), 3),
                        "e": round(min(b, a + w["e"] - s), 3)})
    (p / "transcricao_corte.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    # emendas: pro zoom e pra não pôr animação em cima do pulo
    (p / "emendas.json").write_text(json.dumps([round(a, 3) for a, _, _ in mapa][1:]))
