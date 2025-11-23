# ============================================================================
# CELDA DE VERIFICACIÓN DEL SISTEMA - GOOGLE COLAB
# Ejecuta esta celda ANTES de procesar videos para verificar que todo funciona
# ============================================================================

import sys
import subprocess
import os
from pathlib import Path
from IPython.display import display, HTML, Markdown

# Configuración de colores para Colab
class TestResult:
    def __init__(self):
        self.results = []
    
    def add(self, test_name, success, message=""):
        self.results.append({
            'test': test_name,
            'success': success,
            'message': message
        })
    
    def summary_html(self):
        """Genera resumen en HTML"""
        passed = sum(1 for r in self.results if r['success'])
        failed = len(self.results) - passed
        
        rows = ""
        for r in self.results:
            icon = "✓" if r['success'] else "✗"
            color = "green" if r['success'] else "red"
            msg = f"<br><small style='color: gray;'>{r['message']}</small>" if r['message'] else ""
            rows += f"""
            <tr>
                <td style='text-align: center; color: {color}; font-size: 20px;'>{icon}</td>
                <td><strong>{r['test']}</strong>{msg}</td>
            </tr>
            """
        
        status_color = "green" if failed == 0 else "red"
        status_text = "TODOS LOS TESTS PASARON ✓" if failed == 0 else f"{failed} TEST(S) FALLARON ✗"
        
        html = f"""
        <div style='border: 3px solid {status_color}; border-radius: 10px; padding: 20px; margin: 20px 0;'>
            <h2 style='color: {status_color}; text-align: center;'>{status_text}</h2>
            <table style='width: 100%; margin-top: 20px;'>
                <tr style='background-color: #f0f0f0;'>
                    <th style='width: 50px; text-align: center;'>Estado</th>
                    <th>Test</th>
                </tr>
                {rows}
            </table>
            <div style='margin-top: 20px; padding: 10px; background-color: #f9f9f9; border-radius: 5px;'>
                <strong>Resumen:</strong> {passed}/{len(self.results)} tests exitosos
            </div>
        </div>
        """
        return html

results = TestResult()

print("=" * 80)
print("🔍 VERIFICACIÓN DEL SISTEMA - Google Colab")
print("=" * 80)
print()

# ============================================================================
# TEST 1: Python
# ============================================================================
print("▶ Test 1: Verificando Python")
version = sys.version_info
version_str = f"{version.major}.{version.minor}.{version.micro}"
print(f"  Versión: Python {version_str}")

if version.major >= 3 and version.minor >= 8:
    print("  ✓ Versión compatible")
    results.add("Python", True, version_str)
else:
    print("  ✗ Se requiere Python 3.8+")
    results.add("Python", False, f"Versión {version_str} < 3.8")

# ============================================================================
# TEST 2: FFmpeg
# ============================================================================
print("\n▶ Test 2: Verificando FFmpeg")
try:
    result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True, timeout=5)
    if result.returncode == 0:
        version_line = result.stdout.split('\n')[0]
        print(f"  {version_line}")
        print("  ✓ FFmpeg instalado")
        results.add("FFmpeg", True)
    else:
        print("  ✗ FFmpeg no responde")
        results.add("FFmpeg", False, "No responde")
except Exception as e:
    print(f"  ✗ Error: {e}")
    results.add("FFmpeg", False, str(e))

# ============================================================================
# TEST 3: Paquetes Python
# ============================================================================
print("\n▶ Test 3: Verificando paquetes Python")

packages = {
    'pysrt': 'Subtítulos SRT',
    'whisper': 'Whisper (transcripción)',
    'pydub': 'Procesamiento audio',
    'edge_tts': 'Edge TTS',
    'deep_translator': 'Traducción',
    'langdetect': 'Detección de idioma',
    'yt_dlp': 'Descarga de YouTube'
}

missing = []
for package, description in packages.items():
    try:
        __import__(package)
        print(f"  ✓ {package} ({description})")
    except ImportError:
        print(f"  ✗ {package} NO instalado")
        missing.append(package)

if missing:
    print(f"\n  ⚠ Faltan paquetes: {', '.join(missing)}")
    print("  Ejecuta la celda de instalación de nuevo")
    results.add("Paquetes Python", False, f"Faltan: {', '.join(missing)}")
else:
    print("  ✓ Todos los paquetes instalados")
    results.add("Paquetes Python", True)

# ============================================================================
# TEST 4: Edge TTS (Voces)
# ============================================================================
print("\n▶ Test 4: Probando Edge TTS")
try:
    import edge_tts
    import asyncio
    
    # Obtener voces
    async def get_voices():
        voices = await edge_tts.list_voices()
        return voices
    
    voices = asyncio.run(get_voices())
    
    # Contar por idioma
    es_count = sum(1 for v in voices if v['Locale'].startswith('es'))
    en_count = sum(1 for v in voices if v['Locale'].startswith('en'))
    de_count = sum(1 for v in voices if v['Locale'].startswith('de'))
    
    print(f"  ✓ {len(voices)} voces disponibles")
    print(f"    • Español: {es_count} voces")
    print(f"    • English: {en_count} voces")
    print(f"    • Deutsch: {de_count} voces")
    
    results.add("Edge TTS", True, f"{len(voices)} voces")
    
