#!/usr/bin/env python3
"""Test de TTS nativo de Windows usando pyttsx3"""

import sys
from pathlib import Path

def test_windows_tts():
    """Test del motor TTS nativo de Windows"""
    print("🎙️  TEST TTS NATIVO DE WINDOWS (Python)")
    print("="*60)

    try:
        import pyttsx3
        print("✅ pyttsx3 está instalado\n")
    except ImportError:
        print("❌ pyttsx3 NO está instalado")
        print("\n📦 Para instalar:")
        print("   pip install pyttsx3")
        return False

    try:
        # Inicializar motor
        engine = pyttsx3.init()

        # Mostrar voces disponibles
        print("🎤 Voces disponibles:")
        voices = engine.getProperty('voices')
        spanish_voice = None

        for idx, voice in enumerate(voices):
            name = voice.name
            lang_info = ""
            if voice.languages:
                lang_info = f" ({voice.languages[0]})"
            print(f"  [{idx}] {name}{lang_info}")

            # Buscar voz en español
            if 'spanish' in name.lower() or 'es' in str(voice.languages).lower():
                spanish_voice = voice.id

        # Configurar voz
        if spanish_voice:
            engine.setProperty('voice', spanish_voice)
            print(f"\n✅ Usando voz en español")
        else:
            print(f"\n⚠️  No se encontró voz en español, usando voz por defecto")

        # Configurar velocidad (palabras por minuto)
        # Rango típico: 100-200 WPM
        engine.setProperty('rate', 180)

        print("\n" + "="*60)
        print("TEST 1: Generar audio simple")
        print("="*60)

        text = "Hola, esta es una prueba del sistema de síntesis de voz nativo de Windows usando Python."
        output_file = "test_windows_python.wav"

        print(f"\n📝 Texto: {text}")
        print(f"🎤 Generando audio a {180} WPM...")

        engine.save_to_file(text, output_file)
        engine.runAndWait()

        if Path(output_file).exists():
            size = Path(output_file).stat().st_size
            print(f"✅ Audio generado: {output_file} ({size} bytes)")
        else:
            print(f"❌ Error generando audio")
            return False

        print("\n" + "="*60)
        print("TEST 2: Diferentes velocidades")
        print("="*60)

        speeds = [150, 180, 200, 220]
        for speed in speeds:
            output = f"test_windows_{speed}wpm.wav"
            engine.setProperty('rate', speed)
            engine.save_to_file(f"Prueba de velocidad a {speed} palabras por minuto", output)
            engine.runAndWait()

            if Path(output).exists():
                size = Path(output).stat().st_size
                print(f"  ✅ {speed} WPM: {output} ({size} bytes)")

        print("\n" + "="*60)
        print("✨ VENTAJAS DEL TTS DE WINDOWS:")
        print("="*60)
        print("  ✅ 100% offline - no requiere internet")
        print("  ✅ Rápido - genera audio instantáneamente")
        print("  ✅ Integrado en Windows")
        print("  ✅ Control preciso de velocidad (WPM)")
        print("  ✅ Fácil de usar desde Python")
        print("\n⚠️  CONSIDERACIÓN:")
        print("  - La calidad depende de las voces instaladas en Windows")
        print("\n💡 Para instalar más voces:")
        print("   Configuración > Hora e idioma > Voz > Agregar voces")

        print("\n✅ Test completado exitosamente!")
        return True

    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False

def compare_tts_methods():
    """Comparación de métodos TTS para Windows"""
    print("\n" + "="*60)
    print("📊 COMPARACIÓN DE MÉTODOS TTS PARA WINDOWS")
    print("="*60)

    print("""
┌──────────────┬──────────────┬───────────┬────────────────┬─────────────┐
│ Método       │ Instalación  │ Calidad   │ Velocidad      │ Offline     │
├──────────────┼──────────────┼───────────┼────────────────┼─────────────┤
│ SAPI         │ ⭐⭐⭐       │ ⭐⭐      │ ⭐⭐⭐         │ ✅          │
│ (PowerShell) │ Nativo       │ Variable  │ Muy rápida     │             │
├──────────────┼──────────────┼───────────┼────────────────┼─────────────┤
│ pyttsx3      │ ⭐⭐⭐       │ ⭐⭐      │ ⭐⭐⭐         │ ✅          │
│ (Python)     │ pip install  │ Variable  │ Rápida         │             │
├──────────────┼──────────────┼───────────┼────────────────┼─────────────┤
│ edge-tts     │ ⭐⭐⭐       │ ⭐⭐⭐⭐⭐ │ ⭐⭐           │ ❌          │
│ (MS Edge)    │ pip install  │ Excelente │ Req. internet  │ Necesita web│
├──────────────┼──────────────┼───────────┼────────────────┼─────────────┤
│ gTTS         │ ⭐⭐⭐       │ ⭐⭐⭐⭐⭐ │ ⭐⭐           │ ❌          │
│ (Google)     │ pip install  │ Natural   │ Req. internet  │ Necesita web│
└──────────────┴──────────────┴───────────┴────────────────┴─────────────┘

💡 RECOMENDACIÓN PARA WINDOWS:
   - OFFLINE: pyttsx3 o SAPI (PowerShell)
   - CALIDAD + Online: edge-tts (mejor que gTTS en español)
   - INTEGRACIÓN: pyttsx3 (fácil de integrar en Python)
""")

if __name__ == '__main__':
    success = test_windows_tts()

    compare_tts_methods()

    print("\n" + "="*60)
    print("🎯 PRÓXIMOS PASOS:")
    print("="*60)
    print("1. Reproduce los archivos generados para evaluar calidad")
    print("2. Si la calidad es aceptable, puedo integrar pyttsx3")
    print("   en el script principal para soporte de Windows")
    print("\n3. Para mejor calidad en español, considera edge-tts:")
    print("   pip install edge-tts")
    print('   python -m edge_tts --text "Hola" --voice es-ES-ElviraNeural --write-media test.mp3')

    sys.exit(0 if success else 1)
