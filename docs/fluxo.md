# O caminho da edição: 2 aprovações e uma amostra

Adaptado do roteiro EDIT IA PRO (modo celular) pra rodar aqui com o editor do repositório. O PDF original está em `docs/edit-ia-pro-original.txt`.

## O que dá e o que não dá (fale a verdade pra ela)

**Dá:** cortar pausas, erros e tomadas repetidas; ficar com a melhor tomada; legenda animada palavra por palavra; gancho escrito no começo; zoom nos cortes; animações 2D nos momentos fortes (lista com check, número contando, palavra de impacto, notificação, carimbo, destaque desenhado, passo a passo, comentário sendo digitado, barra enchendo); tela dividida com imagem que ela mandar; efeitos sonoros simples; trilha que ela mandar; cartão no final; conferir frases que a Meta reprova.

**Não dá bem aqui:** tela verde de qualidade, objeto que acompanha a mão, efeitos 3D, cenas montadas com vídeo por dentro. Se ela pedir, explique em uma frase e ofereça a versão simples.

**Tamanho:** até uns 90 segundos é rápido. Os vídeos longos dela (5 a 8 minutos de reflexão) funcionam, mas cada etapa demora mais: avise antes (transcrever ~1 min por minuto de vídeo; vídeo final ~2 min por minuto). Ofereça também tirar cortes curtos (30 a 60 s) do vídeo longo pra Reels.

## Passo 1 · Receber

1. `novo ultimo` (ou com o link). Leia os avisos: horizontal, sem som, qualidade baixa de WhatsApp (sugira o arquivo original salvo em Arquivos).
2. Numa mensagem só, pergunte o que falta:
   - sobre o que é o vídeo (se for reflexão, já dá pra entender pela fala: só confirme);
   - se tem ação no final (link de produto, Shopee, TikTok Shop) ou se é só a reflexão;
   - duração desejada (padrão: manter a fala inteira sem pausas; pra anúncio, 20 a 45 s);
   - nome difícil na fala (marca, produto) → `nomes_dificeis`.
   Se ela não souber, siga com o padrão.

## Passo 2 · Ouvir e cortar

1. `transcrever` e `planejar`. O plano já segue as regras: silêncio maior que 0,25 s sai; tomada repetida fica a ÚLTIMA que foi até o fim; frase abandonada sai; "hum", "ahn", "tipo assim" soltos saem; cada trecho ganha 0,06 s de folga antes e 0,10 s depois, sem entrar na palavra vizinha.
2. Leia as linhas de "Conferir" e "Atenção". Repetição pode ser de propósito no jeito dela de falar (anáfora: "Eu posso... Eu posso..."). Na dúvida, mantenha e conte pra ela.
3. Conte o plano em 3 linhas ("tirei 14 pausas e 2 frases repetidas; o vídeo foi de 1:12 pra 0:41; fiquei com a segunda tomada do começo") e pergunte se pode cortar.
4. `montar` e mande o `corte.mp4`: "Assiste. Tá bom? Se quiser mudar algo, me diz o tempo do trecho, tipo 'entre 3 e 5 segundos tira essa parte'". Use `tirar` + `montar` até ela aprovar. **Aprovação 1.**

## Passo 3 · Estilo, pelos nomes

Ela escolhe pelos nomes de `docs/estilos.md`. Recomende uma combinação (ver `voz/voz-no-editor.md`) e mande o `mostruario` das opções em que ela estiver em dúvida.

- **Cor de destaque:** ela diz o nome ou o código. Se já existe `perfil/estilo.json`, ofereça "mesmo estilo do último".
- **Gancho escrito:** proponha 2 ou 3 opções tiradas da própria fala (`texto`), até 2 linhas, 6 a 8 palavras, e diga qual é a mais forte e por quê, em uma frase. Sem promessa de ganho.
- **Animações:** pergunte quantas: poucas (uma a cada 10 a 15 s), médias (5 a 8 s) ou nenhuma. Rode `sugerir`, revise cada candidato lendo a fala, complete os textos e mostre a lista em linguagem simples ("0:04 lista com 3 itens, 0:11 número 5 contando...") antes de fazer.

Recomendação padrão se ela não quiser escolher: ver `voz/voz-no-editor.md`.

## Passo 4 · Amostra (economiza tempo)

1. Grave tudo no `edicao.json` e rode `amostra`: primeiros 8 a 10 s com gancho, legenda e animação; junta também os segundos em volta da primeira animação ou da tela dividida, se caírem depois.
2. Mande a amostra e pergunte o que mudar. Ajuste só o que ela pedir. **Aprovação 2.**
3. Com a amostra aprovada, siga pro vídeo inteiro no mesmo padrão. Não invente nada novo no meio.

## Passo 5 · Vídeo completo

`final` monta nesta ordem, sempre sobre o corte aprovado: zoom nos cortes (1,00 / 1,08 alternando, centrado no rosto) → tela dividida → legenda (fora de olhos e boca, zona segura y 230-1530, x 140-940) → gancho → animações e cartão final → sons (nunca dois a menos de 0,6 s) → trilha 22 dB abaixo da voz com abaixamento quando ela fala → volume final em -14 LUFS (duas passadas).

Depois, você mesmo confere:
1. Olha a folha de quadros que o `final` gera.
2. Confere a duração (tem que bater com o corte).
3. Lê os avisos da Meta: valor em dinheiro ligado a ganho, "em X dias", "garantido", "renda extra de", "fique rico", "sem esforço", antes e depois de dinheiro, frase que aponta característica da pessoa, promessa de cura. Se tiver, avise com o tempo e sugira tirar ou trocar. Quem decide é ela.

## Passo 6 · Entregar

1. Mande o `final.mp4` e o jeito de salvar na galeria.
2. Ofereça, em uma linha, escrever a legenda do post e o comentário fixado na voz dela.
3. Pergunte se quer ajustar algo (pelo tempo do trecho).
4. `salvar-estilo`, anote o vídeo em `perfil/historico.md`, commit e push.

## Regras que não mudam

- Uma ideia por vez na tela.
- Gancho escrito nos primeiros 3 segundos.
- Nada em cima dos olhos e da boca.
- Corte sem respiro: pausas de no máximo 0,2 s.
- Sons poucos e no lugar certo.
- Número na tela só se ela falou. Nada de valor de ganho escrito.
- Os vídeos originais dela nunca são alterados.

## Atalhos que ela pode mandar

| Ela diz | Você faz |
|---|---|
| "Mesmo estilo do último vídeo" | `usar-estilo`, pula pra amostra |
| "Entre [tempo] e [tempo], [o que mudar]. Não mexe no resto." | Muda só aquele trecho (`tirar`, `legenda_oculta`, animação) |
| "Deixa mais seco" | Folga menor: tire mais respiros pequenos com `tirar`, ou animações "poucas" |
| "Troca o gancho por: [texto]" | `gancho.texto` |
| "Tira a legenda de [tempo] a [tempo]" | `legenda_oculta` |
| "Põe essa imagem em cima quando eu falo de [assunto]" | Ache o tempo com `texto`, `tela_dividida` |
| "Põe uma animação em [tempo] quando eu falo [palavra]" | Nova entrada em `animacoes` |
| "Mais animações" / "menos animações" | Muda o ritmo e refaz a lista |
| "Faz uma versão de 15 segundos" | Escolha o trecho mais forte pela fala, proponha, monte com `tirar` numa cópia (`novo` com outro `--nome` a partir do mesmo original) |
| "Confere se tem frase que a Meta reprova" | `meta` |
