# 🪟 Guía de TTS para Windows

Esta guía muestra cómo usar TTS (Text-to-Speech) nativo en Windows, completamente offline.

## 🚀 Opción 1: PowerShell (Más Rápido)

### ✨ One-Liner Simple

Abre **PowerShell** y copia/pega:

```powershell
Add-Type -AssemblyName System.Speech; $synth = New-Object System.Speech.Synthesis.SpeechSynthesizer; $synth.SetOutputToWaveFile("prueba.wav"); $synth.Speak("Hola, esta es una prueba de voz en español"); Write-Host "Audio generado: prueba.wav"
```

Esto generará `prueba.wav` en el directorio actual.

### 🎛️ One-Liner con Velocidad Ajustada

```powershell
Add-Type -AssemblyName System.Speech; $synth = New-Object System.Speech.Synthesis.SpeechSynthesizer; $synth.Rate = 2; $synth.SetOutputToWaveFile("prueba_rapida.wav"); $synth.Speak("Este audio es más rápido"); Write-Host "Audio rápido generado"
```

**Velocidades:**
- `-10` = Muy lento
- `0` = Normal
- `2` = Un poco más rápido
- `5` = Rápido
- `10` = Muy rápido

### 🎤 Ver Voces Disponibles

```powershell
Add-Type -AssemblyName System.Speech; $synth = New-Object System.Speech.Synthesis.SpeechSynthesizer; $synth.GetInstalledVoices() | ForEach-Object { Write-Host "$($_.VoiceInfo.Name) - $($_.VoiceInfo.Culture.Name)" }
```

### 📜 Script Completo

Para un test más completo, ejecuta:

```powershell
.\test_windows_tts.ps1
```

Este script:
- Muestra todas las voces disponibles
- Genera audio en español (si hay voz instalada)
- Crea archivos con diferentes velocidades
- Reproduce el audio automáticamente

## 🐍 Opción 2: Python con pyttsx3

### Instalación

```bash
pip install pyttsx3
```

### Uso Rápido

```python
import pyttsx3

engine = pyttsx3.init()
engine.setProperty('rate', 180)  # Velocidad en WPM
engine.save_to_file('Hola, prueba de voz', 'audio.wav')
engine.runAndWait()
```

### Script de Test

```bash
python test_windows_tts.py
```

## 🌐 Opción 3: edge-tts (Mejor Calidad, Requiere Internet)

### Instalación

```bash
pip install edge-tts
```

### Uso

```bash
# Generar audio en español con voz neural de alta calidad
edge-tts --text "Hola, esta es una prueba" --voice es-ES-ElviraNeural --write-media audio.mp3

# Ver todas las voces en español
edge-tts --list-voices | findstr "es-"
```

### Voces Recomendadas en Español

```bash
# Mujer - España
edge-tts --voice es-ES-ElviraNeural --text "Prueba de voz femenina española" --write-media test.mp3

# Hombre - España
edge-tts --voice es-ES-AlvaroNeural --text "Prueba de voz masculina española" --write-media test.mp3

# Mujer - México
edge-tts --voice es-MX-DaliaNeural --text "Prueba de voz femenina mexicana" --write-media test.mp3

# Mujer - Argentina
edge-tts --voice es-AR-ElenaNeural --text "Prueba de voz femenina argentina" --write-media test.mp3
```

### Ajustar Velocidad con edge-tts

```bash
# +50% más rápido
edge-tts --text "Texto más rápido" --voice es-ES-ElviraNeural --rate=+50% --write-media rapido.mp3

# -25% más lento
edge-tts --text "Texto más lento" --voice es-ES-ElviraNeural --rate=-25% --write-media lento.mp3
```

## 📊 Comparación de Métodos

| Método | Offline | Calidad | Velocidad | Instalación |
|--------|---------|---------|-----------|-------------|
| **PowerShell (SAPI)** | ✅ | ⭐⭐ | ⚡⚡⚡ | ✅ Incluido |
| **pyttsx3** | ✅ | ⭐⭐ | ⚡⚡⚡ | pip install |
| **edge-tts** | ❌ | ⭐⭐⭐⭐⭐ | ⚡⚡ | pip install |
| **gTTS** | ❌ | ⭐⭐⭐⭐ | ⚡⚡ | pip install |

## 💡 Recomendaciones

### Para uso offline (sin internet):
1. **PowerShell** - La opción más rápida y simple
2. **pyttsx3** - Si necesitas integrarlo en Python

### Para mejor calidad (con internet):
1. **edge-tts** - Excelente calidad, voces neurales
2. **gTTS** - Buena alternativa

### Para proyectos de producción:
- **Desarrollo en Windows**: pyttsx3
- **Máxima calidad**: edge-tts (con fallback a pyttsx3)

## 🔧 Instalar Más Voces en Windows

1. Abrir **Configuración** de Windows
2. Ir a **Hora e idioma** > **Voz**
3. Hacer clic en **Agregar voces**
4. Buscar **"Español"**
5. Instalar voces disponibles (ej: Microsoft Helena, Microsoft Sabina)

Después de instalar, las nuevas voces estarán disponibles en PowerShell y pyttsx3.

## 📝 Archivos de Ejemplo Incluidos

- `test_windows_tts.ps1` - Script PowerShell completo
- `test_windows_tts.py` - Script Python con pyttsx3
- `windows_tts_oneliner.txt` - Colección de one-liners útiles

## 🎯 Ejemplo Práctico: Generar Audio para Subtítulos

### Con PowerShell

```powershell
# Crear función para generar TTS
function Generate-TTS {
    param(
        [string]$Text,
        [string]$OutputFile,
        [int]$Rate = 2
    )

    Add-Type -AssemblyName System.Speech
    $synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
    $synth.Rate = $Rate
    $synth.SetOutputToWaveFile($OutputFile)
    $synth.Speak($Text)
}

# Usar
Generate-TTS -Text "Este es el primer subtítulo" -OutputFile "sub1.wav" -Rate 2
Generate-TTS -Text "Este es el segundo subtítulo" -OutputFile "sub2.wav" -Rate 2
```

### Con Python (pyttsx3)

```python
import pyttsx3

def generate_tts(text, output_file, rate=180):
    engine = pyttsx3.init()
    engine.setProperty('rate', rate)
    engine.save_to_file(text, output_file)
    engine.runAndWait()

# Usar
generate_tts("Este es el primer subtítulo", "sub1.wav", rate=180)
generate_tts("Este es el segundo subtítulo", "sub2.wav", rate=200)
```

## ❓ Solución de Problemas

### "No se encuentra el comando"
Asegúrate de estar ejecutando **PowerShell** (no CMD). En Windows 10/11, busca "PowerShell" en el menú inicio.

### "No hay voz en español"
1. Ve a Configuración > Hora e idioma > Voz
2. Instala voces en español desde "Agregar voces"
3. Reinicia PowerShell después de instalar

### "pyttsx3 no funciona"
```bash
# Reinstalar con todas las dependencias
pip uninstall pyttsx3
pip install pyttsx3 pywin32
```

### "edge-tts da error de conexión"
edge-tts requiere internet. Si no tienes conexión, usa PowerShell o pyttsx3 en su lugar.

---

**¿Necesitas ayuda?** Abre un issue en el repositorio con el error que estás experimentando.
