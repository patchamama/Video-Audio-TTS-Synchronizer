# 🌍 Video TTS Synchronizer - Versión Multiplataforma

## 📋 Descripción

Versión universal que **detecta automáticamente** el sistema operativo y adapta:
- ✅ Motor TTS apropiado
- ✅ Comandos de instalación
- ✅ Voces disponibles
- ✅ Configuración óptima

**Sistemas soportados:**
- 🪟 Windows 10/11
- 🍎 macOS (10.15+)
- 🐧 Linux (Ubuntu, Debian, Fedora, etc.)

---

## 🆕 Archivos Nuevos

### 🧪 **test_system_multiplatform.py**
Script de verificación universal que:
- Detecta sistema operativo automáticamente
- Prueba motores TTS disponibles
- Da recomendaciones específicas por OS
- Sugiere comandos de instalación apropiados

### 🎬 **video_tts_multiplatform.py**
Script principal que:
- Adapta motor TTS según el OS
- Soporta múltiples engines
- Auto-selecciona la mejor opción
- Interfaz unificada para todos los sistemas

---

## 🎤 Motores TTS por Sistema

### 🪟 Windows

| Motor | Descripción | Instalación | Calidad |
|-------|-------------|-------------|---------|
| **pyttsx3** | Voces nativas (SAPI5) | `pip install pyttsx3` | ⭐⭐⭐ |
| **edge-tts** | Microsoft (online) | `pip install edge-tts` | ⭐⭐⭐⭐⭐ |
| **gTTS** | Google (online) | `pip install gtts` | ⭐⭐⭐ |

**Recomendado:** `pyttsx3` (offline) o `edge-tts` (online, mejor calidad)

**Agregar voces:**
1. Configuración → Hora e idioma → Idioma
2. Agregar idioma → Español/Inglés/Alemán
3. Opciones → Descargar paquete de voz

---

### 🍎 macOS

| Motor | Descripción | Instalación | Calidad |
|-------|-------------|-------------|---------|
| **pyttsx3** | Voces nativas | `pip3 install pyttsx3` | ⭐⭐⭐⭐ |
| **edge-tts** | Microsoft (online) | `pip3 install edge-tts` | ⭐⭐⭐⭐⭐ |
| **gTTS** | Google (online) | `pip3 install gtts` | ⭐⭐⭐ |

**Recomendado:** `pyttsx3` (usa voces de macOS de alta calidad)

**Voces disponibles:**
- macOS incluye excelentes voces por defecto
- Añadir más: Preferencias del Sistema → Accesibilidad → Contenido hablado → Voces del sistema

**Calidad de voces macOS:**
- ⭐⭐⭐⭐⭐ Mejores voces nativas de cualquier OS
- Muy naturales y expresivas
- Múltiples idiomas incluidos

---

### 🐧 Linux

| Motor | Descripción | Instalación | Calidad |
|-------|-------------|-------------|---------|
| **espeak** | TTS nativo Linux | `sudo apt install espeak` | ⭐⭐ |
| **pyttsx3** | Con espeak backend | `pip3 install pyttsx3` | ⭐⭐ |
| **edge-tts** | Microsoft (online) | `pip3 install edge-tts` | ⭐⭐⭐⭐⭐ |
| **gTTS** | Google (online) | `pip3 install gtts` | ⭐⭐⭐ |

**Recomendado:** `edge-tts` (mejor calidad) o `espeak` (offline)

**Instalar espeak:**
```bash
# Ubuntu/Debian
sudo apt install espeak espeak-data libespeak-dev

# Fedora
sudo dnf install espeak espeak-devel

# Arch
sudo pacman -S espeak
```

---

## 🚀 Uso Rápido

### 1. Verificar Sistema

```bash
# Ejecutar verificación
python3 test_system_multiplatform.py
```

**Detecta automáticamente:**
- Sistema operativo
- Motores TTS disponibles
- Voces instaladas
- Recomienda instalaciones

