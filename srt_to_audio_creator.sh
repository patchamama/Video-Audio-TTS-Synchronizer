#!/usr/bin/env sh
# Genera audio desde un SRT, Markdown o TXT sin crear video.
# Reenvía opciones adicionales a create_video_tts_from_srt.py mediante start_video_tts.sh.
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

usage() {
  cat <<'USAGE'
Uso:
  ./srt_to_audio_creator.sh archivo.srt [opciones]
  ./srt_to_audio_creator.sh documento.md [opciones]
  ./srt_to_audio_creator.sh documento.txt [opciones]

Genera sólo audio. Para SRT conserva el texto completo y evita truncarlo.
Ejemplos:
  ./srt_to_audio_creator.sh mi_subtitulo.srt --lang es --tts say --voice 'Diego (Enhanced)'
  ./srt_to_audio_creator.sh capitulo.md --lang de --fix-rate-not-truncate 200 --fix-rate-not-truncate-pause 1000
USAGE
}

if [ "$#" -eq 0 ]; then
  usage >&2
  exit 2
fi

case "$1" in
  -h|--help)
    usage
    exit 0
    ;;
  -*)
    echo "El primer argumento debe ser un archivo .srt, .md o .txt." >&2
    usage >&2
    exit 2
    ;;
esac

# start_video_tts.sh crea/usa el entorno virtual local y reenvía todos los
# argumentos. Las banderas se agregan al final para que el usuario pueda
# seguir eligiendo idioma, TTS, voz, rate y pausas.
exec "$ROOT/start_video_tts.sh" "$@" --solo-audio --no-truncate
