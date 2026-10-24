# Nina Fit Food · react do bolo + história do Farol

Montagem especial feita em 24/10/2026 (2min35s): abertura falada da Brenda, história narrada com fotos
(PIB Guarapari → Farol → Danilo e Nina → Nina Fit Food → Guarapari), a reação de cada irmão que gravou
(12 ao todo, com as confeiteiras no fim) e chamada pro @ninafitfood. Só o código fica aqui; vídeos, fotos e
vozes ficam fora do git.

## Pra refazer ou ajustar numa conversa nova

1. Baixar a pasta do Drive com os vídeos em `trabalho/_entrada/nina/` (gdown `download_folder`).
2. `bash projetos/nina-fit-food/prep_hd.sh` (1080x1920 em `trabalho/nina/hd/`, áudio em `proxy/`) e
   `python projetos/nina-fit-food/transcrever_pasta.py trabalho/nina/proxy large-v3`
   sobre os áudios em 16 kHz (`proxy/IMG_*.wav`); a montagem lê `proxy/<vídeo>.large-v3.json`.
3. Pedir pra Brenda mandar de novo as fotos (logo, cidade, prints do Farol, símbolo e foto da PIB, fotos do casal).
   De dentro desta pasta:
   `python preparar_fotos.py <pasta com as fotos>`.
4. Narração: `pip install piper-tts`, baixar a voz `pt_BR-cadu-medium` (`.onnx` e `.onnx.json`, do
   rhasspy/piper-voices no Hugging Face) pra `trabalho/nina/vozes/` e rodar `python narracao.py`
   (gera as falas e o tempo de cada palavra). Os textos ficam em `FALAS`.
5. Ainda desta pasta: `python montagem.py --saida ../../trabalho/nina/final.mp4` (uns 25 minutos).

## Conferências (antes de mandar)

- `python conferir_cortes.py`: ouve de novo cada trecho com fala já cortado. Palavra comida na ponta aparece
  como palavra errada ou faltando no começo ou no fim.
- `python conferir_rostos.py`: acusa legenda, emoji, número ou cartão em cima de olhos e boca. Os únicos
  avisos esperados são o clarão branco do carimbo e mãos que o detector confunde com rosto.
- `python quadros_teste.py folha.jpg 1.5 12 40`: quadros soltos, sem gerar o vídeo.
- Tudo que é texto fica na zona segura do Reels (x de 140 a 940, y de 230 a 1530): as legendas e os números
  desviam de rosto e uns dos outros sozinhos (`Legendas.posicionar`, `lugar_livre`).

## O que dá pra trocar fácil

- Quem aparece e em que trecho: `roteiro.py` (abertura, `reacoes()` na ordem do vídeo, `final()`). Ponto de
  corte perto de fala vem de `cortes.py` (`E`/`S` caem num silêncio de verdade) ou de um tempo conferido com
  `conferir_cortes.py`. A legenda de cada trecho é escrita à mão em `texto` e `legendas.py` acha o tempo de
  cada palavra (cache em `trabalho/nina/legendas.json`, por trecho e texto).
- Danilo e Nina: a câmera passa pelo rosto de cada um na foto da loja (`recortes/casal_loja.jpg`; as posições
  dos rostos ficam em `ROSTO_LOJA`) e depois a selfie dos dois (`recortes/casal_praia.jpg`) cai por cima.
  Sem essas fotos, voltam os cartões com as iniciais.
- PIB: o símbolo (`fotos/09_pib_logo.jpg`) vira um selo com o barquinho balançando, e a foto da igreja cheia
  (`recortes/pib.jpg`) entra já no "Somos membros". Sem esses arquivos, volta o desenho da igreja.
- Textos da história: funções `cena_*` em `montagem.py` (entram palavra por palavra junto com a narração).
- Trilha: `musica.py` gera uma música original (sem direitos autorais) no ritmo dos cortes; o volume por trecho
  fica em `montar_audio()`.
