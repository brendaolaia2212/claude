# Edição da aula "Escala inteligente e algoritmo" — especificação compartilhada

Quem lê isto: os agentes que montam partes da edição em paralelo. Cada um mexe só nos seus arquivos.
Tudo em Python 3 + ffmpeg (já instalados), Pillow, numpy, opencv (cv2), faster-whisper. Sem instalar pacotes novos
sem necessidade. A máquina tem só 4 núcleos: não rode nada pesado (render inteiro, whisper) sem precisar;
para testar, use trechos curtos.

## A aluna/o público
A aula é da Brenda para alunos MUITO leigos (afiliados do TikTok Shop). Precisa "praticamente desenhar":
simples, didático, criativo, um pouco divertido, nada de produção mega elaborada. Formato HORIZONTAL.

## Arquivos de entrada (pasta /home/user/claude/trabalho/aula/)
- `original.mp4`: gravação original (58:25, HEVC, aparece 1920x1080 deitado). NUNCA alterar.
- `base720.mp4`: cópia 1280x720, 30 qps, H.264, sem áudio (sendo gerada; pode ainda não estar pronta).
- `audio48k.wav`: áudio mono 48 kHz da gravação (sendo gerado).
- `voz16k.wav`: áudio mono 16 kHz (pronto).
- `transcricao_small.jsonl`: uma linha por segmento do whisper:
  `{"s": ini, "e": fim, "t": texto, "w": [[palavra, ini, fim, prob], ...]}` (tempos em segundos da gravação).
- `slides/s-01.png` ... `slides/s-46.png`: os 46 slides do material (2001x1125). `slides/texto.txt`: texto de todos.
- `extras/exemplo1.mov` ... `exemplo5.*` (576x1024, 15 a 34 s, em pé): 5 vídeos da mesma blusa que a Brenda
  replicou (a original e as variações; 4 dos 5 passaram a vender todo dia). `extras/dados_tiktok.png`: print do
  painel "Desempenho do conteúdo" do TikTok Shop mostrando de qual vídeo saem as vendas.

## Identidade visual (igual aos slides)
- Fonte: Inter (instalada em /usr/share/fonts/opentype/inter/: Inter-Bold.otf, Inter-ExtraBold.otf,
  Inter-SemiBold.otf, Inter-Medium.otf, Inter-Regular.otf; também InterDisplay-*). Extras em
  /home/user/claude/recursos/fontes (Anton, Caveat, Montserrat) se precisar de destaque.
- Cores: AZUL_NOITE (8, 11, 40) fundo escuro; CREME (251, 247, 239) fundo claro; LARANJA (234, 85, 42) destaque;
  texto escuro (17, 20, 50); cinza (110, 112, 130).
- Traço laranja curto acima dos títulos, como nos slides. Cantos arredondados, sombras suaves.

## Saída e tempos
- O vídeo final é montado em 1280x720, 30 qps (versão leve que ela sobe pelo celular), H.264 + AAC.
- Os cortes geram uma linha do tempo de SAÍDA. `cortes.json` (ver abaixo) traz os trechos mantidos;
  todo evento visual é marcado em tempo de SAÍDA.

## Módulo 1 — cortes (`codigo/cortes_aula.py`)
Entrada: transcrição + áudio. Saída: `/home/user/claude/trabalho/aula/cortes.json`:
```json
{"trechos": [{"a": 12.34, "b": 20.10}, ...],      // tempos da GRAVAÇÃO, múltiplos de 1/30 s, em ordem
 "proteger": [[a, b], ...],                         // trechos que não podem ser cortados por dentro
 "removidos": {"pausas": n, "muletas": n, "respiros": n, "repeticoes": n, "segundos": x},
 "duvidas": [{"t": 123.4, "o_que": "..."}]}
```
Regras (pedido da Brenda): tirar fala errada, suspiros, silêncios, repetição e respiro pra ficar dinâmico,
MAS nunca cortar palavra no meio: deixar a palavra terminar e só então cortar. Pausa que fica: no máximo ~0,2 s.
Tomada repetida (ela recomeça a frase): fica a ÚLTIMA versão completa. Muletas soltas ("é...", "hum", "ahn",
"éé") saem quando isoladas. Se houver trecho com um vídeo tocando na tela (som de outro vídeo), não corta o
áudio dele por dentro. Ponto de corte: no ponto mais quieto entre duas palavras (energia), alinhado a 1/30 s.
Funções úteis para os outros: `saida_de(t_gravacao) -> t_saida` e `gravacao_de(t_saida)`.
Também: `python codigo/cortes_aula.py --proxy saida.mp4 [--de T --ate T]` monta um vídeo de conferência
(pode ser 640x360) com os cortes aplicados, áudio incluído, pra ouvir se ficou palavra comida.

