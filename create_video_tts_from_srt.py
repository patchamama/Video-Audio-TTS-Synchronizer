#!/usr/bin/env python3
"""
Video-Audio-TTS Synchronizer
============================

Script para generar audio TTS (Text-to-Speech) con ajuste automático de velocidad
y sincronización con video a partir de archivos de subtítulos SRT.

Compatible con:
- macOS: Usa el comando 'say' nativo
- Linux/Otros: Usa gTTS (Google Text-to-Speech) vía Python

PARÁMETROS DE USO
=================

Posicionales:
  srt_file              Archivo de subtítulos en formato SRT
  video                 Archivo de video (mkv, mp4, etc.)
  audio_dir             [Opcional] Carpeta con audios previamente generados

Opcionales:
  --test N              Modo test: procesar solo N subtítulos (default: 30 si no se especifica N)
  --solo-audio          Solo generar el audio master, sin procesar video
  --no-freeze           Truncar audios largos en lugar de congelar video
  --remove-breaks       Eliminar pausas mayores a 15 minutos del video final
  --only-remove-breaks  SOLO eliminar pausas del video (sin generar TTS)

EJEMPLOS DE USO
===============

# Procesar video completo con subtítulos
python3 create_video_tts_from_srt.py video.srt video.mp4

# Modo test con 50 subtítulos
python3 create_video_tts_from_srt.py video.srt video.mp4 --test 50

# Solo generar audio sin procesar video
python3 create_video_tts_from_srt.py video.srt video.mp4 --solo-audio

# Eliminar pausas largas del video final
python3 create_video_tts_from_srt.py video.srt video.mp4 --remove-breaks

# Usar audios previamente generados
python3 create_video_tts_from_srt.py video.srt video.mp4 ./audio_folder/

REQUISITOS
==========

macOS:
  - ffmpeg
  - Comando 'say' (incluido en macOS)

Linux/Otros:
  - ffmpeg
  - Python 3.x
  - sudo apt install python3-gtts python3-pydub

ARCHIVOS GENERADOS
==================

- {video}_working.srt     : Subtítulos con IDs renumerados consecutivamente
- {video}_debug.srt       : Subtítulos con metadatos de TTS (rate, offsets, truncados)
- {video}_con_tts.mkv     : Video final con audio TTS sincronizado
- {video}_sin_pausas.mkv  : Video final sin pausas largas (si se usa --remove-breaks)
- temp_audio_YYYYMMDD_HHMMSS/ : Carpeta temporal en directorio actual (conservada en modo --test)

PROCESO
=======

1. VALIDACIÓN: Parsea y valida el archivo SRT
2. GENERACIÓN TTS: Crea audios con velocidades 180-240 WPM según duración
3. SRT DEBUG: Genera archivo debug con metadatos
4. PROCESO VIDEO: Agrega freeze frames si es necesario
5. SINCRONIZACIÓN: Construye pista de audio master sincronizada
6. FUSIÓN: Combina video y audio
7. LIMPIEZA: Elimina pausas largas si se solicitó

Versión Python - Más fácil de debuguear y mantener que bash
"""

import argparse
import os
import platform
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import shutil

# Colores para terminal
class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    MAGENTA = '\033[0;35m'
    CYAN = '\033[0;36m'
    NC = '\033[0m'  # No Color

class ErrorLogger:
    """Registra errores durante la ejecución"""
    def __init__(self):
        self.errors: List[Dict[str, str]] = []
        self.warnings: List[str] = []

    def add_error(self, step: str, command: str, error_msg: str):
        """Registra un error de ffmpeg"""
        self.errors.append({
            'step': step,
            'command': command,
            'error': error_msg
        })

    def add_warning(self, message: str):
        """Registra una advertencia"""
        self.warnings.append(message)

    def has_errors(self) -> bool:
        """Verifica si hay errores registrados"""
        return len(self.errors) > 0

    def print_summary(self):
        """Imprime resumen de errores y advertencias"""
        if self.warnings:
            print(f"\n{Colors.YELLOW}{'═' * 50}{Colors.NC}")
            print(f"{Colors.YELLOW}⚠️  ADVERTENCIAS ({len(self.warnings)}){Colors.NC}")
            print(f"{Colors.YELLOW}{'═' * 50}{Colors.NC}")
            for idx, warning in enumerate(self.warnings, 1):
                print(f"{Colors.YELLOW}{idx}. {warning}{Colors.NC}")

        if self.errors:
            print(f"\n{Colors.RED}{'═' * 50}{Colors.NC}")
            print(f"{Colors.RED}❌ ERRORES DETECTADOS ({len(self.errors)}){Colors.NC}")
            print(f"{Colors.RED}{'═' * 50}{Colors.NC}")
            for idx, error in enumerate(self.errors, 1):
                print(f"\n{Colors.RED}Error {idx}:{Colors.NC}")
                print(f"{Colors.CYAN}  Paso: {error['step']}{Colors.NC}")
                print(f"{Colors.YELLOW}  Comando: {error['command']}{Colors.NC}")
                print(f"{Colors.RED}  Error:{Colors.NC}")
                # Mostrar últimas 15 líneas del error
                error_lines = error['error'].strip().split('\n')
                for line in error_lines[-15:]:
                    print(f"    {line}")

@dataclass
class Subtitle:
    """Representa un subtítulo con su metadata"""
    consecutive_id: int
    original_id: str
    start_time: str
    end_time: str
    start_seconds: float
    end_seconds: float
    duration: float
    text: str

@dataclass
class AudioSegment:
    """Representa un segmento de audio generado"""
    subtitle_id: int
    audio_file: Path
    rate: int
    needs_freeze: bool = False
    freeze_duration: float = 0.0
    was_truncated: bool = False

