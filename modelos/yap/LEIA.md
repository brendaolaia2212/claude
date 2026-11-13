# Modelos do yap (série "Abrindo as compras da minha mãe")

Scripts usados no episódio 2, pra copiar e adaptar nos próximos (troque `pacotes-ep2`
pelo nome do vídeo novo). A ordem:

1. `python -m editor transcrever <nome>` e depois `medium_inteiro.py`: escuta inteira com o
   modelo medium, sem filtro de voz. O small com filtro de voz perde reação baixa no meio do
   barulho do pacote ("É um babyliss!", "esse eu amei").
2. `juntar.py <segundo>`: até ali fica a escuta do small, dali pra frente a do medium
   (escolha o ponto onde começa a abertura do pacote). Guarda o original.
3. `decisoes.py`: palavras corrigidas (confere a palavra antes de trocar), cortes lidos na
   fala (`tirar_palavras`) e trechos de ação (`acoes`). Depois `python -m editor planejar`.
4. `bordas_check.py`: toda emenda que cai com som, com a energia em volta e as palavras.
   Olhe uma por uma. Onde o corte come o fim da palavra mantida ou leva o começo da cortada,
   anote em `ajustar_bordas.py` (borda velha → borda nova, sempre num vale) e rode.
   Pedaço curtinho que só tem rabo de palavra cortada: "tirar". Se a fala estiver colada
   demais pra cortar com segurança, prefira manter a frase.
5. `python -m editor montar`, depois `eventos.py` (gancho, textos, emojis ao lado do rosto,
   carimbos, chuva, sons e efeitos de câmera, tudo achado pela frase, não pelo índice),
   `fx.aplicar(nome)`, `python -m editor final` e `aula.para_celular(nome)`.

Camadas: animação que começa antes fica por baixo. Chuva de emoji junto com texto: a chuva
começa uns 0,15 s antes, pra o texto ficar por cima.

## Estilo maduro (pedido dela no episódio 3: "sem ser infantil, sou uma mulher madura e respeitada")

`eventos_maduro.py`: sem emoji e sem som de desenho (boing, buzina, caixa registradora). Os
ganchos são as frases dela em cartão de serifa (itálico nas frases mais fortes, Kalam só nos
comentários leves), sem som nos momentos de emoção. Aproximação rápida e suave (1,08 a 1,12)
nas reações; aproximação lenta (1,06) no desabafo, sempre terminando numa emenda pra não dar
pulo de volta. Gancho do 1º segundo tirado de uma frase forte do fim do vídeo, e a mesma frase
volta como cartão quando ela fala (o vídeo fecha o que abriu).

- `juntar_janela.py A B`: escuta do medium só dentro de [A, B] (a parte da abertura do pacote).
- `minusculas.py`: legenda com maiúscula só no começo de frase e em nome próprio.
