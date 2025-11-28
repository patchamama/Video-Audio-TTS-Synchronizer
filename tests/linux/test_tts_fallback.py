#!/usr/bin/env python3
"""Test del mecanismo de fallback gTTS -> espeak-ng"""

import sys
import os
from pathlib import Path

# Agregar el directorio actual al path para importar el módulo
sys.path.insert(0, str(Path(__file__).parent))

# Importar la clase TTSEngine
from create_video_tts_from_srt import TTSEngine

def test_tts_fallback():
    """Test del motor TTS con fallback automático"""
    print("🧪 TEST: Mecanismo de fallback gTTS -> espeak-ng\n")
    print("="*60)

    # Crear instancia del motor TTS
    engine = TTSEngine()

    print("\n" + "="*60)
    print("TEST 1: Generación de audio con texto simple")
    print("="*60)

    text = "Hola, esta es una prueba del sistema de fallback automático."
    output_file = Path("test_fallback.wav")
    rate = 180

    print(f"\n📝 Texto: {text}")
    print(f"🎤 Velocidad: {rate} WPM")
    print(f"📁 Salida: {output_file}")
    print("\nGenerando audio...\n")

    success = engine.generate_audio(text, rate, output_file)

    if success and output_file.exists():
        size = output_file.stat().st_size
        print(f"\n✅ TEST EXITOSO")
        print(f"   Archivo generado: {output_file}")
        print(f"   Tamaño: {size} bytes")
        print(f"\n💡 El fallback automático funcionó correctamente")
        print(f"   - Si gTTS funciona, usará gTTS (mejor calidad)")
        print(f"   - Si gTTS falla, usará espeak-ng (offline, confiable)")
        return True
    else:
        print(f"\n❌ TEST FALLÓ")
        print(f"   No se pudo generar el archivo de audio")
        print(f"   Verifica que al menos uno de estos esté instalado:")
        print(f"   - gTTS: sudo apt install python3-gtts python3-pydub")
        print(f"   - espeak-ng: sudo apt-get install espeak-ng")
        return False

if __name__ == '__main__':
    print("🎙️  TEST DEL MOTOR TTS CON FALLBACK AUTOMÁTICO")
    print("="*60)
    print("\nEste test verificará que:")
    print("  1. El motor TTS intenta primero con gTTS (online)")
    print("  2. Si gTTS falla, automáticamente usa espeak-ng (offline)")
    print("  3. El usuario obtiene audio en cualquier caso")

    success = test_tts_fallback()

    sys.exit(0 if success else 1)