## Módulo 2 — visual (`codigo/visual_aula.py`)
Monta o vídeo final a partir da base cortada + uma lista de eventos `eventos.json` (tempo de SAÍDA):
```json
[{"tipo": "zoom", "ini": 3.0, "fim": 6.0, "escala": 1.15},
 {"tipo": "texto", "ini": 1.0, "fim": 4.0, "texto": "Escala inteligente", "estilo": "titulo|palavra|rodape"},
 {"tipo": "abertura", "ini": 0, "fim": 5, "titulo": "...", "sub": "..."},
 {"tipo": "slide", "ini": 30, "fim": 55, "slide": 6, "modo": "dividida|canto", "recorte": [x0,y0,x1,y1] opcional},
 {"tipo": "esquema", "ini": 60, "fim": 75, "modelo": "fluxo|comparacao|ciclo|funil|analogia|equivale|lista|numero",
  "dados": {...}},
 {"tipo": "videos", "ini": 100, "fim": 140, "arquivos": ["extras/exemplo1.mov", ...], "rotulos": ["..."],
  "destaques": [{"t": 105, "texto": "mesma blusa, outra cor"}]},
 {"tipo": "imagem", "ini": 90, "fim": 99, "arquivo": "extras/dados_tiktok.png", "destaque": [x0,y0,x1,y1] opcional}]
```
- Layout "dividida": a Brenda fica à esquerda (recorte do vídeo centrado no rosto dela, ocupando ~45% da largura)
  e o painel (slide/esquema/imagem/vídeos) à direita, sobre fundo AZUL_NOITE ou CREME, com moldura e sombra.
  Transição suave (deslizar ~0,4 s) ao entrar e sair. "canto": slide pequeno numa moldura no canto superior
  direito, sem cobrir o rosto.
- "esquema": desenhos simples, didáticos e animados (itens entram no tempo de `t` de cada item quando houver),
  no estilo dos slides. Modelos mínimos:
  - fluxo: passos numerados com setas (ex.: TESTAR → OBSERVAR → VALIDAR → VARIAR → MEDIR), cada passo acende quando citado.
  - comparacao: duas colunas (ex.: SEM ESTRATÉGIA × COM ESTRATÉGIA) com itens entrando.
  - ciclo: etapas em círculo com seta girando.
  - funil: ALCANCE → ATENÇÃO → INTERESSE → COMPRA.
  - analogia: bonequinhos simples (círculo + corpo) "Maria publica → Joana compra", com setas e ícones.
  - equivale: "palavra do slide = palavra que ela falou" (ex.: "GMV = valor vendido"), pra o aluno entender que é
    a mesma coisa.
  - lista: checklist com ✓ entrando um por um.
  - numero: número grande com rótulo (só números que ela falou).
- "videos": grade com os 5 vídeos em pé lado a lado (tocando sem som, em loop), rótulo em cima de cada um e
  destaques que aparecem no tempo marcado. Ocupa a tela toda (a Brenda pode ficar num quadradinho no canto) ou o
  painel da direita.
- O render: lê `base720.mp4` + `audio48k.wav` aplicando `cortes.json` (ffmpeg faz os cortes e entrega quadros
  crus pelo pipe; Python só desenha por cima quando há evento ativo, senão passa direto, pra ser rápido),
  e codifica em H.264 leve (~1,5–2 Mbps, preset veryfast/faster) + AAC 128k, áudio normalizado em -16 LUFS.
  `python codigo/visual_aula.py --eventos eventos.json --saida X.mp4 [--de T --ate T]` (trecho de teste) e
  `--quadros folha.jpg t1 t2 ...` (folha de quadros sem gerar vídeo).
- Rosto: detector YuNet em /home/user/claude/recursos/modelos/face_detection_yunet_2023mar.onnx
  (cv2.FaceDetectorYN). Rastreie o rosto a cada ~0,5 s e suavize, pra centralizar o zoom e o recorte.

## Módulo 3 — roteiro visual (`eventos.json`)
Feito lendo a transcrição: onde entra cada slide (o que ela fala bate com o slide), onde precisa de esquema
extra, onde entra o print e a comparação dos 5 vídeos, e a abertura (só a introdução tem efeitos, zoom e
texto na tela). Quando o slide usa uma palavra e ela fala outra, usar "equivale".
