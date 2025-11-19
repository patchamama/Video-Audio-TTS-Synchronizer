#!/usr/bin/env python3
"""
Video TTS Synchronizer - Versión Multiplataforma
Soporta: Windows, macOS, Linux
Adapta automáticamente el motor TTS según el sistema operativo.
"""

import os
import sys
import subprocess
import platform
import argparse
from pathlib import Path
from dataclasses import dataclass
from typing import List, Tuple, Optional

try:
    import pysrt
    from pydub import AudioSegment
except ImportError:
    print("❌ Error: Faltan dependencias básicas")
    print("Instala con: pip install pysrt pydub")
    sys.exit(1)


@dataclass
class SubtitleSegment:
    """Representa un segmento de subtítulo"""
    index: int
    start_ms: int
    end_ms: int
    duration_ms: int
    text: str


class PlatformDetector:
    """Detecta la plataforma actual"""
    
    @staticmethod
    def get_os() -> str:
        system = platform.system()
        if system == "Darwin":
            return "macos"
        elif system == "Windows":
            return "windows"
        elif system == "Linux":
            return "linux"
        return "unknown"


class TTSEngineFactory:
    """Factory para crear el motor TTS apropiado"""
    
    @staticmethod
    def create_engine(engine_type: str, voice_id: Optional[str] = None, lang: str = "es"):
        """Crea una instancia del motor TTS especificado"""
        
        if engine_type == "pyttsx3":
            return Pyttsx3Engine(voice_id, lang)
        elif engine_type == "edge":
            return EdgeTTSEngine(voice_id or f"{lang}-ES-AlvaroNeural")
        elif engine_type == "gtts":
            return GTTSEngine(lang)
        elif engine_type == "espeak":
            return ESpeakEngine(lang)
        else:
            raise ValueError(f"Motor TTS desconocido: {engine_type}")
    
    @staticmethod
    def get_default_engine(os_type: str) -> str:
        """Retorna el motor por defecto para cada OS"""
        defaults = {
            'windows': 'pyttsx3',
            'macos': 'pyttsx3',
            'linux': 'espeak'
        }
        return defaults.get(os_type, 'edge')
    
    @staticmethod
    def list_available_engines(os_type: str) -> List[str]:
        """Lista motores disponibles para el OS"""
        engines = []
        
        # pyttsx3 disponible en todos
        try:
            import pyttsx3
            engines.append('pyttsx3')
        except ImportError:
            pass
        
        # espeak (Linux)
        if os_type == 'linux':
            try:
                result = subprocess.run(['espeak', '--version'], 
                                      capture_output=True, timeout=2)
                if result.returncode == 0:
                    engines.append('espeak')
            except:
                pass
        
        # edge-tts (todos, requiere internet)
        try:
            import edge_tts
            engines.append('edge')
        except ImportError:
            pass
        
        # gTTS (todos, requiere internet)
        try:
            from gtts import gTTS
            engines.append('gtts')
        except ImportError:
            pass
        
        return engines


class Pyttsx3Engine:
    """Motor TTS usando pyttsx3 (nativo)"""
    
    def __init__(self, voice_id: Optional[str] = None, lang: str = "es"):
        try:
            import pyttsx3
        except ImportError:
            raise ImportError("pyttsx3 no instalado. Instala con: pip install pyttsx3")
        
        self.engine = pyttsx3.init()
        
        if voice_id:
            self.engine.setProperty('voice', voice_id)
        else:
            self._set_voice_by_language(lang)
    
    def _set_voice_by_language(self, lang: str):
        """Selecciona voz por idioma"""
        voices = self.engine.getProperty('voices')
        
        lang_keywords = {
            'es': ['es-', 'spanish', 'español'],
            'en': ['en-', 'english'],
            'de': ['de-', 'german', 'deutsch']
        }
        
        keywords = lang_keywords.get(lang, ['en-'])
        
        for voice in voices:
            name_lower = voice.name.lower()
            id_lower = voice.id.lower()
            
            if any(k in name_lower or k in id_lower for k in keywords):
                self.engine.setProperty('voice', voice.id)
                print(f"🎤 Voz seleccionada: {voice.name}")
                return
        
        print(f"⚠️  No se encontró voz para '{lang}', usando por defecto")
    
    def generate(self, text: str, output_file: Path) -> int:
        """Genera audio"""
        self.engine.save_to_file(text, str(output_file))
        self.engine.runAndWait()
        
        audio = AudioSegment.from_file(str(output_file))
        return len(audio)
    
    @staticmethod
    def list_voices():
        """Lista voces disponibles"""
        import pyttsx3
        engine = pyttsx3.init()
        voices = engine.getProperty('voices')
        
        print("\n🎤 VOCES DISPONIBLES (pyttsx3):")
        print("=" * 60)
        for i, voice in enumerate(voices, 1):
            print(f"{i}. {voice.name}")
            print(f"   ID: {voice.id}")
            if hasattr(voice, 'languages'):
                print(f"   Idiomas: {voice.languages}")
            print()


