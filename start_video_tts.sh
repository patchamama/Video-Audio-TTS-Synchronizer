#!/usr/bin/env sh
# Descarga/actualiza la app, crea .venv local y reenvía argumentos al programa.
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO=https://raw.githubusercontent.com/patchamama/Video-Audio-TTS-Synchronizer/main
PYTHON_BIN=${PYTHON_BIN:-python3}

download() {
  target=$1
  mkdir -p "$(dirname "$ROOT/$target")"
  curl -fsSL "$REPO/$target" -o "$ROOT/$target"
}

echo "⬇️  Actualizando Video TTS desde GitHub…"
download create_video_tts_from_srt.py
download requirements.txt
for asset in index.html styles.css app.js favicon.svg; do download "web/$asset"; done

if [ ! -x "$ROOT/.venv/bin/python" ]; then
  echo "🐍 Creando entorno virtual local…"
  "$PYTHON_BIN" -m venv "$ROOT/.venv"
fi

PYTHON="$ROOT/.venv/bin/python"
"$PYTHON" -m pip install --upgrade pip
"$PYTHON" -m pip install -r "$ROOT/requirements.txt"

if [ "$#" -eq 0 ]; then
  set -- --web
fi
exec "$PYTHON" "$ROOT/create_video_tts_from_srt.py" "$@"
