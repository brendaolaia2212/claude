# Nina Fit Food · react do bolo + história do Farol

Montagem especial feita em 24/10/2026 (1min11s): abertura falada da Brenda, história com fotos
(PIB Guarapari → Farol → Danilo e Nina → Nina Fit Food → Guarapari), reações de quem provou o bolo
e chamada pro @ninafitfood. Só o código fica aqui; vídeos e fotos ficam fora do git.

## Pra refazer ou ajustar numa conversa nova

1. Baixar a pasta do Drive com os vídeos em `trabalho/_entrada/nina/` (gdown `download_folder`).
2. `bash projetos/nina-fit-food/prep_hd.sh` (1080x1920 em `trabalho/nina/hd/`, áudio em `proxy/`) e
   `python projetos/nina-fit-food/transcrever_pasta.py trabalho/nina/proxy large-v3`
   sobre os áudios em 16 kHz (`proxy/IMG_*.wav`); a montagem lê `proxy/<vídeo>.large-v3.json`.
3. Pedir pra Brenda mandar de novo as fotos (logo, cidade, prints do Farol, símbolo e foto da PIB, fotos do casal).
   De dentro desta pasta:
   `python preparar_fotos.py <pasta com as fotos>`.
4. Ainda desta pasta: `python montagem.py --saida ../../trabalho/nina/final.mp4` (uns 3 minutos).

Conferências: `python quadros_teste.py folha.jpg 1.5 12 40` (quadros soltos) e `python conferir_rostos.py`
(depois de `python rostos.py`), que acusa qualquer texto em cima de olhos e boca.

## O que dá pra trocar fácil

- Danilo e Nina: a câmera passa pelo rosto de cada um na foto da loja (`recortes/casal_loja.jpg`; as posições
  dos rostos ficam em `ROSTO_LOJA`) e depois a selfie dos dois (`recortes/casal_praia.jpg`) cai por cima.
  Sem essas fotos, voltam os cartões com as iniciais.
- PIB: o símbolo (`fotos/09_pib_logo.jpg`) vira um selo com o barquinho balançando, e a foto da igreja cheia
  (`recortes/pib.jpg`) entra no "por ser uma igreja grande". Sem esses arquivos, volta o desenho da igreja.
- Textos da história: funções `cena_*` em `montagem.py`.
- Cortes das reações: `montar_linha()` (fonte, ponto de entrada, duração).
- Trilha: `musica.py` gera uma música original (sem direitos autorais) no ritmo dos cortes; o volume por trecho
  fica em `montar_audio()`.
