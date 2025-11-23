# 🎙️ SRT to Video TTS - Generador de Audio Text-to-Speech para Videos

Sistema automatizado para generar audio TTS (Text-to-Speech) a partir de archivos SRT y sincronizarlo con video. Soporta ajuste inteligente de velocidad, detección automática de plataforma y múltiples modos de operación.

## ✨ Características

- 🤖 **Ajuste automático de velocidad**: Prueba diferentes rates (180-240 wpm) para encontrar el óptimo
- 🎯 **Modo No-Freeze**: Trunca audios largos en lugar de congelar frames del video
- 🧠 **Aprendizaje adaptativo**: Después de 50 subtítulos, determina el rate óptimo para el resto
- 🔄 **Multiplataforma**: Compatible con macOS (comando `say`), Linux y Windows (Python + gTTS)
- 📊 **SRT Debug**: Genera archivo SRT con información de rates, offsets y modificaciones
- 🎬 **Manejo de freezes**: Congela frames cuando el audio es muy largo (modo predeterminado)
- 📝 **Logs detallados**: Sistema completo de logging para debugging
- 🧪 **Modo test**: Procesa solo N subtítulos para pruebas rápidas

## 📋 Requisitos

### Todos los sistemas
- FFmpeg (para procesamiento de audio/video)
- BC (calculadora de línea de comandos)

### macOS
- Bash 4.0+ (instalado vía Homebrew, el script de instalación lo configura)
- Comando `say` (incluido en macOS)

### Linux/Windows
- Python 3.x
- Paquetes Python: `gtts`, `pydub`

## 🚀 Instalación

### Instalación automática

```bash
# Clonar el repositorio
git clone <url-del-repo>
cd srt-to-video-tts

# Ejecutar instalador
chmod +x install.sh
./install.sh
```

El instalador detecta automáticamente tu sistema operativo e instala:
- ✅ FFmpeg
- ✅ BC
- ✅ Bash 4+ (macOS)
- ✅ Python y dependencias (Linux/Windows)
- ✅ Configura alias `bash2` para Bash moderno en macOS

### Instalación manual

#### macOS
```bash
# Instalar Homebrew si no lo tienes
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Instalar dependencias
brew install ffmpeg bc bash

# Configurar Bash moderno (opcional pero recomendado)
echo '/opt/homebrew/bin/bash' | sudo tee -a /etc/shells
# Agregar alias a tu shell
echo 'alias bash2="/opt/homebrew/bin/bash"' >> ~/.zshrc
source ~/.zshrc
```

#### Linux (Ubuntu/Debian)
```bash
sudo apt update
sudo apt install -y ffmpeg bc python3 python3-pip
pip3 install gtts pydub
```

#### Linux (Fedora/RHEL)
```bash
sudo dnf install -y ffmpeg bc python3 python3-pip
pip3 install gtts pydub
```

#### Windows (con Git Bash o WSL)
```bash
# Instalar FFmpeg desde https://ffmpeg.org/download.html
# O usar Chocolatey:
choco install ffmpeg

# Instalar Python y dependencias
pip install gtts pydub
```

## 📖 Uso

### Sintaxis básica

```bash
./srt_to_video_v2.5.sh [archivo.srt] [video] [opciones]
```

### Opciones disponibles

| Opción | Descripción |
|--------|-------------|
| `--test` | Modo test con 30 subtítulos |
| `--test=N` | Modo test con N subtítulos |
| `--solo-audio` | Solo genera audio, sin procesar video |
| `--no-freeze` | Trunca audios largos en lugar de freeze |
| `carpeta_audios` | Usa audios ya generados (sin generar nuevos) |

### Ejemplos de uso

#### 1. Uso básico
```bash
# Procesar subtítulos completos con posibilidad de freeze
./srt_to_video_v2.5.sh subtitulos.srt mi_video.mp4
```

