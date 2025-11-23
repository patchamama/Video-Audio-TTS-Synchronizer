#!/usr/bin/env python3
"""
Sistema de Verificación Pre-Ejecución - Versión Windows
Verifica que todos los componentes estén funcionando antes de procesar videos.
"""

import os
import sys
import subprocess
import platform
from pathlib import Path
from typing import Tuple, List

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


class SystemTester:
    """Prueba todos los componentes del sistema"""
    
    def __init__(self):
        self.results = []
        self.temp_dir = Path("test_temp")
        self.temp_dir.mkdir(exist_ok=True)
    
    def add_result(self, test_name: str, success: bool, message: str = ""):
        """Registra resultado de test"""
        self.results.append({
            'test': test_name,
            'success': success,
            'message': message
        })
    
    def test_python_version(self) -> bool:
        """Verifica versión de Python"""
        print_test("Verificando Python")
        
        version = sys.version_info
        version_str = f"{version.major}.{version.minor}.{version.micro}"
        
        print_info(f"Versión: Python {version_str}")
        print_info(f"Ejecutable: {sys.executable}")
        print_info(f"Plataforma: {platform.system()} {platform.release()}")
        
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
                # Extraer versión
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
            print_info("Descarga desde: https://ffmpeg.org/download.html")
            print_info("Asegúrate de agregarlo al PATH del sistema")
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
            'pyttsx3': 'pyttsx3',
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
    
    def test_pyttsx3_voices(self) -> bool:
        """Verifica voces de pyttsx3"""
        print_test("Verificando voces TTS del sistema")
        
        try:
            import pyttsx3
            
            engine = pyttsx3.init()
            voices = engine.getProperty('voices')
            
            if not voices:
                print_error("No se encontraron voces en el sistema")
                print_info("Instala paquetes de voz desde Configuración → Idioma")
                self.add_result("Voces TTS", False, "Sin voces")
                return False
            
            print_success(f"Encontradas {len(voices)} voces en el sistema")
            
            # Agrupar por idioma
            spanish_voices = []
            english_voices = []
            german_voices = []
            
            for voice in voices:
                name_lower = voice.name.lower()
                id_lower = voice.id.lower()
                
                if any(x in name_lower or x in id_lower for x in ['es-', 'spanish', 'español']):
                    spanish_voices.append(voice.name)
                elif any(x in name_lower or x in id_lower for x in ['de-', 'german', 'deutsch']):
                    german_voices.append(voice.name)
                elif any(x in name_lower or x in id_lower for x in ['en-', 'english']):
                    english_voices.append(voice.name)
            
            print_info(f"Voces en español: {len(spanish_voices)}")
            for v in spanish_voices[:3]:  # Mostrar primeras 3
                print(f"    • {v}")
            
            print_info(f"Voces en inglés: {len(english_voices)}")
            for v in english_voices[:3]:
                print(f"    • {v}")
            
            print_info(f"Voces en alemán: {len(german_voices)}")
            for v in german_voices[:3]:
                print(f"    • {v}")
            
            if not spanish_voices and not english_voices and not german_voices:
                print_warning("No se encontraron voces en ES/EN/DE")
                print_info("Puedes agregar más voces desde Configuración → Idioma")
            
            self.add_result("Voces TTS", True, f"{len(voices)} voces")
            return True
            
        except ImportError:
            print_error("pyttsx3 no está instalado")
            self.add_result("Voces TTS", False, "pyttsx3 no instalado")
            return False
        except Exception as e:
            print_error(f"Error al verificar voces: {e}")
            self.add_result("Voces TTS", False, str(e))
            return False
    
    def test_tts_generation(self) -> bool:
        """Prueba generación de audio TTS"""
        print_test("Probando generación de TTS")
        
        try:
            import pyttsx3
            from pydub import AudioSegment
            
            # Generar audio de prueba
            engine = pyttsx3.init()
            test_file = self.temp_dir / "test_tts.wav"
            test_text = "Hola, esta es una prueba de generación de audio"
            
            print_info("Generando audio de prueba...")
            engine.save_to_file(test_text, str(test_file))
            engine.runAndWait()
            
            if not test_file.exists():
                print_error("No se generó el archivo de audio")
                self.add_result("Generación TTS", False, "Archivo no creado")
                return False
            
            # Verificar que se puede leer
            audio = AudioSegment.from_file(str(test_file))
            duration_ms = len(audio)
            duration_s = duration_ms / 1000
            
            print_success(f"Audio generado correctamente ({duration_s:.2f}s)")
            print_info(f"Archivo: {test_file}")
            
            # Limpiar
            test_file.unlink()
            
            self.add_result("Generación TTS", True)
            return True
            
        except Exception as e:
            print_error(f"Error generando TTS: {e}")
            self.add_result("Generación TTS", False, str(e))
            return False
    
    def test_ffmpeg_operations(self) -> bool:
        """Prueba operaciones básicas de FFmpeg"""
        print_test("Probando operaciones de FFmpeg")
        
        try:
            # Crear video de prueba simple
            test_video = self.temp_dir / "test_video.mp4"
            
            print_info("Creando video de prueba...")
            
            # Crear video de 3 segundos con color sólido
            result = subprocess.run([
                'ffmpeg', '-y',
                '-f', 'lavfi',
                '-i', 'color=c=blue:s=320x240:d=3',
                '-f', 'lavfi',
                '-i', 'sine=frequency=1000:duration=3',
                '-c:v', 'libx264',
                '-c:a', 'aac',
                '-shortest',
                str(test_video)
            ], capture_output=True, timeout=10)
            
            if result.returncode != 0:
                print_error("No se pudo crear video de prueba")
                print_info(f"Error: {result.stderr.decode()[:200]}")
                self.add_result("Operaciones FFmpeg", False, "No crea video")
                return False
            
            print_success("Video de prueba creado")
            
            # Extraer frame
            test_frame = self.temp_dir / "test_frame.png"
            
            print_info("Extrayendo frame...")
            result = subprocess.run([
                'ffmpeg', '-y',
                '-i', str(test_video),
                '-vframes', '1',
                str(test_frame)
            ], capture_output=True, timeout=5)
            
            if result.returncode != 0:
                print_error("No se pudo extraer frame")
                self.add_result("Operaciones FFmpeg", False, "No extrae frames")
                return False
            
            print_success("Frame extraído correctamente")
            
            # Extraer audio
            test_audio = self.temp_dir / "test_audio.wav"
            
            print_info("Extrayendo audio...")
            result = subprocess.run([
                'ffmpeg', '-y',
                '-i', str(test_video),
                '-vn',
                '-acodec', 'pcm_s16le',
                str(test_audio)
            ], capture_output=True, timeout=5)
            
            if result.returncode != 0:
                print_error("No se pudo extraer audio")
                self.add_result("Operaciones FFmpeg", False, "No extrae audio")
                return False
            
            print_success("Audio extraído correctamente")
            
            # Limpiar
            test_video.unlink()
            test_frame.unlink()
            test_audio.unlink()
            
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
            
            # Crear SRT de prueba
            test_srt = self.temp_dir / "test.srt"
            
            srt_content = """1
00:00:00,000 --> 00:00:03,000
Este es el primer subtítulo

2
00:00:03,000 --> 00:00:06,000
Este es el segundo subtítulo

3
00:00:06,000 --> 00:00:09,000
Y este es el tercero
"""
            
            test_srt.write_text(srt_content, encoding='utf-8')
            
            print_info("Archivo SRT de prueba creado")
            
            # Leer SRT
            subs = pysrt.open(str(test_srt), encoding='utf-8')
            
            if len(subs) != 3:
                print_error(f"Se esperaban 3 subtítulos, se leyeron {len(subs)}")
                self.add_result("Lectura SRT", False, "Lectura incorrecta")
                return False
            
            print_success(f"Archivo SRT leído correctamente ({len(subs)} subtítulos)")
            
            # Verificar tiempos
            first_sub = subs[0]
            duration_ms = (first_sub.end.hours * 3600000 +
                          first_sub.end.minutes * 60000 +
                          first_sub.end.seconds * 1000) - \
                         (first_sub.start.hours * 3600000 +
                          first_sub.start.minutes * 60000 +
                          first_sub.start.seconds * 1000)
            
            print_info(f"Duración primer subtítulo: {duration_ms}ms")
            
            # Limpiar
            test_srt.unlink()
            
            self.add_result("Lectura SRT", True)
            return True
            
        except Exception as e:
            print_error(f"Error leyendo SRT: {e}")
            self.add_result("Lectura SRT", False, str(e))
            return False
    
    def test_audio_processing(self) -> bool:
        """Prueba procesamiento de audio con pydub"""
        print_test("Probando procesamiento de audio")
        
        try:
            from pydub import AudioSegment
            from pydub.generators import Sine
            
            print_info("Generando tono de prueba...")
            
            # Generar tono de 1 segundo
            tone = Sine(440).to_audio_segment(duration=1000)
            
            print_success("Tono generado")
            
            # Crear silencio
            silence = AudioSegment.silent(duration=500)
            
            print_success("Silencio generado")
            
            # Combinar
            combined = tone + silence + tone
            
            print_success("Audio combinado")
            
            # Guardar
            test_audio = self.temp_dir / "test_combined.mp3"
            combined.export(str(test_audio), format="mp3")
            
            print_success(f"Audio exportado ({len(combined)}ms)")
            
            # Limpiar
            test_audio.unlink()
            
            self.add_result("Procesamiento Audio", True)
            return True
            
        except Exception as e:
            print_error(f"Error procesando audio: {e}")
            self.add_result("Procesamiento Audio", False, str(e))
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
                print_info("Suficiente para videos cortos, pero se recomienda más espacio")
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
    
    def run_all_tests(self) -> bool:
        """Ejecuta todos los tests"""
        print_header("VERIFICACIÓN DEL SISTEMA - Video TTS Synchronizer")
        print(f"{Colors.BOLD}Versión Windows{Colors.END}\n")
        
        # Ejecutar tests
        self.test_python_version()
        self.test_ffmpeg()
        self.test_python_packages()
        self.test_pyttsx3_voices()
        self.test_tts_generation()
        self.test_ffmpeg_operations()
        self.test_srt_parsing()
        self.test_audio_processing()
        self.test_disk_space()
        
        # Mostrar resumen
        success = self.print_summary()
        
        # Limpiar
        self.cleanup()
        
        return success


def main():
    """Función principal"""
    print(f"""
{Colors.BLUE}{Colors.BOLD}
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║           VERIFICACIÓN DE SISTEMA - WINDOWS                  ║
║           Video TTS Synchronizer                             ║
║                                                              ║
║  Este script verifica que tu sistema esté listo para        ║
║  procesar videos con TTS.                                    ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
{Colors.END}
    """)
    
    try:
        tester = SystemTester()
        success = tester.run_all_tests()
        
        if success:
            print(f"\n{Colors.GREEN}¡Puedes proceder a usar video_tts_windows.py!{Colors.END}\n")
            sys.exit(0)
        else:
            print(f"\n{Colors.YELLOW}Corrige los errores y vuelve a ejecutar este script.{Colors.END}\n")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}Verificación cancelada por el usuario{Colors.END}\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n{Colors.RED}Error inesperado: {e}{Colors.END}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
