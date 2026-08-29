#!/usr/bin/env sh
# Descarga los archivos faltantes, crea .venv local y reenvía argumentos al programa.
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO=https://raw.githubusercontent.com/patchamama/Video-Audio-TTS-Synchronizer/main
PYTHON_BIN=${PYTHON_BIN:-python3}

download_if_missing() {
  target=$1
  if [ -f "$ROOT/$target" ]; then
    echo "✓ Usando archivo local: $target"
    return
  fi
  mkdir -p "$(dirname "$ROOT/$target")"
  curl -fsSL "$REPO/$target" -o "$ROOT/$target"
}

echo "⬇️  Comprobando archivos de Video TTS…"
download_if_missing create_video_tts_from_srt.py
download_if_missing requirements.txt
for asset in index.html styles.css app.js favicon.svg; do download_if_missing "web/$asset"; done

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
