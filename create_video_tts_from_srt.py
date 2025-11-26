#!/usr/bin/env python3
"""
Script para generar audio TTS con ajuste automático de velocidad
Compatible con macOS (say) y Linux/otros (gTTS via Python)

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
                print(f"{Colors.YELLOW}Instala con: pip3 install gtts pydub{Colors.NC}")
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
        milliseconds = int((remainder - secs) * 1000)

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

    # Crear directorio temporal
    temp_dir = Path(tempfile.mkdtemp(prefix="temp_audio_"))
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

    # TODO: Implementar pasos 4-7 (video processing, audio sync, merge, break removal)
    print(f"\n{Colors.GREEN}✅ Implementación principal completada{Colors.NC}")
    print(f"{Colors.YELLOW}Nota: Pasos de procesamiento de video en desarrollo...{Colors.NC}")
    print(f"{Colors.CYAN}Archivos generados:{Colors.NC}")
    print(f"{Colors.GREEN}  - {working_srt}{Colors.NC}")
    print(f"{Colors.GREEN}  - {debug_srt}{Colors.NC}")
    print(f"{Colors.YELLOW}  - Audios en: {temp_dir}{Colors.NC}")

if __name__ == "__main__":
    main()
