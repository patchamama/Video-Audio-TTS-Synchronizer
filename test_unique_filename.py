#!/usr/bin/env python3
"""Test de la función get_unique_output_path"""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))

from create_video_tts_from_srt import get_unique_output_path

def test_unique_output_path():
    """Test de generación de nombres únicos"""
    print("🧪 TEST: get_unique_output_path\n")
    print("="*60)

    # Caso 1: Archivo no existe
    test_path = Path("test_video_con_tts.mkv")
    result = get_unique_output_path(test_path)
    assert result == test_path, f"Error: {result} != {test_path}"
    print(f"✅ Caso 1: Archivo no existe")
    print(f"   Input: {test_path}")
    print(f"   Output: {result}\n")

    # Caso 2: Crear archivo y verificar que genera _1
    test_path.touch()
    result = get_unique_output_path(test_path)
    expected = Path("test_video_con_tts_1.mkv")
    assert result == expected, f"Error: {result} != {expected}"
    print(f"✅ Caso 2: Archivo existe, genera _1")
    print(f"   Input: {test_path}")
    print(f"   Output: {result}\n")

    # Caso 3: Crear _1 y verificar que genera _2
    result.touch()
    result2 = get_unique_output_path(test_path)
    expected2 = Path("test_video_con_tts_2.mkv")
    assert result2 == expected2, f"Error: {result2} != {expected2}"
    print(f"✅ Caso 3: _1 existe, genera _2")
    print(f"   Input: {test_path}")
    print(f"   Output: {result2}\n")

    # Limpiar archivos de test
    test_path.unlink()
    result.unlink()

    print("="*60)
    print("✅ TODOS LOS TESTS PASARON")
    print("="*60)
    print("\n💡 Comportamiento:")
    print("   video_con_tts.mkv (existe)")
    print("   → video_con_tts_1.mkv")
    print("\n   video_con_tts.mkv (existe)")
    print("   video_con_tts_1.mkv (existe)")
    print("   → video_con_tts_2.mkv")
    print("\nEsto evita sobreescribir archivos existentes.")

if __name__ == '__main__':
    test_unique_output_path()