except Exception as e:
    print(f"  ✗ Error: {e}")
    results.add("Edge TTS", False, str(e))

# ============================================================================
# TEST 5: Generación TTS
# ============================================================================
print("\n▶ Test 5: Probando generación de audio TTS")
try:
    import edge_tts
    import asyncio
    from pydub import AudioSegment
    
    async def test_tts():
        text = "Hola, esta es una prueba de audio"
        output = "/tmp/test_tts.mp3"
        
        communicate = edge_tts.Communicate(text, "es-ES-AlvaroNeural")
        await communicate.save(output)
        
        # Verificar audio
        audio = AudioSegment.from_file(output)
        duration = len(audio) / 1000
        
        # Limpiar
        os.remove(output)
        
        return duration
    
    duration = asyncio.run(test_tts())
    print(f"  ✓ Audio generado correctamente ({duration:.2f}s)")
    results.add("Generación TTS", True)
    
except Exception as e:
    print(f"  ✗ Error: {e}")
    results.add("Generación TTS", False, str(e))

# ============================================================================
# TEST 6: Google Translate
# ============================================================================
print("\n▶ Test 6: Probando traducción automática")
try:
    from deep_translator import GoogleTranslator
    
    translator = GoogleTranslator(source='en', target='es')
    translated = translator.translate("Hello world, this is a test")
    
    print(f"  Original: 'Hello world, this is a test'")
    print(f"  Traducido: '{translated}'")
    print("  ✓ Traducción funcionando")
    results.add("Google Translate", True)
    
except Exception as e:
    print(f"  ✗ Error: {e}")
    results.add("Google Translate", False, str(e))

# ============================================================================
# TEST 7: Whisper
# ============================================================================
print("\n▶ Test 7: Verificando Whisper")
try:
    import whisper
    
    # Cargar modelo más pequeño para test
    print("  Cargando modelo 'tiny' para prueba...")
    model = whisper.load_model("tiny")
    
    print("  ✓ Whisper disponible (modelo 'tiny' cargado)")
    print("  ℹ Modelos disponibles: tiny, base, small, medium, large")
    results.add("Whisper", True, "Modelo tiny OK")
    
except Exception as e:
    print(f"  ✗ Error: {e}")
    results.add("Whisper", False, str(e))

# ============================================================================
# TEST 8: yt-dlp
# ============================================================================
print("\n▶ Test 8: Verificando yt-dlp")
try:
    result = subprocess.run(['yt-dlp', '--version'], capture_output=True, text=True, timeout=5)
    if result.returncode == 0:
        version = result.stdout.strip()
        print(f"  ✓ yt-dlp versión: {version}")
        results.add("yt-dlp", True, version)
    else:
        print("  ✗ yt-dlp no responde")
        results.add("yt-dlp", False, "No responde")
except Exception as e:
    print(f"  ✗ Error: {e}")
    results.add("yt-dlp", False, str(e))

# ============================================================================
# TEST 9: Operaciones FFmpeg
# ============================================================================
print("\n▶ Test 9: Probando operaciones de FFmpeg")
try:
    # Crear video de prueba
    test_video = "/tmp/test_video.mp4"
    
    result = subprocess.run([
        'ffmpeg', '-y', '-loglevel', 'error',
        '-f', 'lavfi', '-i', 'color=c=blue:s=320x240:d=2',
        '-f', 'lavfi', '-i', 'sine=frequency=1000:duration=2',
        '-c:v', 'libx264', '-c:a', 'aac',
        '-shortest', test_video
    ], capture_output=True, timeout=10)
    
    if result.returncode == 0 and os.path.exists(test_video):
        print("  ✓ Creación de video")
        
        # Extraer frame
        frame = "/tmp/test_frame.png"
        result = subprocess.run([
            'ffmpeg', '-y', '-loglevel', 'error',
            '-i', test_video, '-vframes', '1', frame
        ], capture_output=True, timeout=5)
        
        if result.returncode == 0:
            print("  ✓ Extracción de frames")
        
        # Extraer audio
        audio = "/tmp/test_audio.wav"
        result = subprocess.run([
            'ffmpeg', '-y', '-loglevel', 'error',
            '-i', test_video, '-vn', '-acodec', 'pcm_s16le', audio
        ], capture_output=True, timeout=5)
        
        if result.returncode == 0:
            print("  ✓ Extracción de audio")
        
        # Limpiar
        for f in [test_video, frame, audio]:
            if os.path.exists(f):
                os.remove(f)
        
        print("  ✓ Todas las operaciones FFmpeg OK")
        results.add("Operaciones FFmpeg", True)
    else:
        print("  ✗ No se pudo crear video de prueba")
        results.add("Operaciones FFmpeg", False, "Error creando video")
        
