#!/usr/bin/env bash
# Deixa as ferramentas do editor prontas. Pode rodar quantas vezes quiser.
set -e
cd "$(dirname "$0")/.."
if ! command -v ffmpeg >/dev/null 2>&1; then
  pip install -q static-ffmpeg && python3 -c "import static_ffmpeg; static_ffmpeg.add_paths()"
fi
if ! python3 -c "import faster_whisper, cv2, PIL, numpy, gdown" >/dev/null 2>&1; then
  pip install -q -r requirements.txt
fi
python3 - <<'PY'
from pathlib import Path
faltando = [p for p in ["recursos/fontes/Anton-Regular.ttf", "recursos/fontes/Montserrat-Variable.ttf",
                        "recursos/modelos/face_detection_yunet_2023mar.onnx"] if not Path(p).exists()]
print("Editor pronto." if not faltando else f"Faltando: {faltando}")
PY
