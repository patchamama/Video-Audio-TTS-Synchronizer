#!/usr/bin/env python3
"""
Sistema de Verificación Pre-Ejecución - Versión Multiplataforma
Detecta automáticamente el sistema operativo y adapta los tests.
Soporta: Windows, macOS, Linux
"""

import os
import sys
import subprocess
import platform
from pathlib import Path
from typing import Tuple, List, Optional

# Colores para terminal
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'

def print_header(text: str):
    """Imprime un encabezado destacado"""
    print("\n" + "=" * 80)
    print(f"{Colors.BOLD}{Colors.BLUE}{text}{Colors.END}")
    print("=" * 80)

def print_test(name: str):
    """Imprime nombre de test"""
    print(f"\n{Colors.BOLD}▶ {name}{Colors.END}")

def print_success(msg: str):
    """Imprime mensaje de éxito"""
    print(f"  {Colors.GREEN}✓{Colors.END} {msg}")

def print_error(msg: str):
    """Imprime mensaje de error"""
    print(f"  {Colors.RED}✗{Colors.END} {msg}")

def print_warning(msg: str):
    """Imprime advertencia"""
    print(f"  {Colors.YELLOW}⚠{Colors.END} {msg}")

def print_info(msg: str):
    """Imprime información"""
    print(f"  {Colors.BLUE}ℹ{Colors.END} {msg}")


class PlatformDetector:
    """Detecta y proporciona información de la plataforma"""
    
    @staticmethod
    def get_os() -> str:
        """Retorna el sistema operativo"""
        system = platform.system()
        if system == "Darwin":
            return "macos"
        elif system == "Windows":
            return "windows"
        elif system == "Linux":
            return "linux"
        else:
            return "unknown"
    
    @staticmethod
    def get_os_info() -> dict:
        """Retorna información detallada del OS"""
        return {
            'system': platform.system(),
            'release': platform.release(),
            'version': platform.version(),
            'machine': platform.machine(),
            'processor': platform.processor()
        }


