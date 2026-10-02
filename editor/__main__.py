"""EDIT IA PRO · linha de comando. Uso: python -m editor <comando> ...

As mensagens saem em português simples: a IA repassa pra pessoa com as palavras dela."""
import argparse
import json
import re
import shutil
import sys
import time

from .base import (COR_PADRAO, PERFIL, TRABALHO, ler_edicao, ler_json, mmss, pasta, registrar,
                   salvar_edicao, sem_acento, sondar)


def _tempo(s):
    """'12', '12.5', '0:12' ou '1:02.5' -> segundos."""
    s = str(s).strip().replace(",", ".")
    if ":" in s:
        m, x = s.split(":", 1)
        return int(m) * 60 + float(x)
    return float(s)


EXT_VIDEO = (".mp4", ".mov", ".m4v", ".webm", ".mkv", ".avi", ".3gp")
PASTA_ANEXOS = "/root/.claude/uploads"


def _ultimo_anexo():
    from pathlib import Path
    vids = [f for f in Path(PASTA_ANEXOS).glob("**/*") if f.suffix.lower() in EXT_VIDEO]
    if not vids:
        raise SystemExit("Não achei vídeo anexado. Peça pra pessoa anexar de novo ou mandar um link.")
    return str(max(vids, key=lambda f: f.stat().st_mtime))


def _baixar(link):
    """Link do Google Drive, Dropbox ou direto -> arquivo local em trabalho/_entrada."""
    entrada = TRABALHO / "_entrada"
    entrada.mkdir(parents=True, exist_ok=True)
    if "drive.google" in link:
        import gdown
        saida = gdown.download(link, str(entrada) + "/", quiet=True, fuzzy=True)
        if not saida:
            raise SystemExit("Não consegui baixar do Drive. O link precisa estar como "
                             "'Qualquer pessoa com o link pode ver'.")
        return saida
    if "dropbox.com" in link:
        link = re.sub(r"([?&])dl=0", r"\1dl=1", link)
        if "dl=1" not in link:
            link += ("&" if "?" in link else "?") + "dl=1"
    nome = re.sub(r"[?#].*", "", link.rstrip("/").split("/")[-1]) or "video.mp4"
    if not nome.lower().endswith(EXT_VIDEO):
        nome += ".mp4"
    saida = entrada / nome
    from .base import rodar
    rodar(["curl", "-sSL", "--fail", "-o", str(saida), link])
    return str(saida)


def c_novo(a):
    origem = a.arquivo
    if origem == "ultimo":
        origem = _ultimo_anexo()
    elif origem.startswith("http"):
        origem = _baixar(origem)
    info = sondar(origem)
    nome = a.nome or re.sub(r"\s+", "-", sem_acento(re.sub(r"\.[^.]+$", "", origem.split("/")[-1])))[:24] or "video"
    p = TRABALHO / nome
    p.mkdir(parents=True, exist_ok=True)
    ext = origem.rsplit(".", 1)[-1].lower() if "." in origem else "mp4"
    destino = p / f"original.{ext}"
    if not destino.exists():
        shutil.copy2(origem, destino)
    ed = ler_json(p / "edicao.json", {}) or {}
    ed.setdefault("original", str(destino))
    ed.setdefault("estilo", {})
    salvar_edicao(nome, ed)
    registrar(nome, f"recebido {origem.split('/')[-1]} ({mmss(info['duracao'])})")
    avisos = []
    if not info.get("vertical", True):
        avisos.append("o vídeo está deitado (horizontal); vou recortar pro formato em pé")
    if not info["tem_som"]:
        avisos.append("o vídeo não tem som")
    if info.get("altura", 1920) < 1280 or info["bitrate"] < 2_500_000:
        avisos.append("a qualidade está baixa (parece vídeo que passou pelo WhatsApp); "
                      "o resultado fica melhor com o arquivo original salvo em Arquivos")
    if info["duracao"] > 95:
        avisos.append(f"o vídeo tem {mmss(info['duracao'])}: funciona, mas cada etapa demora mais")
    print(json.dumps({"nome": nome, "duracao": round(info["duracao"], 1),
                      "vertical": info.get("vertical"), "tem_som": info["tem_som"],
                      "resolucao": f"{info.get('largura')}x{info.get('altura')}", "avisos": avisos},
                     ensure_ascii=False, indent=1))


