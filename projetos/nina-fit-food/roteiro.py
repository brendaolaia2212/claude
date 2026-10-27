"""Quem aparece e em que trecho: abertura, a reação de cada irmão e o final das confeiteiras.

Cada trecho é (clipe, início, fim, opções), em segundos do clipe. Onde o corte encosta numa fala, o tempo vem
de cortes.py (corte num silêncio de verdade) ou foi conferido ouvindo o trecho cortado de novo
(conferir_cortes.py): nenhuma palavra fica pela metade.

Opções: voz (fala que importa: volume de fala), texto (a legenda, escrita à mão; nomes que não dá pra ter certeza
de como se escrevem ficam de fora), legenda=False, legenda_ate=t (clipe), sem_som=(a, b) (cala um pedaço do áudio,
em tempo do clipe), congelar=t (segura o quadro a partir de t no trecho), zoom=(z0, z1), foco=(x, y), socos,
tremer, adesivos=[(t no clipe, tipo, parâmetros)] com tipo emoji, brilhos, coracoes, numero, selo, flash, titulo
ou perfil.
"""
from cortes import entrada as E
from cortes import saida as S


def abertura():
    return [
        ("IMG_6490", E("IMG_6490", "Gente,", 0.86), 3.71,          # o "Food" de verdade soa até 3,70
         dict(voz=True, zoom=(1.0, 1.04), foco=(540, 700), texto="Gente, estamos aqui com o bolo da Nina Fit Food")),
        ("IMG_6490", E("IMG_6490", "a", 12.54), S("IMG_6490", "nada.", 15.22),
         dict(voz=True, zoom=(1.06, 1.0), foco=(540, 700),
              texto="a gente vai fazer uma propaganda pra Nina Fit Food, sem falar nada.",
              adesivos=[(14.98, "emoji", dict(ch="🤫", x=830, y=560, tam=170))])),
        ("IMG_6490", E("IMG_6490", "Só", 15.84), S("IMG_6490", "Nina.", 19.70),
         dict(voz=True, zoom=(1.0, 1.04), foco=(540, 700), texto="Só gravando o react de quem comeu o bolo da Nina.")),
    ]


