#!/usr/bin/env python3
"""Test de motores TTS offline para Ubuntu"""

import subprocess
import sys
from pathlib import Path

def test_espeak():
    """Test espeak-ng (TTS nativo de Linux)"""
    print("\n" + "="*60)
    print("🔊 TEST 1: espeak-ng (TTS nativo de Linux)")
    print("="*60)

    # Verificar si espeak está instalado
    try:
        result = subprocess.run(['which', 'espeak-ng'],
                              capture_output=True, text=True)
        if result.returncode != 0:
            print("❌ espeak-ng NO está instalado")
            print("\n📦 Para instalar:")
            print("   sudo apt-get install espeak-ng")
            return False
    except Exception as e:
        print(f"❌ Error verificando espeak-ng: {e}")
        return False

    print("✅ espeak-ng está instalado")

    # Texto de prueba
    text = "Hola, esta es una prueba del sistema de síntesis de voz offline con espeak."
    output_file = "test_espeak.wav"

    try:
        # Generar audio con espeak-ng
        # -v es: voz en español
        # -s 180: velocidad en palabras por minuto
        # -w: escribir a archivo WAV
        print(f"\n📝 Texto: {text}")
        print(f"🎤 Generando audio con velocidad 180 WPM...")

        cmd = [
            'espeak-ng',
            '-v', 'es',           # Voz en español
            '-s', '180',          # Velocidad 180 WPM
            '-w', output_file,    # Salida a WAV
            text
        ]

        subprocess.run(cmd, check=True, capture_output=True)

        # Verificar archivo
        if Path(output_file).exists():
            size = Path(output_file).stat().st_size
            print(f"✅ Audio generado: {output_file} ({size} bytes)")
            print(f"💡 Reproduce con: aplay {output_file}")
            return True
        else:
            print("❌ No se generó el archivo de audio")
            return False

    except subprocess.CalledProcessError as e:
        print(f"❌ Error ejecutando espeak-ng: {e}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_espeak_different_speeds():
    """Test espeak con diferentes velocidades"""
    print("\n" + "="*60)
    print("🔊 TEST 2: espeak-ng con diferentes velocidades")
    print("="*60)

    text = "Prueba de velocidad de lectura."
    speeds = [180, 200, 220, 240]

    print(f"📝 Texto: {text}")

    for speed in speeds:
        output_file = f"test_espeak_{speed}wpm.wav"
        try:
            cmd = [
                'espeak-ng',
                '-v', 'es',
                '-s', str(speed),
                '-w', output_file,
                text
            ]
            subprocess.run(cmd, check=True, capture_output=True)

            if Path(output_file).exists():
                size = Path(output_file).stat().st_size
                print(f"  ✅ {speed} WPM: {output_file} ({size} bytes)")
            else:
                print(f"  ❌ {speed} WPM: Error generando archivo")

        except Exception as e:
            print(f"  ❌ {speed} WPM: Error - {e}")

    return True

def test_pyttsx3():
    """Test pyttsx3 (wrapper Python para TTS)"""
    print("\n" + "="*60)
    print("🔊 TEST 3: pyttsx3 (Python TTS wrapper)")
    print("="*60)

    try:
        import pyttsx3
        print("✅ pyttsx3 está instalado")
    except ImportError:
        print("❌ pyttsx3 NO está instalado")
        print("\n📦 Para instalar:")
        print("   pip3 install pyttsx3")
        print("   sudo apt-get install espeak-ng  # (backend)")
        return False

    text = "Hola, esta es una prueba con pyttsx3, un wrapper de Python para text to speech."
    output_file = "test_pyttsx3.wav"

    try:
        # Inicializar motor
        engine = pyttsx3.init()

        # Configurar voz en español
        voices = engine.getProperty('voices')
        spanish_voice = None

        print(f"\n🎤 Voces disponibles:")
        for idx, voice in enumerate(voices):
            lang_info = f" (lang: {voice.languages[0] if voice.languages else 'unknown'})"
            print(f"  {idx}: {voice.name}{lang_info}")
            if 'spanish' in voice.name.lower() or 'es' in str(voice.languages).lower():
                spanish_voice = voice.id

        if spanish_voice:
            engine.setProperty('voice', spanish_voice)
            print(f"\n✅ Usando voz en español")
        else:
            print(f"\n⚠️  No se encontró voz en español, usando voz por defecto")

        # Configurar velocidad (180 WPM)
        engine.setProperty('rate', 180)

        # Generar audio
        print(f"\n📝 Texto: {text}")
        print(f"🎤 Generando audio...")

        engine.save_to_file(text, output_file)
        engine.runAndWait()

        # Verificar archivo
        if Path(output_file).exists():
            size = Path(output_file).stat().st_size
            print(f"✅ Audio generado: {output_file} ({size} bytes)")
            return True
        else:
            print("❌ No se generó el archivo de audio")
            return False

    except Exception as e:
        print(f"❌ Error con pyttsx3: {e}")
        return False

def compare_methods():
    """Comparación de métodos"""
    print("\n" + "="*60)
    print("📊 COMPARACIÓN DE MÉTODOS TTS OFFLINE")
    print("="*60)

    print("""
┌─────────────┬──────────────┬───────────┬────────────────┬─────────────┐
│ Método      │ Instalación  │ Calidad   │ Velocidad      │ Español     │
├─────────────┼──────────────┼───────────┼────────────────┼─────────────┤
│ espeak-ng   │ ⭐⭐⭐        │ ⭐⭐      │ ⭐⭐⭐         │ ✅          │
│             │ Muy fácil    │ Sintética │ Muy rápida     │ Bueno       │
├─────────────┼──────────────┼───────────┼────────────────┼─────────────┤
│ pyttsx3     │ ⭐⭐⭐        │ ⭐⭐      │ ⭐⭐⭐         │ ✅          │
│             │ pip install  │ Sintética │ Rápida         │ Variable    │
├─────────────┼──────────────┼───────────┼────────────────┼─────────────┤
│ gTTS        │ ⭐⭐⭐        │ ⭐⭐⭐⭐⭐ │ ⭐⭐ (lenta)   │ ✅          │
│ (online)    │ pip install  │ Natural   │ Req. internet  │ Excelente   │
└─────────────┴──────────────┴───────────┴────────────────┴─────────────┘

💡 RECOMENDACIÓN:
   - Para OFFLINE: espeak-ng (más rápido y confiable)
   - Para CALIDAD: gTTS (requiere internet estable)
   - Para PYTHON: pyttsx3 (wrapper conveniente)
""")

def main():
    print("🎙️  TEST DE MOTORES TTS OFFLINE PARA UBUNTU")
    print("=" * 60)

    results = {
        'espeak': False,
        'espeak_speeds': False,
        'pyttsx3': False
    }

    # Test 1: espeak-ng básico
    results['espeak'] = test_espeak()

    # Test 2: espeak-ng con diferentes velocidades
    if results['espeak']:
        results['espeak_speeds'] = test_espeak_different_speeds()

    # Test 3: pyttsx3
    results['pyttsx3'] = test_pyttsx3()

    # Comparación
    compare_methods()

    # Resumen
    print("\n" + "="*60)
    print("📋 RESUMEN DE TESTS")
    print("="*60)

    for test_name, success in results.items():
        status = "✅ ÉXITO" if success else "❌ FALLÓ"
        print(f"  {test_name}: {status}")

    print("\n" + "="*60)
    print("🎯 PRÓXIMOS PASOS:")
    print("="*60)

    if results['espeak']:
        print("1. Reproduce los archivos generados:")
        print("   aplay test_espeak.wav")
        if results['espeak_speeds']:
            print("   aplay test_espeak_180wpm.wav")
            print("   aplay test_espeak_200wpm.wav")
        print("\n2. Si la calidad es aceptable, puedo integrar espeak-ng")
        print("   en el script principal como alternativa offline.")
    else:
        print("1. Instala espeak-ng:")
        print("   sudo apt-get install espeak-ng")
        print("\n2. Ejecuta este test nuevamente")

    if results['pyttsx3']:
        print("\n3. pyttsx3 también está disponible como opción")

    print("\n💡 Para integrar en el script principal, necesitaré saber:")
    print("   - ¿Qué motor prefieres? (espeak-ng o pyttsx3)")
    print("   - ¿La calidad de voz es aceptable para tu proyecto?")

if __name__ == '__main__':
    main()