**Resultado:**
- `mi_video_con_tts.mkv` - Video con audio TTS
- `mi_video_debug.srt` - SRT con información de debug

#### 2. Modo No-Freeze (sin congelar frames)
```bash
# Trunca audios largos en lugar de congelar video
./srt_to_video_v2.5.sh subtitulos.srt mi_video.mp4 --no-freeze
```

**Ventajas:**
- ✅ Video fluido sin interrupciones
- ✅ Audios cortados exactamente al límite de tiempo
- ⚠️ Puede perder fin de frases largas

#### 3. Modo Test
```bash
# Procesar solo los primeros 50 subtítulos
./srt_to_video_v2.5.sh subtitulos.srt mi_video.mp4 --test=50

# Combinar test con no-freeze
./srt_to_video_v2.5.sh subtitulos.srt mi_video.mp4 --test=50 --no-freeze
```

#### 4. Solo Audio (sin video)
```bash
# Genera solo los archivos de audio
./srt_to_video_v2.5.sh subtitulos.srt mi_video.mp4 --solo-audio
```

**Resultado:**
- `mi_video_tts_audio.wav` - Audio en formato WAV
- `mi_video_tts_audio.aac` - Audio en formato AAC

**Agregar audio al video manualmente:**
```bash
# Reemplazar audio original
ffmpeg -i mi_video.mp4 -i mi_video_tts_audio.aac \
  -map 0:v -map 1:a -c:v copy -c:a copy \
  -shortest mi_video_final.mkv

# Agregar como pista adicional
ffmpeg -i mi_video.mp4 -i mi_video_tts_audio.aac \
  -map 0:v -map 0:a -map 1:a -c copy \
  -metadata:s:a:1 title="Audio TTS" \
  mi_video_dual_audio.mkv
```

#### 5. Reutilizar audios generados
```bash
# Primera ejecución: genera audios
./srt_to_video_v2.5.sh subtitulos.srt video.mp4 --test=100

# Los audios quedan en temp_audio_XXXXX/

# Segunda ejecución: usa audios existentes
./srt_to_video_v2.5.sh subtitulos.srt video.mp4 temp_audio_12345
```

#### 6. Modo interactivo
```bash
# Sin argumentos, pregunta interactivamente
./srt_to_video_v2.5.sh
```

## 🔧 Funcionamiento

### 1. Ajuste inteligente de velocidad

El script prueba diferentes rates de velocidad:

```
180 wpm (palabras por minuto) - Velocidad normal
  ↓ Si no cabe
200 wpm - Velocidad media-rápida
  ↓ Si no cabe
220 wpm - Velocidad rápida
  ↓ Si no cabe (solo con --no-freeze)
240 wpm - Velocidad muy rápida + truncado
```

### 2. Aprendizaje adaptativo

Después de procesar 50 subtítulos, el script:
1. Analiza qué rate fue más usado
2. Determina el rate óptimo
3. Usa ese rate como predeterminado para los restantes

### 3. Modos de operación

#### Modo Normal (con freeze)
```
Audio largo → Congela último frame → Continúa video
```
- ✅ No pierde contenido del audio
- ⚠️ Video se pausa temporalmente

#### Modo No-Freeze
```
Audio largo → Trunca al límite → Continúa inmediato
```
- ✅ Video siempre fluido
- ⚠️ Puede cortar fin de frases

## 📊 Archivo SRT Debug

El archivo `*_debug.srt` contiene información detallada:

```
1
00:00:00,000 --> 00:00:05,000
[#1 r180] Este es el primer subtítulo

2
00:00:05,000 --> 00:00:10,500
[#2 r200 +250ms] [⏸️ FREEZE +1.2s] Subtítulo largo que necesita freeze

3
00:00:11,700 --> 00:00:15,000
[#3 r240 +1450ms] [✂️ TRUNCADO] Subtítulo muy largo truncado
```