class TTSEngine:
    """Maneja la generación de TTS"""

    def __init__(self):
        self.method = self._detect_method()
        self.python_tts_script = None
        if self.method == "python":
            script_dir = Path(__file__).parent
            self.python_tts_script = script_dir / "generate_tts.py"
            if not self.python_tts_script.exists():
                raise FileNotFoundError(f"No se encuentra {self.python_tts_script}")

    def _detect_method(self) -> str:
        """Detecta el método TTS disponible"""
        if platform.system() == "Darwin":
            if shutil.which("say"):
                print(f"{Colors.GREEN}✓ Sistema: macOS - Usando comando 'say'{Colors.NC}")
                return "say"

        if shutil.which("python3"):
            try:
                import gtts
                import pydub
                print(f"{Colors.GREEN}✓ Sistema: Linux/Otro - Usando Python + gTTS{Colors.NC}")
                return "python"
            except ImportError:
                print(f"{Colors.RED}✗ Error: Faltan dependencias de Python{Colors.NC}")
                print(f"{Colors.YELLOW}Instala con: sudo apt install python3-gtts python3-pydub{Colors.NC}")
                sys.exit(1)

        print(f"{Colors.RED}✗ Error: No se encontró método TTS compatible{Colors.NC}")
        sys.exit(1)

    def generate_audio(self, text: str, rate: int, output_file: Path) -> bool:
        """Genera audio TTS con el rate especificado"""
        try:
            if self.method == "say":
                # macOS say command
                aiff_file = output_file.with_suffix('.aiff')
                subprocess.run(
                    ["say", "-v", "Paulina", "-r", str(rate), text, "-o", str(aiff_file)],
                    check=True,
                    stderr=subprocess.DEVNULL
                )
                subprocess.run(
                    ["ffmpeg", "-i", str(aiff_file), str(output_file), "-y"],
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                aiff_file.unlink()
                return True

            elif self.method == "python":
                # Python gTTS
                subprocess.run(
                    ["python3", str(self.python_tts_script), text, str(output_file),
                     "-r", str(rate), "-l", "es"],
                    check=True,
                    stderr=subprocess.DEVNULL
                )
                return output_file.exists()

        except subprocess.CalledProcessError as e:
            print(f"{Colors.RED}Error: TTS falló para rate {rate}{Colors.NC}", file=sys.stderr)
            return False

        return False

class SRTParser:
    """Parsea y valida archivos SRT"""

    @staticmethod
    def parse_srt_time(time_str: str) -> float:
        """Convierte timestamp SRT a segundos"""
        # Formato: HH:MM:SS,mmm
        match = re.match(r'(\d{2}):(\d{2}):(\d{2}),(\d{3})', time_str.strip())
        if not match:
            raise ValueError(f"Formato de tiempo inválido: {time_str}")

        hours, minutes, seconds, milliseconds = map(int, match.groups())
        return hours * 3600 + minutes * 60 + seconds + milliseconds / 1000.0

    @staticmethod
    def seconds_to_srt_time(seconds: float) -> str:
        """Convierte segundos a formato SRT"""
        hours = int(seconds // 3600)
        remainder = seconds % 3600
        minutes = int(remainder // 60)
        remainder = remainder % 60
        secs = int(remainder)
        # Redondear milisegundos para evitar errores de precisión
        milliseconds = round((remainder - secs) * 1000)

        # Evitar overflow de milisegundos
        if milliseconds >= 1000:
            milliseconds = 999

        return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"

    @staticmethod
    def parse_file(srt_file: Path, show_progress: bool = True) -> List[Subtitle]:
        """Parsea archivo SRT y retorna lista de subtítulos validados"""
        subtitles = []

        with open(srt_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        current_id = None
        current_start = None
        current_end = None
        current_text = []
        consecutive_id = 0
        validation_count = 0
        has_errors = False

        for line in lines:
            line = line.rstrip('\n\r')

            # Detectar ID de subtítulo
            if re.match(r'^\d+$', line.strip()):
                current_id = line.strip()
                current_text = []

            # Detectar línea de timestamp
            elif re.match(r'^\d{2}:\d{2}:\d{2},\d{3}\s*-->\s*\d{2}:\d{2}:\d{2},\d{3}', line):
                match = re.match(
                    r'^(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})',
                    line
                )
                if match:
                    current_start = match.group(1).strip()
                    current_end = match.group(2).strip()

                    # Validar que tiempo final >= tiempo inicial
                    try:
                        start_sec = SRTParser.parse_srt_time(current_start)
                        end_sec = SRTParser.parse_srt_time(current_end)

                        if end_sec < start_sec:
                            print(f"{Colors.RED}{'━' * 50}{Colors.NC}")
                            print(f"{Colors.RED}✗ ERROR: Subtítulo con tiempo final < tiempo inicial{Colors.NC}")
                            print(f"{Colors.YELLOW}  ID original: {current_id}{Colors.NC}")
                            print(f"{Colors.YELLOW}  Inicio: {current_start} ({start_sec:.3f} s){Colors.NC}")
                            print(f"{Colors.YELLOW}  Fin: {current_end} ({end_sec:.3f} s){Colors.NC}")
                            print(f"{Colors.YELLOW}  Duración: {end_sec - start_sec:.3f}s (NEGATIVA){Colors.NC}")
                            print(f"{Colors.CYAN}  Por favor, corrige este subtítulo en el archivo SRT{Colors.NC}")
                            print(f"{Colors.RED}{'━' * 50}{Colors.NC}")
                            has_errors = True
                            current_id = None
                            current_start = None
                            current_end = None
                            current_text = []
                            continue

                    except ValueError as e:
                        print(f"{Colors.RED}Error parseando timestamps: {e}{Colors.NC}")
                        current_id = None
                        current_start = None
                        current_end = None
                        continue

            # Línea vacía = fin de subtítulo
            elif not line.strip() and current_id and current_text:
                if current_start and current_end:
                    try:
                        consecutive_id += 1
                        start_sec = SRTParser.parse_srt_time(current_start)
                        end_sec = SRTParser.parse_srt_time(current_end)

                        subtitle = Subtitle(
                            consecutive_id=consecutive_id,
                            original_id=current_id,
                            start_time=current_start,
                            end_time=current_end,
                            start_seconds=start_sec,
                            end_seconds=end_sec,
                            duration=end_sec - start_sec,
                            text=' '.join(current_text)
                        )
                        subtitles.append(subtitle)

                        # Mostrar progreso
                        validation_count += 1
                        if show_progress and validation_count % 100 == 0:
                            print(".", end="", flush=True)

                    except ValueError as e:
                        print(f"{Colors.RED}Error creando subtítulo: {e}{Colors.NC}")

                current_id = None
                current_start = None
                current_end = None
                current_text = []

            # Línea de texto
            elif current_id and current_start:
                if line.strip():
                    current_text.append(line.strip())

        # Procesar último subtítulo si existe
        if current_id and current_text and current_start and current_end:
            try:
                consecutive_id += 1
                start_sec = SRTParser.parse_srt_time(current_start)
                end_sec = SRTParser.parse_srt_time(current_end)

                if end_sec >= start_sec:
                    subtitle = Subtitle(
                        consecutive_id=consecutive_id,
                        original_id=current_id,
                        start_time=current_start,
                        end_time=current_end,
                        start_seconds=start_sec,
                        end_seconds=end_sec,
                        duration=end_sec - start_sec,
                        text=' '.join(current_text)
                    )
                    subtitles.append(subtitle)

                    validation_count += 1
                    if show_progress and validation_count % 100 == 0:
                        print(".", end="", flush=True)

            except ValueError:
                pass

        if show_progress and validation_count > 0:
            print()  # Nueva línea después de los puntos

        if has_errors:
            print(f"{Colors.RED}{'═' * 50}{Colors.NC}")
            print(f"{Colors.RED}Se encontraron subtítulos con errores{Colors.NC}")
            print(f"{Colors.RED}Por favor, corrige los subtítulos marcados arriba{Colors.NC}")
            print(f"{Colors.RED}{'═' * 50}{Colors.NC}")
            sys.exit(1)

        return subtitles

def get_audio_duration(file_path: Path) -> float:
    """Obtiene la duración de un archivo de audio/video"""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(file_path)],
            capture_output=True,
            text=True,
            check=True
        )
        return float(result.stdout.strip())
    except (subprocess.CalledProcessError, ValueError):
        return 0.0

def create_silence(duration: float, output: Path):
    """Crea un archivo de audio con silencio"""
    subprocess.run(
        ["ffmpeg", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
         "-t", str(duration), "-q:a", "9", "-acodec", "pcm_s16le",
         str(output), "-y"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=True
    )

def truncate_audio(input_file: Path, output_file: Path, duration: float) -> bool:
    """Trunca audio a la duración especificada"""
    try:
        subprocess.run(
            ["ffmpeg", "-i", str(input_file), "-t", str(duration),
             "-c:a", "copy", str(output_file), "-y"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True
        )
        return output_file.exists() and output_file.stat().st_size > 0
    except subprocess.CalledProcessError:
        return False

def main():
    parser = argparse.ArgumentParser(
        description="Genera audio TTS sincronizado con video desde archivo SRT"
    )
    parser.add_argument("srt_file", help="Archivo de subtítulos SRT")
    parser.add_argument("video", help="Archivo de video")
    parser.add_argument("audio_dir", nargs="?", help="Carpeta con audios ya generados")
    parser.add_argument("--test", type=int, nargs="?", const=30,
                       help="Modo test: procesar N subtítulos (default: 30)")
    parser.add_argument("--solo-audio", action="store_true",
                       help="Solo generar audio, sin video")
    parser.add_argument("--no-freeze", action="store_true",
                       help="Truncar audios largos en lugar de freeze")
    parser.add_argument("--remove-breaks", action="store_true",
                       help="Eliminar pausas >15min del video final")
    parser.add_argument("--only-remove-breaks", action="store_true",
                       help="SOLO eliminar pausas del video (sin TTS)")

    args = parser.parse_args()

    # Inicializar logger de errores
    error_logger = ErrorLogger()

    # Mostrar configuración
    print(f"{Colors.BLUE}{'═' * 50}{Colors.NC}")
    print(f"{Colors.BLUE}🔍 DETECTANDO MÉTODO TTS{Colors.NC}")
    print(f"{Colors.BLUE}{'═' * 50}{Colors.NC}")

    tts_engine = TTSEngine()

    # Verificar archivos
    srt_path = Path(args.srt_file)
    if not srt_path.exists():
        print(f"{Colors.RED}Error: No existe {srt_path}{Colors.NC}")
        sys.exit(1)

    # Buscar video con extensiones comunes
    video_path = None
    for ext in ['.mkv', '.mp4', '']:
        test_path = Path(args.video).with_suffix(ext) if ext else Path(args.video)
        if test_path.exists():
            video_path = test_path
            break

    if not video_path:
        print(f"{Colors.RED}Error: No se encuentra el video{Colors.NC}")
        sys.exit(1)

    print(f"{Colors.GREEN}SRT: {srt_path}{Colors.NC}")
    print(f"{Colors.GREEN}Video: {video_path}{Colors.NC}")

    if args.test:
        print(f"{Colors.YELLOW}⚠️  MODO TEST: {args.test} subtítulos{Colors.NC}")
    if args.solo_audio:
        print(f"{Colors.CYAN}🎵 MODO SOLO-AUDIO: No se generará video{Colors.NC}")
    if args.no_freeze:
        print(f"{Colors.MAGENTA}🚫 MODO NO-FREEZE: Audios largos serán truncados{Colors.NC}")
    if args.remove_breaks:
        print(f"{Colors.MAGENTA}✂️  MODO REMOVE-BREAKS: Se eliminarán pausas >15min{Colors.NC}")
    if args.only_remove_breaks:
        print(f"{Colors.MAGENTA}✂️  MODO ONLY-REMOVE-BREAKS: SOLO se eliminarán pausas{Colors.NC}")

    # Parsear SRT
    print(f"{Colors.BLUE}{'═' * 50}{Colors.NC}")
    print(f"{Colors.BLUE}📋 PASO 1: PARSEAR Y VALIDAR SUBTÍTULOS{Colors.NC}")
    print(f"{Colors.BLUE}{'═' * 50}{Colors.NC}")

    subtitles = SRTParser.parse_file(srt_path)
    print(f"{Colors.GREEN}Total subtítulos válidos: {len(subtitles)}{Colors.NC}")

    # Limitar en modo test
    if args.test and len(subtitles) > args.test:
        print(f"{Colors.YELLOW}Limitando a {args.test} subtítulos{Colors.NC}")
        subtitles = subtitles[:args.test]

    print(f"{Colors.GREEN}A procesar: {len(subtitles)}{Colors.NC}")

    # Generar SRT con IDs consecutivos
    working_srt = video_path.with_suffix('').with_name(f"{video_path.stem}_working.srt")
    with open(working_srt, 'w', encoding='utf-8') as f:
        for sub in subtitles:
            f.write(f"{sub.consecutive_id}\n")
            f.write(f"{sub.start_time} --> {sub.end_time}\n")
            f.write(f"{sub.text}\n")
            f.write("\n")
    print(f"{Colors.GREEN}✅ SRT de trabajo generado: {working_srt}{Colors.NC}")
    print(f"{Colors.CYAN}   (IDs renumerados: 1-{len(subtitles)}){Colors.NC}")

    # Crear directorio temporal en el directorio actual
    import datetime
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    temp_dir = Path.cwd() / f"temp_audio_{timestamp}"
    temp_dir.mkdir(exist_ok=True)
    logs_dir = temp_dir / "logs"
    logs_dir.mkdir(exist_ok=True)
    print(f"{Colors.GREEN}Carpeta temporal: {temp_dir}{Colors.NC}")

    # PASO 2: Generar audios con ajuste inteligente
    print(f"{Colors.BLUE}{'═' * 50}{Colors.NC}")
    print(f"{Colors.BLUE}🎤 PASO 2: GENERAR AUDIOS CON AJUSTE INTELIGENTE{Colors.NC}")
    print(f"{Colors.BLUE}{'═' * 50}{Colors.NC}")

    audio_segments: Dict[int, AudioSegment] = {}
    rate_usage = {180: 0, 200: 0, 220: 0, 240: 0, 'freeze': 0, 'truncated': 0}
    optimal_rate = 180
    learning_phase = True
    processed_count = 0

    for idx, subtitle in enumerate(subtitles):
        # Limpiar texto HTML
        clean_text = re.sub(r'<[^>]*>', '', subtitle.text)

        # Calcular tiempo disponible
        if idx + 1 < len(subtitles):
            next_subtitle = subtitles[idx + 1]
            available_time = next_subtitle.start_seconds - subtitle.start_seconds
        else:
            available_time = subtitle.duration

        print(f"{Colors.YELLOW}{'━' * 50}{Colors.NC}")
        print(f"{Colors.YELLOW}Subtítulo {subtitle.consecutive_id} "
              f"{Colors.CYAN}(ID original: {subtitle.original_id}){Colors.NC}")
        print(f"{Colors.YELLOW}  Texto: {clean_text[:50]}...{Colors.NC}")
        print(f"{Colors.BLUE}  Duración subtítulo: {subtitle.duration:.3f}s{Colors.NC}")
        print(f"{Colors.BLUE}  Tiempo disponible: {available_time:.3f}s{Colors.NC}")

        current_rate = optimal_rate if not learning_phase else 180

        if not learning_phase:
            print(f"{Colors.MAGENTA}🎯 Usando rate aprendido: {current_rate} wpm{Colors.NC}")

        # Determinar rates a probar
        if args.no_freeze or args.solo_audio:
            rate_list = [current_rate, 200, 220, 240]
        else:
            rate_list = [current_rate, 200, 220]

        audio_created = False
        final_rate = current_rate
        audio_file = temp_dir / f"{subtitle.consecutive_id}.wav"

        # Probar diferentes rates
        for try_rate in rate_list:
            temp_audio = temp_dir / f"{subtitle.consecutive_id}_temp.wav"

            print(f"  {Colors.BLUE}Probando rate {try_rate} wpm...{Colors.NC}")

            if not tts_engine.generate_audio(clean_text, try_rate, temp_audio):
                print(f"  {Colors.RED}Error generando audio{Colors.NC}")
                continue

            audio_duration = get_audio_duration(temp_audio)
            diff = audio_duration - available_time

            print(f"  {Colors.BLUE}→ Duración: {audio_duration:.3f}s (diff: {diff:.3f}s){Colors.NC}")

            if diff < 0.5:
                temp_audio.rename(audio_file)
                audio_created = True
                final_rate = try_rate
                rate_usage[try_rate] += 1
                print(f"  {Colors.GREEN}✅ Audio ajustado con rate {try_rate}{Colors.NC}")

                audio_segments[subtitle.consecutive_id] = AudioSegment(
                    subtitle_id=subtitle.consecutive_id,
                    audio_file=audio_file,
                    rate=try_rate,
                    needs_freeze=False,
                    was_truncated=False
                )
                break
            else:
                temp_audio.unlink()

        # Si no se ajustó, truncar o freeze
        if not audio_created:
            if args.no_freeze or args.solo_audio:
                print(f"  {Colors.YELLOW}⚠️  Audio muy largo, generando con rate 240 y truncando{Colors.NC}")
                full_audio = temp_dir / f"{subtitle.consecutive_id}_full.wav"

                if tts_engine.generate_audio(clean_text, 240, full_audio):
                    if truncate_audio(full_audio, audio_file, available_time):
                        full_audio.unlink()
                        rate_usage['truncated'] += 1
                        print(f"  {Colors.GREEN}✅ Audio truncado a {available_time:.3f}s{Colors.NC}")

                        audio_segments[subtitle.consecutive_id] = AudioSegment(
                            subtitle_id=subtitle.consecutive_id,
                            audio_file=audio_file,
                            rate=240,
                            needs_freeze=False,
                            was_truncated=True
                        )
                    else:
                        print(f"  {Colors.RED}❌ Error truncando audio{Colors.NC}")
                        sys.exit(1)
            else:
                print(f"  {Colors.YELLOW}⚠️  Audio muy largo, generando con rate 220 y marcando para freeze{Colors.NC}")

                if tts_engine.generate_audio(clean_text, 220, audio_file):
                    audio_duration = get_audio_duration(audio_file)
                    freeze_time = audio_duration - available_time
                    rate_usage['freeze'] += 1
                    print(f"  {Colors.RED}🎬 Requerirá freeze de {freeze_time:.3f}s{Colors.NC}")

                    audio_segments[subtitle.consecutive_id] = AudioSegment(
                        subtitle_id=subtitle.consecutive_id,
                        audio_file=audio_file,
                        rate=220,
                        needs_freeze=True,
                        freeze_duration=freeze_time,
                        was_truncated=False
                    )

        processed_count += 1

        # Análisis de aprendizaje
        if processed_count == 50 and learning_phase:
            print(f"{Colors.MAGENTA}{'━' * 50}{Colors.NC}")
            print(f"{Colors.MAGENTA}📊 ANÁLISIS DE APRENDIZAJE (50 subtítulos){Colors.NC}")
            print(f"{Colors.MAGENTA}{'━' * 50}{Colors.NC}")
            for rate in [180, 200, 220, 240]:
                print(f"{Colors.MAGENTA}Rate {rate} wpm: {rate_usage[rate]} veces{Colors.NC}")
            print(f"{Colors.MAGENTA}Freeze necesario: {rate_usage['freeze']} veces{Colors.NC}")
            print(f"{Colors.MAGENTA}Truncados: {rate_usage['truncated']} veces{Colors.NC}")

            # Determinar rate óptimo
            max_count = 0
            for rate in [180, 200, 220, 240]:
                if rate_usage[rate] > max_count:
                    max_count = rate_usage[rate]
                    optimal_rate = rate

            learning_phase = False
            print(f"{Colors.GREEN}🎯 Rate óptimo determinado: {optimal_rate} wpm{Colors.NC}")
            print(f"{Colors.MAGENTA}{'━' * 50}{Colors.NC}")

    print(f"{Colors.GREEN}✅ Audios generados{Colors.NC}")

    # Resumen
    print(f"{Colors.BLUE}{'═' * 50}{Colors.NC}")
    print(f"{Colors.BLUE}📊 RESUMEN DE PROCESAMIENTO{Colors.NC}")
    print(f"{Colors.BLUE}{'═' * 50}{Colors.NC}")

    freeze_count = sum(1 for seg in audio_segments.values() if seg.needs_freeze)
    truncated_count = sum(1 for seg in audio_segments.values() if seg.was_truncated)

    print(f"{Colors.GREEN}Total subtítulos: {len(subtitles)}{Colors.NC}")
    if args.no_freeze or args.solo_audio:
        print(f"{Colors.YELLOW}Audios truncados: {truncated_count}{Colors.NC}")
        print(f"{Colors.GREEN}Sin truncar: {len(subtitles) - truncated_count}{Colors.NC}")
    else:
        print(f"{Colors.YELLOW}Requieren freeze: {freeze_count}{Colors.NC}")
        print(f"{Colors.GREEN}Sin freeze: {len(subtitles) - freeze_count}{Colors.NC}")

    # Generar SRT debug
    print(f"{Colors.BLUE}{'═' * 50}{Colors.NC}")
    print(f"{Colors.BLUE}📝 PASO 3: GENERAR SRT DEBUG{Colors.NC}")
    print(f"{Colors.BLUE}{'═' * 50}{Colors.NC}")

    debug_srt = video_path.with_suffix('').with_name(f"{video_path.stem}_debug.srt")
    time_offset = 0.0

    with open(debug_srt, 'w', encoding='utf-8') as f:
        for subtitle in subtitles:
            segment = audio_segments.get(subtitle.consecutive_id)
            if not segment:
                continue

            new_start = subtitle.start_seconds + time_offset
            new_end = subtitle.end_seconds + time_offset

            new_start_time = SRTParser.seconds_to_srt_time(new_start)
            new_end_time = SRTParser.seconds_to_srt_time(new_end)

            rate = segment.rate
            offset_ms = int(time_offset * 1000)

            # Construir texto con metadatos
            if segment.was_truncated:
                if time_offset > 0:
                    new_text = f"[#{subtitle.consecutive_id} r{rate} +{offset_ms}ms] [✂️ TRUNCADO] {subtitle.text}"
                else:
                    new_text = f"[#{subtitle.consecutive_id} r{rate}] [✂️ TRUNCADO] {subtitle.text}"
            elif segment.needs_freeze:
                if time_offset > 0:
                    new_text = f"[#{subtitle.consecutive_id} r{rate} +{offset_ms}ms] [⏸️ FREEZE +{segment.freeze_duration:.3f}s] {subtitle.text}"
                else:
                    new_text = f"[#{subtitle.consecutive_id} r{rate}] [⏸️ FREEZE +{segment.freeze_duration:.3f}s] {subtitle.text}"
                time_offset += segment.freeze_duration
            else:
                if time_offset > 0:
                    new_text = f"[#{subtitle.consecutive_id} r{rate} +{offset_ms}ms] {subtitle.text}"
                else:
                    new_text = f"[#{subtitle.consecutive_id} r{rate}] {subtitle.text}"

            f.write(f"{subtitle.consecutive_id}\n")
            f.write(f"{new_start_time} --> {new_end_time}\n")
            f.write(f"{new_text}\n")
            f.write("\n")

    print(f"{Colors.GREEN}✅ Archivo SRT debug generado: {debug_srt}{Colors.NC}")

    # PASO 4: Procesar video
    print(f"{Colors.BLUE}{'═' * 50}{Colors.NC}")
    print(f"{Colors.BLUE}🎬 PASO 4: PROCESAR VIDEO{Colors.NC}")
    print(f"{Colors.BLUE}{'═' * 50}{Colors.NC}")

    video_to_use = video_path

    if args.solo_audio:
        print(f"{Colors.CYAN}Modo solo-audio: Saltando procesamiento de video{Colors.NC}")
        video_to_use = None
    elif args.no_freeze:
        print(f"{Colors.CYAN}Modo no-freeze: Usando video original{Colors.NC}")
    else:
        if freeze_count > 0:
            print(f"{Colors.YELLOW}Procesando video con freezes...{Colors.NC}")

            # Obtener FPS del video
            try:
                result = subprocess.run(
                    ["ffprobe", "-v", "error", "-select_streams", "v:0",
                     "-show_entries", "stream=r_frame_rate",
                     "-of", "default=noprint_wrappers=1:nokey=1", str(video_path)],
                    capture_output=True,
                    text=True,
                    check=True
                )
                fps_str = result.stdout.strip()
                if '/' in fps_str:
                    num, denom = fps_str.split('/')
                    fps = float(num) / float(denom)
                else:
                    fps = float(fps_str)
            except:
                fps = 30.0

            print(f"{Colors.GREEN}FPS: {fps:.2f}{Colors.NC}")

            video_segments = []

            for subtitle in subtitles:
                segment = audio_segments.get(subtitle.consecutive_id)
                if not segment:
                    continue

                print(f"{Colors.YELLOW}Segmento {subtitle.consecutive_id} "
                      f"({subtitle.start_seconds:.3f}s, {subtitle.duration:.3f}s){Colors.NC}")

                seg_file = temp_dir / f"vseg_{subtitle.consecutive_id}.mkv"

                # Extraer segmento de video
                try:
                    subprocess.run(
                        ["ffmpeg", "-i", str(video_path),
                         "-ss", str(subtitle.start_seconds),
                         "-t", str(subtitle.duration),
                         "-c:v", "libx264", "-preset", "ultrafast", "-an",
                         str(seg_file), "-y"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        check=True
                    )

                    if seg_file.exists() and seg_file.stat().st_size > 0:
                        print(f"  {Colors.GREEN}✓ Segmento creado{Colors.NC}")
                        video_segments.append(seg_file)
                    else:
                        print(f"  {Colors.RED}✗ Error: segmento vacío{Colors.NC}")
                        continue

                except subprocess.CalledProcessError:
                    print(f"  {Colors.RED}✗ Error creando segmento{Colors.NC}")
                    continue

                # Crear freeze si es necesario
                if segment.needs_freeze:
                    freeze_dur = segment.freeze_duration
                    print(f"  {Colors.YELLOW}+ Creando freeze de {freeze_dur:.3f}s...{Colors.NC}")

                    frame_file = temp_dir / f"freeze_{subtitle.consecutive_id}.png"
                    freeze_file = temp_dir / f"vfreeze_{subtitle.consecutive_id}.mkv"

                    try:
                        # Extraer último frame
                        subprocess.run(
                            ["ffmpeg", "-sseof", "-0.1", "-i", str(seg_file),
                             "-frames:v", "1", str(frame_file), "-y"],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            check=True
                        )

                        if frame_file.exists() and frame_file.stat().st_size > 0:
                            # Crear video de freeze
                            subprocess.run(
                                ["ffmpeg", "-loop", "1", "-i", str(frame_file),
                                 "-t", str(freeze_dur), "-r", str(fps),
                                 "-pix_fmt", "yuv420p", "-c:v", "libx264",
                                 "-preset", "ultrafast", str(freeze_file), "-y"],
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL,
                                check=True
                            )

                            if freeze_file.exists() and freeze_file.stat().st_size > 0:
                                video_segments.append(freeze_file)
                                print(f"  {Colors.GREEN}✓ Freeze creado{Colors.NC}")

                    except subprocess.CalledProcessError:
                        print(f"  {Colors.YELLOW}⚠ Error creando freeze{Colors.NC}")

            # Concatenar segmentos
            if video_segments:
                print(f"{Colors.YELLOW}Concatenando {len(video_segments)} segmentos...{Colors.NC}")

                concat_list = temp_dir / "video_segments.txt"
                with open(concat_list, 'w') as f:
                    for seg in video_segments:
                        f.write(f"file '{seg.name}'\n")

                processed_video = temp_dir / "video_processed.mkv"

                try:
                    subprocess.run(
                        ["ffmpeg", "-f", "concat", "-safe", "0",
                         "-i", str(concat_list), "-c", "copy",
                         str(processed_video), "-y"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        check=True
                    )

                    if processed_video.exists() and processed_video.stat().st_size > 0:
                        video_to_use = processed_video
                        print(f"{Colors.GREEN}✓ Video procesado{Colors.NC}")
                    else:
                        print(f"{Colors.RED}✗ Error: video vacío{Colors.NC}")
                        sys.exit(1)

                except subprocess.CalledProcessError:
                    print(f"{Colors.RED}✗ Error concatenando{Colors.NC}")
                    sys.exit(1)
            else:
                print(f"{Colors.RED}✗ No se crearon segmentos{Colors.NC}")
                sys.exit(1)
        else:
            print(f"{Colors.GREEN}Sin freezes, usando video original{Colors.NC}")

    # PASO 5: Construir audio sincronizado
    print(f"{Colors.BLUE}{'═' * 50}{Colors.NC}")
    print(f"{Colors.BLUE}🎵 PASO 5: CONSTRUIR AUDIO SINCRONIZADO{Colors.NC}")
    print(f"{Colors.BLUE}{'═' * 50}{Colors.NC}")

    # Crear audio master con silencio inicial
    audio_master = temp_dir / "audio_master.wav"
    create_silence(0.001, audio_master)
    current_master_duration = 0.0
    concat_counter = 0  # Contador para nombres únicos

    for idx, subtitle in enumerate(subtitles):
        segment = audio_segments.get(subtitle.consecutive_id)
        if not segment:
            continue

        print(f"{Colors.YELLOW}{'━' * 50}{Colors.NC}")
        print(f"{Colors.YELLOW}Subtítulo {subtitle.consecutive_id} "
              f"(inicio: {subtitle.start_seconds:.3f}s){Colors.NC}")

        # Verificar duración actual del audio master
        current_master_duration = get_audio_duration(audio_master)

        # Agregar gap si es necesario
        gap = subtitle.start_seconds - current_master_duration

        if gap > 0.01:
            print(f"  {Colors.GREEN}→ Agregando silencio de {gap:.3f}s{Colors.NC}")
            gap_file = temp_dir / f"gap_{subtitle.consecutive_id}.wav"
            create_silence(gap, gap_file)

            # Concatenar con nombre único
            concat_counter += 1
            temp_master = temp_dir / f"audio_concat_{concat_counter}.wav"
            subprocess.run(
                ["ffmpeg", "-i", str(audio_master), "-i", str(gap_file),
                 "-filter_complex", "[0:a][1:a]concat=n=2:v=0:a=1[out]",
                 "-map", "[out]", str(temp_master), "-y"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True
            )
            # Eliminar master anterior si no es el inicial
            if audio_master != temp_dir / "audio_master.wav":
                audio_master.unlink()
            audio_master = temp_master
            gap_file.unlink()
            current_master_duration = get_audio_duration(audio_master)

        # Agregar audio TTS
        audio_duration = get_audio_duration(segment.audio_file)
        print(f"  {Colors.GREEN}→ Agregando audio TTS ({audio_duration:.3f}s){Colors.NC}")

        if segment.was_truncated:
            print(f"  {Colors.MAGENTA}  (Audio truncado){Colors.NC}")

        concat_counter += 1
        temp_master = temp_dir / f"audio_concat_{concat_counter}.wav"
        subprocess.run(
            ["ffmpeg", "-i", str(audio_master), "-i", str(segment.audio_file),
             "-filter_complex", "[0:a][1:a]concat=n=2:v=0:a=1[out]",
             "-map", "[out]", str(temp_master), "-y"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True
        )
        # Eliminar master anterior
        if audio_master != temp_dir / "audio_master.wav":
            audio_master.unlink()
        audio_master = temp_master
        current_master_duration = get_audio_duration(audio_master)

        # Agregar padding si es necesario
        if idx + 1 < len(subtitles):
            next_subtitle = subtitles[idx + 1]
            expected_position = next_subtitle.start_seconds
        else:
            expected_position = subtitle.start_seconds + subtitle.duration

        padding = expected_position - current_master_duration

        if padding > 0.01:
            print(f"  {Colors.GREEN}→ Agregando padding de {padding:.3f}s{Colors.NC}")
            padding_file = temp_dir / f"padding_{subtitle.consecutive_id}.wav"
            create_silence(padding, padding_file)

            concat_counter += 1
            temp_master = temp_dir / f"audio_concat_{concat_counter}.wav"
            subprocess.run(
                ["ffmpeg", "-i", str(audio_master), "-i", str(padding_file),
                 "-filter_complex", "[0:a][1:a]concat=n=2:v=0:a=1[out]",
                 "-map", "[out]", str(temp_master), "-y"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True
            )
            # Eliminar master anterior
            if audio_master != temp_dir / "audio_master.wav":
                audio_master.unlink()
            audio_master = temp_master
            padding_file.unlink()
            current_master_duration = get_audio_duration(audio_master)

        # Verificar sincronización
        final_diff = abs(current_master_duration - expected_position)

        if final_diff < 0.05:
            print(f"  {Colors.GREEN}✅ Sincronizado (diff: {final_diff:.3f}s){Colors.NC}")
        else:
            print(f"  {Colors.RED}❌ Desincronizado (diff: {final_diff:.3f}s){Colors.NC}")

    audio_final = temp_dir / "audio_final.wav"
    audio_master.rename(audio_final)
    print(f"{Colors.GREEN}✅ Audio final creado{Colors.NC}")

    # PASO 6: Fusionar video y audio
    print(f"{Colors.BLUE}{'═' * 50}{Colors.NC}")
    print(f"{Colors.BLUE}🎞️  PASO 6: FUSIONAR VIDEO Y AUDIO{Colors.NC}")
    print(f"{Colors.BLUE}{'═' * 50}{Colors.NC}")

    if args.solo_audio:
        output_audio_wav = video_path.with_suffix('').with_name(f"{video_path.stem}_tts_audio.wav")
        output_audio_aac = video_path.with_suffix('').with_name(f"{video_path.stem}_tts_audio.aac")

        shutil.copy(audio_final, output_audio_wav)
        print(f"{Colors.GREEN}✅ Audio: {output_audio_wav}{Colors.NC}")

        # Convertir a AAC
        try:
            subprocess.run(
                ["ffmpeg", "-i", str(output_audio_wav),
                 "-c:a", "aac", "-b:a", "192k",
                 str(output_audio_aac), "-y"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True
            )
            if output_audio_aac.exists():
                print(f"{Colors.GREEN}✅ Audio AAC: {output_audio_aac}{Colors.NC}")
        except subprocess.CalledProcessError:
            pass

        output_video = None
    else:
        output_video = video_path.with_suffix('').with_name(f"{video_path.stem}_con_tts.mkv")

        try:
            result = subprocess.run(
                ["ffmpeg", "-i", str(video_to_use), "-i", str(audio_final),
                 "-map", "0:v:0", "-map", "1:a:0",
                 "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", "-b:a", "192k",
                 "-shortest", str(output_video), "-y"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True
            )

            if not output_video.exists():
                print(f"{Colors.RED}✗ Error creando video{Colors.NC}")
                sys.exit(1)

            print(f"{Colors.GREEN}✅ Video: {output_video}{Colors.NC}")

        except subprocess.CalledProcessError as e:
            print(f"{Colors.RED}✗ Error fusionando video y audio{Colors.NC}")
            print(f"{Colors.YELLOW}Comando: {' '.join(e.cmd)}{Colors.NC}")
            if e.stderr:
                print(f"{Colors.YELLOW}Error de ffmpeg:{Colors.NC}")
                # Mostrar solo las últimas 20 líneas del error
                error_lines = e.stderr.strip().split('\n')
                for line in error_lines[-20:]:
                    print(f"  {line}")
            sys.exit(1)

    # PASO 7: Eliminar pausas largas (si está activado)
    output_video_clean = None
    if (args.remove_breaks or args.only_remove_breaks) and not args.solo_audio and output_video:
        print(f"{Colors.BLUE}{'═' * 50}{Colors.NC}")
        print(f"{Colors.BLUE}✂️  PASO 7: ELIMINAR PAUSAS LARGAS DEL VIDEO{Colors.NC}")
        print(f"{Colors.BLUE}{'═' * 50}{Colors.NC}")

        MIN_GAP_SECONDS = 900  # 15 minutos
        MARGIN_SECONDS = 60     # 1 minuto de margen

        print(f"{Colors.YELLOW}Analizando gaps en los subtítulos...{Colors.NC}")

        gaps = []
        for idx in range(len(subtitles) - 1):
            current = subtitles[idx]
            next_sub = subtitles[idx + 1]

            gap = next_sub.start_seconds - current.end_seconds

            if gap >= MIN_GAP_SECONDS:
                cut_start = current.end_seconds + MARGIN_SECONDS
                cut_end = next_sub.start_seconds - MARGIN_SECONDS
                cut_duration = cut_end - cut_start

                if cut_duration > 0:
                    gaps.append((cut_start, cut_end))
                    print(f"{Colors.YELLOW}  ✓ Gap detectado: {gap:.1f}s "
                          f"({gap/60:.1f} min) entre subtítulo {current.consecutive_id} "
                          f"y {next_sub.consecutive_id}{Colors.NC}")
                    print(f"{Colors.GREEN}    → Se eliminará: {cut_duration:.1f}s "
                          f"({cut_duration/60:.1f} min){Colors.NC}")

        if not gaps:
            print(f"{Colors.GREEN}✓ No se encontraron pausas largas (>15 min){Colors.NC}")
        else:
            print(f"{Colors.CYAN}{'═' * 50}{Colors.NC}")
            print(f"{Colors.CYAN}Total de pausas a eliminar: {len(gaps)}{Colors.NC}")

            # Calcular segmentos a mantener
            keep_segments = []
            current_pos = 0.0

            for gap_start, gap_end in gaps:
                keep_segments.append((current_pos, gap_start))
                current_pos = gap_end

            # Agregar segmento final
            video_duration = get_audio_duration(output_video)
            keep_segments.append((current_pos, video_duration))

            print(f"{Colors.YELLOW}Segmentos a mantener: {len(keep_segments)}{Colors.NC}")

            # Crear segmentos
            segment_files = []
            for idx, (start, end) in enumerate(keep_segments):
                duration = end - start

                if duration > 0.1:
                    print(f"{Colors.YELLOW}  Extrayendo segmento {idx+1}: "
                          f"{start:.1f}s a {end:.1f}s ({duration:.1f}s){Colors.NC}")

                    seg_file = temp_dir / f"seg_{idx}.mkv"

                    try:
                        subprocess.run(
                            ["ffmpeg", "-i", str(output_video),
                             "-ss", str(start), "-t", str(duration),
                             "-c", "copy", str(seg_file), "-y"],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            check=True
                        )

                        if seg_file.exists() and seg_file.stat().st_size > 0:
                            segment_files.append(seg_file)
                            print(f"{Colors.GREEN}    ✓ Segmento creado{Colors.NC}")
                        else:
                            print(f"{Colors.RED}    ✗ Error: segmento vacío{Colors.NC}")

                    except subprocess.CalledProcessError:
                        print(f"{Colors.RED}    ✗ Error creando segmento{Colors.NC}")

            # Concatenar segmentos
            if segment_files:
                print(f"{Colors.CYAN}{'═' * 50}{Colors.NC}")
                print(f"{Colors.CYAN}Concatenando {len(segment_files)} segmentos...{Colors.NC}")

                concat_list = temp_dir / "concat_breaks.txt"
                with open(concat_list, 'w') as f:
                    for seg in segment_files:
                        f.write(f"file '{seg}'\n")

                output_video_clean = video_path.with_suffix('').with_name(
                    f"{video_path.stem}_clean_breaks.mkv"
                )

                try:
                    subprocess.run(
                        ["ffmpeg", "-f", "concat", "-safe", "0",
                         "-i", str(concat_list), "-c", "copy",
                         str(output_video_clean), "-y"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        check=True
                    )

                    if output_video_clean.exists() and output_video_clean.stat().st_size > 0:
                        total_removed = sum(end - start for start, end in gaps)
                        print(f"{Colors.GREEN}✓ Video sin pausas creado: {output_video_clean}{Colors.NC}")
                        print(f"{Colors.GREEN}✓ Tiempo total eliminado: {total_removed:.1f}s "
                              f"({total_removed/60:.1f} min){Colors.NC}")
                    else:
                        print(f"{Colors.RED}✗ Error: video vacío{Colors.NC}")

                except subprocess.CalledProcessError:
                    print(f"{Colors.RED}✗ Error concatenando segmentos{Colors.NC}")
            else:
                print(f"{Colors.RED}✗ No se crearon segmentos válidos{Colors.NC}")

    # Resumen final
    print(f"{Colors.GREEN}{'═' * 50}{Colors.NC}")
    print(f"{Colors.CYAN}📄 ARCHIVOS GENERADOS{Colors.NC}")
    print(f"{Colors.CYAN}{'═' * 50}{Colors.NC}")

    if args.solo_audio:
        print(f"{Colors.GREEN}✅ {output_audio_wav}{Colors.NC}")
        if output_audio_aac and output_audio_aac.exists():
            print(f"{Colors.GREEN}✅ {output_audio_aac}{Colors.NC}")
    else:
        if output_video:
            print(f"{Colors.GREEN}✅ {output_video}{Colors.NC}")
        if output_video_clean and output_video_clean.exists():
            print(f"{Colors.GREEN}✅ {output_video_clean} {Colors.CYAN}(sin pausas largas){Colors.NC}")

    print(f"{Colors.GREEN}✅ {working_srt}{Colors.NC}")
    print(f"{Colors.GREEN}✅ {debug_srt}{Colors.NC}")

    # Mostrar resumen de errores si los hay
    if args.test or error_logger.has_errors() or error_logger.warnings:
        error_logger.print_summary()

    if args.test or args.only_remove_breaks:
        print(f"{Colors.YELLOW}⚠️  Conservando: {temp_dir}{Colors.NC}")
    else:
        print(f"{Colors.YELLOW}Limpiando temporales...{Colors.NC}")
        # shutil.rmtree(temp_dir)  # Descomentar cuando esté probado

    print(f"{Colors.GREEN}¡Proceso completado!{Colors.NC}")

if __name__ == "__main__":
    main()
