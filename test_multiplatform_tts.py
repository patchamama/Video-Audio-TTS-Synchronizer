#!/usr/bin/env python3
"""Test de detección de sistema operativo y motores TTS"""

import sys
import platform
from pathlib import Path

# Agregar el directorio actual al path
sys.path.insert(0, str(Path(__file__).parent))

from create_video_tts_from_srt import TTSEngine, Colors

def test_os_detection():
    """Test de detección de sistema operativo"""
    print("🧪 TEST DE DETECCIÓN DE SISTEMA OPERATIVO Y MOTORES TTS\n")
    print("="*60)

    # Mostrar sistema detectado
    system = platform.system()
    print(f"💻 Sistema operativo: {system}")
    print(f"🐍 Python: {sys.version}")
    print(f"📁 Ejecutable: {sys.executable}")

    print("\n" + "="*60)
    print("Inicializando motor TTS...")
    print("="*60 + "\n")

    # Inicializar motor
    engine = TTSEngine()

    print("\n" + "="*60)
    print(f"✅ Motor seleccionado: {engine.method}")
    print("="*60)

    # Mostrar estrategia según el sistema
    if engine.method == "say":
        print("\n📋 Estrategia para macOS:")
        print("  1. Usar comando 'say' nativo de macOS")
        print("  2. Convertir AIFF a WAV con ffmpeg")

    elif engine.method == "windows":
        print("\n📋 Estrategia para Windows:")
        print("  1. Intentar edge-tts (online, alta calidad)")
        print("     └─ Voz: es-ES-ElviraNeural")
        print("  2. Si falla, usar SAPI/pyttsx3 (offline)")
        print("     └─ Busca voz en español instalada en Windows")

    elif engine.method == "linux":
        print("\n📋 Estrategia para Linux:")
        print("  1. Intentar gTTS (online, alta calidad)")
        print("     └─ 3 reintentos con backoff exponencial")
        print("  2. Si falla, usar espeak-ng (offline)")
        print("     └─ Voz sintética pero confiable")

    # Test de generación
    print("\n" + "="*60)
    print("TEST: Generación de audio de prueba")
    print("="*60 + "\n")

    text = "Hola, esta es una prueba del sistema de síntesis de voz."
    output_file = Path(f"test_os_{engine.method}.wav")
    rate = 180

    print(f"📝 Texto: {text}")
    print(f"🎤 Velocidad: {rate} WPM")
    print(f"📁 Salida: {output_file}")
    print("\nGenerando audio...\n")

    success = engine.generate_audio(text, rate, output_file)

    if success and output_file.exists():
        size = output_file.stat().st_size
        print(f"\n{Colors.GREEN}✅ TEST EXITOSO{Colors.NC}")
        print(f"   Archivo: {output_file}")
        print(f"   Tamaño: {size} bytes")

        # Resumen de fallback
        print("\n" + "="*60)
        print("✨ RESUMEN DEL SISTEMA DE FALLBACK")
        print("="*60)

        if engine.method == "windows":
            print("""
Windows:
  ┌─ Intento 1: edge-tts (online)
  │  ├─ Voz neural de alta calidad
  │  └─ Requiere internet
  └─ Intento 2: SAPI/pyttsx3 (offline)
     ├─ TTS nativo de Windows
     └─ Siempre disponible
            """)
        elif engine.method == "linux":
            print("""
Linux:
  ┌─ Intento 1: gTTS (online)
  │  ├─ Voz natural de Google
  │  ├─ 3 reintentos automáticos
  │  └─ Requiere internet
  └─ Intento 2: espeak-ng (offline)
     ├─ TTS de código abierto
     └─ Siempre disponible
            """)
        elif engine.method == "say":
            print("""
macOS:
  └─ Comando 'say' nativo
     ├─ Voz Paulina para español
     └─ Siempre disponible
            """)

        return True
    else:
        print(f"\n{Colors.RED}❌ TEST FALLÓ{Colors.NC}")
        print(f"   No se pudo generar el archivo de audio")
        return False

if __name__ == '__main__':
    print("🎙️  TEST DE MULTI-PLATAFORMA TTS")
    print("="*60)
    print("\nEste script verifica que el sistema TTS se adapta")
    print("correctamente a cada sistema operativo:\n")
    print("  • macOS → say")
    print("  • Windows → edge-tts + SAPI")
    print("  • Linux → gTTS + espeak-ng")
    print()

    success = test_os_detection()

    sys.exit(0 if success else 1)
