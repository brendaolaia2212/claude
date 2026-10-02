# EDIT IA PRO · editor de vídeos da Brenda

Um editor de vídeos que funciona por conversa, direto do celular, e escreve na voz da Brenda.

## Como usar

Abra uma sessão do Claude Code neste repositório (pelo app ou por claude.ai/code) e:

- **Mande um vídeo** (anexo ou link do Google Drive/Dropbox). O Claude ouve, corta as pausas e as tomadas repetidas, te mostra o corte, deixa você escolher o estilo pelo nome, manda uma amostra e depois o vídeo pronto pra salvar na galeria.
- **Mande um tema ou uma ideia solta.** O Claude devolve hooks, roteiro pra teleprompter, legenda e comentário fixado no seu tom de voz.
- **Use atalhos:** "mesmo estilo do último vídeo", "entre 0:03 e 0:05 tira essa parte", "troca o gancho por: ...", "faz uma versão de 15 segundos", "confere se tem frase que a Meta reprova".

A lista de estilos (legendas, ganchos, cores e animações) está em [docs/estilos.md](docs/estilos.md).

## O que tem aqui

| Pasta | O que é |
|---|---|
| `CLAUDE.md` | As instruções que o Claude segue ao abrir a sessão |
| `voz/` | O comando-mestre do seu tom de voz e como ele entra na edição |
| `docs/` | O passo a passo da edição, a lista de estilos e o roteiro EDIT IA PRO original |
| `editor/` | O motor de edição (Python + ffmpeg): transcrição, corte, legendas, ganchos, animações, sons, mixagem |
| `recursos/` | Fontes (Anton, Montserrat, Caveat, licença OFL) e o detector de rosto |
| `perfil/` | Seu estilo aprovado e o histórico de vídeos, pra lembrar entre conversas |

## Para quem for mexer no código

```bash
bash scripts/preparar.sh                         # instala o que faltar
python -m editor novo video.mp4 --nome teste
python -m editor transcrever teste
python -m editor planejar teste && python -m editor montar teste
python -m editor mostruario teste --tipo legenda
python -m editor amostra teste
python -m editor final teste
```

As decisões de cada vídeo ficam em `trabalho/<nome>/edicao.json` (formato descrito no `CLAUDE.md`).