def reacoes():
    """[(quem, [trechos])]: todo mundo que gravou a reação, na ordem do vídeo."""
    return [
        ("vô", [
            ("IMG_6500", 4.85, 6.20, dict(zoom=(1.0, 1.05), foco=(540, 700))),
            ("IMG_6500", 7.70, 8.95, dict(zoom=(1.08, 1.12), foco=(560, 640),
                                          adesivos=[(7.8, "coracoes", dict(area=(850, 990, 1000, 1250)))])),
            ("IMG_6500", 9.95, 12.25, dict(zoom=(1.0, 1.0), foco=(540, 760), socos=(0.08,),
                                           adesivos=[(10.0, "brilhos", dict(x=290, y=600))])),
            ("IMG_6500", 14.60, 15.40, dict(zoom=(1.04, 1.04), foco=(540, 760),
                                            adesivos=[(14.75, "emoji", dict(ch="👍", x=200, y=830, tam=150))])),
        ]),
        ("casal de verde e laranja", [
            ("IMG_6492", 0.0, 2.30, dict(voz=True, sem_som=(0.0, 0.37), zoom=(1.0, 1.04), foco=(420, 700),
                                         texto="O primeiro pedaço da Nina Fit Food.")),
            ("IMG_6492", E("IMG_6492", "Avaliação", 8.12), S("IMG_6492", "casal.", 9.22),
             dict(voz=True, zoom=(1.0, 1.05), foco=(420, 760), texto="Avaliação crítica do casal.",
                  adesivos=[(8.3, "emoji", dict(ch="🧐", x=880, y=420, tam=150))])),
            ("IMG_6492", 12.45, 14.55, dict(voz=True, zoom=(1.0, 1.04), foco=(560, 760), texto="Aprovado?",
                                            adesivos=[(13.5, "emoji", dict(ch="👍", x=900, y=470, tam=140))])),
        ]),
        ("moça de branco", [
            ("IMG_6497", E("IMG_6497", "Vamos", 1.48), S("IMG_6497", "pedaço.", 4.82),
             dict(voz=True, zoom=(1.0, 1.04), foco=(540, 700), texto="Vamos lá, reação do bolo da Nina, o primeiro pedaço.",
                  adesivos=[(2.0, "emoji", dict(ch="💃", x=870, y=400, tam=150))])),
            ("IMG_6497", 10.0, 11.45, dict(zoom=(1.06, 1.1), foco=(540, 700))),
            ("IMG_6497", E("IMG_6497", "Aprovado?", 14.52), 16.45,
             dict(voz=True, zoom=(1.0, 1.04), foco=(540, 700), texto="Aprovado?",
                  adesivos=[(15.5, "emoji", dict(ch="👍", x=880, y=420, tam=140))])),
        ]),
        ("família", [
            ("IMG_6496", E("IMG_6496", "Junta", 8.62), 13.75,
             dict(voz=True, zoom=(1.0, 1.05), foco=(540, 900), texto="Junta aí, família. Um, dois, três e...",
                  adesivos=[(10.72, "numero", dict(txt="1")), (11.32, "numero", dict(txt="2")),
                            (11.72, "numero", dict(txt="3"))])),
            ("IMG_6496", E("IMG_6496", "Aprovado?", 27.42), 29.90,   # em 30,0 começa outra palavra e o vídeo acaba
             dict(voz=True, zoom=(1.0, 1.03), foco=(540, 900), texto="Aprovado?",
                  adesivos=[(28.95, "selo", dict(txt="APROVADO!", y=1330))])),
        ]),
        ("menina", [
            ("IMG_6502", E("IMG_6502", "Onde", 1.20), 5.25,
             dict(voz=True, zoom=(1.0, 1.06), foco=(540, 700), texto="Vai, sua vez.",
                  adesivos=[(3.0, "emoji", dict(ch="🥰", x=860, y=420, tam=150)),
                            (3.2, "coracoes", dict(area=(780, 980, 1000, 1250)))])),
        ]),
        ("senhor de camisa xadrez", [
            ("IMG_6498", E("IMG_6498", "Você", 0.66), 1.66,          # "ator" vai até 1,58
             dict(voz=True, zoom=(1.0, 1.03), foco=(540, 800), texto="Você é ator.")),
            ("IMG_6498", E("IMG_6498", "Vamos", 6.60), S("IMG_6498", "produção.", 8.02),
             dict(voz=True, zoom=(1.0, 1.04), foco=(540, 700), texto="Entendeu? Vamos lá, vamos fazer alta produção.",
                  adesivos=[(7.6, "emoji", dict(ch="🎬", x=880, y=330, tam=150))])),
            ("IMG_6498", 11.40, 14.90, dict(zoom=(1.04, 1.1), foco=(540, 640), socos=(2.65,),
                                            adesivos=[(14.05, "brilhos", dict(x=880, y=640))])),
        ]),
        ("senhora de rosa", [
            ("IMG_6495", E("IMG_6495", "Qual", 43.22), S("IMG_6495", "dizer?", 45.20),
             dict(voz=True, zoom=(1.0, 1.06), foco=(540, 700), texto="Qual é a sua reação? O que você tem a dizer?",
                  adesivos=[(43.6, "emoji", dict(ch="🥹", x=900, y=400, tam=160))])),
        ]),
        ("moça do V", [
            ("IMG_6499", 4.45, 8.36,                                  # "vídeo" vai até 8,32
             dict(voz=True, zoom=(1.0, 1.04), foco=(380, 800), texto="É foto? É vídeo.", tempos=[4.40, 4.72, 7.58, 7.82],
                  adesivos=[(4.8, "flash", {}), (4.8, "emoji", dict(ch="📸", x=880, y=380, tam=150)),
                            (7.7, "emoji", dict(ch="🎥", x=880, y=380, tam=150))])),
        ]),
        ("irmão de azul", [
            ("IMG_6499", E("IMG_6499", "Eu", 11.64), S("IMG_6499", "todo.", 17.28),
             dict(voz=True, zoom=(1.0, 1.04), foco=(560, 640),
                  texto="Eu comeria um bolo inteiro. Sério, eu sentaria assim, ó, assistindo um filme, comia um bolo todo.",
                  adesivos=[(12.62, "emoji", dict(ch="🎂", x=200, y=420, tam=140)),
                            (15.9, "emoji", dict(ch="🍿", x=880, y=420, tam=140))])),
        ]),
        ("moça de jaqueta", [
            ("IMG_6499", E("IMG_6499", "O", 24.24), 28.69,           # o "Nina" final vai até 28,62
             dict(voz=True, zoom=(1.03, 1.07), foco=(540, 800),
                  texto="O aniversário dele é mês que vem. Já queremos bolo, Nina!",
                  adesivos=[(24.7, "emoji", dict(ch="🎉", x=880, y=420, tam=150)),
                            (27.6, "emoji", dict(ch="🎂", x=200, y=420, tam=140))])),
        ]),
        ("casal de branco e preto", [
            ("IMG_6493", E("IMG_6493", "Reaction", 0.80), S("IMG_6493", "casal.", 1.44),
             dict(voz=True, zoom=(1.0, 1.03), foco=(540, 700), texto="React do casal!")),
            ("IMG_6493", 6.50, 7.60, dict(zoom=(1.04, 1.08), foco=(540, 760))),
            ("IMG_6493", E("IMG_6493", "Posso", 9.78), 12.65,
             dict(voz=True, zoom=(1.0, 1.0), foco=(540, 760), texto="Posso passar debaixo da mesa?",
                  adesivos=[(11.6, "emoji", dict(ch="😂", x=860, y=360, tam=160))])),
            ("IMG_6493", E("IMG_6493", "Excelente.", 14.36), S("IMG_6493", "Excelente.", 14.36),
             dict(voz=True, zoom=(1.04, 1.06), foco=(540, 700), texto="Excelente!",
                  adesivos=[(14.45, "brilhos", dict(x=850, y=480))])),
            ("IMG_6494", 0.0, 3.0, dict(voz=True, congelar=2.12, tremer=((2.05, 18),), zoom=(1.0, 1.06), foco=(540, 700),
                                         texto="Aprovado, gente?", legenda_ate=1.9,
                                         adesivos=[(2.02, "selo", dict(txt="APROVADÍSSIMO!", y=1150))])),
        ]),
    ]