class EdgeTTSEngine:
    """Motor TTS usando Microsoft Edge"""
    
    def __init__(self, voice: str):
        try:
            import edge_tts
        except ImportError:
            raise ImportError("edge-tts no instalado. Instala con: pip install edge-tts")
        
        self.voice = voice
        print(f"🎤 Voz edge-tts: {voice}")
    
    def generate(self, text: str, output_file: Path) -> int:
        """Genera audio"""
        import edge_tts
        import asyncio
        
        async def _generate():
            communicate = edge_tts.Communicate(text, self.voice)
            await communicate.save(str(output_file))
        
        asyncio.run(_generate())
        
        audio = AudioSegment.from_file(str(output_file))
        return len(audio)
    
    @staticmethod
    def list_voices(lang_filter: Optional[str] = None):
        """Lista voces disponibles"""
        import edge_tts
        import asyncio
        
        async def _list():
            voices = await edge_tts.list_voices()
            
            print("\n🎤 VOCES DISPONIBLES (edge-tts):")
            print("=" * 60)
            
            if lang_filter:
                voices = [v for v in voices if v['Locale'].startswith(lang_filter)]
            
            for voice in sorted(voices, key=lambda x: x['ShortName'])[:20]:
                gender = "👨" if voice['Gender'] == 'Male' else "👩"
                print(f"{gender} {voice['ShortName']}")
                print(f"   Nombre: {voice['FriendlyName']}")
                print()
            
            if len(voices) > 20:
                print(f"... y {len(voices) - 20} voces más")
        
        asyncio.run(_list())


class GTTSEngine:
    """Motor TTS usando Google"""
    
    def __init__(self, lang: str = "es"):
        try:
            from gtts import gTTS
        except ImportError:
            raise ImportError("gtts no instalado. Instala con: pip install gtts")
        
        self.lang = lang
        print(f"🎤 Usando gTTS con idioma: {lang}")
    
    def generate(self, text: str, output_file: Path) -> int:
        """Genera audio"""
        from gtts import gTTS
        
        tts = gTTS(text=text, lang=self.lang, slow=False)
        tts.save(str(output_file))
        
        audio = AudioSegment.from_file(str(output_file))
        return len(audio)


class ESpeakEngine:
    """Motor TTS usando eSpeak (Linux)"""
    
    def __init__(self, lang: str = "es"):
        # Verificar que espeak esté instalado
        try:
            subprocess.run(['espeak', '--version'], 
                         capture_output=True, check=True, timeout=2)
        except:
            raise ImportError("espeak no instalado. Instala con: sudo apt install espeak")
        
        self.lang = lang
        print(f"🎤 Usando eSpeak con idioma: {lang}")
    
    def generate(self, text: str, output_file: Path) -> int:
        """Genera audio"""
        # Generar con espeak
        wav_file = output_file.with_suffix('.wav')
        
        subprocess.run([
            'espeak',
            '-v', self.lang,
            '-w', str(wav_file),
            text
        ], check=True)
        
        # Convertir a formato deseado
        audio = AudioSegment.from_file(str(wav_file))
        
        if output_file.suffix != '.wav':
            audio.export(str(output_file), format=output_file.suffix[1:])
            wav_file.unlink()
        
        return len(audio)


