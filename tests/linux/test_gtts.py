#!/usr/bin/env python3
"""Test script to verify gTTS functionality"""

import sys
from pathlib import Path

try:
    from gtts import gTTS
    from pydub import AudioSegment
    from pydub.effects import speedup
    print("✓ Dependencias importadas correctamente")
except ImportError as e:
    print(f"✗ Error importando dependencias: {e}")
    sys.exit(1)

# Test text
test_text = "Hola, esta es una prueba del sistema de síntesis de voz."

print(f"\n📝 Texto de prueba: {test_text}")
print("🔄 Intentando generar audio con gTTS...")

try:
    # Generate TTS
    tts = gTTS(text=test_text, lang='es', slow=False)

    # Save to temporary MP3
    temp_mp3 = Path("test_output.mp3")
    tts.save(str(temp_mp3))
    print(f"✓ Audio MP3 generado: {temp_mp3}")

    # Convert to WAV with speed adjustment
    audio = AudioSegment.from_mp3(str(temp_mp3))
    print(f"✓ Audio cargado: duración={len(audio)}ms, tasa={audio.frame_rate}Hz")

    # Test speed adjustment (180 WPM)
    speed_factor = 180 / 150.0
    audio_fast = speedup(audio, playback_speed=speed_factor)

    # Export to WAV
    output_wav = Path("test_output.wav")
    audio_fast.export(str(output_wav), format='wav')
    print(f"✓ Audio WAV generado: {output_wav}")

    # Verify file exists and has content
    if output_wav.exists() and output_wav.stat().st_size > 0:
        print(f"✓ Archivo WAV válido: {output_wav.stat().st_size} bytes")
        print("\n✅ TEST EXITOSO: gTTS está funcionando correctamente")

        # Cleanup
        temp_mp3.unlink()
        print(f"\n💡 Se generó el archivo: {output_wav}")
        print("   Puedes reproducirlo para verificar la calidad")
    else:
        print("✗ ERROR: El archivo WAV está vacío o no existe")
        sys.exit(1)

except Exception as e:
    print(f"\n✗ ERROR: {e}")
    print(f"   Tipo de error: {type(e).__name__}")

    if "Failed to connect" in str(e):
        print("\n⚠ Error de conexión detectado")
        print("Posibles causas:")
        print("  1. Sin conexión a internet")
        print("  2. Firewall bloqueando acceso a Google TTS")
        print("  3. Proxy o VPN interferiendo")
        print("  4. Google TTS temporalmente no disponible")

    sys.exit(1)