def c_transcrever(a):
    from .transcrever import transcrever
    ini = time.time()
    ps = transcrever(a.nome, a.modelo)
    registrar(a.nome, f"transcrito ({len(ps)} palavras, modelo {a.modelo})")
    print(f"{len(ps)} palavras em {time.time() - ini:.0f}s")


def c_planejar(a):
    from .corte import planejar
    print(planejar(a.nome))


def c_tirar(a):
    from .corte import tirar
    d = tirar(a.nome, _tempo(a.ini), _tempo(a.fim))
    registrar(a.nome, f"pedido: tirar {a.ini}-{a.fim} do corte")
    print(f"Tirei. O corte agora tem {mmss(d)}. Rode 'montar' pra gerar o vídeo de novo.")


def c_montar(a):
    from .corte import montar
    from .rosto import detectar
    ini = time.time()
    d = montar(a.nome)
    rs = detectar(a.nome)
    com = sum(1 for r in rs if r["rosto"])
    print(f"corte.mp4 pronto: {mmss(d)} (em {time.time() - ini:.0f}s). Rosto encontrado em "
          f"{com}/{len(rs)} pontos.\nArquivo: {pasta(a.nome) / 'corte.mp4'}")


def c_texto(a):
    """Fala do corte em frases com tempo: base pra gancho e animações."""
    ps = ler_json(pasta(a.nome) / ("transcricao.json" if a.original else "transcricao_corte.json"), [])
    linha, ini = [], None
    for w in ps:
        if ini is None:
            ini = w["s"]
        linha.append(w["w"])
        if re.search(r"[.?!…]$", w["w"]) or len(linha) >= 16:
            print(f"{mmss(ini)}  {' '.join(linha)}")
            linha, ini = [], None
    if linha:
        print(f"{mmss(ini)}  {' '.join(linha)}")
    if a.palavras:
        print("\n" + " ".join(f"{w['w']}@{w['s']:.2f}" for w in ps))


def c_mostruario(a):
    from .conferir import mostruario
    ops = [o.strip() for o in a.opcoes.split(",")] if a.opcoes else None
    print(mostruario(a.nome, a.tipo, _tempo(a.t) if a.t else None, a.cor, ops, a.texto))


def c_sugerir(a):
    from .animacoes import sugerir
    p = pasta(a.nome)
    ps = ler_json(p / "transcricao_corte.json", [])
    dur = sondar(p / "corte.mp4")["duracao"]
    ed = ler_edicao(a.nome)
    ritmo = a.ritmo or ed.get("estilo", {}).get("animacoes", "medias")
    lista = sugerir(ps, ritmo, fim_video=dur)
    print(json.dumps(lista, ensure_ascii=False, indent=1))
    print("\n(Candidatos automáticos. Revise o texto de cada um, complete os campos com '...' "
          "e grave em edicao.json → animacoes.)", file=sys.stderr)


def c_quadros(a):
    from .conferir import folha_de_quadros
    p = pasta(a.nome)
    tempos = [_tempo(t) for t in a.tempos]
    print(folha_de_quadros(p / a.arquivo, tempos, p / f"quadros_{int(time.time())}.jpg"))


def c_amostra(a):
    from .render import amostra
    ini = time.time()
    saida, js = amostra(a.nome)
    registrar(a.nome, "amostra gerada: " + ", ".join(f"{mmss(x)}-{mmss(y)}" for x, y in js))
    print(f"{saida}\nTrechos: " + ", ".join(f"{mmss(x)} a {mmss(y)}" for x, y in js)
          + f" (em {time.time() - ini:.0f}s)")


def c_final(a):
    from .conferir import frases_meta, olhar_final
    from .render import completo
    ini = time.time()
    saida = completo(a.nome)
    conf = olhar_final(a.nome)
    meta = frases_meta(a.nome)
    registrar(a.nome, "vídeo final gerado")
    print(f"{saida}  ({mmss(conf['duracao'])}, em {time.time() - ini:.0f}s)")
    print(f"Duração bate com o corte: {'sim' if conf['bate'] else 'NÃO — conferir'} "
          f"(corte {mmss(conf['duracao_corte'])})")
    print(f"Quadros pra conferir rosto e zona segura: {conf['folha']}")
    _imprimir_meta(meta)


def _imprimir_meta(meta):
    if not meta:
        print("Frases que a Meta reprova: nenhuma encontrada.")
    for t, trecho, motivo in meta:
        print(f"ATENÇÃO Meta · {mmss(t) if t is not None else 'final'} · {motivo}: \"{trecho}\"")


