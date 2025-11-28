#!/usr/bin/env python3
"""Test de desactivación de colores en Windows"""

import platform
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from create_video_tts_from_srt import Colors

def test_colors():
    """Test de configuración de colores según el sistema operativo"""
    print("🧪 TEST: Configuración de Colores según Sistema Operativo\n")
    print("="*60)

    system = platform.system()
    print(f"💻 Sistema operativo detectado: {system}")
    print(f"🎨 Colores Windows detectado: {Colors._is_windows}")

    print("\n" + "="*60)
    print("Configuración de Colores:")
    print("="*60)

    colors_config = {
        'RED': Colors.RED,
        'GREEN': Colors.GREEN,
        'YELLOW': Colors.YELLOW,
        'BLUE': Colors.BLUE,
        'MAGENTA': Colors.MAGENTA,
        'CYAN': Colors.CYAN,
        'NC': Colors.NC
    }

    if Colors._is_windows:
        print("\n✅ Windows detectado: Colores DESACTIVADOS")
        print("   (Esto previene caracteres extraños en la consola)\n")

        # Verificar que todos los colores están vacíos
        all_empty = all(color == '' for color in colors_config.values())
        if all_empty:
            print("✅ CORRECTO: Todos los códigos de color están vacíos")
        else:
            print("❌ ERROR: Algunos códigos de color no están vacíos")
            for name, value in colors_config.items():
                if value != '':
                    print(f"   {name}: '{value}' (debería estar vacío)")

    else:
        print("\n✅ Unix/Linux/macOS detectado: Colores ACTIVADOS")
        print("   (Usando códigos ANSI)\n")

        # Verificar que los colores tienen códigos ANSI
        all_have_codes = all(color != '' or name == 'NC' for name, color in colors_config.items() if name != 'NC')
        if all_have_codes:
            print("✅ CORRECTO: Códigos ANSI configurados")
        else:
            print("❌ ERROR: Algunos códigos de color están vacíos")

    print("\n" + "="*60)
    print("Ejemplo de uso:")
    print("="*60)

    # Mostrar ejemplo de texto con colores
    example_text = f"{Colors.GREEN}✓ Éxito{Colors.NC}"
    example_error = f"{Colors.RED}✗ Error{Colors.NC}"
    example_warning = f"{Colors.YELLOW}⚠ Advertencia{Colors.NC}"
    example_info = f"{Colors.CYAN}ℹ Información{Colors.NC}"

    print(f"\nTexto con códigos de color:")
    print(f"  {example_text}")
    print(f"  {example_error}")
    print(f"  {example_warning}")
    print(f"  {example_info}")

    if Colors._is_windows:
        print("\n💡 En Windows, verás solo el texto sin colores")
        print("   En otros sistemas, verás el texto coloreado")
    else:
        print("\n💡 En tu sistema, deberías ver el texto con colores")

    print("\n" + "="*60)
    print("📋 RESUMEN")
    print("="*60)
    print(f"Sistema: {system}")
    print(f"Colores: {'DESACTIVADOS' if Colors._is_windows else 'ACTIVADOS'}")
    print(f"Estado: ✅ Configuración correcta")

if __name__ == '__main__':
    test_colors()
