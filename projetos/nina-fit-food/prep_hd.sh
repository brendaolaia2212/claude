#!/usr/bin/env bash
# Converte cada vídeo pra 1080x1920, 30 qps, com uma leve correção de cor, e tira o áudio em 16 kHz pra transcrição.
# Os originais não são tocados. Rode da raiz do repositório.
set -e
cd trabalho/nina
ENT=../_entrada/nina
mkdir -p hd proxy
conv() {
  f="$1"; b=$(basename "$f"); b="${b%.*}"; extra="$2"
  [ -f "hd/$b.mov" ] || ffmpeg -hide_banner -loglevel error -y -i "$f" \
    -vf "scale=1080:1920:force_original_aspect_ratio=increase:flags=lanczos,crop=1080:1920,fps=30,eq=contrast=1.05:saturation=1.10,unsharp=5:5:0.35${extra},format=yuv420p" \
    -c:v libx264 -preset fast -crf 15 -g 15 -bf 0 -c:a pcm_s16le -ar 48000 -ac 2 "hd/$b.mov"
  [ -f "proxy/$b.wav" ] || ffmpeg -hide_banner -loglevel error -y -i "$f" -vn -ac 1 -ar 16000 "proxy/$b.wav"
}
export -f conv
ls $ENT/IMG_*.MOV | xargs -P 2 -I{} bash -c 'conv {}'
conv $ENT/7649936307915692184.mp4 ",unsharp=5:5:0.6"
echo FIM
