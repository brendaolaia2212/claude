"""Episódio 2: palavras corrigidas, cortes lidos na fala e trechos de ação -> edicao.json.

Cada correção confere a palavra que está lá antes de trocar (índice errado = para tudo).
"""
import json
import shutil
import sys
from pathlib import Path

P = Path("/home/user/claude/trabalho/pacotes-ep2")
ws = json.loads((P / "transcricao.json").read_text())
if not (P / "transcricao_junta.json").exists():
    shutil.copy(P / "transcricao.json", P / "transcricao_junta.json")

# (índice, o que está lá, o que fica)
FIX = [
    (40, "da", "dar"), (52, "bluzinhas", "blusinhas"), (53, "t", "t-shirt,"), (54, "-shirt,", ""),
    (63, "bluzinha", "blusinha"), (82, "bluzinhas", "blusinhas"), (91, "que,", "quê,"),
    (97, "bluzinhas", "blusinhas"), (141, "espalhar", "espalhafatoso."), (142, "fatoso", ""),
    (145, "bluzinhas", "blusinhas"), (151, "guarda", "guarda-roupa"), (152, "-roupa", ""),
    (187, "da", "do"), (253, "dela,", "dela na"), (257, "A", "a"), (258, "Lini", "Aline"),
    (328, "guarda", "guarda-roupa."), (329, "-roupa", ""), (377, "tem", "têm"), (378, "palpite", "palpite?"),
    (388, "Te", ""), (501, "E", "imperdível,"), (502, "perdida,", ""), (503, "ó,", ""),
    (504, "aperta,", "oferta"), (523, "Shopidot", "Shopee,"), (524, "Que", "do"), (525, "toque", "TikTok"),
    (530, "Velório", "velório."), (554, "2D,", "2 de"), (598, "quero", "Quero"), (636, "to", "tô"),
    (677, "to", "tô"), (740, "meu", "meio"), (798, "boa", "bon"), (799, "vivana", "vivant"),
    # daqui pra frente é a escuta do medium
    (1039, "círculo.", "curler."), (1041, "círculo.", "curler."), (1048, "círculo.", "curler."),
    (1053, "tiktok", "TikTok"), (1054, "shop,", "Shop!"), (1066, "isso,", "isso!"),
    (1068, "acredito,", "acredito!"), (1127, "está", "tá"), (1153, "Cooler", "Curler"),
    (1195, "utilizá", "utilizá-lo"), (1196, "-lo", ""), (1199, "money,", ""), (1211, "t", "t-shirt"),
    (1212, "-shirt", ""), (1232, "hair", "Hair"), (1233, "circuler", "Curler"),
    (1388, "cabelo", "O cabelo,"), (1391, "minha", "minha mãe"), (1392, "falecia", "faleceu,"),
    (1399, "ó", "ó."), (1415, "então", "Então…"), (1416, "comprinha", "Comprinha"),
    (1417, "aprovada", "aprovada!"), (1418, "e", "E"), (1420, "que", "o que"), (1422, "achou", "achou?"),
    (1444, "choppido", "Shop do"), (1445, "tiktok", "TikTok."), (1454, "na", "na Shop do TikTok,"),
    (1478, "com", "como"), (1479, "uma", ""), (1526, "tiktok", "TikTok"), (1527, "shop", "Shop,"),
    (1561, "2", "2."),
]
ruins = []
for i, antes, depois in FIX:
    atual = ws[i]["w"]
    if atual == depois:
        continue                    # já corrigida numa rodada anterior
    if atual != antes:
        ruins.append((i, antes, atual))
        continue
    ws[i]["w"] = depois
if ruins:
    sys.exit(f"Índice não bate: {ruins}")
(P / "transcricao.json").write_text(json.dumps(ws, ensure_ascii=False, indent=1))

ed = json.loads((P / "edicao.json").read_text())
ed["tirar_palavras"] = [
    [122, 130],    # "Ela estava criando um novo estilo, inclusive, tá pessoal?" (repete logo depois)
    [354, 356],    # "Então, vamos lá" (ainda não abre o pacote)
    [461, 465],    # "eu fico realmente, eu olho," (começo abandonado)
    [590, 597],    # "Vamos escolher aqui um aleatório de hoje. Mas" (não escolhe ali)
    [634, 645],    # "E eu tô amando conhecer a minha mãe pela ótica de vocês" (repete com "essa versão")
    [699, 705],    # "Uma lembrança que eu ainda não tinha" (repete "lembranças que eu não tinha")
    [922, 923],    # "Alexa, desligar"
    [964, 966],    # "bem pacotes pequenos" (repete)
    [977, 987],    # "Esse é uma caixa e tem um que é muito pesado" (repete "esse aqui é muito pesado")
    [1001, 1012],  # "mas esse é uma caixa, eu fiquei curiosa e não tem nada" (repete)
    [1031, 1035],  # "Fiquei curiosa, é uma caixa." (repete)
    [1040, 1041],  # 2º "É curler"
    [1047, 1048],  # 3º "É curler"
    [1255, 1258],  # "Ah, esse eu amei!" (repete "esse eu amei definitivamente")
    [1333, 1341],  # "sempre imaginava que fosse ser alguma coisa de casa" (repete "eu jurava que...")
    [1344, 1345],  # "eu imaginava" (troca por "eu jurava")
    [1474, 1485],  # "você não sabe, trabalho como afiliada e desenvolvedora de IA" (corrige pra "sou especialista")
    [1529, 1532],  # 1º "então gente até amanhã" (o "até amanhã, pessoal" do fim fica)
]
# trechos de ação: (primeira, última palavra, pausa que fica inteira, ponta guardada no corte seco)
ed["acoes"] = [
    [1105, 1106, 3.2, 0.9],    # sai do quadro pra buscar as escovas e volta (36 s de sala vazia)
    [1147, 1148, 3.2, 0.9],    # sai de novo e volta com o modelador
    [1266, 1266, 2.0, 1.75],   # "aprovado!": a comemoração fica
    [1026, 1054, 3.2, 1.7],    # abrindo o saco e a caixa até "É um babyliss do TikTok Shop!"
    [1055, 1104, 4.6, 1.7],    # reação: risada, "não acredito", "esse eu amei"
    [1107, 1146, 1.2, 0.6],    # mostrando as escovas dela, uma por uma
]
(P / "edicao.json").write_text(json.dumps(ed, ensure_ascii=False, indent=2))
print("ok:", len(FIX), "correções,", len(ed["tirar_palavras"]), "cortes de fala,", len(ed["acoes"]), "ações")