def c_meta(a):
    from .conferir import frases_meta
    _imprimir_meta(frases_meta(a.nome))


def c_estado(a):
    registrar(a.nome, a.linha)
    print((pasta(a.nome) / "estado.md").read_text())


def c_salvar_estilo(a):
    ed = ler_edicao(a.nome)
    PERFIL.mkdir(exist_ok=True)
    dados = {"estilo": ed.get("estilo", {}), "chamada": ed.get("chamada"),
             "origem": a.nome, "salvo_em": time.strftime("%Y-%m-%d")}
    (PERFIL / "estilo.json").write_text(json.dumps(dados, ensure_ascii=False, indent=2))
    print(f"Estilo salvo em {PERFIL / 'estilo.json'}. Faça commit e push pra lembrar nas próximas conversas.")


def c_usar_estilo(a):
    salvo = ler_json(PERFIL / "estilo.json")
    if not salvo:
        raise SystemExit("Ainda não tem estilo salvo.")
    ed = ler_edicao(a.nome)
    ed["estilo"] = salvo["estilo"]
    if salvo.get("chamada") and not ed.get("chamada"):
        ed["chamada"] = salvo["chamada"]
    salvar_edicao(a.nome, ed)
    registrar(a.nome, f"usando o estilo salvo: {json.dumps(salvo['estilo'], ensure_ascii=False)}")
    print(json.dumps(ed["estilo"], ensure_ascii=False))


def c_situacao(a):
    p = pasta(a.nome)
    ed = ler_edicao(a.nome)
    for arq in ["original." + ed["original"].rsplit(".", 1)[-1], "transcricao.json", "corte.mp4",
                "rosto.json", "amostra.mp4", "final.mp4"]:
        print(f"{'✔' if (p / arq).exists() else '·'} {arq}")
    print(json.dumps({k: v for k, v in ed.items() if k != "corte"}, ensure_ascii=False, indent=1))
    if (p / "estado.md").exists():
        print((p / "estado.md").read_text())


def main():
    ap = argparse.ArgumentParser(prog="python -m editor")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("novo"); s.add_argument("arquivo"); s.add_argument("--nome"); s.set_defaults(f=c_novo)
    s = sub.add_parser("transcrever"); s.add_argument("nome"); s.add_argument("--modelo", default="small")
    s.set_defaults(f=c_transcrever)
    s = sub.add_parser("planejar"); s.add_argument("nome"); s.set_defaults(f=c_planejar)
    s = sub.add_parser("tirar"); s.add_argument("nome"); s.add_argument("ini"); s.add_argument("fim")
    s.set_defaults(f=c_tirar)
    s = sub.add_parser("montar"); s.add_argument("nome"); s.set_defaults(f=c_montar)
    s = sub.add_parser("texto"); s.add_argument("nome"); s.add_argument("--original", action="store_true")
    s.add_argument("--palavras", action="store_true"); s.set_defaults(f=c_texto)
    s = sub.add_parser("mostruario"); s.add_argument("nome"); s.add_argument("--tipo", default="legenda",
                                                                               choices=["legenda", "gancho"])
    s.add_argument("--t"); s.add_argument("--cor"); s.add_argument("--opcoes"); s.add_argument("--texto")
    s.set_defaults(f=c_mostruario)
    s = sub.add_parser("sugerir"); s.add_argument("nome"); s.add_argument("--ritmo"); s.set_defaults(f=c_sugerir)
    s = sub.add_parser("quadros"); s.add_argument("nome"); s.add_argument("tempos", nargs="+")
    s.add_argument("--arquivo", default="corte.mp4"); s.set_defaults(f=c_quadros)
    s = sub.add_parser("amostra"); s.add_argument("nome"); s.set_defaults(f=c_amostra)
    s = sub.add_parser("final"); s.add_argument("nome"); s.set_defaults(f=c_final)
    s = sub.add_parser("meta"); s.add_argument("nome"); s.set_defaults(f=c_meta)
    s = sub.add_parser("estado"); s.add_argument("nome"); s.add_argument("linha"); s.set_defaults(f=c_estado)
    s = sub.add_parser("salvar-estilo"); s.add_argument("nome"); s.set_defaults(f=c_salvar_estilo)
    s = sub.add_parser("usar-estilo"); s.add_argument("nome"); s.set_defaults(f=c_usar_estilo)
    s = sub.add_parser("situacao"); s.add_argument("nome"); s.set_defaults(f=c_situacao)
    a = ap.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
