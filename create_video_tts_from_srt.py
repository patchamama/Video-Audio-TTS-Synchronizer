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
  video                 [Opcional] Archivo de video (mkv, mp4, etc.)
  audio_dir             [Opcional] Carpeta con audios previamente generados

Opcionales:
  --test N              Modo test: procesar solo N subtítulos (default: 30 si no se especifica N)
  --solo-audio          Solo generar el audio master, sin procesar video
  --no-freeze           Truncar audios largos en lugar de congelar video
  --no-truncate        Nunca truncar: recuperar desfase usando rate máximo
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

# Atajo: usa video.mp4 y activa --solo-audio automáticamente
python3 create_video_tts_from_srt.py video.srt

# No-truncate: conservar todo el texto y recuperar el desfase a rate máximo
python3 create_video_tts_from_srt.py video.srt video.mp4 --no-truncate

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

- {video}_working.srt                           : Subtítulos con IDs renumerados consecutivamente
- {video}_debug.srt                             : Subtítulos con metadatos de TTS
- {srt}-to-test.srt                             : Subtítulos ajustados al audio (--no-truncate)
- {video}_{tts}_{os}_{freeze}.mkv               : Video final (ej: video_gtts_Linux_freeze.mkv)
- {video}_{tts}_{os}_{freeze}_sin_pausas.mkv    : Video sin pausas largas (--remove-breaks)
- {video}_tts_audio.{wav,aac,mp3}               : Audio exportado (--solo-audio)
- temp_{srt-name}_{code}/                       : Carpeta temporal con checkpoints

Donde {freeze} puede ser:
  - freeze   : Se usaron freeze frames para audios largos
  - nofreeze : Se truncaron audios largos (--no-freeze) o no hubo audios largos

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
import datetime
import json
import os
import platform
import re
import subprocess
import sys
import tempfile
import time
import uuid
import base64
import http.server
import importlib.util
import io
import webbrowser
import threading
import mimetypes
from urllib.parse import parse_qs, quote, urlparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple
import shutil
import zipfile

# Incrementar en cada actualización publicada (SemVer).
APP_VERSION = "2.38.0"

NOTES_FILE = Path(__file__).resolve().parent / 'notas.txt'


def count_notes(content: str) -> int:
    """Cuenta líneas de notas visibles, incluyendo tareas de checklist."""
    return sum(bool(line.strip()) for line in content.splitlines())


def remove_temp_directories(directory: Path) -> List[str]:
    """Elimina únicamente directorios locales `temp_*`, sin seguir enlaces."""
    deleted = []
    for candidate in directory.glob('temp_*'):
        if candidate.is_dir() and not candidate.is_symlink():
            shutil.rmtree(candidate)
            deleted.append(candidate.name)
    return sorted(deleted)


def set_terminal_progress(current: int, total: int) -> None:
    """Actualiza el título de una terminal interactiva con el progreso actual."""
    if not sys.stdout.isatty() or total <= 0:
        return
    percent = min(100, max(0, round(current / total * 100)))
    sys.stdout.write(f'\033]0;Video TTS · {percent}%\007')
    sys.stdout.flush()


def sync_notes_to_github() -> dict:
    """Versiona y publica solo notas.txt en el remoto Git configurado."""
    repository = NOTES_FILE.parent
    try:
        subprocess.run(['git', '-C', str(repository), 'add', NOTES_FILE.name], check=True, capture_output=True, text=True)
        changed = subprocess.run(['git', '-C', str(repository), 'diff', '--cached', '--quiet', '--', NOTES_FILE.name], capture_output=True, text=True).returncode == 1
        if not changed:
            return {'synced': True, 'message': 'Sin cambios pendientes en GitHub.'}
        subprocess.run(['git', '-C', str(repository), 'commit', '-m', 'docs: update notes'], check=True, capture_output=True, text=True)
        subprocess.run(['git', '-C', str(repository), 'push', 'origin', 'HEAD'], check=True, capture_output=True, text=True, timeout=60)
        return {'synced': True, 'message': 'Notas guardadas y sincronizadas con GitHub.'}
    except (OSError, subprocess.SubprocessError) as error:
        return {'synced': False, 'message': f'Notas guardadas localmente; GitHub no se pudo sincronizar: {error}'}


def configure_console_output():
    """Evita que consolas Windows cp1252 fallen al imprimir Unicode."""
    if platform.system() != "Windows":
        return
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError):
            pass


configure_console_output()

# Colores para terminal
class Colors:
    """Códigos de colores ANSI (desactivados en Windows)"""
    # Detectar si estamos en Windows
    _is_windows = platform.system() == "Windows"

    if _is_windows:
        # En Windows, no usar códigos de color para evitar caracteres extraños
        RED = ''
        GREEN = ''
        YELLOW = ''
        BLUE = ''
        MAGENTA = ''
        CYAN = ''
        NC = ''
    else:
        # En Unix/Linux/macOS, usar códigos ANSI
        RED = '\033[0;31m'
        GREEN = '\033[0;32m'
        YELLOW = '\033[1;33m'
        BLUE = '\033[0;34m'
        MAGENTA = '\033[0;35m'
        CYAN = '\033[0;36m'
        NC = '\033[0m'  # No Color


MAX_TTS_RATE = 240

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
    timing_offset: float = 0.0

def get_unique_output_path(base_path: Path) -> Path:
    """
    Genera un nombre de archivo único si el archivo ya existe.
    Si video_con_tts.mkv existe, intenta video_con_tts_1.mkv, video_con_tts_2.mkv, etc.
    """
    if not base_path.exists():
        return base_path

    # Extraer partes del nombre
    stem = base_path.stem
    suffix = base_path.suffix
    parent = base_path.parent

    # Intentar con números incrementales
    counter = 1
    while True:
        new_path = parent / f"{stem}_{counter}{suffix}"
        if not new_path.exists():
            return new_path
        counter += 1
        # Límite de seguridad para evitar loop infinito
        if counter > 9999:
            # Usar timestamp como último recurso
            import time
            timestamp = int(time.time())
            return parent / f"{stem}_{timestamp}{suffix}"


def apply_audio_only_defaults(args: argparse.Namespace) -> None:
    """Completa el video y activa solo-audio sin truncar cuando se recibe solo un SRT."""
    if args.srt_file and not args.video:
        args.video = str(Path(args.srt_file).with_suffix('.mp4'))
        args.solo_audio = True
        args.no_truncate = True


def is_rate_optimization_enabled(args: argparse.Namespace) -> bool:
    """La búsqueda de rate óptimo es explícita y no altera los demás modos."""
    return bool(
        getattr(args, 'optimize_rate', False)
        and not getattr(args, 'fix_rate', None)
        and getattr(args, 'fix_rate_not_truncate', None) is None
        and not getattr(args, 'no_truncate', False)
    )


def resolve_video_path(video: str, allow_missing: bool = False) -> Optional[Path]:
    """Encuentra el video o conserva su ruta como referencia en modo solo-audio."""
    for ext in ['.mkv', '.mp4', '']:
        candidate = Path(video).with_suffix(ext) if ext else Path(video)
        if candidate.exists():
            return candidate

    return Path(video) if allow_missing else None


def calculate_no_truncate_lag(current_lag: float, audio_duration: float,
                               available_time: float) -> float:
    """Devuelve el desfase acumulado después de ubicar un audio completo."""
    return max(0.0, current_lag + audio_duration - available_time)


def get_no_truncate_rate_list(current_rate: int, is_behind: bool,
                               fixed_rate: Optional[int]) -> List[int]:
    """Prioriza el rate máximo mientras haya desfase, sin repetir valores."""
    candidates = [MAX_TTS_RATE] if is_behind else (
        [fixed_rate, MAX_TTS_RATE] if fixed_rate and fixed_rate <= MAX_TTS_RATE else
        [current_rate, 200, 220, MAX_TTS_RATE]
    )
    return list(dict.fromkeys(candidates))


def calculate_required_video_padding(video_duration: float, audio_duration: float) -> float:
    """Calcula cuánto congelar el último frame para no cortar audio no-truncate."""
    return max(0.0, audio_duration - video_duration)

LANGUAGE_NAMES = {
    'de': 'Deutsch', 'en': 'English', 'es': 'Español', 'fi': 'Suomi',
    'fr': 'Français', 'he': 'עברית', 'it': 'Italiano', 'ja': '日本語',
    'ko': '한국어', 'nl': 'Nederlands', 'pt': 'Português', 'sv': 'Svenska',
    'zh': '中文',
}
EUROPEAN_LANGUAGE_CODES = ('de', 'en', 'es', 'fi', 'fr', 'it', 'nl', 'pt', 'sv')
ELEVENLABS_CONFIG_FILENAME = '.srt-essay-secrets.json'
_ELEVENLABS_CACHE_TTL_SECONDS = 60
_elevenlabs_voices_cache: tuple[float, List[dict]] | None = None
_elevenlabs_credits_cache: tuple[float, dict] | None = None


def get_elevenlabs_config() -> Optional[dict]:
    """Obtiene el secreto local o variable de entorno sin exponerlo al frontend."""
    api_key = os.getenv('ELEVENLABS_API_KEY', '').strip()
    model_id = os.getenv('ELEVENLABS_MODEL_ID', '').strip() or 'eleven_multilingual_v2'
    if not api_key:
        config_path = Path.cwd() / ELEVENLABS_CONFIG_FILENAME
        try:
            config = json.loads(config_path.read_text(encoding='utf-8'))
            elevenlabs = config.get('elevenlabs', {}) if isinstance(config, dict) else {}
            api_key = str(elevenlabs.get('api_key', '')).strip()
            model_id = str(elevenlabs.get('model_id', '')).strip() or model_id
        except (OSError, json.JSONDecodeError):
            pass
    return {'api_key': api_key, 'model_id': model_id} if api_key else None


