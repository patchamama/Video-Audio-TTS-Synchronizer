#!/usr/bin/env python3
"""Ejemplo simple de uso de espeak-ng desde Python"""

import subprocess
from pathlib import Path

def generate_tts_espeak(text: str, output_file: str, rate: int = 180) -> bool:
    """
    Genera audio TTS usando espeak-ng (100% offline)

    Args:
        text: Texto a convertir a voz
        output_file: Archivo WAV de salida
        rate: Velocidad en palabras por minuto (WPM)

    Returns:
        True si se generó exitosamente, False en caso contrario
    """
    try:
        cmd = [
            'espeak-ng',
            '-v', 'es',              # Voz en español
            '-s', str(rate),         # Velocidad en WPM
            '-w', output_file,       # Archivo de salida WAV
            text                     # Texto a convertir
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )

        # Verificar que el archivo existe
        return Path(output_file).exists()

    except subprocess.CalledProcessError as e:
        print(f"Error ejecutando espeak-ng: {e.stderr}")
        return False
    except Exception as e:
        print(f"Error: {e}")
        return False


# Ejemplo de uso
if __name__ == '__main__':
    print("🎙️  Ejemplo de uso de espeak-ng\n")

    # Ejemplo 1: Audio simple
    text1 = "Hola, este es un ejemplo de texto a voz con espeak."
    output1 = "ejemplo_1.wav"

    print(f"📝 Generando: {text1}")
    if generate_tts_espeak(text1, output1, rate=180):
        print(f"✅ Generado: {output1}\n")
    else:
        print(f"❌ Error generando {output1}\n")

    # Ejemplo 2: Diferentes velocidades
    text2 = "Prueba de diferentes velocidades de lectura."

    for wpm in [180, 200, 220, 240]:
        output2 = f"ejemplo_velocidad_{wpm}.wav"
        print(f"🎤 Generando a {wpm} WPM...")

        if generate_tts_espeak(text2, output2, rate=wpm):
            size = Path(output2).stat().st_size
            print(f"   ✅ {output2} ({size} bytes)")
        else:
            print(f"   ❌ Error")

    print("\n💡 Reproduce los archivos con: aplay ejemplo_1.wav")

    # Ventajas de espeak-ng
    print("\n" + "="*60)
    print("✨ VENTAJAS DE ESPEAK-NG:")
    print("="*60)
    print("  ✅ 100% offline - no requiere internet")
    print("  ✅ Muy rápido - genera audio instantáneamente")
    print("  ✅ Ligero - no requiere descargar modelos pesados")
    print("  ✅ Confiable - siempre funciona")
    print("  ✅ Control preciso de velocidad (WPM)")
    print("  ✅ Múltiples idiomas incluidos")
    print("\n⚠️  DESVENTAJA:")
    print("  - Voz sintética (menos natural que gTTS)")
    print("\n🎯 IDEAL PARA:")
    print("  - Ambientes sin internet confiable")
    print("  - Procesamiento de muchos archivos")
    print("  - Cuando velocidad > calidad de voz")