class VideoTTSProcessor:
    """Procesador principal multiplataforma"""
    
    def __init__(self, video_path: str, subtitle_path: str, output_path: str,
                 tts_engine: str, voice_id: Optional[str] = None, lang: str = "es"):
        self.video_path = Path(video_path)
        self.subtitle_path = Path(subtitle_path)
        self.output_path = Path(output_path)
        self.lang = lang
        self.temp_dir = Path("temp_tts_processing")
        self.temp_dir.mkdir(exist_ok=True)
        
        # Crear motor TTS
        self.tts_engine = TTSEngineFactory.create_engine(tts_engine, voice_id, lang)
    
    def parse_subtitles(self) -> List[SubtitleSegment]:
        """Lee subtítulos"""
        print(f"📖 Leyendo: {self.subtitle_path}")
        subs = pysrt.open(str(self.subtitle_path), encoding='utf-8')
        
        segments = []
        for i, sub in enumerate(subs):
            start_ms = (sub.start.hours * 3600000 + sub.start.minutes * 60000 +
                       sub.start.seconds * 1000 + sub.start.milliseconds)
            end_ms = (sub.end.hours * 3600000 + sub.end.minutes * 60000 +
                     sub.end.seconds * 1000 + sub.end.milliseconds)
            
            segments.append(SubtitleSegment(
                index=i,
                start_ms=start_ms,
                end_ms=end_ms,
                duration_ms=end_ms - start_ms,
                text=sub.text.replace('\n', ' ').strip()
            ))
        
        print(f"✅ {len(segments)} segmentos")
        return segments
    
    def generate_tts_audio(self, text: str, output_file: Path) -> int:
        """Genera audio TTS"""
        print(f"🎤 '{text[:50]}...'")
        duration = self.tts_engine.generate(text, output_file)
        print(f"   ⏱️  {duration/1000:.2f}s")
        return duration
    
    def generate_all_tts(self, segments: List[SubtitleSegment]):
        """Genera todos los audios"""
        print("\n🎵 Generando TTS...")
        audio_files = []
        
        for segment in segments:
            if not segment.text.strip():
                continue
            
            audio_file = self.temp_dir / f"tts_{segment.index:04d}.mp3"
            duration = self.generate_tts_audio(segment.text, audio_file)
            audio_files.append((audio_file, duration, segment))
        
        return audio_files
    
    def create_adjusted_timeline(self, segments, audio_files):
        """Crea timeline ajustada"""
        print("\n⚙️  Calculando timeline...")
        timeline = []
        current_time = 0
        
        for i, (audio_file, tts_duration_ms, segment) in enumerate(audio_files):
            padding = 200
            final_duration = max(tts_duration_ms, segment.duration_ms) + padding
            
            timeline.append({
                'index': i,
                'start_original': segment.start_ms,
                'end_original': segment.end_ms,
                'start_new': current_time,
                'end_new': current_time + final_duration,
                'duration_new': final_duration,
                'audio_file': audio_file,
                'text': segment.text,
                'extended': tts_duration_ms > segment.duration_ms,
                'extension_ms': final_duration - segment.duration_ms if tts_duration_ms > segment.duration_ms else 0
            })
            
            current_time += final_duration
        
        print(f"✅ Duración: {current_time/1000:.2f}s")
        return timeline
    
    # [Resto de métodos idénticos a la versión Windows: create_video_segments, 
    # combine_audio, combine_video, merge_final, process]
    # ... (copiar del script Windows)
    
    def process(self):
        """Ejecuta el proceso completo"""
        print("\n" + "="*80)
        print("🎬 PROCESANDO VIDEO")
        print("="*80)
        
        segments = self.parse_subtitles()
        audio_files = self.generate_all_tts(segments)
        timeline = self.create_adjusted_timeline(segments, audio_files)
        
        print("\n✨ Proceso de TTS completado")
        print("⚠️  Nota: Implementación completa requiere métodos de video")
        print("    Ver video_tts_windows.py para implementación completa")


def main():
    """Función principal"""
    os_type = PlatformDetector.get_os()
    
    parser = argparse.ArgumentParser(
        description=f"Video TTS Synchronizer - Multiplataforma ({os_type})",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('video', nargs='?', help='Video de entrada')
    parser.add_argument('subtitles', nargs='?', help='Archivo de subtítulos (.srt)')
    parser.add_argument('output', nargs='?', help='Video de salida')
    parser.add_argument('--engine', choices=['pyttsx3', 'edge', 'gtts', 'espeak', 'auto'],
                       default='auto', help='Motor TTS a usar')
    parser.add_argument('-v', '--voice', help='ID de voz específica')
    parser.add_argument('--lang', default='es', help='Idioma (es/en/de)')
    parser.add_argument('--list-voices', action='store_true', 
                       help='Listar voces disponibles')
    parser.add_argument('--list-engines', action='store_true',
                       help='Listar motores TTS disponibles')
    
    args = parser.parse_args()
    
    # Listar motores
    if args.list_engines:
        engines = TTSEngineFactory.list_available_engines(os_type)
        print(f"\n🎤 MOTORES TTS DISPONIBLES EN {os_type.upper()}:")
        print("="*60)
        for engine in engines:
            print(f"  • {engine}")
        print()
        return
    
    # Listar voces
    if args.list_voices:
        if args.engine == 'pyttsx3' or (args.engine == 'auto' and os_type != 'linux'):
            try:
                Pyttsx3Engine.list_voices()
            except:
                print("❌ pyttsx3 no disponible")
        
        if args.engine == 'edge' or args.engine == 'auto':
            try:
                EdgeTTSEngine.list_voices(args.lang)
            except:
                print("❌ edge-tts no disponible")
        
        return
    
    # Validar argumentos
    if not all([args.video, args.subtitles, args.output]):
        parser.print_help()
        return
    
    # Seleccionar motor
    if args.engine == 'auto':
        available = TTSEngineFactory.list_available_engines(os_type)
        if not available:
            print("❌ No hay motores TTS disponibles")
            print("Instala al menos uno:")
            print("  pip install pyttsx3 edge-tts gtts")
            sys.exit(1)
        
        engine = TTSEngineFactory.get_default_engine(os_type)
        if engine not in available:
            engine = available[0]
        
        print(f"🎤 Motor auto-seleccionado: {engine}")
    else:
        engine = args.engine
    
    # Procesar
    try:
        processor = VideoTTSProcessor(
            video_path=args.video,
            subtitle_path=args.subtitles,
            output_path=args.output,
            tts_engine=engine,
            voice_id=args.voice,
            lang=args.lang
        )
        
        processor.process()
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