**Salida esperada:**
```
╔══════════════════════════════════════════════════════════════╗
║         VERIFICACIÓN DE SISTEMA - MULTIPLATAFORMA           ║
║         Sistema detectado: macOS                            ║
╚══════════════════════════════════════════════════════════════╝

▶ Detectando plataforma
  ℹ Sistema Operativo: macOS
  ℹ Versión: 13.5
  ✓ Plataforma soportada: macOS

▶ Verificando motores TTS para MACOS
  ℹ Motores a verificar: pyttsx3, edge-tts, gtts

  ℹ Probando pyttsx3 (voces nativas)...
  ✓ pyttsx3: 24 voces encontradas
  ℹ Voces encontradas:
    • Alex
    • Samantha
    • Victoria
    ... y 21 más

  ✓ Motores TTS disponibles: pyttsx3, edge-tts, gtts

▶ Probando generación de TTS
  ℹ Intentando con pyttsx3...
  ✓ Audio generado con pyttsx3

✓ TODOS LOS TESTS PASARON

RECOMENDACIONES PARA TU SISTEMA

macOS:
  • pyttsx3 usa voces nativas de macOS
  • Voces disponibles en: Preferencias → Accesibilidad
  • edge-tts recomendado para mejor calidad
```

---

### 2. Listar Motores Disponibles

```bash
python3 video_tts_multiplatform.py --list-engines
```

**Salida (ejemplo en Linux):**
```
🎤 MOTORES TTS DISPONIBLES EN LINUX:
============================================================
  • espeak
  • pyttsx3
  • edge
  • gtts
```

---

### 3. Listar Voces

```bash
# Voces nativas (pyttsx3)
python3 video_tts_multiplatform.py --list-voices --engine pyttsx3

# Voces edge-tts
python3 video_tts_multiplatform.py --list-voices --engine edge --lang es
```

---

### 4. Procesar Video

#### Modo Automático (Recomendado)

```bash
# El script auto-detecta y usa el mejor motor
python3 video_tts_multiplatform.py video.mp4 subtitulos.srt output.mp4 --lang es
```

**¿Qué hace?**
- Detecta tu OS
- Elige el mejor motor disponible
- Selecciona voz apropiada
- Procesa automáticamente

#### Especificar Motor

```bash
# Usar pyttsx3 (voces nativas)
python3 video_tts_multiplatform.py video.mp4 subs.srt out.mp4 --engine pyttsx3 --lang es

# Usar edge-tts (alta calidad, online)
python3 video_tts_multiplatform.py video.mp4 subs.srt out.mp4 --engine edge --lang es

# Usar gTTS (Google, online)
python3 video_tts_multiplatform.py video.mp4 subs.srt out.mp4 --engine gtts --lang es

# Usar espeak (Linux)
python3 video_tts_multiplatform.py video.mp4 subs.srt out.mp4 --engine espeak --lang es
```

#### Con Voz Específica

```bash
# pyttsx3 con voz específica
python3 video_tts_multiplatform.py video.mp4 subs.srt out.mp4 \
    --engine pyttsx3 --voice "VOICE_ID" --lang es

# edge-tts con voz específica
python3 video_tts_multiplatform.py video.mp4 subs.srt out.mp4 \
    --engine edge --voice "es-MX-DaliaNeural"
```

---

## 📦 Instalación por Sistema

### 🪟 Windows

```cmd
# 1. Python 3.8+
# Descarga: https://www.python.org/

# 2. FFmpeg
# Descarga: https://ffmpeg.org/download.html
# Agregar al PATH

# 3. Dependencias Python
pip install pysrt pydub pyttsx3

# 4. Opcional (mejor calidad)
pip install edge-tts
```

---

### 🍎 macOS

```bash
# 1. Homebrew (si no está instalado)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# 2. FFmpeg
brew install ffmpeg

# 3. Python (si no está instalado)
brew install python3

# 4. Dependencias Python
pip3 install pysrt pydub pyttsx3

# 5. Opcional (mejor calidad)
pip3 install edge-tts gtts
```

**Verificar instalación:**
```bash
python3 --version
ffmpeg -version
python3 test_system_multiplatform.py
```

---

### 🐧 Linux (Ubuntu/Debian)

```bash
# 1. Actualizar sistema
sudo apt update

# 2. Python y FFmpeg
sudo apt install python3 python3-pip ffmpeg

# 3. eSpeak (recomendado para Linux)
sudo apt install espeak espeak-data libespeak-dev

# 4. Dependencias Python
pip3 install pysrt pydub pyttsx3

# 5. Opcional (mejor calidad)
pip3 install edge-tts gtts
```