class TTSEngineManager:
    """Gestiona motores TTS según la plataforma"""
    
    @staticmethod
    def get_available_engines(os_type: str) -> List[str]:
        """Retorna motores TTS disponibles para el OS"""
        engines = {
            'windows': ['pyttsx3', 'edge-tts', 'gtts'],
            'macos': ['pyttsx3', 'edge-tts', 'gtts'],
            'linux': ['pyttsx3', 'espeak', 'edge-tts', 'gtts']
        }
        return engines.get(os_type, ['edge-tts', 'gtts'])
    
    @staticmethod
    def test_pyttsx3() -> Tuple[bool, str, List[str]]:
        """Prueba pyttsx3 (Windows, macOS, Linux)"""
        try:
            import pyttsx3
            engine = pyttsx3.init()
            voices = engine.getProperty('voices')
            
            voice_names = [v.name for v in voices] if voices else []
            
            if voices:
                return True, f"{len(voices)} voces encontradas", voice_names
            else:
                return False, "Sin voces disponibles", []
        except Exception as e:
            return False, str(e), []
    
    @staticmethod
    def test_espeak() -> Tuple[bool, str]:
        """Prueba espeak (Linux)"""
        try:
            result = subprocess.run(
                ['espeak', '--version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                version = result.stdout.split('\n')[0]
                return True, version
            return False, "No responde"
        except FileNotFoundError:
            return False, "No instalado"
        except Exception as e:
            return False, str(e)
    
    @staticmethod
    def test_edge_tts() -> Tuple[bool, str, int]:
        """Prueba edge-tts (todas las plataformas)"""
        try:
            import edge_tts
            import asyncio
            
            async def get_voice_count():
                voices = await edge_tts.list_voices()
                return len(voices)
            
            count = asyncio.run(get_voice_count())
            return True, "Disponible", count
        except ImportError:
            return False, "No instalado", 0
        except Exception as e:
            return False, str(e), 0
    
    @staticmethod
    def test_gtts() -> Tuple[bool, str]:
        """Prueba gTTS (todas las plataformas)"""
        try:
            from gtts import gTTS
            # Test rápido
            test_text = "test"
            tts = gTTS(text=test_text, lang='es')
            return True, "Disponible"
        except ImportError:
            return False, "No instalado"
        except Exception as e:
            return False, str(e)


class SystemTester:
    """Prueba todos los componentes del sistema"""
    
    def __init__(self):
        self.results = []
        self.temp_dir = Path("test_temp")
        self.temp_dir.mkdir(exist_ok=True)
        self.os_type = PlatformDetector.get_os()
        self.os_info = PlatformDetector.get_os_info()
    
    def add_result(self, test_name: str, success: bool, message: str = ""):
        """Registra resultado de test"""
        self.results.append({
            'test': test_name,
            'success': success,
            'message': message
        })
    
    def test_platform(self) -> bool:
        """Detecta y muestra información de plataforma"""
        print_test("Detectando plataforma")
        
        os_names = {
            'windows': 'Windows',
            'macos': 'macOS',
            'linux': 'Linux',
            'unknown': 'Desconocido'
        }
        
        os_name = os_names.get(self.os_type, 'Desconocido')
        
        print_info(f"Sistema Operativo: {os_name}")
        print_info(f"Versión: {self.os_info['release']}")
        print_info(f"Arquitectura: {self.os_info['machine']}")
        
        if self.os_type == 'unknown':
            print_error("Sistema operativo no soportado completamente")
            print_warning("Algunos tests pueden fallar")
            self.add_result("Plataforma", False, "No soportado")
            return False
        else:
            print_success(f"Plataforma soportada: {os_name}")
            self.add_result("Plataforma", True, os_name)
            return True
    
    def test_python_version(self) -> bool:
        """Verifica versión de Python"""
        print_test("Verificando Python")
        
        version = sys.version_info
        version_str = f"{version.major}.{version.minor}.{version.micro}"
        
        print_info(f"Versión: Python {version_str}")
        print_info(f"Ejecutable: {sys.executable}")
        
        if version.major >= 3 and version.minor >= 8:
            print_success("Versión de Python compatible (3.8+)")
            self.add_result("Python", True)
            return True
        else:
            print_error(f"Python 3.8+ requerido, tienes {version_str}")
            print_info("Descarga desde: https://www.python.org/")
            self.add_result("Python", False, f"Versión {version_str} < 3.8")
            return False
    
    def test_ffmpeg(self) -> bool:
        """Verifica instalación de FFmpeg"""
        print_test("Verificando FFmpeg")
        
        try:
            result = subprocess.run(
                ['ffmpeg', '-version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                version_line = result.stdout.split('\n')[0]
                print_info(version_line)
                print_success("FFmpeg instalado y funcionando")
                self.add_result("FFmpeg", True)
                return True
            else:
                print_error("FFmpeg no responde correctamente")
                self.add_result("FFmpeg", False, "No responde")
                return False
                
        except FileNotFoundError:
            print_error("FFmpeg no encontrado en el sistema")
            
            if self.os_type == 'macos':
                print_info("Instala con: brew install ffmpeg")
            elif self.os_type == 'linux':
                print_info("Instala con: sudo apt install ffmpeg")
            elif self.os_type == 'windows':
                print_info("Descarga desde: https://ffmpeg.org/download.html")
            
            self.add_result("FFmpeg", False, "No instalado")
            return False
        except Exception as e:
            print_error(f"Error al verificar FFmpeg: {e}")
            self.add_result("FFmpeg", False, str(e))
            return False
    
    def test_python_packages(self) -> bool:
        """Verifica paquetes de Python instalados"""
        print_test("Verificando paquetes de Python")
        
        required_packages = {
            'pysrt': 'pysrt',
            'pydub': 'pydub'
        }
        
        all_installed = True
        missing_packages = []
        
        for package_name, import_name in required_packages.items():
            try:
                __import__(import_name)
                print_success(f"{package_name} instalado")
            except ImportError:
                print_error(f"{package_name} NO instalado")
                missing_packages.append(package_name)
                all_installed = False
        
        if all_installed:
            self.add_result("Paquetes Python", True)
        else:
            print_warning("\nPara instalar paquetes faltantes:")
            print_info(f"pip install {' '.join(missing_packages)}")
            self.add_result("Paquetes Python", False, f"Faltan: {', '.join(missing_packages)}")
        
        return all_installed
    
    def test_tts_engines(self) -> bool:
        """Verifica motores TTS disponibles"""
        print_test(f"Verificando motores TTS para {self.os_type.upper()}")
        
        available_engines = TTSEngineManager.get_available_engines(self.os_type)
        working_engines = []
        
        print_info(f"Motores a verificar: {', '.join(available_engines)}")
        print()
        
        # Test pyttsx3 (nativo)
        if 'pyttsx3' in available_engines:
            print_info("Probando pyttsx3 (voces nativas)...")
            success, message, voices = TTSEngineManager.test_pyttsx3()
            
            if success:
                print_success(f"pyttsx3: {message}")
                working_engines.append('pyttsx3')
                
                # Mostrar algunas voces
                if voices:
                    print_info("Voces encontradas:")
                    for voice in voices[:5]:  # Primeras 5
                        print(f"    • {voice}")
                    if len(voices) > 5:
                        print(f"    ... y {len(voices) - 5} más")
            else:
                print_warning(f"pyttsx3: {message}")
                
                # Sugerencias de instalación según OS
                if self.os_type == 'macos':
                    print_info("macOS usa voces del sistema automáticamente")
                elif self.os_type == 'linux':
                    print_info("Instala espeak: sudo apt install espeak")
                elif self.os_type == 'windows':
                    print_info("Instala voces desde Configuración → Idioma")
        
        # Test espeak (Linux)
        if 'espeak' in available_engines and self.os_type == 'linux':
            print_info("Probando espeak (Linux TTS)...")
            success, message = TTSEngineManager.test_espeak()
            
            if success:
                print_success(f"espeak: {message}")
                working_engines.append('espeak')
            else:
                print_warning(f"espeak: {message}")
                print_info("Instala con: sudo apt install espeak")
        
        # Test edge-tts (online)
        if 'edge-tts' in available_engines:
            print_info("Probando edge-tts (Microsoft)...")
            success, message, count = TTSEngineManager.test_edge_tts()
            
            if success:
                print_success(f"edge-tts: {count} voces disponibles")
                working_engines.append('edge-tts')
            else:
                print_warning(f"edge-tts: {message}")
                print_info("Instala con: pip install edge-tts")
        
        # Test gTTS (online)
        if 'gtts' in available_engines:
            print_info("Probando gTTS (Google)...")
            success, message = TTSEngineManager.test_gtts()
            
            if success:
                print_success(f"gTTS: {message}")
                working_engines.append('gtts')
            else:
                print_warning(f"gTTS: {message}")
                print_info("Instala con: pip install gtts")
        
        print()
        if working_engines:
            print_success(f"Motores TTS disponibles: {', '.join(working_engines)}")
            self.add_result("Motores TTS", True, ', '.join(working_engines))
            return True
        else:
            print_error("No hay motores TTS disponibles")
            print_warning("Instala al menos uno de los siguientes:")
            print_info("  • pip install pyttsx3 (voces nativas)")
            print_info("  • pip install edge-tts (Microsoft, requiere internet)")
            print_info("  • pip install gtts (Google, requiere internet)")
            self.add_result("Motores TTS", False, "Ninguno disponible")
            return False
    
    def test_tts_generation(self) -> bool:
        """Prueba generación de audio TTS con el primer motor disponible"""
        print_test("Probando generación de TTS")
        
        # Intentar con cada motor disponible
        engines_to_try = [
            ('pyttsx3', self._test_pyttsx3_generation),
            ('edge-tts', self._test_edge_generation),
            ('gtts', self._test_gtts_generation)
        ]
        
        for engine_name, test_func in engines_to_try:
            try:
                print_info(f"Intentando con {engine_name}...")
                success, message = test_func()
                if success:
                    print_success(f"Audio generado con {engine_name}")
                    self.add_result("Generación TTS", True, engine_name)
                    return True
            except Exception as e:
                print_warning(f"{engine_name} falló: {e}")
                continue
        
        print_error("No se pudo generar audio con ningún motor")
        self.add_result("Generación TTS", False, "Todos fallaron")
        return False
    
    def _test_pyttsx3_generation(self) -> Tuple[bool, str]:
        """Prueba generación con pyttsx3"""
        import pyttsx3
        from pydub import AudioSegment
        
        engine = pyttsx3.init()
        test_file = self.temp_dir / "test_pyttsx3.wav"
        test_text = "Hola, esta es una prueba de audio"
        
        engine.save_to_file(test_text, str(test_file))
        engine.runAndWait()
        
        if not test_file.exists():
            return False, "Archivo no creado"
        
        audio = AudioSegment.from_file(str(test_file))
        duration_s = len(audio) / 1000
        
        test_file.unlink()
        
        return True, f"{duration_s:.2f}s"
    
    def _test_edge_generation(self) -> Tuple[bool, str]:
        """Prueba generación con edge-tts"""
        import edge_tts
        import asyncio
        from pydub import AudioSegment
        
        async def generate():
            test_file = self.temp_dir / "test_edge.mp3"
            text = "Hola, esta es una prueba de audio"
            
            communicate = edge_tts.Communicate(text, "es-ES-AlvaroNeural")
            await communicate.save(str(test_file))
            
            audio = AudioSegment.from_file(str(test_file))
            duration_s = len(audio) / 1000
            
            test_file.unlink()
            
            return duration_s
        
        duration = asyncio.run(generate())
        return True, f"{duration:.2f}s"
    
    def _test_gtts_generation(self) -> Tuple[bool, str]:
        """Prueba generación con gTTS"""
        from gtts import gTTS
        from pydub import AudioSegment
        
        test_file = self.temp_dir / "test_gtts.mp3"
        text = "Hola, esta es una prueba de audio"
        
        tts = gTTS(text=text, lang='es')
        tts.save(str(test_file))
        
        audio = AudioSegment.from_file(str(test_file))
        duration_s = len(audio) / 1000
        
        test_file.unlink()
        
        return True, f"{duration_s:.2f}s"
    
    def test_ffmpeg_operations(self) -> bool:
        """Prueba operaciones básicas de FFmpeg"""
        print_test("Probando operaciones de FFmpeg")
        
        try:
            test_video = self.temp_dir / "test_video.mp4"
            
            print_info("Creando video de prueba...")
            
            result = subprocess.run([
                'ffmpeg', '-y', '-loglevel', 'error',
                '-f', 'lavfi', '-i', 'color=c=blue:s=320x240:d=3',
                '-f', 'lavfi', '-i', 'sine=frequency=1000:duration=3',
                '-c:v', 'libx264', '-c:a', 'aac',
                '-shortest', str(test_video)
            ], capture_output=True, timeout=10)
            
            if result.returncode != 0:
                print_error("No se pudo crear video de prueba")
                self.add_result("Operaciones FFmpeg", False, "No crea video")
                return False
            
            print_success("Video de prueba creado")
            
            # Extraer frame
            test_frame = self.temp_dir / "test_frame.png"
            print_info("Extrayendo frame...")
            
            result = subprocess.run([
                'ffmpeg', '-y', '-loglevel', 'error',
                '-i', str(test_video),
                '-vframes', '1', str(test_frame)
            ], capture_output=True, timeout=5)
            
            if result.returncode != 0:
                print_error("No se pudo extraer frame")
                self.add_result("Operaciones FFmpeg", False, "No extrae frames")
                return False
            
            print_success("Frame extraído correctamente")
            
            # Limpiar
            test_video.unlink()
            test_frame.unlink()
            
            self.add_result("Operaciones FFmpeg", True)
            return True
            
        except Exception as e:
            print_error(f"Error en operaciones FFmpeg: {e}")
            self.add_result("Operaciones FFmpeg", False, str(e))
            return False
    
    def test_srt_parsing(self) -> bool:
        """Prueba lectura de archivos SRT"""
        print_test("Probando lectura de subtítulos SRT")
        
        try:
            import pysrt
            
            test_srt = self.temp_dir / "test.srt"
            
            srt_content = """1
00:00:00,000 --> 00:00:03,000
Este es el primer subtítulo

2
00:00:03,000 --> 00:00:06,000
Este es el segundo subtítulo
"""
            
            test_srt.write_text(srt_content, encoding='utf-8')
            
            subs = pysrt.open(str(test_srt), encoding='utf-8')
            
            if len(subs) != 2:
                print_error(f"Se esperaban 2 subtítulos, se leyeron {len(subs)}")
                self.add_result("Lectura SRT", False, "Lectura incorrecta")
                return False
            
            print_success(f"Archivo SRT leído correctamente ({len(subs)} subtítulos)")
            
            test_srt.unlink()
            
            self.add_result("Lectura SRT", True)
            return True
            
        except Exception as e:
            print_error(f"Error leyendo SRT: {e}")
            self.add_result("Lectura SRT", False, str(e))
            return False
    
    def test_disk_space(self) -> bool:
        """Verifica espacio en disco"""
        print_test("Verificando espacio en disco")
        
        try:
            import shutil
            
            total, used, free = shutil.disk_usage(Path.cwd())
            
            free_gb = free / (1024**3)
            total_gb = total / (1024**3)
            
            print_info(f"Espacio total: {total_gb:.2f} GB")
            print_info(f"Espacio libre: {free_gb:.2f} GB")
            
            if free_gb < 1:
                print_warning("Menos de 1 GB libre")
                print_info("Se recomienda al menos 2 GB para procesar videos")
                self.add_result("Espacio en disco", False, f"Solo {free_gb:.2f} GB")
                return False
            elif free_gb < 2:
                print_warning(f"Solo {free_gb:.2f} GB libres")
                print_info("Suficiente para videos cortos")
                self.add_result("Espacio en disco", True, f"{free_gb:.2f} GB (bajo)")
                return True
            else:
                print_success(f"Espacio suficiente: {free_gb:.2f} GB")
                self.add_result("Espacio en disco", True, f"{free_gb:.2f} GB")
                return True
                
        except Exception as e:
            print_error(f"Error verificando espacio: {e}")
            self.add_result("Espacio en disco", False, str(e))
            return False
    
    def cleanup(self):
        """Limpia archivos temporales"""
        try:
            import shutil
            if self.temp_dir.exists():
                shutil.rmtree(self.temp_dir)
        except:
            pass
    
    def print_summary(self):
        """Imprime resumen de resultados"""
        print_header("RESUMEN DE VERIFICACIÓN")
        
        total = len(self.results)
        passed = sum(1 for r in self.results if r['success'])
        failed = total - passed
        
        print(f"\n{Colors.BOLD}Resultados:{Colors.END}")
        print(f"  Total de tests: {total}")
        print(f"  {Colors.GREEN}Exitosos: {passed}{Colors.END}")
        print(f"  {Colors.RED}Fallidos: {failed}{Colors.END}")
        
        if failed > 0:
            print(f"\n{Colors.BOLD}Tests fallidos:{Colors.END}")
            for result in self.results:
                if not result['success']:
                    msg = f" ({result['message']})" if result['message'] else ""
                    print(f"  {Colors.RED}✗{Colors.END} {result['test']}{msg}")
        
        print("\n" + "=" * 80)
        
        if failed == 0:
            print(f"{Colors.GREEN}{Colors.BOLD}✓ TODOS LOS TESTS PASARON{Colors.END}")
            print(f"{Colors.GREEN}El sistema está listo para procesar videos{Colors.END}")
            return True
        else:
            print(f"{Colors.RED}{Colors.BOLD}✗ ALGUNOS TESTS FALLARON{Colors.END}")
            print(f"{Colors.YELLOW}Por favor corrige los errores antes de continuar{Colors.END}")
            return False
    
    def print_recommendations(self):
        """Imprime recomendaciones específicas del OS"""
        print_header("RECOMENDACIONES PARA TU SISTEMA")
        
        if self.os_type == 'windows':
            print(f"\n{Colors.BOLD}Windows:{Colors.END}")
            print("  • Usa pyttsx3 con voces del sistema (SAPI5)")
            print("  • Instala más voces desde: Configuración → Idioma")
            print("  • edge-tts es excelente para alta calidad (requiere internet)")
            print("\n  Comando recomendado:")
            print("  python video_tts_windows.py video.mp4 subs.srt out.mp4 --lang es")
            
        elif self.os_type == 'macos':
            print(f"\n{Colors.BOLD}macOS:{Colors.END}")
            print("  • pyttsx3 usa voces nativas de macOS")
            print("  • Voces disponibles en: Preferencias → Accesibilidad → Contenido hablado")
            print("  • edge-tts recomendado para mejor calidad")
            print("\n  Instalar dependencias:")
            print("  brew install ffmpeg")
            print("  pip3 install pysrt pyttsx3 pydub edge-tts")
            
        elif self.os_type == 'linux':
            print(f"\n{Colors.BOLD}Linux:{Colors.END}")
            print("  • Instala espeak para pyttsx3:")
            print("    sudo apt install espeak espeak-data libespeak-dev")
            print("  • O usa edge-tts (mejor calidad):")
            print("    pip3 install edge-tts")
            print("  • gTTS también es buena opción")
            print("\n  Instalar dependencias:")
            print("  sudo apt install ffmpeg espeak")
            print("  pip3 install pysrt pyttsx3 pydub edge-tts gtts")
        
        print("\n" + "=" * 80)
    
    def run_all_tests(self) -> bool:
        """Ejecuta todos los tests"""
        print_header("VERIFICACIÓN DEL SISTEMA - Multiplataforma")
        
        # Detectar plataforma primero
        self.test_platform()
        
        # Ejecutar tests
        self.test_python_version()
        self.test_ffmpeg()
        self.test_python_packages()
        self.test_tts_engines()
        self.test_tts_generation()
        self.test_ffmpeg_operations()
        self.test_srt_parsing()
        self.test_disk_space()
        
        # Mostrar resumen
        success = self.print_summary()
        
        # Mostrar recomendaciones
        self.print_recommendations()
        
        # Limpiar
        self.cleanup()
        
        return success


def main():
    """Función principal"""
    os_type = PlatformDetector.get_os()
    os_names = {
        'windows': 'Windows',
        'macos': 'macOS',
        'linux': 'Linux',
        'unknown': 'Desconocido'
    }
    
    print(f"""
{Colors.BLUE}{Colors.BOLD}
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║           VERIFICACIÓN DE SISTEMA - MULTIPLATAFORMA         ║
║           Video TTS Synchronizer                             ║
║                                                              ║
║  Sistema detectado: {os_names.get(os_type, 'Desconocido'):^40s} ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
{Colors.END}
    """)
    
    try:
        tester = SystemTester()
        success = tester.run_all_tests()
        
        if success:
            print(f"\n{Colors.GREEN}¡Sistema listo para procesar videos!{Colors.END}\n")
            sys.exit(0)
        else:
            print(f"\n{Colors.YELLOW}Corrige los errores y vuelve a ejecutar.{Colors.END}\n")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}Verificación cancelada{Colors.END}\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n{Colors.RED}Error inesperado: {e}{Colors.END}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