except Exception as e:
    print(f"  ✗ Error: {e}")
    results.add("Operaciones FFmpeg", False, str(e))

# ============================================================================
# TEST 10: Lectura de SRT
# ============================================================================
print("\n▶ Test 10: Probando lectura de subtítulos")
try:
    import pysrt
    
    # Crear SRT de prueba
    test_srt = "/tmp/test.srt"
    srt_content = """1
00:00:00,000 --> 00:00:03,000
Primer subtítulo de prueba

2
00:00:03,000 --> 00:00:06,000
Segundo subtítulo de prueba
"""
    
    with open(test_srt, 'w', encoding='utf-8') as f:
        f.write(srt_content)
    
    # Leer
    subs = pysrt.open(test_srt, encoding='utf-8')
    
    if len(subs) == 2:
        print(f"  ✓ Archivo SRT leído correctamente ({len(subs)} subtítulos)")
        results.add("Lectura SRT", True)
    else:
        print(f"  ✗ Lectura incorrecta (esperados 2, leídos {len(subs)})")
        results.add("Lectura SRT", False, "Lectura incorrecta")
    
    # Limpiar
    os.remove(test_srt)
    
except Exception as e:
    print(f"  ✗ Error: {e}")
    results.add("Lectura SRT", False, str(e))

# ============================================================================
# TEST 11: Espacio en disco
# ============================================================================
print("\n▶ Test 11: Verificando espacio en disco")
try:
    import shutil
    
    total, used, free = shutil.disk_usage("/content")
    free_gb = free / (1024**3)
    
    print(f"  Espacio libre: {free_gb:.2f} GB")
    
    if free_gb < 1:
        print("  ⚠ Menos de 1 GB libre")
        results.add("Espacio disco", False, f"Solo {free_gb:.2f} GB")
    elif free_gb < 5:
        print("  ⚠ Poco espacio, pero suficiente para videos cortos")
        results.add("Espacio disco", True, f"{free_gb:.2f} GB (bajo)")
    else:
        print("  ✓ Espacio suficiente")
        results.add("Espacio disco", True, f"{free_gb:.2f} GB")
        
except Exception as e:
    print(f"  ✗ Error: {e}")
    results.add("Espacio disco", False, str(e))

# ============================================================================
# TEST 12: GPU (opcional)
# ============================================================================
print("\n▶ Test 12: Verificando GPU (opcional para Whisper)")
try:
    import torch
    
    if torch.cuda.is_available():
        gpu_name = torch.cuda.get_device_name(0)
        print(f"  ✓ GPU disponible: {gpu_name}")
        print("  ℹ Whisper será más rápido con GPU")
        results.add("GPU", True, gpu_name)
    else:
        print("  ℹ No hay GPU disponible")
        print("  ℹ Puedes activarla: Runtime → Change runtime type → GPU")
        results.add("GPU", True, "No disponible (opcional)")
        
except Exception as e:
    print("  ℹ PyTorch no disponible (no crítico)")
    results.add("GPU", True, "N/A")

# ============================================================================
# RESUMEN FINAL
# ============================================================================
print("\n" + "=" * 80)
print("📊 RESUMEN DE VERIFICACIÓN")
print("=" * 80)

passed = sum(1 for r in results.results if r['success'])
failed = len(results.results) - passed

print(f"\nTotal de tests: {len(results.results)}")
print(f"Exitosos: {passed}")
print(f"Fallidos: {failed}")

if failed > 0:
    print("\n⚠ TESTS FALLIDOS:")
    for r in results.results:
        if not r['success']:
            msg = f" ({r['message']})" if r['message'] else ""
            print(f"  ✗ {r['test']}{msg}")

# Mostrar HTML
display(HTML(results.summary_html()))

if failed == 0:
    display(HTML("""
    <div style='background-color: #d4edda; border: 2px solid #28a745; border-radius: 10px; padding: 20px; margin: 20px 0;'>
        <h2 style='color: #28a745; margin: 0;'>✓ SISTEMA LISTO</h2>
        <p style='margin: 10px 0 0 0; font-size: 16px;'>
            Todos los componentes están funcionando correctamente.<br>
            <strong>Puedes proceder a configurar y ejecutar el procesamiento de video.</strong>
        </p>
    </div>
    """))
    print("\n✓ ¡Puedes continuar con la configuración y ejecución!")
else:
    display(HTML("""
    <div style='background-color: #f8d7da; border: 2px solid #dc3545; border-radius: 10px; padding: 20px; margin: 20px 0;'>
        <h2 style='color: #dc3545; margin: 0;'>✗ ACCIÓN REQUERIDA</h2>
        <p style='margin: 10px 0 0 0; font-size: 16px;'>
            Algunos tests fallaron. Por favor:<br>
            1. Revisa los errores arriba<br>
            2. Ejecuta de nuevo la celda de instalación (Celda 1)<br>
            3. Vuelve a ejecutar esta verificación
        </p>
    </div>
    """))
    print("\n⚠ Corrige los errores antes de continuar")

print("\n" + "=" * 80)