**Verificar instalación:**
```bash
python3 --version
ffmpeg -version
espeak --version
python3 test_system_multiplatform.py
```

---

## 🎯 Ejemplos por Sistema

### Ejemplo Windows

```cmd
REM Verificar sistema
python test_system_multiplatform.py

REM Listar voces disponibles
python video_tts_multiplatform.py --list-voices

REM Procesar con voces nativas
python video_tts_multiplatform.py video.mp4 subs_es.srt output.mp4 --lang es

REM Procesar con edge-tts (mejor calidad)
python video_tts_multiplatform.py video.mp4 subs_es.srt output.mp4 ^
    --engine edge --voice es-ES-AlvaroNeural
```

---

### Ejemplo macOS

```bash
# Verificar sistema
python3 test_system_multiplatform.py

# Listar voces de macOS
python3 video_tts_multiplatform.py --list-voices --engine pyttsx3

# Procesar con voces de macOS (excelente calidad)
python3 video_tts_multiplatform.py video.mp4 subs_es.srt output.mp4 --lang es

# Procesar con edge-tts
python3 video_tts_multiplatform.py video.mp4 subs_en.srt output.mp4 \
    --engine edge --voice en-US-AriaNeural
```

---

### Ejemplo Linux

```bash
# Verificar sistema
python3 test_system_multiplatform.py

# Listar motores disponibles
python3 video_tts_multiplatform.py --list-engines

# Procesar con espeak (offline)
python3 video_tts_multiplatform.py video.mp4 subs_es.srt output.mp4 \
    --engine espeak --lang es

# Procesar con edge-tts (mejor calidad, online)
python3 video_tts_multiplatform.py video.mp4 subs_es.srt output.mp4 \
    --engine edge --voice es-ES-AlvaroNeural

# Procesar con gTTS (Google, online)
python3 video_tts_multiplatform.py video.mp4 subs_de.srt output.mp4 \
    --engine gtts --lang de
```

---

## 🔧 Configuración Avanzada

### Voces en macOS

**Ver voces instaladas:**
```bash
# Sistema
say -v "?"

# En el script
python3 video_tts_multiplatform.py --list-voices --engine pyttsx3
```

**Instalar más voces:**
1. Preferencias del Sistema
2. Accesibilidad
3. Contenido hablado
4. Voces del sistema
5. Descargar más voces

**Probar voz:**
```bash
say -v "Mónica" "Hola, esta es una prueba"
```

---

### Voces en Linux (espeak)

**Idiomas disponibles:**
```bash
espeak --voices
```

**Probar voz:**
```bash
espeak -v es "Hola, esta es una prueba"
espeak -v en "Hello, this is a test"
espeak -v de "Hallo, das ist ein Test"
```

**Mejorar calidad en espeak:**
```bash
# Velocidad más lenta
espeak -v es -s 150 "Texto"

# Tono más bajo
espeak -v es -p 30 "Texto"

# Amplitud mayor
espeak -v es -a 150 "Texto"
```

---

## 📊 Comparación de Motores

| Motor | Windows | macOS | Linux | Online | Calidad | Velocidad |
|-------|---------|-------|-------|--------|---------|-----------|
| **pyttsx3** | ✅ | ✅ | ✅ | ❌ | ⭐⭐⭐ (Win)<br>⭐⭐⭐⭐⭐ (Mac)<br>⭐⭐ (Linux) | Rápida |
| **espeak** | ❌ | ❌ | ✅ | ❌ | ⭐⭐ | Muy rápida |
| **edge-tts** | ✅ | ✅ | ✅ | ✅ | ⭐⭐⭐⭐⭐ | Media |
| **gTTS** | ✅ | ✅ | ✅ | ✅ | ⭐⭐⭐ | Media |

---

## 🐛 Solución de Problemas

### Windows: Sin voces

**Problema:**
```
✗ pyttsx3: Sin voces disponibles
```

**Solución:**
1. Configuración → Hora e idioma
2. Idioma → Agregar idioma
3. Seleccionar Español
4. Opciones → Descargar paquete de voz
5. Reiniciar script

---

### macOS: Error de permisos

**Problema:**
```
Error: Operation not permitted
```