def final():
    """As confeiteiras: a última reação, o segredo do creme e a chamada pro Instagram."""
    t = [
        # entra no "Bom," (6,10: o ponto mais quieto antes dele; não tem silêncio de verdade, é conversa de fundo)
        ("IMG_6503", 6.10, S("IMG_6503", "reações.", 11.76),
         dict(voz=True, zoom=(1.0, 1.04), foco=(540, 700), legenda=False,
              # o título entra depois do número da reação (os dois disputam a parte de baixo da tela)
              adesivos=[(8.25, "titulo", dict(linhas=["AGORA, AS", "CONFEITEIRAS"]))])),
        ("IMG_6503", 17.20, 19.45, dict(zoom=(1.04, 1.08), foco=(560, 640))),
        # antes do "Olha" tem outra frase (fica de fora); o "Olha" começa em 22,62
        ("IMG_6503", 22.62, S("IMG_6503", "pecado.", 27.56),
         dict(voz=True, zoom=(1.0, 1.04), foco=(540, 700), texto="Olha pra vocês, esse creminho branco aqui, ó, é um pecado.",
              adesivos=[(27.62, "emoji", dict(ch="😋", x=470, y=470, tam=160))])),
        ("IMG_6503", 31.95, 34.78,
         dict(voz=True, zoom=(1.03, 1.0), foco=(540, 700), texto="Conta pra gente o segredo desse creme branco de chocolate.",
              adesivos=[(32.9, "emoji", dict(ch="🤫", x=470, y=470, tam=150))])),
        # entre o "É," e o "gente" tem outra conversa no fundo: entra direto no "É, gente"
        ("IMG_6503", 37.93, S("IMG_6503", "pedindo.", 41.32),
         dict(voz=True, zoom=(1.0, 1.04), foco=(540, 700), texto="É, gente, pra vocês descobrirem, só pedindo.")),
        ("IMG_6503", E("IMG_6503", "Apesar", 43.22), 47.66,
         dict(voz=True, zoom=(1.04, 1.0), foco=(540, 700),
              texto="Apesar que ela dá muitas dicas só no Instagram dela, tá? Verdade! Muitas receitas.",
              adesivos=[(45.05, "perfil", {})])),
    ]
    # a fala do Instagram, sem as duas pausas longas (pedaços conferidos ouvindo de novo)
    for a, b, txt in [(47.63, 51.60, "Vamos deixar o Instagram da Nina aqui, mas"), (51.90, 54.33, "pra comer esse aqui,"),
                      (54.93, 57.37, "não tem jeito, só pedindo lá na Nina, né?")]:
        t.append(("IMG_6503", a, b, dict(voz=True, zoom=(1.0, 1.05), foco=(540, 700), texto=txt)))
    # zoom alternado entre os pedaços seguidos do mesmo vídeo: esconde o pulo do corte
    for k, (_, _, _, op) in enumerate(t):
        if k % 2:
            op["zoom"] = (1.07, 1.09)
    return t