def _elevenlabs_request(path: str, api_key: str, payload: Optional[dict] = None, timeout: int = 15) -> bytes:
    data = json.dumps(payload).encode('utf-8') if payload is not None else None
    request = Request(
        f'https://api.elevenlabs.io/v1/{path.lstrip("/")}', data=data,
        headers={'xi-api-key': api_key, 'Content-Type': 'application/json'}, method='POST' if data else 'GET',
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            return response.read()
    except HTTPError as exc:
        detail = exc.read().decode('utf-8', errors='replace')[:500]
        raise ValueError(f'ElevenLabs respondió HTTP {exc.code}: {detail}') from exc
    except URLError as exc:
        raise ValueError(f'No se pudo conectar con ElevenLabs: {exc.reason}') from exc


def get_elevenlabs_voices() -> List[dict]:
    global _elevenlabs_voices_cache
    if _elevenlabs_voices_cache and time.time() - _elevenlabs_voices_cache[0] < _ELEVENLABS_CACHE_TTL_SECONDS:
        return _elevenlabs_voices_cache[1]
    config = get_elevenlabs_config()
    if not config:
        return []
    try:
        payload = json.loads(_elevenlabs_request('voices', config['api_key']).decode('utf-8'))
    except (ValueError, json.JSONDecodeError):
        return []
    voices = payload.get('voices', []) if isinstance(payload, dict) else []
    result = []
    for item in voices:
        if not isinstance(item, dict) or not isinstance(item.get('voice_id'), str):
            continue
        labels = item.get('labels') or {}
        declared_language = str(labels.get('language', '')).lower().strip()
        languages = [declared_language] if declared_language in EUROPEAN_LANGUAGE_CODES else []
        result.append({
            'id': item['voice_id'], 'name': item.get('name') or item['voice_id'], 'labels': labels,
            'languages': languages, 'category': item.get('category') or '',
            'available_for_tiers': item.get('available_for_tiers') or [],
        })
    _elevenlabs_voices_cache = (time.time(), result)
    return result


def get_elevenlabs_credits() -> dict:
    """Obtiene créditos sin propagar errores de permisos al listado de TTS."""
    global _elevenlabs_credits_cache
    if _elevenlabs_credits_cache and time.time() - _elevenlabs_credits_cache[0] < _ELEVENLABS_CACHE_TTL_SECONDS:
        return _elevenlabs_credits_cache[1]
    config = get_elevenlabs_config()
    if not config:
        return {'available': False, 'error': 'ElevenLabs no está configurado.'}
    try:
        subscription = json.loads(_elevenlabs_request('user/subscription', config['api_key']).decode('utf-8'))
        used, limit = int(subscription.get('character_count', 0)), int(subscription.get('character_limit', 0))
        result = {'available': True, 'used': used, 'limit': limit, 'remaining': max(0, limit - used),
                  'tier': subscription.get('tier'), 'reset_unix': subscription.get('next_character_count_reset_unix')}
    except (ValueError, json.JSONDecodeError) as exc:
        result = {'available': False, 'error': str(exc)}
    _elevenlabs_credits_cache = (time.time(), result)
    return result


def get_say_voices() -> List[dict]:
    """Lee directamente las voces instaladas por macOS `say -v ?`."""
    if not shutil.which('say'):
        return []
    try:
        result = subprocess.run(['say', '-v', '?'], capture_output=True, text=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        return []
    voices = []
    for line in result.stdout.splitlines():
        match = re.match(r'^(.+?)\s+([a-z]{2,3}_[A-Z]{2,3})\s+#', line)
        if match:
            name, locale = match.groups()
            voices.append({'id': name, 'name': name, 'locale': locale, 'language': locale.split('_', 1)[0]})
    return voices


def get_available_tts() -> List[dict]:
    """Devuelve motores, idiomas y voces instalados que la API puede seleccionar."""
    engines = []
    say_voices = get_say_voices()
    if say_voices:
        languages = sorted({voice['language'] for voice in say_voices})
        engines.append({'id': 'say', 'label': 'macOS say', 'offline': True,
                        'languages': languages, 'voices': say_voices})
    if importlib.util.find_spec('edge_tts'):
        engines.append({'id': 'edge-tts', 'label': 'Microsoft Edge TTS', 'offline': False,
                        'languages': sorted({'es', 'en', 'de', 'fr', 'it', 'pt', 'ja', 'zh'})})
    if importlib.util.find_spec('pyttsx3'):
        engines.append({'id': 'sapi', 'label': 'SAPI / pyttsx3', 'offline': True,
                        'languages': sorted({'es', 'en', 'de', 'fr', 'it', 'pt'})})
    if importlib.util.find_spec('gtts'):
        engines.append({'id': 'gtts', 'label': 'Google TTS', 'offline': False,
                        'languages': sorted({'es', 'en', 'de', 'fr', 'it', 'pt', 'ja', 'zh'})})
    if shutil.which('espeak-ng'):
        engines.append({'id': 'espeak-ng', 'label': 'eSpeak NG', 'offline': True,
                        'languages': sorted({'es', 'en', 'de', 'fr', 'it', 'pt', 'ja', 'zh'})})
    config = get_elevenlabs_config()
    engines.append({
        'id': 'elevenlabs', 'label': 'ElevenLabs' if config else 'ElevenLabs · requiere API key',
        'offline': False, 'configured': bool(config), 'languages': list(EUROPEAN_LANGUAGE_CODES),
        'voices': get_elevenlabs_voices() if config else [], 'credits': get_elevenlabs_credits(),
    })
    return engines


def is_paid_tts_quota_error(detail: Optional[str]) -> bool:
    """Indica si el proveedor pago agotó cuota y conviene pasar a un motor gratuito."""
    message = (detail or '').lower()
    return any(marker in message for marker in ('quota_exceeded', 'quota exceeded', 'insufficient_credits', 'credit balance', 'credits remaining'))


class TTSEngine:
    """Maneja la generación de TTS"""

    def __init__(self, language: str = 'es', tts_method: Optional[str] = None,
                 tts_voice: Optional[str] = None):
        self.language = language  # Idioma del TTS (es, en, de, fr, etc.)
        self.requested_tts = tts_method
        self.requested_voice = tts_voice
        available_ids = {item['id'] for item in get_available_tts()}
        if tts_method and tts_method not in available_ids:
            raise ValueError(f"TTS no instalado o no soportado: {tts_method}")
        selected_methods = {'say': 'say', 'edge-tts': 'edge-tts', 'sapi': 'sapi',
                            'gtts': 'linux', 'espeak-ng': 'espeak-ng', 'elevenlabs': 'elevenlabs'}
        self.method = selected_methods.get(tts_method) if tts_method else self._detect_method()
        self.gtts_consecutive_failures = 0
        self.gtts_permanently_disabled = False
        self.using_fallback = False
        self.last_tts_used = None  # Rastrear el TTS realmente usado
        self.last_error = None
        self._configure_voice()  # Configurar voz según idioma

    def _configure_voice(self):
        """Configura la voz según el idioma y el sistema operativo"""
        # Mapeo de idiomas a voces según el sistema
        self.voice_config = {
            'say': {
                'es': 'Paulina',    # Español (España/México)
                'en': 'Samantha',   # Inglés (US)
                'de': 'Anna',       # Alemán
                'fr': 'Thomas',     # Francés
                'it': 'Alice',      # Italiano
                'pt': 'Luciana',    # Portugués
                'ja': 'Kyoko',      # Japonés
                'zh': 'Ting-Ting',  # Chino
            },
            'edge-tts': {
                'es': 'es-ES-ElviraNeural',
                'en': 'en-US-JennyNeural',
                'de': 'de-DE-KatjaNeural',
                'fr': 'fr-FR-DeniseNeural',
                'it': 'it-IT-ElsaNeural',
                'pt': 'pt-BR-FranciscaNeural',
                'ja': 'ja-JP-NanamiNeural',
                'zh': 'zh-CN-XiaoxiaoNeural',
            },
            'espeak': {
                'es': 'es',
                'en': 'en',
                'de': 'de',
                'fr': 'fr',
                'it': 'it',
                'pt': 'pt',
                'ja': 'ja',
                'zh': 'zh',
            }
        }

        # macOS expone sus voces instaladas, que pueden abarcar más idiomas que el mapa base.
        supported_languages = set(self.voice_config['espeak'])
        if self.method == 'say':
            supported_languages.update(voice['language'] for voice in get_say_voices())
        elif self.method == 'elevenlabs':
            supported_languages.update(EUROPEAN_LANGUAGE_CODES)
        if self.language not in supported_languages:
            print(f"{Colors.YELLOW}⚠️  Idioma '{self.language}' no soportado, usando 'es' por defecto{Colors.NC}")
            self.language = 'es'

        # Mostrar configuración de voz según el método
        if self.method == "say":
            installed_voices = get_say_voices()
            preferred = self.voice_config['say'].get(self.language)
            selected_voice = next((item for item in installed_voices if item['id'] == self.requested_voice), None)
            if self.requested_voice and not selected_voice:
                raise ValueError(f"Voz no instalada: {self.requested_voice}")
            if selected_voice and selected_voice['language'] != self.language:
                raise ValueError(f"La voz '{self.requested_voice}' no corresponde al idioma '{self.language}'")
            voice = selected_voice['name'] if selected_voice else None
            voice = voice or next((item['name'] for item in installed_voices if item['name'] == preferred), None)
            voice = voice or next((item['name'] for item in installed_voices if item['language'] == self.language), 'Paulina')
            self.say_voice = voice
            print(f"{Colors.CYAN}  🎙️  Voz seleccionada: {voice} ({self.language}){Colors.NC}")
        elif self.method == 'elevenlabs':
            voices = get_elevenlabs_voices()
            selected = next((voice for voice in voices if voice['id'] == self.requested_voice), None) if self.requested_voice else None
            if self.requested_voice and not selected:
                raise ValueError(f"Voz de ElevenLabs no disponible: {self.requested_voice}")
            selected = selected or (voices[0] if voices else None)
            if not selected:
                raise ValueError('ElevenLabs no devolvió voces. Revisá la API key y la conexión.')
            self.elevenlabs_voice = selected['id']
            print(f"{Colors.CYAN}  🎙️  Voz seleccionada: {selected['name']} (ElevenLabs){Colors.NC}")
        elif self.requested_voice:
            raise ValueError(f"El TTS '{self.requested_tts or self.method}' no expone voces seleccionables")
        elif self.method in {"windows", "edge-tts"}:
            voice = self.voice_config['edge-tts'].get(self.language, 'es-ES-ElviraNeural')
            print(f"{Colors.CYAN}  🎙️  Voz seleccionada: {voice} ({self.language}){Colors.NC}")
        elif self.method in {"linux", "gtts", "espeak-ng", "sapi"}:
            print(f"{Colors.CYAN}  🎙️  Idioma de TTS: {self.language}{Colors.NC}")

    def get_tts_name(self) -> str:
        """Devuelve el nombre del TTS usado para el nombre del archivo"""
        if self.last_tts_used:
            return self.last_tts_used
        # Fallback si no se ha usado ningún TTS aún
        if self.method == "say":
            return "say"
        elif self.method == "edge-tts":
            return "edge-tts"
        elif self.method == "sapi":
            return "sapi"
        elif self.method == "espeak-ng":
            return "espeak-ng"
        elif self.method == "elevenlabs":
            return "elevenlabs"
        elif self.method == "windows":
            return "edge-tts"
        elif self.method == "linux":
            return "gtts" if not self.gtts_permanently_disabled else "espeak-ng"
        return "tts"

    def _detect_method(self) -> str:
        """Detecta el método TTS disponible"""
        system = platform.system()

        if system == "Darwin":
            if shutil.which("say"):
                print(f"{Colors.GREEN}✓ Sistema: macOS - Usando comando 'say'{Colors.NC}")
                return "say"

        elif system == "Windows":
            print(f"{Colors.GREEN}✓ Sistema: Windows - Usando edge-tts (con fallback a SAPI){Colors.NC}")
            return "windows"

        # Linux u otros sistemas
        try:
            import gtts
            from pydub import AudioSegment
            print(f"{Colors.GREEN}✓ Sistema: Linux - Usando gTTS (con fallback a espeak-ng){Colors.NC}")
            return "linux"
        except ImportError:
            print(f"{Colors.RED}✗ Error: Faltan dependencias de Python{Colors.NC}")
            print(f"{Colors.YELLOW}Instala con: sudo apt install python3-gtts python3-pydub{Colors.NC}")
            sys.exit(1)

    def _generate_with_espeak(self, text: str, rate: int, output_file: Path) -> bool:
        """Genera audio usando espeak-ng (offline fallback para Linux)"""
        try:
            # Verificar que espeak-ng está instalado
            if not shutil.which("espeak-ng"):
                return False

            # Obtener el código de voz configurado para el idioma
            voice_code = self.voice_config['espeak'].get(self.language, 'es')

            cmd = [
                'espeak-ng',
                '-v', voice_code,        # Voz según idioma configurado
                '-s', str(rate),         # Velocidad en WPM
                '-w', str(output_file),  # Archivo de salida WAV
                text                     # Texto a convertir
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )

            if output_file.exists():
                self.last_tts_used = "espeak-ng"
                return True
            return False

        except subprocess.CalledProcessError as e:
            return False
        except Exception as e:
            return False

    def _generate_with_edge_tts(self, text: str, rate: int, output_file: Path) -> bool:
        """Genera audio usando edge-tts (Windows online)"""
        try:
            # Calcular rate para edge-tts (en porcentaje)
            # rate 180 = normal (0%), 200 = +11%, 220 = +22%, 240 = +33%
            rate_percent = int(((rate - 180) / 180) * 100)
            rate_arg = f"+{rate_percent}%" if rate_percent >= 0 else f"{rate_percent}%"

            # Generar MP3 primero con edge-tts usando voz configurada
            voice = self.voice_config['edge-tts'].get(self.language, 'es-ES-ElviraNeural')
            temp_mp3 = output_file.with_suffix('.mp3')

            # DEBUG: Mostrar voz usada (solo una vez por sesión)
            if not hasattr(self, '_voice_logged'):
                print(f"{Colors.CYAN}  🔍 DEBUG edge-tts: Usando voz '{voice}' (idioma: {self.language}){Colors.NC}")
                self._voice_logged = True

            cmd = [
                sys.executable, '-m', 'edge_tts',
                '--text', text,
                '--voice', voice,
                '--rate', rate_arg,
                '--write-media', str(temp_mp3)
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=30
            )

            # Convertir MP3 a WAV con ffmpeg
            if temp_mp3.exists():
                subprocess.run(
                    ['ffmpeg', '-i', str(temp_mp3), str(output_file), '-y'],
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                temp_mp3.unlink()
                if output_file.exists():
                    self.last_tts_used = "edge-tts"
                    return True

            return False

        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as e:
            return False
        except Exception as e:
            return False

    def _generate_with_sapi(self, text: str, rate: int, output_file: Path) -> bool:
        """Genera audio usando SAPI de Windows (offline fallback para Windows)"""
        try:
            import pyttsx3

            engine = pyttsx3.init()

            # Buscar voz en el idioma especificado
            language_names = {
                'es': ['spanish', 'español', 'es'],
                'en': ['english', 'en'],
                'de': ['german', 'deutsch', 'de'],
                'fr': ['french', 'français', 'fr'],
                'it': ['italian', 'italiano', 'it'],
                'pt': ['portuguese', 'português', 'pt'],
            }

            search_terms = language_names.get(self.language, ['spanish', 'es'])
            voices = engine.getProperty('voices')
            voice_found = False

            for voice in voices:
                voice_lower = voice.name.lower()
                lang_lower = str(voice.languages).lower()
                if any(term in voice_lower or term in lang_lower for term in search_terms):
                    engine.setProperty('voice', voice.id)
                    voice_found = True
                    break

            if not voice_found and self.language != 'en':
                # Si no se encuentra voz en el idioma, intentar inglés como fallback
                print(f"{Colors.YELLOW}  ⚠️ No se encontró voz en '{self.language}', usando inglés{Colors.NC}")

            # Configurar velocidad (pyttsx3 usa WPM directamente)
            engine.setProperty('rate', rate)

            # Generar audio
            engine.save_to_file(text, str(output_file))
            engine.runAndWait()

            if output_file.exists():
                self.last_tts_used = "sapi"
                return True
            return False

        except ImportError:
            return False
        except Exception as e:
            return False

    def _generate_with_elevenlabs(self, text: str, rate: int, output_file: Path) -> bool:
        """Genera MP3 con ElevenLabs y lo normaliza a WAV para la unión local."""
        config = get_elevenlabs_config()
        if not config:
            return False
        try:
            speed = min(1.2, max(0.7, rate / 200))
            audio = _elevenlabs_request(
                f"text-to-speech/{self.elevenlabs_voice}?output_format=mp3_44100_128", config['api_key'],
                {'text': text, 'model_id': config['model_id'], 'voice_settings': {'speed': speed}},
                timeout=90,
            )
            mp3_file = output_file.with_suffix('.mp3')
            mp3_file.write_bytes(audio)
            subprocess.run(['ffmpeg', '-i', str(mp3_file), str(output_file), '-y'], check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            mp3_file.unlink(missing_ok=True)
            self.last_tts_used = 'elevenlabs'
            return output_file.exists()
        except (OSError, ValueError, subprocess.CalledProcessError) as exc:
            detail = str(exc)
            self.last_error = (
                'Esta voz de Voice Library requiere un plan pago de ElevenLabs para usarse por API.'
                if 'paid_plan_required' in detail else detail
            )
            return False

    def generate_audio(self, text: str, rate: int, output_file: Path) -> bool:
        """Genera audio TTS con el rate especificado"""
        try:
            if self.method == "espeak-ng":
                return self._generate_with_espeak(text, rate, output_file)

            if self.method == "edge-tts":
                return self._generate_with_edge_tts(text, rate, output_file)

            if self.method == "sapi":
                return self._generate_with_sapi(text, rate, output_file)

            if self.method == "elevenlabs":
                return self._generate_with_elevenlabs(text, rate, output_file)

            if self.method == "say":
                # macOS say command con voz configurada según idioma
                voice = getattr(self, 'say_voice', self.voice_config['say'].get(self.language, 'Paulina'))
                aiff_file = output_file.with_suffix('.aiff')
                subprocess.run(
                    ["say", "-v", voice, "-r", str(rate), text, "-o", str(aiff_file)],
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
                self.last_tts_used = "say"
                return True

            elif self.method == "windows":
                # Windows: Intentar edge-tts primero, luego SAPI
                import time

                # Intentar con edge-tts (online, mejor calidad)
                if self._generate_with_edge_tts(text, rate, output_file):
                    return True

                # Si edge-tts falla, usar SAPI (offline fallback)
                print(f"{Colors.CYAN}  🔄 edge-tts no disponible, usando SAPI (TTS offline)...{Colors.NC}")
                if self._generate_with_sapi(text, rate, output_file):
                    print(f"{Colors.GREEN}  ✓ Audio generado con SAPI{Colors.NC}")
                    return True
                else:
                    print(f"{Colors.RED}  ✗ SAPI no está disponible{Colors.NC}")
                    print(f"{Colors.YELLOW}  Instala con: pip install pyttsx3{Colors.NC}")
                    return False

            elif self.method == "linux":
                # Linux: gTTS integrado con reintentos y fallback a espeak-ng
                from gtts import gTTS
                from pydub import AudioSegment
                from pydub.effects import speedup
                import time

                # Si gTTS fue deshabilitado permanentemente, usar espeak-ng directamente
                if self.gtts_permanently_disabled:
                    if not self.using_fallback:
                        print(f"{Colors.CYAN}  ℹ Usando espeak-ng para el resto de la sesión{Colors.NC}")
                        self.using_fallback = True
                    if self._generate_with_espeak(text, rate, output_file):
                        return True
                    else:
                        print(f"{Colors.RED}  ✗ espeak-ng no está disponible{Colors.NC}")
                        return False

                # Reintentar hasta 3 veces con backoff exponencial
                max_retries = 3
                retry_delay = 1.0

                for attempt in range(max_retries):
                    try:
                        # Generar audio con gTTS
                        tts = gTTS(text=text, lang=self.language, slow=False)
                        temp_mp3 = output_file.with_suffix('.mp3')
                        tts.save(str(temp_mp3))

                        # Cargar audio con pydub
                        audio = AudioSegment.from_mp3(str(temp_mp3))

                        # Ajustar velocidad según rate
                        # gTTS genera a ~150 WPM, ajustamos según el rate deseado
                        speed_factor = rate / 150.0

                        if speed_factor != 1.0:
                            # Ajustar velocidad sin cambiar el pitch
                            if speed_factor > 1.0:
                                audio = speedup(audio, playback_speed=speed_factor)
                            else:
                                # Para velocidades más lentas, usar frame_rate
                                audio = audio._spawn(audio.raw_data, overrides={
                                    "frame_rate": int(audio.frame_rate * speed_factor)
                                })
                                audio = audio.set_frame_rate(44100)

                        # Exportar a WAV
                        audio.export(str(output_file), format='wav')

                        # Limpiar archivo temporal
                        if temp_mp3.exists():
                            temp_mp3.unlink()

                        # Éxito: resetear contador de fallos
                        self.gtts_consecutive_failures = 0
                        if output_file.exists():
                            self.last_tts_used = "gtts"
                            return True
                        return False

                    except Exception as e:
                        error_msg = str(e)

                        # Incrementar contador de fallos
                        self.gtts_consecutive_failures += 1

                        # Detectar errores que requieren cambio permanente a espeak-ng
                        is_rate_limit = "429" in error_msg or "Too Many Requests" in error_msg
                        is_persistent_error = self.gtts_consecutive_failures >= 3

                        if is_rate_limit:
                            print(f"{Colors.RED}  ✗ Error 429: Google TTS bloqueó las peticiones (demasiadas solicitudes){Colors.NC}")
                            print(f"{Colors.YELLOW}  🔄 Cambiando permanentemente a espeak-ng para esta sesión{Colors.NC}")
                            self.gtts_permanently_disabled = True
                            self.using_fallback = True

                            if self._generate_with_espeak(text, rate, output_file):
                                print(f"{Colors.GREEN}  ✓ Audio generado con espeak-ng{Colors.NC}")
                                return True
                            else:
                                print(f"{Colors.RED}  ✗ espeak-ng no está disponible{Colors.NC}")
                                print(f"{Colors.YELLOW}  Instala con: sudo apt-get install espeak-ng{Colors.NC}")
                                return False

                        # Detectar tipo de error
                        if "Failed to connect" in error_msg or "Connection" in error_msg:
                            if attempt < max_retries - 1:
                                print(f"{Colors.YELLOW}  ⚠ Error de conexión (intento {attempt + 1}/{max_retries}). Reintentando en {retry_delay:.1f}s...{Colors.NC}")
                                time.sleep(retry_delay)
                                retry_delay *= 2  # Backoff exponencial
                                continue
                            else:
                                if is_persistent_error:
                                    print(f"{Colors.RED}  ✗ gTTS falló 3 veces consecutivas{Colors.NC}")
                                    print(f"{Colors.YELLOW}  🔄 Cambiando permanentemente a espeak-ng para esta sesión{Colors.NC}")
                                    self.gtts_permanently_disabled = True
                                    self.using_fallback = True
                                else:
                                    print(f"{Colors.RED}  ✗ gTTS falló después de {max_retries} intentos{Colors.NC}")
                                    print(f"{Colors.CYAN}  🔄 Intentando con espeak-ng (TTS offline)...{Colors.NC}")

                                # Intentar con espeak-ng como fallback
                                if self._generate_with_espeak(text, rate, output_file):
                                    print(f"{Colors.GREEN}  ✓ Audio generado con espeak-ng{Colors.NC}")
                                    return True
                                else:
                                    print(f"{Colors.RED}  ✗ espeak-ng no está disponible{Colors.NC}")
                                    print(f"{Colors.YELLOW}  Instala con: sudo apt-get install espeak-ng{Colors.NC}")
                                    return False
                        else:
                            # Otro tipo de error
                            print(f"{Colors.RED}  ✗ Error generando TTS: {error_msg}{Colors.NC}")
                            if attempt < max_retries - 1:
                                time.sleep(retry_delay)
                                retry_delay *= 2
                                continue
                            else:
                                if is_persistent_error:
                                    print(f"{Colors.YELLOW}  🔄 Cambiando permanentemente a espeak-ng para esta sesión{Colors.NC}")
                                    self.gtts_permanently_disabled = True
                                    self.using_fallback = True
                                else:
                                    print(f"{Colors.CYAN}  🔄 Intentando con espeak-ng (TTS offline)...{Colors.NC}")

                                # Intentar con espeak-ng como fallback
                                if self._generate_with_espeak(text, rate, output_file):
                                    print(f"{Colors.GREEN}  ✓ Audio generado con espeak-ng{Colors.NC}")
                                    return True
                                else:
                                    return False

                # Si llegamos aquí, intentar con espeak-ng
                print(f"{Colors.CYAN}  🔄 Intentando con espeak-ng (TTS offline)...{Colors.NC}")
                if self._generate_with_espeak(text, rate, output_file):
                    print(f"{Colors.GREEN}  ✓ Audio generado con espeak-ng{Colors.NC}")
                    return True
                return False

        except Exception as e:
            print(f"{Colors.RED}Error: TTS falló para rate {rate}: {e}{Colors.NC}", file=sys.stderr)
            return False

        return False

def get_free_tts_fallback(language: str, excluded: Optional[str] = None) -> Optional[TTSEngine]:
    """Devuelve el primer TTS gratuito/local disponible para continuar una generación."""
    available = {item['id'] for item in get_available_tts()}
    system = platform.system()
    preferred = (
        ('say', 'sapi', 'espeak-ng', 'edge-tts', 'gtts') if system == 'Darwin' else
        ('sapi', 'edge-tts', 'espeak-ng', 'gtts') if system == 'Windows' else
        ('espeak-ng', 'edge-tts', 'gtts')
    )
    for candidate in preferred:
        if candidate != excluded and candidate in available:
            return TTSEngine(language=language, tts_method=candidate)
    return None


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


def create_no_truncate_test_srt(srt_path: Path, subtitles: List[Subtitle],
                                audio_segments: Dict[int, AudioSegment],
                                duration_getter=get_audio_duration) -> Path:
    """Genera subtítulos con la línea temporal real del audio sin truncar."""
    output_path = srt_path.with_name(f"{srt_path.stem}-to-test.srt")

    with open(output_path, 'w', encoding='utf-8') as output:
        for subtitle in subtitles:
            segment = audio_segments.get(subtitle.consecutive_id)
            if not segment:
                continue

            offset = segment.timing_offset
            start = subtitle.start_seconds + offset
            duration = max(0.001, duration_getter(segment.audio_file))
            end = start + duration

            output.write(f"{subtitle.consecutive_id}\n")
            output.write(
                f"{SRTParser.seconds_to_srt_time(start)} --> "
                f"{SRTParser.seconds_to_srt_time(end)}\n"
            )
            prefix = f"({offset:.3f}s) " if offset > 0.0005 else ""
            output.write(f"{prefix}{subtitle.text}\n\n")

    return output_path


def create_fixed_rate_not_truncate_srt(srt_path: Path, subtitles: List[Subtitle],
                                        audio_segments: Dict[int, AudioSegment],
                                        rate: int, pause_ms: int = 1000,
                                        duration_getter=get_audio_duration) -> Path:
    """Genera un SRT secuencial que ignora por completo el timeline de entrada."""
    output_path = srt_path.with_name(f"{srt_path.stem}-fixed-rate-{rate}.srt")
    cursor = 0.0
    with open(output_path, 'w', encoding='utf-8') as output:
        for subtitle in subtitles:
            segment = audio_segments.get(subtitle.consecutive_id)
            if not segment:
                continue
            end = cursor + max(0.001, duration_getter(segment.audio_file))
            output.write(f"{subtitle.consecutive_id}\n")
            output.write(f"{SRTParser.seconds_to_srt_time(cursor)} --> {SRTParser.seconds_to_srt_time(end)}\n")
            output.write(f"{subtitle.text}\n\n")
            cursor = end + (pause_ms / 1000.0 if subtitle != subtitles[-1] else 0.0)
    return output_path

def create_silence(duration: float, output: Path, error_logger: Optional[ErrorLogger] = None):
    """Crea un archivo de audio con silencio"""
    try:
        subprocess.run(
            ["ffmpeg", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
             "-t", str(duration), "-q:a", "9", "-acodec", "pcm_s16le",
             str(output), "-y"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
    except subprocess.CalledProcessError as e:
        error_msg = f"Error creando silencio de {duration}s"
        if error_logger:
            error_logger.add_error("Crear silencio", ' '.join(e.cmd), e.stderr or error_msg)
        print(f"{Colors.RED}{error_msg}{Colors.NC}")
        raise

def truncate_audio(input_file: Path, output_file: Path, duration: float, error_logger: Optional[ErrorLogger] = None) -> bool:
    """Trunca audio a la duración especificada"""
    try:
        result = subprocess.run(
            ["ffmpeg", "-i", str(input_file), "-t", str(duration),
             "-c:a", "copy", str(output_file), "-y"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
        return output_file.exists() and output_file.stat().st_size > 0
    except subprocess.CalledProcessError as e:
        if error_logger:
            error_logger.add_error("Truncar audio", ' '.join(e.cmd), e.stderr or "Error truncando audio")
        return False

def get_config_file() -> Path:
    """Obtiene la ruta al archivo de configuración"""
    home = Path.home()
    return home / ".video_tts_config.json"

def load_last_config() -> dict:
    """Carga la última configuración usada"""
    config_file = get_config_file()
    if config_file.exists():
        try:
            import json
            with open(config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_config(srt_file: str, video: str, test: Optional[int], solo_audio: bool,
                no_freeze: bool, remove_breaks: bool):
    """Guarda la configuración actual para futuras ejecuciones"""
    config_file = get_config_file()
    try:
        import json
        config = {
            'srt_file': srt_file,
            'video': video,
            'test': test,
            'solo_audio': solo_audio,
            'no_freeze': no_freeze,
            'remove_breaks': remove_breaks
        }
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2)
    except Exception:
        pass  # No es crítico si falla guardar

def suggest_video_from_srt(srt_file: str) -> Optional[str]:
    """Sugiere un archivo de video basado en el nombre del SRT"""
    if not srt_file:
        return None

    srt_path = Path(srt_file)
    base_name = srt_path.stem

    # Buscar video con el mismo nombre base
    for ext in ['.mp4', '.mkv', '.avi', '.mov', '.webm']:
        video_path = srt_path.parent / f"{base_name}{ext}"
        if video_path.exists():
            return str(video_path)

    # Si no existe, sugerir el nombre con .mp4
    return str(srt_path.parent / f"{base_name}.mp4")

def show_usage_and_prompt():
    """Muestra ejemplos de uso y ofrece modo interactivo"""
    print(f"{Colors.CYAN}{'═' * 60}{Colors.NC}")
    print(f"{Colors.CYAN}Video-Audio-TTS Synchronizer{Colors.NC}")
    print(f"{Colors.CYAN}{'═' * 60}{Colors.NC}")
    print()
    print(f"{Colors.YELLOW}USO:{Colors.NC}")
    print(f"  python3 create_video_tts_from_srt.py <archivo.srt> [video.mp4] [opciones]")
    print()
    print(f"{Colors.YELLOW}EJEMPLOS:{Colors.NC}")
    print(f"  {Colors.GREEN}# Procesar video completo{Colors.NC}")
    print(f"  python3 create_video_tts_from_srt.py mi_video.srt mi_video.mp4")
    print()
    print(f"  {Colors.GREEN}# Modo test (solo 50 subtítulos){Colors.NC}")
    print(f"  python3 create_video_tts_from_srt.py mi_video.srt mi_video.mp4 --test 50")
    print()
    print(f"  {Colors.GREEN}# Solo generar audio, sin video{Colors.NC}")
    print(f"  python3 create_video_tts_from_srt.py mi_video.srt mi_video.mp4 --solo-audio")
    print(f"  # Atajo equivalente: python3 create_video_tts_from_srt.py mi_video.srt")
    print()
    print(f"  {Colors.GREEN}# No-truncate: conserva el texto y recupera desfase a {MAX_TTS_RATE} wpm{Colors.NC}")
    print(f"  python3 create_video_tts_from_srt.py mi_video.srt mi_video.mp4 --no-truncate")
    print()
    print(f"  {Colors.GREEN}# Eliminar pausas largas del video{Colors.NC}")
    print(f"  python3 create_video_tts_from_srt.py mi_video.srt mi_video.mp4 --remove-breaks")
    print()
    print(f"{Colors.CYAN}{'─' * 60}{Colors.NC}")

    # Preguntar si desea modo interactivo
    try:
        response = input(f"\n¿Desea usar el {Colors.GREEN}modo interactivo{Colors.NC}? (s/N): ").strip().lower()
        if response in ['s', 'si', 'sí', 'y', 'yes']:
            return interactive_prompt()
    except (KeyboardInterrupt, EOFError):
        print(f"\n{Colors.YELLOW}Operación cancelada{Colors.NC}")
        sys.exit(0)

    return None

def interactive_prompt():
    """Modo interactivo para obtener parámetros del usuario"""
    print(f"\n{Colors.BLUE}{'═' * 60}{Colors.NC}")
    print(f"{Colors.BLUE}MODO INTERACTIVO{Colors.NC}")
    print(f"{Colors.BLUE}{'═' * 60}{Colors.NC}\n")

    # Cargar última configuración
    last_config = load_last_config()
    if last_config:
        print(f"{Colors.CYAN}💾 Última configuración cargada{Colors.NC}\n")

    try:
        # Archivo SRT
        print(f"{Colors.YELLOW}1. Archivo de subtítulos (SRT){Colors.NC}")
        print(f"   {Colors.CYAN}Ruta al archivo .srt con los subtítulos del video{Colors.NC}")

        default_srt = last_config.get('srt_file', '')
        if default_srt:
            prompt = f"   → Archivo SRT [{Colors.GREEN}{default_srt}{Colors.NC}]: "
        else:
            prompt = f"   → Archivo SRT: "

        srt_file = input(prompt).strip()
        if not srt_file:
            if default_srt:
                srt_file = default_srt
                print(f"   {Colors.CYAN}Usando: {srt_file}{Colors.NC}")
            else:
                print(f"{Colors.RED}Error: Debe especificar un archivo SRT{Colors.NC}")
                sys.exit(1)

        # Archivo de video (sugerir basado en SRT)
        print(f"\n{Colors.YELLOW}2. Archivo de video{Colors.NC}")
        print(f"   {Colors.CYAN}Ruta al archivo de video (.mp4, .mkv, etc.){Colors.NC}")

        # Si el SRT cambió, sugerir video con el mismo nombre
        suggested_video = suggest_video_from_srt(srt_file)
        default_video = suggested_video if suggested_video else last_config.get('video', '')

        if default_video:
            exists_marker = "✓" if Path(default_video).exists() else "?"
            prompt = f"   → Archivo video [{Colors.GREEN}{exists_marker} {default_video}{Colors.NC}]: "
        else:
            prompt = f"   → Archivo video: "

        video = input(prompt).strip()
        if not video:
            if default_video:
                video = default_video
                print(f"   {Colors.CYAN}Usando: {video}{Colors.NC}")
            else:
                print(f"{Colors.RED}Error: Debe especificar un archivo de video{Colors.NC}")
                sys.exit(1)

        # Modo test
        print(f"\n{Colors.YELLOW}3. Modo test (opcional){Colors.NC}")
        print(f"   {Colors.CYAN}Procesar solo N subtítulos para pruebas rápidas{Colors.NC}")

        default_test = last_config.get('test')
        if default_test:
            test_prompt = f"   → ¿Activar modo test? [{Colors.GREEN}s, {default_test} subtítulos{Colors.NC}/N]: "
        else:
            test_prompt = f"   → ¿Activar modo test? (s/N): "

        test_input = input(test_prompt).strip().lower()
        test_value = None

        if test_input in ['s', 'si', 'sí', 'y', 'yes']:
            if default_test:
                num_prompt = f"   → ¿Cuántos subtítulos? [{Colors.GREEN}{default_test}{Colors.NC}]: "
            else:
                num_prompt = f"   → ¿Cuántos subtítulos? (default: 30): "
            test_num = input(num_prompt).strip()

            if not test_num and default_test:
                test_value = default_test
            else:
                test_value = int(test_num) if test_num else 30
        elif not test_input and default_test:
            # Si presiona Enter y había un default, usarlo
            test_value = default_test
            print(f"   {Colors.CYAN}Usando: modo test con {test_value} subtítulos{Colors.NC}")

        # Solo audio
        print(f"\n{Colors.YELLOW}4. Solo audio (opcional){Colors.NC}")
        print(f"   {Colors.CYAN}Generar únicamente el audio TTS, sin procesar video{Colors.NC}")

        default_solo = last_config.get('solo_audio', False)
        if default_solo:
            solo_prompt = f"   → ¿Solo generar audio? [{Colors.GREEN}S{Colors.NC}/n]: "
        else:
            solo_prompt = f"   → ¿Solo generar audio? (s/N): "

        solo_input = input(solo_prompt).strip().lower()
        if solo_input:
            solo_audio = solo_input in ['s', 'si', 'sí', 'y', 'yes']
        else:
            solo_audio = default_solo

        # No freeze
        print(f"\n{Colors.YELLOW}5. Manejo de audios largos{Colors.NC}")
        print(f"   {Colors.CYAN}Cuando el audio TTS es más largo que el subtítulo:{Colors.NC}")
        print(f"   {Colors.GREEN}  - Freeze (default): Congela el último frame del video{Colors.NC}")
        print(f"   {Colors.YELLOW}  - Truncar: Corta el audio al tiempo disponible{Colors.NC}")

        default_nofreeze = last_config.get('no_freeze', False)
        if default_nofreeze:
            freeze_prompt = f"   → ¿Truncar audios largos? [{Colors.GREEN}S{Colors.NC}/n]: "
        else:
            freeze_prompt = f"   → ¿Truncar audios largos? (s/N): "

        freeze_input = input(freeze_prompt).strip().lower()
        if freeze_input:
            no_freeze = freeze_input in ['s', 'si', 'sí', 'y', 'yes']
        else:
            no_freeze = default_nofreeze

        # Eliminar pausas
        print(f"\n{Colors.YELLOW}6. Eliminar pausas largas (opcional){Colors.NC}")
        print(f"   {Colors.CYAN}Remover pausas mayores a 15 minutos del video final{Colors.NC}")

        default_breaks = last_config.get('remove_breaks', False)
        if default_breaks:
            breaks_prompt = f"   → ¿Eliminar pausas largas? [{Colors.GREEN}S{Colors.NC}/n]: "
        else:
            breaks_prompt = f"   → ¿Eliminar pausas largas? (s/N): "

        breaks_input = input(breaks_prompt).strip().lower()
        if breaks_input:
            remove_breaks = breaks_input in ['s', 'si', 'sí', 'y', 'yes']
        else:
            remove_breaks = default_breaks

        # Construir lista de argumentos
        args_list = [srt_file, video]
        if test_value:
            args_list.extend(['--test', str(test_value)])
        if solo_audio:
            args_list.append('--solo-audio')
        if no_freeze:
            args_list.append('--no-freeze')
        if remove_breaks:
            args_list.append('--remove-breaks')

        # Mostrar resumen
        print(f"\n{Colors.CYAN}{'═' * 60}{Colors.NC}")
        print(f"{Colors.CYAN}CONFIGURACIÓN:{Colors.NC}")
        print(f"  SRT: {srt_file}")
        print(f"  Video: {video}")
        if test_value:
            print(f"  Modo test: {test_value} subtítulos")
        if solo_audio:
            print(f"  Solo audio: Sí")
        if no_freeze:
            print(f"  Truncar audios: Sí")
        if remove_breaks:
            print(f"  Eliminar pausas: Sí")
        print(f"{Colors.CYAN}{'═' * 60}{Colors.NC}")

        confirm = input(f"\n¿Continuar con esta configuración? (S/n): ").strip().lower()
        if confirm in ['n', 'no']:
            print(f"{Colors.YELLOW}Operación cancelada{Colors.NC}")
            sys.exit(0)

        # Guardar configuración para futuras ejecuciones
        save_config(srt_file, video, test_value, solo_audio, no_freeze, remove_breaks)

        return args_list

    except (KeyboardInterrupt, EOFError):
        print(f"\n{Colors.YELLOW}Operación cancelada{Colors.NC}")
        sys.exit(0)
    except Exception as e:
        print(f"{Colors.RED}Error: {e}{Colors.NC}")
        sys.exit(1)

def save_checkpoint(temp_dir: Path, srt_file: str, video_file: str,
                   params: dict, last_subtitle_id: int, total_subtitles: int):
    """Guarda el estado actual del procesamiento para poder reanudar"""
    checkpoint_file = temp_dir / "checkpoint.json"

    checkpoint_data = {
        "srt_file": str(Path(srt_file).absolute()),
        "video_file": str(Path(video_file).absolute()),
        "parameters": params,
        "last_subtitle_id": last_subtitle_id,
        "total_subtitles": total_subtitles,
        "timestamp": datetime.datetime.now().isoformat(),
        "temp_dir": str(temp_dir.absolute())
    }

    with open(checkpoint_file, 'w', encoding='utf-8') as f:
        json.dump(checkpoint_data, f, indent=2, ensure_ascii=False)

def load_checkpoint(temp_dir: Path) -> Optional[dict]:
    """Carga el checkpoint de una carpeta temporal"""
    checkpoint_file = temp_dir / "checkpoint.json"

    if not checkpoint_file.exists():
        return None

    try:
        with open(checkpoint_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"{Colors.RED}Error cargando checkpoint: {e}{Colors.NC}")
        return None

def extract_youtube_id(youtube_input: str) -> Optional[str]:
    """Extrae el ID de YouTube de una URL o devuelve el ID si ya es un ID"""
    # Si es un ID directo (11 caracteres alfanuméricos)
    if len(youtube_input) == 11 and youtube_input.isalnum():
        return youtube_input

    # Patrones de URL de YouTube
    patterns = [
        r'(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})',
        r'youtube\.com/embed/([a-zA-Z0-9_-]{11})',
        r'youtube\.com/v/([a-zA-Z0-9_-]{11})'
    ]

    for pattern in patterns:
        match = re.search(pattern, youtube_input)
        if match:
            return match.group(1)

    return None

def list_youtube_subtitles(video_id: str) -> Optional[List[dict]]:
    """Lista todos los subtítulos disponibles para un video de YouTube"""
    try:
        # Usar yt-dlp para obtener información del video
        cmd = [
            sys.executable, '-m', 'yt_dlp',
            '--list-subs',
            '--skip-download',
            f'https://www.youtube.com/watch?v={video_id}'
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )

        # Parsear la salida para obtener los idiomas disponibles
        subtitles = []
        lines = result.stdout.split('\n')
        in_subs_section = False

        for line in lines:
            if 'Available subtitles' in line or 'Available automatic captions' in line:
                in_subs_section = True
                is_auto = 'automatic' in line
                continue

            if in_subs_section and line.strip():
                # Formato típico: "en    English"
                parts = line.split()
                if len(parts) >= 2 and parts[0].isalpha():
                    lang_code = parts[0]
                    lang_name = ' '.join(parts[1:])
                    subtitles.append({
                        'lang_code': lang_code,
                        'lang_name': lang_name,
                        'auto_generated': is_auto
                    })

        return subtitles if subtitles else None

    except subprocess.CalledProcessError as e:
        print(f"{Colors.RED}Error listando subtítulos: {e.stderr}{Colors.NC}")
        return None
    except FileNotFoundError:
        print(f"{Colors.RED}Error: yt-dlp no está instalado{Colors.NC}")
        print(f"{Colors.YELLOW}Instala con: pip install yt-dlp{Colors.NC}")
        return None

def download_youtube_video(video_id: str, output_dir: Path) -> Optional[Path]:
    """Descarga un video de YouTube en la mejor calidad disponible"""
    try:
        output_template = str(output_dir / f'{video_id}.%(ext)s')

        cmd = [
            sys.executable, '-m', 'yt_dlp',
            '-f', 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            '--merge-output-format', 'mp4',
            '-o', output_template,
            f'https://www.youtube.com/watch?v={video_id}'
        ]

        print(f"{Colors.CYAN}Descargando video de YouTube...{Colors.NC}")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )

        # Buscar el archivo descargado
        video_file = output_dir / f'{video_id}.mp4'
        if video_file.exists():
            print(f"{Colors.GREEN}✓ Video descargado: {video_file}{Colors.NC}")
            return video_file

        return None

    except subprocess.CalledProcessError as e:
        print(f"{Colors.RED}Error descargando video: {e.stderr}{Colors.NC}")
        return None

def download_youtube_subtitle(video_id: str, lang_code: str, output_dir: Path) -> Optional[Path]:
    """Descarga un subtítulo específico de YouTube"""
    try:
        output_template = str(output_dir / f'{video_id}_{lang_code}.%(ext)s')

        cmd = [
            sys.executable, '-m', 'yt_dlp',
            '--write-sub',
            '--write-auto-sub',
            '--sub-lang', lang_code,
            '--sub-format', 'srt',
            '--skip-download',
            '--convert-subs', 'srt',
            '-o', output_template,
            f'https://www.youtube.com/watch?v={video_id}'
        ]

        print(f"{Colors.CYAN}Descargando subtítulos en {lang_code}...{Colors.NC}")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )

        # Buscar el archivo de subtítulos descargado
        srt_file = output_dir / f'{video_id}_{lang_code}.{lang_code}.srt'
        if not srt_file.exists():
            srt_file = output_dir / f'{video_id}_{lang_code}.srt'

        if srt_file.exists():
            print(f"{Colors.GREEN}✓ Subtítulos descargados: {srt_file}{Colors.NC}")
            return srt_file

        return None

    except subprocess.CalledProcessError as e:
        print(f"{Colors.RED}Error descargando subtítulos: {e.stderr}{Colors.NC}")
        return None

def select_subtitle_interactive(subtitles: List[dict], target_lang: Optional[str] = None) -> Optional[str]:
    """Prompt interactivo para seleccionar un subtítulo"""
    if not subtitles:
        return None

    # Si se especificó un idioma objetivo, buscar coincidencia
    if target_lang:
        for sub in subtitles:
            if sub['lang_code'] == target_lang:
                print(f"{Colors.GREEN}Subtítulo en {target_lang} seleccionado automáticamente{Colors.NC}")
                return sub['lang_code']

    # Mostrar lista de subtítulos disponibles
    print(f"{Colors.YELLOW}{'═' * 60}{Colors.NC}")
    print(f"{Colors.YELLOW}SUBTÍTULOS DISPONIBLES{Colors.NC}")
    print(f"{Colors.YELLOW}{'═' * 60}{Colors.NC}")

    for idx, sub in enumerate(subtitles, 1):
        auto_tag = " (auto-generado)" if sub.get('auto_generated') else ""
        print(f"{Colors.CYAN}{idx:2d}.{Colors.NC} {sub['lang_code']:5s} - {sub['lang_name']}{auto_tag}")

    print(f"{Colors.YELLOW}{'═' * 60}{Colors.NC}")

    # Solicitar selección
    while True:
        try:
            choice = input(f"{Colors.GREEN}Selecciona el número del subtítulo a usar (o 'q' para salir): {Colors.NC}")

            if choice.lower() == 'q':
                return None

            choice_num = int(choice)
            if 1 <= choice_num <= len(subtitles):
                selected = subtitles[choice_num - 1]
                print(f"{Colors.GREEN}✓ Seleccionado: {selected['lang_code']} - {selected['lang_name']}{Colors.NC}")
                return selected['lang_code']
            else:
                print(f"{Colors.RED}Opción inválida. Elige entre 1 y {len(subtitles)}{Colors.NC}")

        except ValueError:
            print(f"{Colors.RED}Entrada inválida. Ingresa un número o 'q'{Colors.NC}")
        except KeyboardInterrupt:
            print(f"\n{Colors.YELLOW}Operación cancelada{Colors.NC}")
            return None

def process_youtube_video(youtube_input: str, target_lang: Optional[str] = None) -> Tuple[Optional[Path], Optional[Path]]:
    """
    Procesa un video de YouTube: descarga video y subtítulos
    Retorna (video_path, srt_path) o (None, None) si falla
    """
    # Extraer ID de YouTube
    video_id = extract_youtube_id(youtube_input)
    if not video_id:
        print(f"{Colors.RED}Error: No se pudo extraer el ID de YouTube de: {youtube_input}{Colors.NC}")
        return None, None

    print(f"{Colors.GREEN}ID de YouTube: {video_id}{Colors.NC}")

    # Crear carpeta temporal para descargas
    download_dir = Path.cwd() / f"youtube_{video_id}"
    download_dir.mkdir(exist_ok=True)

    # Listar subtítulos disponibles
    print(f"{Colors.CYAN}Obteniendo subtítulos disponibles...{Colors.NC}")
    subtitles = list_youtube_subtitles(video_id)

    if not subtitles:
        print(f"{Colors.RED}No se encontraron subtítulos para este video{Colors.NC}")
        return None, None

    # Seleccionar subtítulo
    selected_lang = select_subtitle_interactive(subtitles, target_lang)
    if not selected_lang:
        print(f"{Colors.YELLOW}No se seleccionó ningún subtítulo. Abortando.{Colors.NC}")
        return None, None

    # Descargar video
    video_path = download_youtube_video(video_id, download_dir)
    if not video_path:
        print(f"{Colors.RED}Error descargando video{Colors.NC}")
        return None, None

    # Descargar subtítulos
    srt_path = download_youtube_subtitle(video_id, selected_lang, download_dir)
    if not srt_path:
        print(f"{Colors.RED}Error descargando subtítulos{Colors.NC}")
        return None, None

    print(f"{Colors.GREEN}{'═' * 60}{Colors.NC}")
    print(f"{Colors.GREEN}✓ Descarga completada{Colors.NC}")
    print(f"{Colors.GREEN}  Video: {video_path}{Colors.NC}")
    print(f"{Colors.GREEN}  Subtítulos: {srt_path}{Colors.NC}")
    print(f"{Colors.GREEN}{'═' * 60}{Colors.NC}")

    return video_path, srt_path

API_RATE_CANDIDATES = (180, 200, 220, 240)


def _concat_wav_batch(parts: List[Path], output: Path) -> None:
    """Une un lote de WAVs con el demuxer concat de ffmpeg."""
    manifest = output.with_suffix('.txt')
    entries = ("file '" + str(part.resolve()).replace("'", "'\\\\''") + "'\n" for part in parts)
    manifest.write_text(
        ''.join(entries),
        encoding='utf-8',
    )
    try:
        subprocess.run(
            ['ffmpeg', '-f', 'concat', '-safe', '0', '-i', str(manifest),
             '-c:a', 'pcm_s16le', str(output), '-y'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True,
        )
    finally:
        manifest.unlink(missing_ok=True)


def _concat_wav_files(fragment_parts: List[List[Path]], output: Path, batch_size: int = 50,
                      progress: Optional[Callable[[str], None]] = None) -> None:
    """Concatena fragmentos por lotes para informar avance sin concatenación O(n²)."""
    if not fragment_parts:
        raise ValueError('No hay texto para sintetizar')
    if batch_size < 1:
        raise ValueError('El tamaño de lote debe ser mayor que cero')
    report = progress or (lambda _message: None)
    batches = [fragment_parts[index:index + batch_size] for index in range(0, len(fragment_parts), batch_size)]
    batch_outputs = []
    for index, batch in enumerate(batches, 1):
        first = (index - 1) * batch_size + 1
        last = first + len(batch) - 1
        report(f"TTS: uniendo lote {index}/{len(batches)} (fragmentos {first}-{last}).")
        batch_output = output.parent / f'batch-{index:04d}.wav'
        _concat_wav_batch([part for fragment in batch for part in fragment], batch_output)
        batch_outputs.append(batch_output)
        report(f"TTS: lote {index}/{len(batches)} unido.")
    if len(batch_outputs) == 1:
        shutil.copy(batch_outputs[0], output)
    else:
        report(f"TTS: uniendo {len(batch_outputs)} lotes para crear la pista final.")
        _concat_wav_batch(batch_outputs, output)
    for temporary in batch_outputs:
        temporary.unlink(missing_ok=True)


def _api_text_lines(payload: dict, directory: Path) -> Tuple[List[str], str]:
    """Acepta texto, SRT textual o un SRT base64 para la API local."""
    srt_content = payload.get('srt_text') or payload.get('srt')
    srt_file = payload.get('srt_file')
    if srt_file:
        srt_content = base64.b64decode(srt_file['data']).decode('utf-8-sig')
    if srt_content:
        srt_path = directory / 'request.srt'
        srt_path.write_text(srt_content, encoding='utf-8')
        return [subtitle.text for subtitle in SRTParser.parse_file(srt_path)], 'srt'
    text = str(payload.get('text', '')).strip()
    if not text:
        raise ValueError('Enviá text, srt_text/srt o srt_file')
    return [line.strip() for line in text.splitlines() if line.strip()], 'text'


def generate_api_audio(payload: dict, directory: Path) -> Tuple[Path, dict]:
    """Genera una respuesta de audio autocontenida para la API HTTP local."""
    report_progress = payload.get('_progress')
    if not callable(report_progress):
        report_progress = lambda _message: None
    lines, source_type = _api_text_lines(payload, directory)
    max_fragments = payload.get('max_fragments')
    if max_fragments not in (None, ''):
        max_fragments = int(max_fragments)
        if max_fragments < 1:
            raise ValueError('max_fragments debe ser mayor que cero')
        if max_fragments < len(lines):
            report_progress(f"TTS: modo test activo; se procesarán los primeros {max_fragments}/{len(lines)} fragmentos.")
            lines = lines[:max_fragments]
    language = str(payload.get('lang') or payload.get('language') or 'es')
    pause_ms = max(0, int(payload.get('pause_ms', 0) or 0))
    target_duration = payload.get('duration')
    target_duration = float(target_duration) if target_duration not in (None, '') else None
    if target_duration is not None and target_duration <= 0:
        raise ValueError('duration debe ser mayor que cero')
    fixed_rate = bool(payload.get('fixed_rate'))
    requested_rate = int(payload.get('rate', 180) or 180)
    rates = [requested_rate] if fixed_rate or target_duration is None else list(API_RATE_CANDIDATES)
    requested_tts = payload.get('tts') or payload.get('tts_method')
    requested_voice = payload.get('voice') or payload.get('tts_voice')
    batch_size = int(payload.get('merge_batch_size', 50) or 50)
    if batch_size < 1:
        raise ValueError('merge_batch_size debe ser mayor que cero')
    report_progress(f"TTS: preparando {len(lines)} fragmentos con {requested_tts or 'motor automático'}.")
    engine = TTSEngine(language=language, tts_method=requested_tts, tts_voice=requested_voice)
    engines_used: List[str] = []
    fallback_reason: Optional[str] = None
    candidates = []
    for rate in dict.fromkeys(rates):
        rate_dir = directory / f'rate_{rate}'
        rate_dir.mkdir(exist_ok=True)
        fragment_parts = []
        for index, line in enumerate(lines):
            audio_file = rate_dir / f'{index}.wav'
            if audio_file.is_file() and get_audio_duration(audio_file) > 0:
                report_progress(f"TTS: reutilizando fragmento {index + 1}/{len(lines)} ya generado.")
                engines_used.append('caché')
            else:
                audio_file.unlink(missing_ok=True)
                report_progress(f"TTS: generando fragmento {index + 1}/{len(lines)} a {rate} wpm.")
                generated = engine.generate_audio(re.sub(r'<[^>]*>', '', line), rate, audio_file)
                if not generated and requested_tts == 'elevenlabs' and is_paid_tts_quota_error(engine.last_error):
                    fallback = get_free_tts_fallback(language, excluded='elevenlabs')
                    if fallback:
                        fallback_reason = engine.last_error
                        engine = fallback
                        report_progress(f"TTS: cuota de ElevenLabs agotada; continuando con {engine.get_tts_name()} gratuito/local.")
                        generated = engine.generate_audio(re.sub(r'<[^>]*>', '', line), rate, audio_file)
                    else:
                        raise RuntimeError('La cuota de ElevenLabs se agotó y no hay un TTS gratuito/local disponible para continuar.')
                if not generated:
                    detail = f': {engine.last_error}' if engine.last_error else ''
                    raise RuntimeError(f'No se pudo generar audio a {rate} wpm{detail}')
                if get_audio_duration(audio_file) <= 0:
                    audio_file.unlink(missing_ok=True)
                    raise RuntimeError(f'ElevenLabs o el TTS devolvió un audio vacío a {rate} wpm')
                engines_used.append(engine.get_tts_name())
            parts = [audio_file]
            report_progress(f"TTS: fragmento {index + 1}/{len(lines)} generado.")
            if pause_ms and index + 1 < len(lines):
                silence = rate_dir / f'pause_{index}.wav'
                if silence.is_file() and get_audio_duration(silence) > 0:
                    report_progress(f"TTS: reutilizando pausa tras el fragmento {index + 1}.")
                else:
                    silence.unlink(missing_ok=True)
                    create_silence(pause_ms / 1000.0, silence)
                parts.append(silence)
                report_progress(f"TTS: pausa de {pause_ms} ms agregada tras el fragmento {index + 1}.")
            fragment_parts.append(parts)
        output = rate_dir / 'combined.wav'
        _concat_wav_files(fragment_parts, output, batch_size=batch_size, progress=report_progress)
        duration = get_audio_duration(output)
        candidates.append((abs(duration - target_duration) if target_duration is not None else 0, rate, duration, output))
    _, rate, duration, selected = min(candidates, key=lambda candidate: candidate[0])
    output_format = str(payload.get('output_format') or 'wav').lower()
    if output_format not in {'wav', 'mp3'}:
        raise ValueError('output_format debe ser wav o mp3')
    final_audio = directory / f'generated_audio.{output_format}'
    if output_format == 'mp3':
        report_progress("TTS: codificando la pista final a MP3.")
        subprocess.run(
            ['ffmpeg', '-i', str(selected), '-c:a', 'libmp3lame', '-b:a', '192k', str(final_audio), '-y'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True,
        )
    else:
        shutil.copy(selected, final_audio)
    report_progress(f"TTS: archivo {output_format.upper()} final preparado ({duration:.1f} s).")
    cursor, cues = 0.0, []
    for index, line in enumerate(lines, 1):
        # La duración por cue se obtiene de la generación seleccionada, no del SRT fuente.
        cue_audio = selected.parent / f'{index - 1}.wav'
        end = cursor + get_audio_duration(cue_audio)
        cues.append({'id': index, 'start': cursor, 'end': end, 'text': line})
        cursor = end + (pause_ms / 1000.0 if index < len(lines) else 0.0)
    return final_audio, {
        'language': language, 'rate': rate, 'duration': duration,
        'target_duration': target_duration, 'fixed_rate': fixed_rate,
        'pause_ms': pause_ms, 'source_type': source_type, 'cues': cues,
        'fragment_count': len(lines), 'merge_batch_size': batch_size,
        'output_format': output_format,
        'tts_requested': requested_tts, 'tts_used': ' → '.join(dict.fromkeys(engines_used)) or engine.get_tts_name(),
        'tts_fallback_reason': fallback_reason,
        'voice_requested': requested_voice, 'voice_used': getattr(engine, 'say_voice', None),
    }


PLAIN_DOCUMENT_EXTENSIONS = {'.txt', '.md', '.markdown'}


def plain_document_lines(path: Path) -> List[str]:
    """Lee texto o Markdown en fragmentos narrables, sin timestamps de entrada."""
    content = path.read_text(encoding='utf-8-sig')
    lines = []
    in_code_block = False
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if line.startswith('```'):
            in_code_block = not in_code_block
            continue
        if in_code_block or not line or line in {'---', '***', '___'}:
            continue
        if path.suffix.lower() in {'.md', '.markdown'}:
            line = re.sub(r'!?\[([^\]]*)\]\([^)]*\)', r'\1', line)
            line = re.sub(r'^[>#\-*+]+\s*', '', line)
            line = re.sub(r'`([^`]+)`', r'\1', line)
            line = line.replace('**', '').replace('__', '').replace('*', '').replace('_', '')
        line = re.sub(r'\s+', ' ', line).strip()
        if line:
            lines.append(line)
    if not lines:
        raise ValueError('El archivo no contiene texto narrable')
    return lines


def generate_plain_document_audio(document_path: Path, args) -> dict:
    """Genera audio continuo y un SRT nuevo desde TXT/Markdown, ignorando tiempos externos."""
    lines = plain_document_lines(document_path)
    if args.test:
        lines = lines[:args.test]
    rate = args.fix_rate_not_truncate if args.fix_rate_not_truncate is not None else 200
    pause_ms = args.fix_rate_not_truncate_pause
    directory = Path.cwd() / f"temp_{document_path.stem}_plain_{uuid.uuid4().hex[:8]}"
    directory.mkdir(parents=True, exist_ok=False)
    audio, metadata = generate_api_audio({
        'text': '\n'.join(lines),
        'lang': args.lang or 'es',
        'tts': args.tts,
        'voice': args.voice,
        'rate': rate,
        'fixed_rate': True,
        'pause_ms': pause_ms,
    }, directory)
    stem = document_path.with_suffix('').with_name(f"{document_path.stem}_plain_rate_{rate}")
    output_wav = stem.with_name(f"{stem.name}_audio.wav")
    output_mp3 = stem.with_name(f"{stem.name}_audio.mp3")
    output_aac = stem.with_name(f"{stem.name}_audio.aac")
    output_srt = stem.with_suffix('.srt')
    shutil.copy(audio, output_wav)
    for codec, output in (('aac', output_aac), ('libmp3lame', output_mp3)):
        try:
            subprocess.run(['ffmpeg', '-i', str(output_wav), '-c:a', codec, '-b:a', '192k', str(output), '-y'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass
    with output_srt.open('w', encoding='utf-8') as output:
        for cue in metadata['cues']:
            output.write(f"{cue['id']}\n{SRTParser.seconds_to_srt_time(cue['start'])} --> {SRTParser.seconds_to_srt_time(cue['end'])}\n{cue['text']}\n\n")
    return {'wav': output_wav, 'mp3': output_mp3, 'aac': output_aac, 'srt': output_srt, 'metadata': metadata}


def main():
    parser = argparse.ArgumentParser(
        description="Genera audio TTS sincronizado con video desde archivo SRT",
        add_help=False  # Manejamos --help manualmente
    )
    parser.add_argument("srt_file", nargs="?", help="Archivo SRT, Markdown (.md) o texto plano (.txt)")
    parser.add_argument("video", nargs="?", help="Archivo de video")
    parser.add_argument("audio_dir", nargs="?", help="Carpeta con audios ya generados")
    parser.add_argument("--test", type=int, nargs="?", const=30,
                       help="Modo test: procesar N subtítulos (default: 30)")
    parser.add_argument("--solo-audio", action="store_true",
                       help="Solo generar audio, sin video")
    parser.add_argument("--no-freeze", action="store_true",
                       help="Truncar audios largos en lugar de freeze")
    parser.add_argument("--no-truncate", action="store_true",
                       help="Conservar audios completos y recuperar desfase a 240 wpm")
    parser.add_argument("--web", action="store_true", help="Abrir la interfaz web local")
    parser.add_argument("--install-dependencies", action="store_true", help="Instalar requisitos del sistema y Python")
    parser.add_argument("--remove-breaks", action="store_true",
                       help="Eliminar pausas >15min del video final")
    parser.add_argument("--only-remove-breaks", action="store_true",
                       help="SOLO eliminar pausas del video (sin TTS)")
    parser.add_argument("--continue", dest="continue_from", type=str,
                       help="Reanudar desde carpeta temporal (ej: temp_video_abc123)")
    parser.add_argument("--youtube", type=str,
                       help="ID o URL de YouTube para descargar video y subtítulos")
    parser.add_argument("--lang", type=str,
                       help="Idioma de los subtítulos (es, en, de, etc.)")
    parser.add_argument("--tts", type=str,
                       help="Motor TTS instalado a utilizar")
    parser.add_argument("--voice", type=str,
                       help="Voz instalada del motor TTS elegido")
    parser.add_argument("--fix-rate", type=int, nargs="?", const=180,
                       help="Usar rate de audio fijo (default: 180 si no se especifica valor)")
    parser.add_argument("--optimize-rate", action="store_true",
                       help="Evaluar 50 líneas y reutilizar el rate óptimo detectado")
    parser.add_argument("--fix-rate-not-truncate", type=int, nargs="?", const=200,
                       help="Solo audio plano sin truncar ni respetar tiempos SRT (default: 200 wpm)")
    parser.add_argument("--fix-rate-not-truncate-pause", type=int, default=1000,
                       help="Pausa entre líneas del audio plano en ms (default: 1000)")
    parser.add_argument("-h", "--help", action="store_true",
                       help="Mostrar ayuda")

    args = parser.parse_args()

    if args.install_dependencies:
        install_dependencies()
        return
    if args.web:
        start_web_ui()
        return

    document_path = Path(args.srt_file) if args.srt_file else None
    if document_path and not args.help and document_path.suffix.lower() in PLAIN_DOCUMENT_EXTENSIONS:
        if args.video:
            parser.error("Los archivos Markdown o TXT generan solo audio y no aceptan video")
        if args.fix_rate_not_truncate_pause < 0:
            parser.error("--fix-rate-not-truncate-pause no puede ser negativo")
        if not document_path.is_file():
            parser.error(f"No existe el archivo: {document_path}")
        try:
            result = generate_plain_document_audio(document_path, args)
        except (ValueError, RuntimeError, OSError) as error:
            parser.error(str(error))
        metadata = result['metadata']
        print(f"{Colors.GREEN}✅ Audio plano generado desde {document_path.name}{Colors.NC}")
        print(f"{Colors.CYAN}   Idioma: {metadata['language']} · TTS: {metadata['tts_used']} · Rate: {metadata['rate']} wpm · Duración: {metadata['duration']:.3f}s{Colors.NC}")
        for kind in ('wav', 'mp3', 'aac', 'srt'):
            output = result[kind]
            if output.exists():
                print(f"{Colors.GREEN}   {kind.upper()}: {output}{Colors.NC}")
        return

    # Si se especifica --continue, cargar checkpoint y reanudar
    if args.continue_from:
        temp_dir_path = Path(args.continue_from)
        if not temp_dir_path.exists():
            print(f"{Colors.RED}Error: Carpeta temporal no existe: {temp_dir_path}{Colors.NC}")
            sys.exit(1)

        checkpoint = load_checkpoint(temp_dir_path)
        if not checkpoint:
            print(f"{Colors.RED}Error: No se encontró checkpoint en {temp_dir_path}{Colors.NC}")
            sys.exit(1)

        print(f"{Colors.GREEN}📂 Reanudando desde checkpoint{Colors.NC}")
        print(f"{Colors.CYAN}   Carpeta: {temp_dir_path}{Colors.NC}")
        print(f"{Colors.CYAN}   SRT: {Path(checkpoint['srt_file']).name}{Colors.NC}")
        print(f"{Colors.CYAN}   Último subtítulo procesado: {checkpoint['last_subtitle_id']}/{checkpoint['total_subtitles']}{Colors.NC}")
        print(f"{Colors.CYAN}   Guardado: {checkpoint['timestamp']}{Colors.NC}")

        # Sobrescribir args con datos del checkpoint
        args.srt_file = checkpoint['srt_file']
        args.video = checkpoint['video_file']
        checkpoint_params = checkpoint['parameters']
        for key, value in checkpoint_params.items():
            setattr(args, key, value)
        # Compatibilidad con checkpoints creados antes de renombrar la opción.
        if checkpoint_params.get('experimental'):
            args.no_truncate = True

    # Si se especifica --youtube, descargar video y subtítulos
    if hasattr(args, 'youtube') and args.youtube:
        print(f"{Colors.BLUE}{'═' * 60}{Colors.NC}")
        print(f"{Colors.BLUE}📺 MODO YOUTUBE: Descargando video y subtítulos{Colors.NC}")
        print(f"{Colors.BLUE}{'═' * 60}{Colors.NC}")

        video_path, srt_path = process_youtube_video(
            args.youtube,
            args.lang if hasattr(args, 'lang') else None
        )

        if not video_path or not srt_path:
            print(f"{Colors.RED}Error procesando video de YouTube{Colors.NC}")
            sys.exit(1)

        # Actualizar args con los archivos descargados
        args.video = str(video_path)
        args.srt_file = str(srt_path)

    # Si se pide ayuda o no hay parámetros, mostrar uso y prompt
    if not args.srt_file and not args.video and not (hasattr(args, 'youtube') and args.youtube):
        parser.print_help()
        print("\nAbrí http://127.0.0.1:8765 para usar la interfaz web. Ctrl+C para detenerla.")
        start_web_ui()
        return
    if args.help:
        interactive_args = show_usage_and_prompt()
        if interactive_args:
            # Re-parsear con los argumentos interactivos
            args = parser.parse_args(interactive_args)
        else:
            sys.exit(0)

    # Este modo genera un audio plano; un video haría ambigua su semántica.
    if args.fix_rate_not_truncate is not None and args.video:
        parser.error("--fix-rate-not-truncate solo se puede usar sin video")
    if args.fix_rate_not_truncate_pause < 0:
        parser.error("--fix-rate-not-truncate-pause no puede ser negativo")

    # Un SRT sin video es el atajo para generar únicamente el audio. El video
    # homónimo .mp4 se conserva como referencia para nombres y checkpoints.
    apply_audio_only_defaults(args)
    if args.fix_rate_not_truncate is not None:
        args.solo_audio = True
        args.no_truncate = False

    # Validar que se proporcionaron los argumentos requeridos
    if not args.srt_file or not args.video:
        print(f"{Colors.RED}Error: Se requieren los parámetros srt_file y video, o usar --youtube{Colors.NC}")
        sys.exit(1)

    # Inicializar logger de errores
    error_logger = ErrorLogger()

    # Mostrar configuración
    print(f"{Colors.BLUE}{'═' * 50}{Colors.NC}")
    print(f"{Colors.BLUE}🔍 DETECTANDO MÉTODO TTS{Colors.NC}")
    print(f"{Colors.BLUE}{'═' * 50}{Colors.NC}")

    # Obtener idioma desde argumentos (default: 'es')
    print(f"{Colors.CYAN}🔍 DEBUG: args.lang = {args.lang if hasattr(args, 'lang') else 'NO DEFINIDO'}{Colors.NC}")
    language = args.lang if hasattr(args, 'lang') and args.lang else 'es'
    print(f"{Colors.CYAN}🌍 Idioma configurado: {language}{Colors.NC}")
    tts_engine = TTSEngine(language=language, tts_method=args.tts, tts_voice=args.voice)

    # Verificar archivos
    srt_path = Path(args.srt_file)
    if not srt_path.exists():
        print(f"{Colors.RED}Error: No existe {srt_path}{Colors.NC}")
        sys.exit(1)

    # En solo-audio no se lee el video: su ruta solo define los nombres de salida.
    video_path = resolve_video_path(args.video, allow_missing=args.solo_audio)

    if not video_path:
        print(f"{Colors.RED}Error: No se encuentra el video{Colors.NC}")
        sys.exit(1)

    print(f"{Colors.GREEN}SRT: {srt_path}{Colors.NC}")
    print(f"{Colors.GREEN}Video: {video_path}{Colors.NC}")

    if args.test:
        print(f"{Colors.YELLOW}⚠️  MODO TEST: {args.test} subtítulos{Colors.NC}")
    if args.solo_audio:
        print(f"{Colors.CYAN}🎵 MODO SOLO-AUDIO: No se generará video{Colors.NC}")
    if args.fix_rate_not_truncate is not None:
        print(f"{Colors.MAGENTA}📖 MODO AUDIO PLANO: sin truncar ni tiempos SRT, rate fijo {args.fix_rate_not_truncate} wpm, pausa {args.fix_rate_not_truncate_pause} ms{Colors.NC}")
    if is_rate_optimization_enabled(args):
        print(f"{Colors.MAGENTA}🎯 MODO OPTIMIZE-RATE: evaluará 50 líneas antes de reutilizar el rate óptimo{Colors.NC}")
    if args.no_freeze:
        print(f"{Colors.MAGENTA}🚫 MODO NO-FREEZE: Audios largos serán truncados{Colors.NC}")
    if args.no_truncate:
        print(f"{Colors.MAGENTA}🧪 MODO NO-TRUNCATE: Sin truncar; se recuperará desfase a {MAX_TTS_RATE} wpm{Colors.NC}")
    if args.remove_breaks:
        print(f"{Colors.MAGENTA}✂️  MODO REMOVE-BREAKS: Se eliminarán pausas >15min{Colors.NC}")
    if args.only_remove_breaks:
        print(f"{Colors.MAGENTA}✂️  MODO ONLY-REMOVE-BREAKS: SOLO se eliminarán pausas{Colors.NC}")

    # Guardar configuración para futuras ejecuciones
    save_config(
        str(srt_path),
        str(video_path),
        args.test,
        args.solo_audio,
        args.no_freeze,
        args.remove_breaks
    )

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

    # Crear o usar directorio temporal
    import datetime
    import uuid

    # Si estamos reanudando, usar la carpeta del checkpoint
    if args.continue_from:
        temp_dir = Path(args.continue_from)
        checkpoint = load_checkpoint(temp_dir)
        last_processed_id = checkpoint['last_subtitle_id']
        print(f"{Colors.GREEN}♻️  Reanudando desde subtítulo {last_processed_id + 1}{Colors.NC}")
    else:
        # Crear directorio temporal con nombre descriptivo
        srt_base_name = Path(args.srt_file).stem
        random_code = str(uuid.uuid4())[:8]
        temp_dir = Path.cwd() / f"temp_{srt_base_name}_{random_code}"
        temp_dir.mkdir(exist_ok=True)
        last_processed_id = 0
        print(f"{Colors.GREEN}Carpeta temporal: {temp_dir}{Colors.NC}")

    logs_dir = temp_dir / "logs"
    logs_dir.mkdir(exist_ok=True)

    # Preparar parámetros para checkpoint
    checkpoint_params = {
        'test': args.test,
        'solo_audio': args.solo_audio,
        'no_freeze': args.no_freeze,
        'no_truncate': args.no_truncate,
        'fix_rate_not_truncate': args.fix_rate_not_truncate,
        'fix_rate_not_truncate_pause': args.fix_rate_not_truncate_pause,
        'optimize_rate': args.optimize_rate,
        'remove_breaks': args.remove_breaks,
        'lang': language,
        'tts': args.tts,
        'voice': args.voice,
    }

    # PASO 2: Generar audios con ajuste inteligente
    print(f"{Colors.BLUE}{'═' * 50}{Colors.NC}")
    print(f"{Colors.BLUE}🎤 PASO 2: GENERAR AUDIOS CON AJUSTE INTELIGENTE{Colors.NC}")
    print(f"{Colors.BLUE}{'═' * 50}{Colors.NC}")

    audio_segments: Dict[int, AudioSegment] = {}
    rate_usage = {180: 0, 200: 0, 220: 0, 240: 0, 'freeze': 0, 'truncated': 0}
    optimal_rate = 180
    plain_audio_mode = args.fix_rate_not_truncate is not None
    learning_phase = is_rate_optimization_enabled(args)
    processed_count = 0
    no_truncate_lag = 0.0

    srt_filename = Path(args.srt_file).name
    total_subtitles = len(subtitles)
    set_terminal_progress(0, total_subtitles)

    for idx, subtitle in enumerate(subtitles):
        progress_percent = (idx + 1) / total_subtitles * 100 if total_subtitles else 100
        set_terminal_progress(idx + 1, total_subtitles)
        # El hueco hasta el siguiente subtítulo es la ventana de tiempo para
        # este audio; el último usa su propia duración.
        if idx + 1 < len(subtitles):
            available_time = subtitles[idx + 1].start_seconds - subtitle.start_seconds
        else:
            available_time = subtitle.duration

        # Skip already processed subtitles when resuming
        if subtitle.consecutive_id <= last_processed_id:
            print(f"{Colors.CYAN}⏭️  Saltando subtítulo {subtitle.consecutive_id}/{len(subtitles)} · Progreso: {progress_percent:.0f}% (ya procesado){Colors.NC}")
            # Still load the audio segment for final processing
            audio_file = temp_dir / f"{subtitle.consecutive_id}.wav"
            if audio_file.exists():
                # Determine if it needs freeze or was truncated from existing data
                # For now, assume basic AudioSegment (will be correct in final video)
                audio_segments[subtitle.consecutive_id] = AudioSegment(
                    subtitle_id=subtitle.consecutive_id,
                    audio_file=audio_file,
                    rate=MAX_TTS_RATE if args.no_truncate else 180,
                    needs_freeze=False,
                    was_truncated=False,
                    timing_offset=0.0 if plain_audio_mode else no_truncate_lag
                )
                if args.no_truncate and not plain_audio_mode:
                    no_truncate_lag = calculate_no_truncate_lag(
                        no_truncate_lag, get_audio_duration(audio_file), available_time
                    )
            continue

        # Limpiar texto HTML
        clean_text = re.sub(r'<[^>]*>', '', subtitle.text)

        print(f"{Colors.YELLOW}{'━' * 50}{Colors.NC}")
        print(f"{Colors.YELLOW}📄 {srt_filename} - Subtítulo {subtitle.consecutive_id}/{len(subtitles)} · Progreso: {progress_percent:.0f}%{Colors.NC}")
        print(f"{Colors.CYAN}  (ID original: {subtitle.original_id}){Colors.NC}")
        print(f"{Colors.YELLOW}  Texto: {clean_text[:50]}...{Colors.NC}")
        print(f"{Colors.BLUE}  Duración subtítulo: {subtitle.duration:.3f}s{Colors.NC}")
        print(f"{Colors.BLUE}  Tiempo disponible: {available_time:.3f}s{Colors.NC}")

        current_rate = optimal_rate if not learning_phase else 180

        if not learning_phase:
            print(f"{Colors.MAGENTA}🎯 Usando rate aprendido: {current_rate} wpm{Colors.NC}")

        # Determinar rates a probar
        fixed_rate = args.fix_rate if hasattr(args, 'fix_rate') and args.fix_rate else None
        if plain_audio_mode:
            rate_list = [args.fix_rate_not_truncate]
            print(f"{Colors.MAGENTA}📖 Rate plano fijo: {args.fix_rate_not_truncate} wpm{Colors.NC}")
        elif args.no_truncate:
            rate_list = get_no_truncate_rate_list(
                current_rate, no_truncate_lag > 0.01, fixed_rate
            )
            if no_truncate_lag > 0.01:
                print(f"{Colors.MAGENTA}🧪 Desfase acumulado: {no_truncate_lag:.3f}s; usando {MAX_TTS_RATE} wpm{Colors.NC}")
        elif fixed_rate:
            # Si se especificó --fix-rate, usar solo ese rate
            rate_list = [fixed_rate]
            print(f"{Colors.MAGENTA}🔒 Usando rate fijo: {fixed_rate} wpm{Colors.NC}")
        elif is_rate_optimization_enabled(args):
            rate_list = [current_rate, 200, 220, 240] if (args.no_freeze or args.solo_audio) else [current_rate, 200, 220]
        else:
            # Sin --optimize-rate no se prueba ni persiste un rate alternativo.
            rate_list = [current_rate]

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

            # En no-truncate se conserva el audio completo a rate máximo,
            # aunque aún no entre en la ventana del subtítulo.
            if plain_audio_mode or diff < 0.5 or (args.no_truncate and try_rate == MAX_TTS_RATE):
                temp_audio.rename(audio_file)
                audio_created = True
                final_rate = try_rate
                rate_usage[try_rate] = rate_usage.get(try_rate, 0) + 1
                if args.no_truncate and diff >= 0.5:
                    print(f"  {Colors.YELLOW}🧪 Audio completo conservado; continuará el desfase{Colors.NC}")
                else:
                    print(f"  {Colors.GREEN}✅ Audio ajustado con rate {try_rate}{Colors.NC}")

                audio_segments[subtitle.consecutive_id] = AudioSegment(
                    subtitle_id=subtitle.consecutive_id,
                    audio_file=audio_file,
                    rate=try_rate,
                    needs_freeze=False,
                    was_truncated=False,
                    timing_offset=0.0 if plain_audio_mode else no_truncate_lag
                )
                if args.no_truncate and not plain_audio_mode:
                    no_truncate_lag = calculate_no_truncate_lag(
                        no_truncate_lag, audio_duration, available_time
                    )
                break
            else:
                temp_audio.unlink()

        # Si no se ajustó, truncar o freeze
        if not audio_created:
            # Determinar si se está forzando un rate fijo
            is_fixed_rate = hasattr(args, 'fix_rate') and args.fix_rate

            if args.no_truncate:
                print(f"{Colors.RED}❌ No se pudo generar el audio completo a {MAX_TTS_RATE} wpm{Colors.NC}")
                sys.exit(1)
            elif args.no_freeze or args.solo_audio:
                # En modo truncate, usar el rate fijo o 240 si no hay rate fijo
                truncate_rate = args.fix_rate if is_fixed_rate else 240
                print(f"  {Colors.YELLOW}⚠️  Audio muy largo, generando con rate {truncate_rate} y truncando{Colors.NC}")
                full_audio = temp_dir / f"{subtitle.consecutive_id}_full.wav"

                if tts_engine.generate_audio(clean_text, truncate_rate, full_audio):
                    if truncate_audio(full_audio, audio_file, available_time, error_logger):
                        full_audio.unlink()
                        rate_usage['truncated'] += 1
                        error_logger.add_warning(f"Subtítulo {subtitle.consecutive_id}: Audio truncado a {available_time:.3f}s")
                        print(f"  {Colors.GREEN}✅ Audio truncado a {available_time:.3f}s{Colors.NC}")

                        audio_segments[subtitle.consecutive_id] = AudioSegment(
                            subtitle_id=subtitle.consecutive_id,
                            audio_file=audio_file,
                            rate=truncate_rate,
                            needs_freeze=False,
                            was_truncated=True
                        )
                    else:
                        print(f"  {Colors.RED}❌ Error truncando audio{Colors.NC}")
                        sys.exit(1)
            else:
                # En modo freeze, usar el rate fijo o 220 si no hay rate fijo
                freeze_rate = args.fix_rate if is_fixed_rate else 220
                print(f"  {Colors.YELLOW}⚠️  Audio muy largo, generando con rate {freeze_rate} y marcando para freeze{Colors.NC}")

                if tts_engine.generate_audio(clean_text, freeze_rate, audio_file):
                    audio_duration = get_audio_duration(audio_file)
                    freeze_time = audio_duration - available_time

                    # Solo marcar para freeze si la duración es positiva
                    if freeze_time > 0.01:
                        rate_usage['freeze'] += 1
                        print(f"  {Colors.RED}🎬 Requerirá freeze de {freeze_time:.3f}s{Colors.NC}")

                        audio_segments[subtitle.consecutive_id] = AudioSegment(
                            subtitle_id=subtitle.consecutive_id,
                            audio_file=audio_file,
                            rate=freeze_rate,
                            needs_freeze=True,
                            freeze_duration=freeze_time,
                            was_truncated=False
                        )
                    else:
                        # El audio cabe sin necesidad de freeze
                        rate_usage[freeze_rate] += 1
                        print(f"  {Colors.GREEN}✅ Audio ajustado con rate {freeze_rate} (sin freeze){Colors.NC}")

                        audio_segments[subtitle.consecutive_id] = AudioSegment(
                            subtitle_id=subtitle.consecutive_id,
                            audio_file=audio_file,
                            rate=freeze_rate,
                            needs_freeze=False,
                            was_truncated=False
                        )

        processed_count += 1

        # Save checkpoint every 10 subtitles
        if subtitle.consecutive_id % 10 == 0:
            save_checkpoint(temp_dir, args.srt_file, str(video_path),
                           checkpoint_params, subtitle.consecutive_id, len(subtitles))
            print(f"{Colors.GREEN}💾 Checkpoint guardado (subtítulo {subtitle.consecutive_id}/{len(subtitles)}){Colors.NC}")

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

    # Save final checkpoint
    if subtitles:
        save_checkpoint(temp_dir, args.srt_file, str(video_path),
                       checkpoint_params, subtitles[-1].consecutive_id, len(subtitles))
        print(f"{Colors.GREEN}💾 Checkpoint final guardado{Colors.NC}")

    print(f"{Colors.GREEN}✅ Audios generados{Colors.NC}")

    # Resumen
    print(f"{Colors.BLUE}{'═' * 50}{Colors.NC}")
    print(f"{Colors.BLUE}📊 RESUMEN DE PROCESAMIENTO{Colors.NC}")
    print(f"{Colors.BLUE}{'═' * 50}{Colors.NC}")

    freeze_count = sum(1 for seg in audio_segments.values() if seg.needs_freeze)
    truncated_count = sum(1 for seg in audio_segments.values() if seg.was_truncated)

    print(f"{Colors.GREEN}Total subtítulos: {len(subtitles)}{Colors.NC}")
    if args.fix_rate_not_truncate is not None:
        print(f"{Colors.GREEN}Audio plano continuo a {args.fix_rate_not_truncate} wpm, sin truncar ni desfase{Colors.NC}")
    elif args.no_truncate:
        print(f"{Colors.YELLOW}Desfase final pendiente: {no_truncate_lag:.3f}s{Colors.NC}")
        print(f"{Colors.GREEN}Audios completos, sin truncar: {len(subtitles)}{Colors.NC}")
    elif args.no_freeze or args.solo_audio:
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

            offset = segment.timing_offset if args.no_truncate else time_offset
            new_start = subtitle.start_seconds + offset
            new_end = subtitle.end_seconds + offset

            new_start_time = SRTParser.seconds_to_srt_time(new_start)
            new_end_time = SRTParser.seconds_to_srt_time(new_end)

            rate = segment.rate
            offset_ms = int(offset * 1000)

            # Construir texto con metadatos
            if args.no_truncate and offset > 0.01:
                new_text = f"[#{subtitle.consecutive_id} r{rate} +{offset_ms}ms] [🧪 DESFASE] {subtitle.text}"
            elif segment.was_truncated:
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

    if args.no_truncate:
        test_srt = create_no_truncate_test_srt(srt_path, subtitles, audio_segments)
        print(f"{Colors.GREEN}✅ SRT ajustado al audio generado: {test_srt}{Colors.NC}")
    elif args.fix_rate_not_truncate is not None:
        test_srt = create_fixed_rate_not_truncate_srt(
            srt_path, subtitles, audio_segments, args.fix_rate_not_truncate,
            args.fix_rate_not_truncate_pause
        )
        print(f"{Colors.GREEN}✅ SRT plano ajustado al audio generado: {test_srt}{Colors.NC}")

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
            print(f"{Colors.YELLOW}Procesando video con freezes (optimizado)...{Colors.NC}")
            print(f"{Colors.CYAN}ℹ️  {freeze_count} segmentos necesitan freeze{Colors.NC}")

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

            # Agrupar subtítulos en bloques (bloques sin freeze vs. individuales con freeze)
            blocks = []
            current_block = {
                'type': 'normal',  # 'normal' o 'freeze'
                'start_time': None,
                'end_time': None,
                'subtitles': []
            }

            for subtitle in subtitles:
                segment = audio_segments.get(subtitle.consecutive_id)
                if not segment:
                    continue

                if segment.needs_freeze:
                    # Finalizar bloque actual si existe
                    if current_block['subtitles']:
                        blocks.append(current_block)
                        current_block = {'type': 'normal', 'start_time': None, 'end_time': None, 'subtitles': []}

                    # Agregar bloque individual con freeze
                    blocks.append({
                        'type': 'freeze',
                        'start_time': subtitle.start_seconds,
                        'end_time': subtitle.start_seconds + subtitle.duration,
                        'subtitles': [subtitle],
                        'freeze_duration': segment.freeze_duration,
                        'segment': segment
                    })
                else:
                    # Agregar al bloque normal actual
                    if not current_block['subtitles']:
                        current_block['start_time'] = subtitle.start_seconds

                    current_block['end_time'] = subtitle.start_seconds + subtitle.duration
                    current_block['subtitles'].append(subtitle)

            # Agregar último bloque si existe
            if current_block['subtitles']:
                blocks.append(current_block)

            print(f"{Colors.GREEN}Bloques optimizados: {len(blocks)} (antes: {len(subtitles)} segmentos){Colors.NC}")

            # Procesar bloques
            video_segments = []
            for idx, block in enumerate(blocks):
                if block['type'] == 'normal':
                    # Extraer un solo segmento grande para todos los subtítulos del bloque
                    duration = block['end_time'] - block['start_time']
                    seg_file = temp_dir / f"vblock_{idx}.mkv"

                    print(f"{Colors.YELLOW}Bloque {idx+1}/{len(blocks)}: Normal "
                          f"({block['start_time']:.1f}s - {block['end_time']:.1f}s, "
                          f"{len(block['subtitles'])} subtítulos){Colors.NC}")

                    try:
                        subprocess.run(
                            ["ffmpeg", "-i", str(video_path),
                             "-ss", str(block['start_time']),
                             "-t", str(duration),
                             "-c:v", "libx264", "-preset", "ultrafast", "-an",
                             str(seg_file), "-y"],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            text=True,
                            check=True
                        )

                        if seg_file.exists() and seg_file.stat().st_size > 0:
                            video_segments.append(seg_file)
                            print(f"  {Colors.GREEN}✓ Bloque creado{Colors.NC}")
                        else:
                            print(f"  {Colors.RED}✗ Error: bloque vacío{Colors.NC}")
                            error_logger.add_warning(f"Bloque {idx}: Segmento vacío")

                    except subprocess.CalledProcessError as e:
                        error_logger.add_error(
                            f"PASO 4: Extraer bloque {idx}",
                            ' '.join(e.cmd),
                            e.stderr or "Error extrayendo bloque"
                        )
                        print(f"  {Colors.RED}✗ Error creando bloque{Colors.NC}")

                else:  # block['type'] == 'freeze'
                    subtitle = block['subtitles'][0]
                    seg_file = temp_dir / f"vseg_{subtitle.consecutive_id}.mkv"

                    print(f"{Colors.YELLOW}Bloque {idx+1}/{len(blocks)}: Freeze "
                          f"(subtítulo {subtitle.consecutive_id}, "
                          f"+{block['freeze_duration']:.1f}s freeze){Colors.NC}")

                    try:
                        # Extraer segmento original
                        subprocess.run(
                            ["ffmpeg", "-i", str(video_path),
                             "-ss", str(subtitle.start_seconds),
                             "-t", str(subtitle.duration),
                             "-c:v", "libx264", "-preset", "ultrafast", "-an",
                             str(seg_file), "-y"],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            text=True,
                            check=True
                        )

                        if seg_file.exists() and seg_file.stat().st_size > 0:
                            video_segments.append(seg_file)
                            print(f"  {Colors.GREEN}✓ Segmento creado{Colors.NC}")

                            # Crear freeze
                            freeze_dur = block['freeze_duration']
                            frame_file = temp_dir / f"freeze_{subtitle.consecutive_id}.png"
                            freeze_file = temp_dir / f"vfreeze_{subtitle.consecutive_id}.mkv"

                            # Extraer último frame
                            subprocess.run(
                                ["ffmpeg", "-sseof", "-0.1", "-i", str(seg_file),
                                 "-frames:v", "1", str(frame_file), "-y"],
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                text=True,
                                check=True
                            )

                            if frame_file.exists() and frame_file.stat().st_size > 0:
                                # Crear video de freeze
                                subprocess.run(
                                    ["ffmpeg", "-loop", "1", "-i", str(frame_file),
                                     "-t", str(freeze_dur), "-r", str(fps),
                                     "-pix_fmt", "yuv420p", "-c:v", "libx264",
                                     "-preset", "ultrafast", str(freeze_file), "-y"],
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE,
                                    text=True,
                                    check=True
                                )

                                if freeze_file.exists() and freeze_file.stat().st_size > 0:
                                    video_segments.append(freeze_file)
                                    error_logger.add_warning(f"Subtítulo {subtitle.consecutive_id}: Freeze frame de {freeze_dur:.3f}s agregado")
                                    print(f"  {Colors.GREEN}✓ Freeze creado{Colors.NC}")

                        else:
                            print(f"  {Colors.RED}✗ Error: segmento vacío{Colors.NC}")

                    except subprocess.CalledProcessError as e:
                        error_logger.add_error(
                            f"PASO 4: Procesar segmento con freeze (subtítulo {subtitle.consecutive_id})",
                            ' '.join(e.cmd),
                            e.stderr or "Error procesando freeze"
                        )
                        print(f"  {Colors.RED}✗ Error creando freeze{Colors.NC}")

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
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        check=True
                    )

                    if processed_video.exists() and processed_video.stat().st_size > 0:
                        video_to_use = processed_video
                        print(f"{Colors.GREEN}✓ Video procesado{Colors.NC}")
                    else:
                        error_logger.add_error(
                            "PASO 4: Concatenar segmentos de video",
                            "ffmpeg concat",
                            "Video concatenado está vacío"
                        )
                        print(f"{Colors.RED}✗ Error: video vacío{Colors.NC}")
                        sys.exit(1)

                except subprocess.CalledProcessError as e:
                    error_logger.add_error(
                        "PASO 4: Concatenar segmentos de video",
                        ' '.join(e.cmd),
                        e.stderr or "Error concatenando segmentos de video"
                    )
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
    create_silence(0.001, audio_master, error_logger)
    current_master_duration = 0.0
    concat_counter = 0  # Contador para nombres únicos

    for idx, subtitle in enumerate(subtitles):
        segment = audio_segments.get(subtitle.consecutive_id)
        if not segment:
            continue

        print(f"{Colors.YELLOW}{'━' * 50}{Colors.NC}")
        print(f"{Colors.YELLOW}Subtítulo {subtitle.consecutive_id}/{len(subtitles)} "
              f"(inicio: {subtitle.start_seconds:.3f}s){Colors.NC}")

        # Verificar duración actual del audio master
        current_master_duration = get_audio_duration(audio_master)

        # Agregar gap si es necesario
        gap = 0.0 if args.fix_rate_not_truncate is not None else subtitle.start_seconds - current_master_duration

        if gap > 0.01:
            print(f"  {Colors.GREEN}→ Agregando silencio de {gap:.3f}s{Colors.NC}")
            gap_file = temp_dir / f"gap_{subtitle.consecutive_id}.wav"
            create_silence(gap, gap_file, error_logger)

            # Concatenar con nombre único
            concat_counter += 1
            temp_master = temp_dir / f"audio_concat_{concat_counter}.wav"
            try:
                subprocess.run(
                    ["ffmpeg", "-i", str(audio_master), "-i", str(gap_file),
                     "-filter_complex", "[0:a][1:a]concat=n=2:v=0:a=1[out]",
                     "-map", "[out]", str(temp_master), "-y"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=True
                )
            except subprocess.CalledProcessError as e:
                error_logger.add_error(
                    f"PASO 5: Concatenar gap (subtítulo {subtitle.consecutive_id})",
                    ' '.join(e.cmd),
                    e.stderr or "Error concatenando silencio gap"
                )
                print(f"{Colors.RED}Error concatenando gap{Colors.NC}")
                raise
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
        try:
            subprocess.run(
                ["ffmpeg", "-i", str(audio_master), "-i", str(segment.audio_file),
                 "-filter_complex", "[0:a][1:a]concat=n=2:v=0:a=1[out]",
                 "-map", "[out]", str(temp_master), "-y"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True
            )
        except subprocess.CalledProcessError as e:
            error_logger.add_error(
                f"PASO 5: Concatenar audio TTS (subtítulo {subtitle.consecutive_id})",
                ' '.join(e.cmd),
                e.stderr or "Error concatenando audio TTS"
            )
            print(f"{Colors.RED}Error concatenando audio TTS{Colors.NC}")
            raise
        # Eliminar master anterior
        if audio_master != temp_dir / "audio_master.wav":
            audio_master.unlink()
        audio_master = temp_master
        current_master_duration = get_audio_duration(audio_master)

        # Agregar padding si es necesario
        if args.fix_rate_not_truncate is not None:
            expected_position = current_master_duration + (
                args.fix_rate_not_truncate_pause / 1000.0 if idx + 1 < len(subtitles) else 0.0
            )
        elif idx + 1 < len(subtitles):
            next_subtitle = subtitles[idx + 1]
            expected_position = next_subtitle.start_seconds
        else:
            expected_position = subtitle.start_seconds + subtitle.duration

        padding = expected_position - current_master_duration

        if padding > 0.01:
            print(f"  {Colors.GREEN}→ Agregando padding de {padding:.3f}s{Colors.NC}")
            padding_file = temp_dir / f"padding_{subtitle.consecutive_id}.wav"
            create_silence(padding, padding_file, error_logger)

            concat_counter += 1
            temp_master = temp_dir / f"audio_concat_{concat_counter}.wav"
            try:
                subprocess.run(
                    ["ffmpeg", "-i", str(audio_master), "-i", str(padding_file),
                     "-filter_complex", "[0:a][1:a]concat=n=2:v=0:a=1[out]",
                     "-map", "[out]", str(temp_master), "-y"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=True
                )
            except subprocess.CalledProcessError as e:
                error_logger.add_error(
                    "PASO 5: Concatenar padding",
                    ' '.join(e.cmd),
                    e.stderr or "Error concatenando padding"
                )
                print(f"{Colors.RED}Error concatenando padding{Colors.NC}")
                raise
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
        audio_stem = (f"{video_path.stem}_fixed_rate_{args.fix_rate_not_truncate}_audio"
                      if args.fix_rate_not_truncate is not None else f"{video_path.stem}_tts_audio")
        output_audio_wav = video_path.with_suffix('').with_name(f"{audio_stem}.wav")
        output_audio_aac = video_path.with_suffix('').with_name(f"{audio_stem}.aac")
        output_audio_mp3 = video_path.with_suffix('').with_name(f"{audio_stem}.mp3")

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

        # Convertir a MP3
        try:
            subprocess.run(
                ["ffmpeg", "-i", str(output_audio_wav),
                 "-c:a", "libmp3lame", "-b:a", "192k",
                 str(output_audio_mp3), "-y"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True
            )
            if output_audio_mp3.exists():
                print(f"{Colors.GREEN}✅ Audio MP3: {output_audio_mp3}{Colors.NC}")
        except subprocess.CalledProcessError:
            pass

        output_video = None
    else:
        # Generar nombre base con TTS, SO y opciones usadas
        tts_name = tts_engine.get_tts_name()
        os_name = platform.system()  # Darwin, Windows, Linux

        # Normalizar nombre del SO para el archivo
        if os_name == "Darwin":
            os_name = "macOS"

        # Determinar si se usó freeze o no
        if args.no_truncate:
            freeze_status = "no-truncate"
        elif args.no_freeze or args.solo_audio:
            freeze_status = "nofreeze"
        else:
            # Verificar si realmente se usó freeze en algún segmento
            has_freeze = any(seg.needs_freeze for seg in audio_segments.values())
            freeze_status = "freeze" if has_freeze else "nofreeze"

        base_output = video_path.with_suffix('').with_name(
            f"{video_path.stem}_{tts_name}_{os_name}_{freeze_status}.mkv"
        )
        output_video = get_unique_output_path(base_output)

        if output_video != base_output:
            print(f"{Colors.YELLOW}⚠ El archivo {base_output.name} ya existe{Colors.NC}")
            print(f"{Colors.CYAN}ℹ Generando nuevo archivo: {output_video.name}{Colors.NC}")

        try:
            merge_command = [
                "ffmpeg", "-i", str(video_to_use), "-i", str(audio_final),
            ]
            if args.no_truncate:
                video_padding = calculate_required_video_padding(
                    get_audio_duration(video_to_use), get_audio_duration(audio_final)
                )
                if video_padding > 0.01:
                    print(f"{Colors.MAGENTA}🧪 Extendiendo último frame {video_padding:.3f}s para conservar el audio{Colors.NC}")
                    merge_command.extend([
                        "-filter_complex",
                        f"[0:v]tpad=stop_mode=clone:stop_duration={video_padding:.6f}[video]",
                        "-map", "[video]",
                    ])
                else:
                    merge_command.extend(["-map", "0:v:0"])
            else:
                merge_command.extend(["-map", "0:v:0"])

            merge_command.extend([
                "-map", "1:a:0",
                "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", "-b:a", "192k",
                "-shortest", str(output_video), "-y",
            ])
            result = subprocess.run(
                merge_command,
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
                    print(f"{Colors.YELLOW}  Extrayendo segmento {idx+1}/{len(keep_segments)}: "
                          f"{start:.1f}s a {end:.1f}s ({duration:.1f}s){Colors.NC}")

                    seg_file = temp_dir / f"seg_{idx}.mkv"

                    try:
                        subprocess.run(
                            ["ffmpeg", "-i", str(output_video),
                             "-ss", str(start), "-t", str(duration),
                             "-c", "copy", str(seg_file), "-y"],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            text=True,
                            check=True
                        )

                        if seg_file.exists() and seg_file.stat().st_size > 0:
                            segment_files.append(seg_file)
                            print(f"{Colors.GREEN}    ✓ Segmento creado{Colors.NC}")
                        else:
                            error_logger.add_warning(f"PASO 7: Segmento {idx+1} está vacío")
                            print(f"{Colors.RED}    ✗ Error: segmento vacío{Colors.NC}")

                    except subprocess.CalledProcessError as e:
                        error_logger.add_error(
                            f"PASO 7: Extraer segmento {idx+1} sin pausas",
                            ' '.join(e.cmd),
                            e.stderr or "Error extrayendo segmento"
                        )
                        print(f"{Colors.RED}    ✗ Error creando segmento{Colors.NC}")

            # Concatenar segmentos
            if segment_files:
                print(f"{Colors.CYAN}{'═' * 50}{Colors.NC}")
                print(f"{Colors.CYAN}Concatenando {len(segment_files)} segmentos...{Colors.NC}")

                concat_list = temp_dir / "concat_breaks.txt"
                with open(concat_list, 'w') as f:
                    for seg in segment_files:
                        f.write(f"file '{seg}'\n")

                # Generar nombre base con TTS, SO, freeze status y sin pausas
                base_clean_output = video_path.with_suffix('').with_name(
                    f"{video_path.stem}_{tts_name}_{os_name}_{freeze_status}_sin_pausas.mkv"
                )
                output_video_clean = get_unique_output_path(base_clean_output)

                if output_video_clean != base_clean_output:
                    print(f"{Colors.YELLOW}⚠ El archivo {base_clean_output.name} ya existe{Colors.NC}")
                    print(f"{Colors.CYAN}ℹ Generando nuevo archivo: {output_video_clean.name}{Colors.NC}")

                try:
                    subprocess.run(
                        ["ffmpeg", "-f", "concat", "-safe", "0",
                         "-i", str(concat_list), "-c", "copy",
                         str(output_video_clean), "-y"],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        check=True
                    )

                    if output_video_clean.exists() and output_video_clean.stat().st_size > 0:
                        total_removed = sum(end - start for start, end in gaps)
                        print(f"{Colors.GREEN}✓ Video sin pausas creado: {output_video_clean}{Colors.NC}")
                        print(f"{Colors.GREEN}✓ Tiempo total eliminado: {total_removed:.1f}s "
                              f"({total_removed/60:.1f} min){Colors.NC}")
                    else:
                        error_logger.add_error(
                            "PASO 7: Concatenar segmentos sin pausas",
                            "ffmpeg concat",
                            "Video concatenado está vacío"
                        )
                        print(f"{Colors.RED}✗ Error: video vacío{Colors.NC}")

                except subprocess.CalledProcessError as e:
                    error_logger.add_error(
                        "PASO 7: Concatenar segmentos sin pausas",
                        ' '.join(e.cmd),
                        e.stderr or "Error concatenando segmentos"
                    )
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
    if args.fix_rate_not_truncate is not None:
        print(f"{Colors.GREEN}✅ {test_srt}{Colors.NC}")

    # Mostrar resumen de errores si los hay
    if args.test or error_logger.has_errors() or error_logger.warnings:
        error_logger.print_summary()

    if args.test or args.only_remove_breaks:
        print(f"{Colors.YELLOW}⚠️  Conservando: {temp_dir}{Colors.NC}")
    else:
        print(f"{Colors.YELLOW}Limpiando temporales...{Colors.NC}")
        # shutil.rmtree(temp_dir)  # Descomentar cuando esté probado

    print(f"{Colors.GREEN}¡Proceso completado!{Colors.NC}")

def install_dependencies():
    """Instala requisitos desde este único archivo Python."""
    system = platform.system()
    if not shutil.which("ffmpeg"):
        if system == "Darwin":
            if not shutil.which("brew"):
                subprocess.run(["/bin/bash", "-c", "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"], check=True)
            command = ["brew", "install", "ffmpeg"]
        elif system == "Windows": command = ["winget", "install", "--id", "Gyan.FFmpeg", "-e"]
        elif shutil.which("apt-get"): command = ["sudo", "apt-get", "install", "-y", "ffmpeg"]
        elif shutil.which("dnf"): command = ["sudo", "dnf", "install", "-y", "ffmpeg"]
        else: raise RuntimeError("Instalá FFmpeg manualmente: no se encontró un gestor compatible")
        subprocess.run(command, check=True)
    subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "gTTS", "pydub", "edge-tts", "pyttsx3", "yt-dlp"], check=True)
    print("✅ Dependencias listas.")


def fetch_web_asset(url: str) -> bytes:
    """Descarga un asset de GitHub; usa GITHUB_TOKEN si el repo es privado."""
    headers = {'User-Agent': 'Video-Audio-TTS-Synchronizer'}
    token = os.environ.get('GITHUB_TOKEN')
    if token:
        headers['Authorization'] = f'Bearer {token}'
    return urlopen(Request(url, headers=headers), timeout=15).read()


WEB_ASSET_NAMES = ('index.html', 'styles.css', 'app.js', 'favicon.svg')
# `main` es el destino estable; la rama publicada conserva el fallback mientras
# esos assets llegan a main, para que el script autónomo siga siendo instalable.
WEB_ASSETS_URLS = (
    'https://raw.githubusercontent.com/patchamama/Video-Audio-TTS-Synchronizer/main/web/',
    'https://raw.githubusercontent.com/patchamama/Video-Audio-TTS-Synchronizer/claude/enhance-tts-subtitle-detection-01DCWM9NWFVeBvyqAHEuXXcR/web/',
)


def ensure_web_assets(web_dir: Optional[Path] = None, fetcher=None) -> Optional[Path]:
    """Descarga los assets web faltantes y devuelve el directorio completo.

    Si GitHub no está disponible, el servidor conserva su UI mínima integrada.
    """
    web_dir = web_dir or Path(__file__).resolve().parent / 'web'
    fetcher = fetcher or fetch_web_asset
    missing = [name for name in WEB_ASSET_NAMES if not (web_dir / name).is_file()]
    if missing:
        try:
            web_dir.mkdir(parents=True, exist_ok=True)
            for name in missing:
                data = None
                for base_url in WEB_ASSETS_URLS:
                    try:
                        data = fetcher(base_url + name)
                        if data:
                            break
                    except (OSError, ValueError, URLError):
                        continue
                if not data:
                    raise OSError(f'GitHub no devolvió el asset: {name}')
                target = web_dir / name
                temporary = target.with_suffix(target.suffix + '.tmp')
                temporary.write_bytes(data)
                temporary.replace(target)
        except (OSError, ValueError, URLError) as error:
            print(f"{Colors.YELLOW}⚠️  No se pudo descargar la UI web: {error}.{Colors.NC}")
            print(f"{Colors.YELLOW}   Si el repositorio es privado, definí GITHUB_TOKEN antes de iniciar el script. Usando interfaz mínima.{Colors.NC}")
    return web_dir if all((web_dir / name).is_file() for name in WEB_ASSET_NAMES) else None


def start_web_ui(port: int = 8765):
    """UI local con progreso en vivo, resultados y reproducción sincronizada."""
    jobs = {}
    result_extensions = {'.wav', '.aac', '.mp3', '.ogg', '.m4a', '.mkv', '.mp4', '.mov', '.avi', '.webm', '.srt'}
    audio_extensions = {'.wav', '.aac', '.mp3', '.ogg', '.m4a'}
    video_extensions = {'.mkv', '.mp4', '.mov', '.avi', '.webm'}

    def existing_results():
        """Archivos ya presentes, agrupados para mostrarlos al abrir la UI."""
        all_files = [path for path in Path.cwd().iterdir() if path.is_file() and path.suffix.lower() in result_extensions]
        ordered = sorted(all_files, key=lambda path: (0 if path.suffix.lower() in video_extensions else 1 if path.suffix.lower() in audio_extensions else 2, path.name.lower()))
        return [{'name': path.name, 'url': f'/existing?name={quote(path.name)}',
                 'audio': path.suffix.lower() in audio_extensions, 'deletable': True} for path in ordered]
    web_dir = ensure_web_assets()
    page = """<!doctype html><html lang=es><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><title>Video TTS · Vista mínima</title><style>:root{font:16px system-ui;color:#253238;background:#f4f7f5}body{max-width:680px;margin:auto;padding:1.5rem}form,pre,#results{display:grid;gap:12px;background:#fff;padding:1.2rem;border-radius:12px;margin:1rem 0;box-shadow:0 2px 10px #18382b0d}label{display:grid;gap:.35rem}input,select,button{padding:.7rem;border:1px solid #dce5e1;border-radius:8px}button{background:#256a58;color:#fff;font-weight:700;cursor:pointer}pre{white-space:pre-wrap;max-height:320px;overflow:auto}a{display:block;color:#256a58;font-weight:650;margin:.5rem 0}#options{display:grid;gap:.5rem}</style><main><h1>🎙️ Video TTS <small id=version></small></h1><p>Vista mínima servida directamente por el backend.</p><form id=minimalForm><label>📝 SRT de esta carpeta <select id=localSrt><option value="">Seleccioná…</option></select></label><label>o subir SRT <input id=srt type=file accept=.srt></label><label>🎬 Video de esta carpeta <select id=localVideo><option value="">Sin video</option></select></label><label>o subir video <input id=video type=file accept="video/*"></label><label>🌐 Idioma <select id=lang name=lang><option value=es>Español</option><option value=en>English</option><option value=de>Deutsch</option><option value=fr>Français</option><option value=it>Italiano</option><option value=pt>Português</option></select></label><div id=options></div><button>✨ Procesar</button></form><p id=status>Cargando configuración del backend…</p><pre id=output></pre><div id=results></div></main><script>const $=s=>document.querySelector(s),read=async f=>{if(!f)return null;let text='',bytes=new Uint8Array(await f.arrayBuffer());for(const b of bytes)text+=String.fromCharCode(b);return{name:f.name,data:btoa(text)}},add=(select,names)=>names.forEach(name=>select.add(new Option(name,name))),selected=async(input,local)=>local.value?{local:local.value}:read(input.files[0]);async function poll(id){const data=await fetch('/status?id='+encodeURIComponent(id)).then(r=>r.json());$('#output').textContent=data.output||data.error||'';if(!data.done)return setTimeout(()=>poll(id),700);$('#status').textContent='✅ Procesamiento finalizado';$('#results').replaceChildren(...(data.files||[]).map(file=>{const link=document.createElement('a');link.href=file.url;link.download=file.name;link.textContent='⬇ '+file.name;return link}))}async function load(){try{const[info,files,options]=await Promise.all([fetch('/info').then(r=>r.json()),fetch('/files').then(r=>r.json()),fetch('/options').then(r=>r.json())]);$('#version').textContent='v'+info.version;add($('#localSrt'),files.srt||[]);add($('#localVideo'),files.video||[]);$('#options').replaceChildren(...options.map(option=>{const label=document.createElement('label'),input=document.createElement('input');input.type='checkbox';input.name=option.name;label.append(input,' '+option.label);return label}));$('#status').textContent='Esperando un SRT.'}catch(error){$('#status').textContent='No se pudo cargar la configuración del backend: '+error.message}}load();$('#minimalForm').onsubmit=async event=>{event.preventDefault();const srt=await selected($('#srt'),$('#localSrt'));if(!srt){$('#status').textContent='Seleccioná o subí un SRT.';return}$('#status').textContent='⏳ Preparando procesamiento…';const video=await selected($('#video'),$('#localVideo')),opts=Object.fromEntries(new FormData(event.currentTarget));for(const key of ['solo_audio','no_truncate','optimize_rate','fix_rate_not_truncate','no_freeze','remove_breaks','only_remove_breaks'])opts[key]=opts[key]==='on';const response=await fetch('/run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({srt,video,opts})}),job=await response.json();if(!job.id){$('#status').textContent='Error: '+(job.error||'No se pudo crear el trabajo');return}poll(job.id)}</script></html>"""

    def run_job(job, command):
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        for line in process.stdout:
            clean_line = re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '', line)
            print(clean_line, end='', flush=True)
            job['output'] += clean_line
        process.wait()
        job['done'] = True
        extensions = {'.wav', '.aac', '.mp3', '.mkv', '.mp4', '.srt'}
        job['files'] = [
            p for root in (job['directory'], Path.cwd()) for p in root.iterdir()
            if p.is_file() and p.suffix.lower() in extensions
            and (root == job['directory'] or p.stat().st_mtime >= job['started_at'])
        ]

    class Handler(http.server.BaseHTTPRequestHandler):
        def write_body(self, data):
            """No registra un traceback cuando el navegador cancela una descarga."""
            try:
                self.wfile.write(data)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def send_json(self, data, status=200):
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.write_body(json.dumps(data).encode())

        def send_file(self, path):
            """Sirve archivos grandes por rangos, necesario para audio/video HTML5."""
            size = path.stat().st_size
            start, end = 0, size - 1
            range_header = self.headers.get('Range', '')
            match = re.fullmatch(r'bytes=(\d*)-(\d*)', range_header)
            if match:
                if match.group(1):
                    start = int(match.group(1))
                if match.group(2):
                    end = min(int(match.group(2)), end)
                if start > end or start >= size:
                    self.send_error(416)
                    return
                self.send_response(206)
                self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
            else:
                self.send_response(200)
            self.send_header('Content-Type', mimetypes.guess_type(path.name)[0] or 'application/octet-stream')
            self.send_header('Accept-Ranges', 'bytes')
            self.send_header('Content-Length', str(end - start + 1))
            self.end_headers()
            try:
                with path.open('rb') as source:
                    source.seek(start)
                    remaining = end - start + 1
                    while remaining:
                        chunk = source.read(min(64 * 1024, remaining))
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                        remaining -= len(chunk)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def send_zip(self, paths):
            """Empaqueta resultados locales seleccionados sin exponer rutas arbitrarias."""
            output = io.BytesIO()
            with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
                for path in paths:
                    archive.write(path, path.name)
            payload = output.getvalue()
            self.send_response(200)
            self.send_header('Content-Type', 'application/zip')
            self.send_header('Content-Disposition', 'attachment; filename="video-tts-resultados.zip"')
            self.send_header('Content-Length', str(len(payload)))
            self.end_headers()
            self.write_body(payload)

        def do_GET(self):
            parsed = urlparse(self.path)
            query = parse_qs(parsed.query)
            if parsed.path == '/favicon.svg':
                try:
                    progress = int(query.get('progress', [''])[0])
                except ValueError:
                    progress = None
                label = f'{max(0, min(100, progress))}%' if progress is not None else '▶'
                svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect x="3" y="8" width="58" height="48" rx="9" fill="#256a58"/><text x="32" y="39" text-anchor="middle" fill="white" font-family="Arial,sans-serif" font-size="20" font-weight="700">{label}</text></svg>'
                self.send_response(200)
                self.send_header('Content-Type', 'image/svg+xml')
                self.send_header('Cache-Control', 'no-store, max-age=0')
                self.end_headers()
                self.write_body(svg.encode())
                return
            if parsed.path == '/info':
                return self.send_json({'version': APP_VERSION})
            if parsed.path == '/notes':
                content = NOTES_FILE.read_text(encoding='utf-8') if NOTES_FILE.is_file() else ''
                return self.send_json({'content': content, 'count': count_notes(content), 'tracked': NOTES_FILE.is_file()})
            if parsed.path == '/api/tts':
                engines = get_available_tts()
                return self.send_json({
                    'tts': engines,
                    'languages': sorted({language for engine in engines for language in engine['languages']}),
                    'language_names': LANGUAGE_NAMES,
                })
            if parsed.path == '/options':
                def option(name, spanish, english, **extra):
                    # "label" se mantiene por compatibilidad con clientes anteriores.
                    return {'name': name, 'label': spanish, 'label_es': spanish, 'label_en': english, **extra}
                return self.send_json([
                    option('solo_audio', 'Solo audio', 'Audio only'),
                    option('no_truncate', 'No truncar', 'Do not truncate'),
                    option('optimize_rate', 'Optimizar rate tras 50 entradas', 'Optimize rate after 50 entries'),
                    option('fix_rate_not_truncate', 'Audio plano sin truncar ni pausas SRT', 'Plain audio without truncation or SRT pauses', rate_name='fix_rate_not_truncate_rate', default=200, pause_name='fix_rate_not_truncate_pause', pause_default=1000),
                    option('no_freeze', 'No freeze', 'No freeze'),
                    option('remove_breaks', 'Eliminar pausas', 'Remove pauses'),
                    option('only_remove_breaks', 'Solo eliminar pausas', 'Only remove pauses'),
                ])
            if parsed.path == '/files':
                return self.send_json({
                    'srt': [p.name for p in Path.cwd().iterdir() if p.is_file() and p.suffix.lower() == '.srt'],
                    'video': [p.name for p in Path.cwd().iterdir() if p.is_file() and p.suffix.lower() in video_extensions],
                    'audio': [p.name for p in Path.cwd().iterdir() if p.is_file() and p.suffix.lower() in audio_extensions],
                    'results': existing_results(),
                    'temp_dirs': sorted(path.name for path in Path.cwd().glob('temp_*') if path.is_dir() and not path.is_symlink() and (path / 'checkpoint.json').is_file()),
                })
            if parsed.path == '/minimal':
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.end_headers()
                self.write_body(page.encode())
                return
            if parsed.path.startswith('/web/') and web_dir:
                asset = web_dir / Path(parsed.path).name
                if asset.is_file():
                    self.send_response(200)
                    self.send_header('Content-Type', mimetypes.guess_type(asset.name)[0] or 'text/plain')
                    self.end_headers()
                    self.write_body(asset.read_bytes())
                    return
            if parsed.path == '/status':
                job = jobs.get(query.get('id', [''])[0])
                if not job:
                    return self.send_json({'error': 'Job not found'})
                files = [{'name': p.name, 'url': f"/file?id={job['id']}&name={p.name}", 'audio': p.suffix.lower() in {'.wav', '.aac', '.mp3'}} for p in job.get('files', [])]
                return self.send_json({'output': job['output'], 'done': job['done'], 'files': files})
            if parsed.path == '/file':
                job = jobs.get(query.get('id', [''])[0])
                name = Path(query.get('name', [''])[0]).name
                path = next((p for p in job.get('files', []) if p.name == name), None) if job else None
                if not path or not path.exists():
                    self.send_error(404)
                    return
                return self.send_file(path)
            if parsed.path == '/existing':
                path = Path.cwd() / Path(query.get('name', [''])[0]).name
                if not path.is_file() or path.suffix.lower() not in result_extensions:
                    self.send_error(404)
                    return
                return self.send_file(path)
            if parsed.path == '/download':
                paths = []
                for name in query.get('name', []):
                    path = Path.cwd() / Path(name).name
                    if not path.is_file() or path.suffix.lower() not in result_extensions:
                        self.send_error(404)
                        return
                    paths.append(path)
                if not paths:
                    self.send_error(400, 'Seleccioná al menos un archivo')
                    return
                return self.send_zip(paths)
            if web_dir:
                self.send_response(302)
                self.send_header('Location', '/web/index.html')
                self.end_headers()
                return
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.write_body(page.encode())

        def do_POST(self):
            path = urlparse(self.path).path
            if path not in {'/run', '/api/generate-audio', '/delete', '/delete-temp-folders', '/notes'}:
                self.send_error(404)
                return
            try:
                payload = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                if path == '/notes':
                    content = str(payload.get('content', ''))
                    NOTES_FILE.write_text(content, encoding='utf-8')
                    return self.send_json({'content': content, 'count': count_notes(content), 'github': sync_notes_to_github()})
                if path == '/delete':
                    target = Path.cwd() / Path(payload.get('name', '')).name
                    if not target.is_file() or target.suffix.lower() not in result_extensions:
                        raise ValueError('El archivo no existe o no se puede borrar')
                    target.unlink()
                    return self.send_json({'deleted': target.name})
                if path == '/delete-temp-folders':
                    deleted = remove_temp_directories(Path.cwd())
                    return self.send_json({'deleted': deleted, 'count': len(deleted)})
                directory = Path(tempfile.mkdtemp(prefix='video_tts_web_'))
                if path == '/api/generate-audio':
                    audio, metadata = generate_api_audio(payload, directory)
                    job = {'id': uuid.uuid4().hex, 'directory': directory, 'started_at': time.time(), 'output': '', 'done': True, 'files': [audio]}
                    jobs[job['id']] = job
                    metadata['audio'] = {'name': audio.name, 'url': f"/file?id={job['id']}&name={audio.name}"}
                    return self.send_json(metadata)

                def local_or_saved(item):
                    if not item:
                        return None
                    if item.get('local'):
                        candidate = Path.cwd() / Path(item['local']).name
                        if not candidate.is_file():
                            raise ValueError('El archivo local seleccionado no existe')
                        return candidate
                    path = directory / Path(item['name']).name
                    path.write_bytes(base64.b64decode(item['data']))
                    return path

                opts = payload.get('opts', {})
                youtube_url = str(opts.get('youtube') or '').strip()
                continue_from = str(opts.get('continue_from') or '').strip()
                srt = local_or_saved(payload.get('srt'))
                video = local_or_saved(payload.get('video'))
                command = [sys.executable, '-u', str(Path(__file__).resolve())]
                if youtube_url:
                    command.extend(['--youtube', youtube_url])
                elif continue_from:
                    checkpoint_dir = Path.cwd() / Path(continue_from).name
                    if not checkpoint_dir.is_dir() or not (checkpoint_dir / 'checkpoint.json').is_file():
                        raise ValueError('La carpeta temporal elegida no contiene un checkpoint válido')
                    command.extend(['--continue', str(checkpoint_dir)])
                elif srt:
                    command.append(str(srt))
                    if video:
                        command.append(str(video))
                else:
                    raise ValueError('Seleccioná un SRT, una URL de YouTube o una carpeta temporal')
                for key in ('solo_audio', 'no_truncate', 'optimize_rate', 'no_freeze', 'remove_breaks', 'only_remove_breaks'):
                    if opts.get(key):
                        command.append('--' + key.replace('_', '-'))
                if opts.get('fix_rate_not_truncate'):
                    command.extend(['--fix-rate-not-truncate', str(opts.get('fix_rate_not_truncate_rate') or 200)])
                    command.extend(['--fix-rate-not-truncate-pause', str(opts.get('fix_rate_not_truncate_pause') or 1000)])
                if opts.get('lang'):
                    command.extend(['--lang', str(opts['lang'])])
                if opts.get('tts'):
                    command.extend(['--tts', str(opts['tts'])])
                if opts.get('voice'):
                    command.extend(['--voice', str(opts['voice'])])
                if opts.get('test'):
                    command.extend(['--test', str(opts.get('test_count') or 30)])
                job = {'id': uuid.uuid4().hex, 'directory': directory, 'started_at': time.time(), 'output': '▶ Trabajo creado. Iniciando backend...\n', 'done': False, 'files': []}
                jobs[job['id']] = job
                threading.Thread(target=run_job, args=(job, command), daemon=True).start()
                self.send_json({'id': job['id'], 'command': command})
            except Exception as error:
                self.send_json({'error': str(error)}, status=400)

        def log_message(self, *args):
            pass

    server = http.server.ThreadingHTTPServer(('127.0.0.1', port), Handler)
    webbrowser.open(f'http://127.0.0.1:{port}')
    print(f'🌐 UI: http://127.0.0.1:{port}')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()


if __name__ == "__main__":
    main()