**Solución:**
```bash
# Dar permisos a Terminal
Sistema → Privacidad → Accesibilidad → Terminal

# O usar con sudo
sudo python3 test_system_multiplatform.py
```

---

### Linux: espeak no funciona

**Problema:**
```
✗ espeak: No instalado
```

**Solución:**
```bash
# Ubuntu/Debian
sudo apt install espeak espeak-data libespeak-dev
sudo apt install python3-espeak

# Fedora
sudo dnf install espeak espeak-devel

# Verificar
espeak --version
```

---

### Todos: edge-tts falla

**Problema:**
```
✗ edge-tts: Error de conexión
```

**Soluciones:**
1. Verificar conexión a internet
2. Verificar firewall
3. Reinstalar:
   ```bash
   pip3 uninstall edge-tts
   pip3 install edge-tts
   ```

---

## 💡 Recomendaciones por Uso

### Uso Offline (sin internet)

**Windows:** `pyttsx3` + voces del sistema  
**macOS:** `pyttsx3` (excelente calidad)  
**Linux:** `espeak` + `pyttsx3`

```bash
python3 video_tts_multiplatform.py video.mp4 subs.srt out.mp4 \
    --engine pyttsx3 --lang es
```

---

### Máxima Calidad (con internet)

**Todos los sistemas:** `edge-tts`

```bash
python3 video_tts_multiplatform.py video.mp4 subs.srt out.mp4 \
    --engine edge --voice es-ES-AlvaroNeural
```

---

### Procesamiento Rápido

**Windows/macOS:** `pyttsx3`  
**Linux:** `espeak`

```bash
python3 video_tts_multiplatform.py video.mp4 subs.srt out.mp4 \
    --engine auto  # Auto-selecciona el más rápido
```

---

### Producción Profesional

**Recomendación:** `edge-tts` con voces neuronales

```bash
# Español (España)
--engine edge --voice es-ES-AlvaroNeural

# Español (México)
--engine edge --voice es-MX-DaliaNeural

# Inglés (USA)
--engine edge --voice en-US-AriaNeural

# Alemán
--engine edge --voice de-DE-KatjaNeural
```

---

## 🎓 Tutorial Completo Multiplataforma

### Primer Uso

1. **Instalar requisitos según tu OS** (ver sección Instalación)

2. **Verificar sistema:**
   ```bash
   python3 test_system_multiplatform.py
   ```

3. **Ver motores disponibles:**
   ```bash
   python3 video_tts_multiplatform.py --list-engines
   ```

4. **Ver voces:**
   ```bash
   python3 video_tts_multiplatform.py --list-voices --lang es
   ```

5. **Probar con video corto:**
   ```bash
   python3 video_tts_multiplatform.py test.mp4 test.srt output.mp4
   ```

6. **Procesar video real:**
   ```bash
   python3 video_tts_multiplatform.py mi_video.mp4 subs.srt final.mp4 \
       --engine edge --voice es-ES-AlvaroNeural
   ```

---

## ✅ Checklist

### Instalación Completada:
- [ ] Python 3.8+ instalado
- [ ] FFmpeg instalado
- [ ] Paquetes Python: pysrt, pydub
- [ ] Al menos un motor TTS instalado
- [ ] Verificación ejecutada exitosamente

### Listo para Producción:
- [ ] Tests pasan al 100%
- [ ] Voces disponibles en idioma objetivo
- [ ] Espacio suficiente en disco
- [ ] Probado con video de prueba

---

## 🎉 Ventajas de la Versión Multiplataforma

✅ **Un solo script para todos**
- Windows, macOS, Linux
- Detección automática
- Sin configuración manual

✅ **Múltiples motores soportados**
- Nativo (pyttsx3, espeak)
- Online (edge-tts, gTTS)
- Auto-selección inteligente

✅ **Mejor calidad según OS**
- macOS: Voces nativas excelentes
- Windows: SAPI5 + edge-tts
- Linux: espeak + edge-tts

✅ **Flexible y extensible**
- Fácil agregar motores
- Configuración por OS
- Recomendaciones automáticas

---

**¡Ahora tu script funciona en cualquier sistema operativo!** 🌍🎉

**Versión:** 2.0 Multiplataforma  
**Fecha:** 2024-11-19  
**Licencia:** Uso libre y gratuito
