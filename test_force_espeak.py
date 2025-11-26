#!/usr/bin/env python3
"""Test forzando el uso de espeak-ng (simulando fallo de gTTS)"""

import sys
from pathlib import Path

# Simular que gTTS no está disponible
sys.modules['gtts'] = None

# Importar después de bloquear gTTS
from create_video_tts_from_srt import TTSEngine, Colors

def test_espeak_direct():
    """Test directo de espeak-ng sin pasar por gTTS"""
    print("🧪 TEST: Uso directo de espeak-ng (simulando fallo de gTTS)\n")
    print("="*60)

    engine = TTSEngine()

    # Usar método directo de espeak
    text = "Esta es una prueba directa de espeak como fallback."
    output_file = Path("test_espeak_direct.wav")
    rate = 200

    print(f"\n📝 Texto: {text}")
    print(f"🎤 Velocidad: {rate} WPM")
    print(f"\nGenerando con espeak-ng directamente...\n")

    success = engine._generate_with_espeak(text, rate, output_file)

    if success and output_file.exists():
        size = output_file.stat().st_size
        print(f"{Colors.GREEN}✅ ESPEAK-NG FUNCIONÓ{Colors.NC}")
        print(f"   Archivo: {output_file}")
        print(f"   Tamaño: {size} bytes")
        print(f"\n💡 Cuando gTTS falle, automáticamente usará espeak-ng")
        return True
    else:
        print(f"{Colors.RED}❌ ESPEAK-NG NO ESTÁ DISPONIBLE{Colors.NC}")
        print(f"   Instala con: sudo apt-get install espeak-ng")
        return False

if __name__ == '__main__':
    test_espeak_direct()