**Leyenda:**
- `#N` - Número de subtítulo original
- `rXXX` - Rate usado (wpm)
- `+XXms` - Offset acumulado por freezes
- `⏸️ FREEZE +Xs` - Freeze de X segundos
- `✂️ TRUNCADO` - Audio fue cortado

## 🐛 Debugging

### Logs disponibles

Cuando hay errores, revisa los logs en `temp_audio_XXXXX/logs/`:

```
logs/
├── vseg_256.log          # Error en segmento de video
├── frame_256.log         # Error extrayendo frame
├── freeze_256.log        # Error creando freeze
├── truncate_42.log       # Error truncando audio
├── concat_video.log      # Error concatenando segmentos
├── ffmpeg_merge.log      # Error en fusión final
└── ffmpeg_merge_alt.log  # Intento con método alternativo
```

### Errores comunes

#### 1. "Error parsing options for output file"
```bash
# El script ahora muestra:
# - Parámetros exactos usados (start_sec, duration)
# - Últimas 10 líneas del error
# - Log completo en vseg_XXX.log

# Revisar el log:
cat temp_audio_12345/logs/vseg_256.log
```

**Causas comunes:**
- Timestamps negativos o inválidos en SRT
- Duración de subtítulo = 0
- Video corrupto en esa posición

#### 2. "No hay audio en el video final"
El script intenta automáticamente método alternativo con re-encoding.

#### 3. Audio desincronizado
Revisar el SRT debug para ver offsets acumulados.

## 🎨 Estructura del proyecto

```
srt-to-video-tts/
├── srt_to_video_v2.5.sh      # Script principal
├── generate_tts.py            # Generador TTS Python (Linux/Windows)
├── install.sh                 # Instalador automático
├── README.md                  # Esta documentación
└── temp_audio_XXXXX/          # Carpeta temporal (se genera)
    ├── logs/                  # Logs de operaciones
    ├── N.wav                  # Audios generados
    ├── vseg_N.mkv            # Segmentos de video
    ├── vfreeze_N.mkv         # Segmentos congelados
    └── audio_final.wav        # Audio maestro final
```

## 🔍 Resolución de problemas

### macOS: "bad array subscript"
```bash
# Tu versión de Bash es muy antigua
bash --version

# Usar Bash moderno instalado por el script
bash2 srt_to_video_v2.5.sh subtitulos.srt video.mp4
```

### Linux/Windows: "gtts not found"
```bash
pip3 install gtts pydub --upgrade
```

### FFmpeg no encontrado
```bash
# Verificar instalación
ffmpeg -version

# Si no está instalado, ejecutar install.sh nuevamente
./install.sh
```

## 🤝 Contribuir

1. Fork el proyecto
2. Crea una rama para tu feature (`git checkout -b feature/AmazingFeature`)
3. Commit tus cambios (`git commit -m 'Add some AmazingFeature'`)
4. Push a la rama (`git push origin feature/AmazingFeature`)
5. Abre un Pull Request

## 📝 Changelog

### v2.5 (Actual)
- ✨ Nuevo: Opción `--no-freeze` para truncar audios
- 🐛 Mejorado: Manejo robusto de errores con logs detallados
- 📊 Nuevo: Validación de parámetros antes de ejecutar ffmpeg
- 🔧 Mejorado: Mensajes de error más informativos
- 📝 Nuevo: Sistema completo de logging

### v2.4
- ✨ Detección automática de sistema operativo
- 🎯 Ajuste automático de velocidad
- 🧠 Aprendizaje adaptativo de rate óptimo

## 📄 Licencia

Este proyecto está bajo la Licencia MIT - ver el archivo LICENSE para detalles.

## 👥 Autores

- Desarrollo inicial - Script para automatización de TTS en videos

## 🙏 Agradecimientos

- FFmpeg por el procesamiento multimedia
- gTTS por el motor TTS en Python
- Comunidad de código abierto

---

**¿Problemas? ¿Sugerencias?** Abre un issue en el repositorio.