# Video-Audio-TTS Synchronizer

Sistema inteligente de sincronización de audio TTS (Text-to-Speech) con video a partir de archivos de subtítulos SRT.

## 📋 Tabla de Contenidos

- [Descripción](#-descripción)
- [Características](#-características)
- [Requisitos](#-requisitos)
- [Instalación](#-instalación)
- [Uso](#-uso)
- [Algoritmos y Lógica](#-algoritmos-y-lógica)
- [Diagrama de Flujo](#-diagrama-de-flujo)
- [Archivos Generados](#-archivos-generados)
- [Pendientes y Roadmap](#-pendientes-y-roadmap)

## 🎯 Descripción

Este proyecto permite convertir archivos de subtítulos (SRT) en audio sincronizado con video, generando automáticamente voces TTS con ajuste inteligente de velocidad. Es especialmente útil para:

- Crear audiolibros visuales desde subtítulos
- Generar contenido accesible para personas con discapacidad visual
- Crear versiones narradas de presentaciones o cursos
- Procesar y sincronizar contenido educativo

## ✨ Características

### Implementadas

- ✅ **Parseo robusto de SRT**: Valida y renumera subtítulos automáticamente
- ✅ **Ajuste inteligente de velocidad**: 180-240 WPM según disponibilidad de tiempo
- ✅ **Freeze frames automáticos**: Congela video cuando el audio es más largo que el subtítulo
- ✅ **Sincronización precisa**: Construye pista de audio master alineada con timestamps
- ✅ **Eliminación de pausas**: Remueve gaps mayores a 15 minutos
- ✅ **Multi-plataforma**: Compatible con macOS (say) y Linux (gTTS)
- ✅ **Modo test**: Procesar solo N subtítulos para pruebas rápidas
- ✅ **Progreso visual**: Indicadores de progreso cada 100 subtítulos
- ✅ **SRT debug**: Genera archivo con metadatos de TTS para inspección
- ✅ **Reutilización de audio**: Soporte para carpeta de audios pre-generados

### En Desarrollo

- 🔄 Suite de testing automatizado
- 🔄 Interfaz interactiva para parámetros
- 🔄 Conversión de formatos de salida

## 📦 Requisitos

### Sistema Operativo

**macOS:**
```bash
brew install ffmpeg
# El comando 'say' viene incluido en macOS
```

**Linux/Ubuntu:**
```bash
sudo apt-get install ffmpeg python3
sudo apt install python3-gtts python3-pydub
```

### Python

- Python 3.7+
- Dependencias (Linux):
  - `python3-gtts` (desde repositorios apt)
  - `python3-pydub` (desde repositorios apt)

## 🚀 Instalación

```bash
# Clonar el repositorio
git clone https://github.com/tu-usuario/Video-Audio-TTS-Synchronizer.git
cd Video-Audio-TTS-Synchronizer

# Instalar dependencias (Linux)
sudo apt install python3-gtts python3-pydub

# Verificar ffmpeg
ffmpeg -version

# Dar permisos de ejecución
chmod +x create_video_tts_from_srt.py
```

## 💻 Uso

### Sintaxis Básica

```bash
python3 create_video_tts_from_srt.py <archivo.srt> <video.mp4> [opciones]
```

### Parámetros

#### Posicionales

| Parámetro | Descripción | Requerido |
|-----------|-------------|-----------|
| `srt_file` | Archivo de subtítulos SRT | ✅ Sí |
| `video` | Archivo de video (mp4, mkv, etc.) | ✅ Sí |
| `audio_dir` | Carpeta con audios ya generados | ❌ No |

#### Opcionales

| Opción | Descripción | Default |
|--------|-------------|---------|
| `--test N` | Procesar solo N subtítulos | - |
| `--solo-audio` | Solo generar audio, sin video | False |
| `--no-freeze` | Truncar en lugar de freeze | False |
| `--remove-breaks` | Eliminar pausas >15min | False |
| `--only-remove-breaks` | Solo eliminar pausas (sin TTS) | False |

### Ejemplos

#### Caso 1: Proceso completo

```bash
# Genera video completo con audio TTS sincronizado
python3 create_video_tts_from_srt.py mi_video.srt mi_video.mp4
```

**Resultado:** `mi_video_con_tts.mkv`

#### Caso 2: Modo test

```bash
# Procesa solo los primeros 50 subtítulos
python3 create_video_tts_from_srt.py mi_video.srt mi_video.mp4 --test 50
```

**Uso:** Ideal para probar configuración sin procesar todo el video.

#### Caso 3: Solo audio

```bash
# Genera únicamente el audio master sin procesar video
python3 create_video_tts_from_srt.py mi_video.srt mi_video.mp4 --solo-audio
```

**Resultado:** `temp_audio_*/audio_final.wav`

#### Caso 4: Sin freeze frames

```bash
# Trunca audios largos en lugar de congelar video
python3 create_video_tts_from_srt.py mi_video.srt mi_video.mp4 --no-freeze
```

**Uso:** Cuando prefieres mantener el ritmo del video original.

#### Caso 5: Eliminar pausas

```bash
# Procesa y elimina pausas mayores a 15 minutos
python3 create_video_tts_from_srt.py mi_video.srt mi_video.mp4 --remove-breaks
```

**Resultado:** `mi_video_sin_pausas.mkv`

#### Caso 6: Reutilizar audios

```bash
# Usa audios previamente generados
python3 create_video_tts_from_srt.py mi_video.srt mi_video.mp4 ./temp_audio_xyz/
```

**Uso:** Evita regenerar audios si ya los tienes.

## 🧠 Algoritmos y Lógica

### 1. Validación y Parseo de SRT

**Objetivo:** Extraer y validar subtítulos con timestamps correctos.

**Proceso:**
1. Lee archivo SRT línea por línea
2. Detecta bloques: ID → Timestamps → Texto
3. Valida formato de timestamps (HH:MM:SS,mmm)
4. Verifica duración positiva (end > start)
5. Asigna IDs consecutivos (1, 2, 3...) preservando el ID original
6. Muestra progreso cada 100 subtítulos (puntos en pantalla)

**Manejo de errores:**
- Timestamps negativos: Muestra error detallado y continúa
- Formatos inválidos: Salta el subtítulo y reporta
- IDs duplicados: Renumera automáticamente

### 2. Generación TTS con Ajuste Inteligente

**Objetivo:** Generar audio que se ajuste al tiempo disponible.

**Algoritmo de velocidad adaptativa:**

```
Para cada subtítulo:
  1. Calcular tiempo disponible:
     - Si hay siguiente: tiempo_disponible = start_next - start_current
     - Si es el último: tiempo_disponible = duration

  2. Fase de aprendizaje (primeros 10 subtítulos):
     - Probar rates: 180, 200, 220, 240 WPM
     - Elegir el rate más rápido que cabe
     - Si ninguno cabe: marcar para freeze frame

  3. Fase de optimización (después de 10 subtítulos):
     - Usar el rate más exitoso de la fase de aprendizaje
     - Si no cabe: probar rates más lentos
     - Si aún no cabe: freeze frame o truncar

  4. Generar audio con el rate seleccionado

  5. Actualizar estadísticas de uso de rates
```

**Rates disponibles:**
- 180 WPM: Velocidad lenta, clara
- 200 WPM: Velocidad normal
- 220 WPM: Velocidad rápida
- 240 WPM: Velocidad muy rápida

**Estrategias cuando el audio es muy largo:**

- **Freeze Frame** (default): Congela el último frame del video durante el exceso
- **Truncate** (`--no-freeze`): Corta el audio al tiempo disponible

### 3. Construcción del Audio Master

**Objetivo:** Crear pista de audio sincronizada con los timestamps del SRT.

**Algoritmo:**

```
audio_master = silencio(0.001s)
current_time = 0.0

Para cada subtítulo:
  1. Calcular gap = subtitle.start_seconds - current_time

  2. Si gap > 0:
     - Agregar silencio de duración 'gap'

  3. Concatenar audio del subtítulo:
     ffmpeg -i audio_master -i subtitle_audio
            -filter_complex concat
            -o nuevo_master

  4. Actualizar current_time:
     - Si hay freeze: += subtitle.duration + freeze_duration
     - Si no hay freeze: += subtitle.duration

  5. audio_master = nuevo_master
```

**Optimización de nombres:** Usa contador incremental para evitar conflictos de archivos temporales.

### 4. Procesamiento de Video con Freeze Frames

**Objetivo:** Extender video cuando el audio TTS es más largo que el subtítulo.

**Algoritmo:**

```
Para cada subtítulo con freeze:
  1. Calcular frame de inicio y fin del subtítulo

  2. Extraer segmento de video hasta el último frame

  3. Generar freeze:
     - Extraer último frame como imagen
     - Crear video estático de duración = freeze_duration
     - Mantener FPS del video original

  4. Concatenar: video_segment + freeze_video

  5. Actualizar offset de tiempo para siguientes segmentos
```

**Cálculos:**
```python
start_frame = int(subtitle.start_seconds * fps)
end_frame = int(subtitle.end_seconds * fps)
freeze_frames = int(freeze_duration * fps)
```

### 5. Eliminación de Pausas Largas

**Objetivo:** Remover gaps mayores a 15 minutos del video final.

**Algoritmo:**

```
segments = []
current_start = 0.0

Para cada par de subtítulos consecutivos:
  1. Calcular gap = next.start_seconds - current.end_seconds

  2. Si gap >= 900s (15 minutos):
     - Agregar segmento: [current_start, current.end_seconds]
     - current_start = next.start_seconds

  3. Si es el último subtítulo:
     - Agregar segmento final

Luego:
  Para cada segmento:
    1. Extraer con ffmpeg
    2. Generar archivo de lista para concatenación

  3. Concatenar todos los segmentos
```

## 📊 Diagrama de Flujo

```mermaid
flowchart TD
    Start([Inicio]) --> CheckTTS[Detectar método TTS<br/>macOS: say<br/>Linux: gTTS]
    CheckTTS --> ValidateFiles{¿Archivos<br/>existen?}
    ValidateFiles -->|No| Error1([Error: Archivos no encontrados])
    ValidateFiles -->|Sí| ParseSRT[PASO 1: Parsear y validar SRT]

    ParseSRT --> ValidateTimestamps{¿Timestamps<br/>válidos?}
    ValidateTimestamps -->|No| Error2([Error: Timestamps inválidos])
    ValidateTimestamps -->|Sí| RenumberIDs[Renumerar IDs: 1, 2, 3...]

    RenumberIDs --> TestMode{¿Modo<br/>test?}
    TestMode -->|Sí| LimitSubs[Limitar a N subtítulos]
    TestMode -->|No| GenerateWorking[Generar working.srt]
    LimitSubs --> GenerateWorking

    GenerateWorking --> CheckOnlyBreaks{¿Solo eliminar<br/>pausas?}
    CheckOnlyBreaks -->|Sí| Step7
    CheckOnlyBreaks -->|No| Step2

    Step2[PASO 2: Generar audios TTS] --> LearningPhase{¿Primeros 10<br/>subtítulos?}

    LearningPhase -->|Sí| TryRates[Probar rates: 180, 200, 220, 240 WPM]
    LearningPhase -->|No| UseOptimal[Usar rate óptimo aprendido]

    TryRates --> SelectBest[Seleccionar rate más rápido que cabe]
    SelectBest --> CheckFits{¿Audio<br/>cabe?}
    UseOptimal --> CheckFits

    CheckFits -->|No| CheckNoFreeze{¿No-freeze<br/>activo?}
    CheckFits -->|Sí| GenerateTTS[Generar audio TTS]

    CheckNoFreeze -->|Sí| TruncateAudio[Truncar audio]
    CheckNoFreeze -->|No| MarkFreeze[Marcar para freeze frame]

    TruncateAudio --> GenerateTTS
    MarkFreeze --> GenerateTTS

    GenerateTTS --> UpdateStats[Actualizar estadísticas de rates]
    UpdateStats --> MoreSubs{¿Más<br/>subtítulos?}
    MoreSubs -->|Sí| Step2
    MoreSubs -->|No| ShowStats[Mostrar estadísticas finales]

    ShowStats --> Step3[PASO 3: Generar debug.srt<br/>con metadatos de TTS]

    Step3 --> CheckSoloAudio{¿Solo<br/>audio?}
    CheckSoloAudio -->|Sí| Step5
    CheckSoloAudio -->|No| Step4

    Step4[PASO 4: Procesar video] --> CheckFreeze{¿Hay freeze<br/>frames?}
    CheckFreeze -->|No| UseOriginal[Usar video original]
    CheckFreeze -->|Sí| ProcessVideo[Procesar video con freezes]

    ProcessVideo --> GetFPS[Obtener FPS del video]
    GetFPS --> LoopSegments[Para cada subtítulo con freeze]

    LoopSegments --> ExtractSegment[Extraer segmento de video]
    ExtractSegment --> ExtractFrame[Extraer último frame como imagen]
    ExtractFrame --> CreateFreeze[Crear video estático<br/>duración = freeze_duration]
    CreateFreeze --> ConcatFreeze[Concatenar segmento + freeze]
    ConcatFreeze --> MoreSegments{¿Más<br/>segmentos?}
    MoreSegments -->|Sí| LoopSegments
    MoreSegments -->|No| FinalConcat[Concatenar todos los segmentos]

    FinalConcat --> Step5
    UseOriginal --> Step5

    Step5[PASO 5: Sincronizar audio master] --> InitAudio[Crear audio inicial: silencio 0.001s]
    InitAudio --> LoopSync[Para cada subtítulo]

    LoopSync --> CalcGap[Calcular gap = start - current_time]
    CalcGap --> CheckGap{¿Gap > 0?}
    CheckGap -->|Sí| AddSilence[Agregar silencio]
    CheckGap -->|No| ConcatAudio[Concatenar audio TTS]
    AddSilence --> ConcatAudio

    ConcatAudio --> UpdateTime[Actualizar current_time]
    UpdateTime --> MoreSync{¿Más<br/>subtítulos?}
    MoreSync -->|Sí| LoopSync
    MoreSync -->|No| FinalAudio[Audio master completo]

    FinalAudio --> CheckVideoSkip{¿Solo<br/>audio?}
    CheckVideoSkip -->|Sí| Cleanup
    CheckVideoSkip -->|No| Step6

    Step6[PASO 6: Fusionar video y audio] --> ReencodeVideo[Re-codificar video<br/>libx264 -preset ultrafast]
    ReencodeVideo --> MergeAudio[Fusionar con audio master<br/>codec AAC 192k]
    MergeAudio --> CheckMerge{¿Merge<br/>exitoso?}
    CheckMerge -->|No| Error3([Error: No se pudo fusionar])
    CheckMerge -->|Sí| OutputTTS[Video con TTS generado]

    OutputTTS --> Step7{¿Eliminar<br/>pausas?}
    Step7 -->|No| Cleanup
    Step7 -->|Sí| FindGaps[PASO 7: Buscar gaps >= 15 min]

    FindGaps --> CheckGaps{¿Hay<br/>gaps?}
    CheckGaps -->|No| NoBreaks[No hay pausas a eliminar]
    CheckGaps -->|Sí| CreateSegments[Crear segmentos sin pausas]

    NoBreaks --> Cleanup
    CreateSegments --> ExtractSegs[Extraer cada segmento con ffmpeg]
    ExtractSegs --> ConcatSegs[Concatenar segmentos]
    ConcatSegs --> OutputClean[Video sin pausas generado]

    OutputClean --> Cleanup[Limpiar archivos temporales]
    Cleanup --> End([Fin])

    style Start fill:#90EE90
    style End fill:#90EE90
    style Error1 fill:#FFB6C6
    style Error2 fill:#FFB6C6
    style Error3 fill:#FFB6C6
    style Step2 fill:#87CEEB
    style Step3 fill:#87CEEB
    style Step4 fill:#87CEEB
    style Step5 fill:#87CEEB
    style Step6 fill:#87CEEB
    style Step7 fill:#87CEEB
```

## 📁 Archivos Generados

### Durante el Proceso

| Archivo | Descripción | Ubicación |
|---------|-------------|-----------|
| `{video}_working.srt` | Subtítulos con IDs renumerados 1-N | Directorio de trabajo |
| `{video}_debug.srt` | Subtítulos con metadatos TTS (rate, offsets, flags) | Directorio de trabajo |
| `temp_audio_*/` | Carpeta temporal con audios individuales y master | Directorio actual de trabajo |
| `temp_audio_*/logs/` | Logs de generación TTS | Dentro de temp_audio |

### Salida Final

| Archivo | Descripción | Generado con |
|---------|-------------|--------------|
| `{video}_con_tts.mkv` | Video final con audio TTS sincronizado | Por defecto |
| `{video}_sin_pausas.mkv` | Video sin pausas largas | `--remove-breaks` |
| `audio_final.wav` | Audio master sincronizado | `--solo-audio` |

### Ejemplo de debug.srt

```srt
1
00:00:00,000 --> 00:00:03,500
[#1 r200] Bienvenidos al curso de programación

2
00:00:03,500 --> 00:00:07,800
[#2 r220 +150ms] En esta lección aprenderemos Python

3
00:00:07,800 --> 00:00:12,500
[#3 r240] [🎬 FREEZE 1.2s] Python es un lenguaje muy popular

4
00:00:12,500 --> 00:00:15,000
[#4 r180] [✂️ TRUNCADO] Este texto fue demasiado largo...
```

**Metadatos:**
- `#N`: ID consecutivo
- `rXXX`: Rate en WPM (180, 200, 220, 240)
- `+XXXms`: Offset acumulado por freeze frames anteriores
- `🎬 FREEZE Xs`: Video congelado X segundos
- `✂️ TRUNCADO`: Audio cortado (modo `--no-freeze`)

## 🚧 Pendientes y Roadmap

### 🔴 Alta Prioridad

#### Testing Automatizado

**Estado:** 📝 Por implementar

**Descripción:**
Suite completa de tests unitarios y de integración usando `pytest`.

**Tareas:**
- [ ] Tests de parseo de SRT (válidos, inválidos, edge cases)
- [ ] Tests de conversión de timestamps
- [ ] Tests de algoritmo de selección de rate
- [ ] Tests de generación de TTS (mock)
- [ ] Tests de concatenación de audio
- [ ] Tests de procesamiento de video
- [ ] Tests de eliminación de pausas
- [ ] Tests de integración end-to-end
- [ ] CI/CD con GitHub Actions

**Archivos a crear:**
```
tests/
├── test_srt_parser.py
├── test_tts_engine.py
├── test_audio_sync.py
├── test_video_processor.py
├── test_integration.py
├── fixtures/
│   ├── sample.srt
│   ├── sample_invalid.srt
│   └── sample_video.mp4
└── conftest.py
```

#### Interfaz Interactiva para Parámetros

**Estado:** 📝 Por implementar

**Descripción:**
Prompt interactivo que guía al usuario en la configuración.

**Funcionalidad:**
```bash
$ python3 create_video_tts_from_srt.py --interactive

🎬 Video-Audio-TTS Synchronizer - Modo Interactivo
===================================================

📄 Archivo SRT: |> video.srt
🎥 Archivo de video: |> video.mp4

🔧 Configuración:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  ¿Modo test? (s/N): s
  → ¿Cuántos subtítulos? (default: 30): 50

  ¿Solo generar audio? (s/N): n

  ¿Cómo manejar audios largos?
    1) Freeze frame (default)
    2) Truncar audio
  → Opción (1): 1

  ¿Eliminar pausas largas? (s/N): s

✅ Configuración completa. ¿Continuar? (S/n): s

Procesando...
```

**Tareas:**
- [ ] Implementar clase `InteractivePrompt`
- [ ] Validación de inputs en tiempo real
- [ ] Confirmación de configuración antes de procesar
- [ ] Guardar configuración como preset (JSON/YAML)
- [ ] Cargar presets guardados

### 🟡 Media Prioridad

#### Descarga Directa de Videos de YouTube

**Estado:** 📝 Por implementar

**Descripción:**
Integración con `yt-dlp` para descargar videos con subtítulos directamente.

**Funcionalidad:**
```bash
# Descargar video con subtítulos
python3 create_video_tts_from_srt.py --youtube URL

# Descargar y procesar directamente
python3 create_video_tts_from_srt.py --youtube URL --auto-process

# Seleccionar idioma de subtítulos
python3 create_video_tts_from_srt.py --youtube URL --lang es
```

**Tareas:**
- [ ] Instalar dependencia: `pip install yt-dlp`
- [ ] Implementar clase `YouTubeDownloader`
- [ ] Descargar video en mejor calidad disponible
- [ ] Extraer/descargar subtítulos disponibles
- [ ] Soporte para subtítulos automáticos
- [ ] Soporte para múltiples idiomas
- [ ] Limpieza de subtítulos automáticos (ruido, duplicados)
- [ ] Integración con flujo principal

**Implementación:**
```python
class YouTubeDownloader:
    def download(self, url: str, output_dir: Path) -> Tuple[Path, Path]:
        """
        Descarga video y subtítulos
        Returns: (video_path, srt_path)
        """
        # Usar yt-dlp con opciones optimizadas
        pass

    def list_subtitles(self, url: str) -> List[str]:
        """Lista idiomas de subtítulos disponibles"""
        pass
```

#### Sistema de Múltiples Voces

**Estado:** 📝 Por implementar

**Descripción:**
Soporte para asignar diferentes voces a diferentes hablantes.

**Casos de uso:**
- Diálogos con personajes
- Entrevistas
- Narrador + personajes

**Formato SRT extendido:**
```srt
1
00:00:00,000 --> 00:00:03,500
[NARRADOR] Bienvenidos al programa

2
00:00:03,500 --> 00:00:06,000
[JUAN] Hola, mucho gusto

3
00:00:06,000 --> 00:00:08,500
[MARÍA] Encantada de conocerte
```

**Configuración de voces:**
```yaml
# voices.yaml
voices:
  NARRADOR:
    system: macos
    voice: "Jorge"
    rate_base: 200

  JUAN:
    system: macos
    voice: "Diego"
    rate_base: 180

  MARÍA:
    system: macos
    voice: "Paulina"
    rate_base: 190

  default:
    system: macos
    voice: "Paulina"
    rate_base: 200
```

**Tareas:**
- [ ] Parsear etiquetas de hablante en SRT
- [ ] Cargar configuración de voces (YAML/JSON)
- [ ] Extender `TTSEngine` para múltiples voces
- [ ] Mapeo automático de hablantes a voces disponibles
- [ ] Soporte para voces de gTTS (múltiples idiomas)
- [ ] UI para asignar voces interactivamente

#### Autogeneración de Subtítulos con Whisper

**Estado:** 📝 Por implementar

**Descripción:**
Integración con OpenAI Whisper para transcribir audio a subtítulos.

**Funcionalidad:**
```bash
# Extraer subtítulos de un video
python3 create_video_tts_from_srt.py --extract-subs video.mp4

# Extraer en idioma específico
python3 create_video_tts_from_srt.py --extract-subs video.mp4 --lang es

# Extraer y procesar directamente
python3 create_video_tts_from_srt.py --extract-subs video.mp4 --auto-process
```

**Tareas:**
- [ ] Instalar: `pip install openai-whisper`
- [ ] Implementar clase `WhisperTranscriber`
- [ ] Extraer audio del video con ffmpeg
- [ ] Transcribir con Whisper (modelo configurable)
- [ ] Generar archivo SRT desde transcripción
- [ ] Soporte para múltiples idiomas
- [ ] Opción de traducción automática
- [ ] Post-procesamiento: puntuación, capitalización
- [ ] Detección de hablantes (diarization)

**Modelos Whisper:**
- `tiny`: Rápido, menos preciso
- `base`: Balance
- `small`: Buena precisión
- `medium`: Alta precisión
- `large`: Máxima precisión (lento)

#### Traducción y Multi-idioma

**Estado:** 📝 Por implementar

**Descripción:**
Generar versiones del video en múltiples idiomas automáticamente.

**Funcionalidad:**
```bash
# Traducir subtítulos y generar TTS
python3 create_video_tts_from_srt.py video.srt video.mp4 \
  --translate en,fr,de

# Especificar idioma origen
python3 create_video_tts_from_srt.py video.srt video.mp4 \
  --translate-from es --translate-to en,fr,de,pt
```

**Salida:**
```
video_con_tts_es.mkv  (español - original)
video_con_tts_en.mkv  (inglés)
video_con_tts_fr.mkv  (francés)
video_con_tts_de.mkv  (alemán)
```

**Tareas:**
- [ ] Integrar API de traducción (Google Translate, DeepL, etc.)
- [ ] Implementar clase `SubtitleTranslator`
- [ ] Traducir subtítulos manteniendo formato
- [ ] Ajustar timing si el texto traducido es más largo
- [ ] Generar TTS en idioma destino (gTTS multilenguaje)
- [ ] Mapeo de voces por idioma
- [ ] Procesamiento en paralelo de múltiples idiomas
- [ ] Verificación de calidad de traducción

**Configuración:**
```yaml
# translation.yaml
translation:
  provider: "deepl"  # google, deepl, openai
  api_key: "xxx"

  voices_per_language:
    es: "Paulina"
    en: "Samantha"
    fr: "Amelie"
    de: "Anna"
    pt: "Luciana"
```

### 🟢 Baja Prioridad

#### Conversión de Formatos de Salida

**Estado:** 📝 Por implementar

**Descripción:**
Convertir el video final a diferentes formatos y resoluciones.

**Funcionalidad:**
```bash
# Especificar formato de salida
python3 create_video_tts_from_srt.py video.srt video.mp4 \
  --output-format mp4

# Especificar codec
python3 create_video_tts_from_srt.py video.srt video.mp4 \
  --video-codec h265 --audio-codec opus

# Presets de calidad
python3 create_video_tts_from_srt.py video.srt video.mp4 \
  --preset web    # 720p, H264, AAC
  --preset hd     # 1080p, H264, AAC
  --preset 4k     # 4K, H265, AAC
  --preset stream # Optimizado para streaming
```

**Tareas:**
- [ ] Implementar clase `VideoConverter`
- [ ] Soporte para formatos: MP4, MKV, WebM, AVI
- [ ] Soporte para codecs: H264, H265, VP9, AV1
- [ ] Presets de calidad
- [ ] Redimensionar video (1080p, 720p, 480p)
- [ ] Ajuste de bitrate
- [ ] Optimización para plataformas (YouTube, Vimeo, etc.)

#### Preparación para Whisper

**Estado:** 📝 Por implementar

**Descripción:**
Preparar video para procesamiento óptimo con Whisper.

**Funcionalidad:**
```bash
# Preparar video para Whisper
python3 create_video_tts_from_srt.py --prepare-whisper video.mp4

# Salida: video_whisper_ready.mp4 + audio_16k.wav
```

**Optimizaciones:**
- Extraer audio en formato óptimo (WAV, 16kHz, mono)
- Reducción de ruido
- Normalización de audio
- Detección de silencios para segmentación
- Separación de voces (si hay música de fondo)

**Tareas:**
- [ ] Implementar clase `WhisperPreprocessor`
- [ ] Extraer audio en formato óptimo
- [ ] Reducción de ruido con `noisereduce`
- [ ] Normalización con `pydub`
- [ ] Detección de actividad de voz (VAD)
- [ ] Segmentación inteligente en chunks
- [ ] Separación de fuentes con `spleeter` (opcional)

#### Sistema de Plugins

**Estado:** 📝 Por implementar

**Descripción:**
Arquitectura de plugins para extender funcionalidad.

**Ejemplo de plugin:**
```python
# plugins/custom_voice.py
from tts_synchronizer import Plugin, TTSEngine

class CustomVoicePlugin(Plugin):
    name = "custom_voice"
    version = "1.0.0"

    def process_audio(self, text: str, rate: int) -> Path:
        # Lógica personalizada
        pass

    def register(self, engine: TTSEngine):
        engine.register_voice_provider(self)
```

**Tareas:**
- [ ] Diseñar API de plugins
- [ ] Sistema de descubrimiento de plugins
- [ ] Hooks en puntos clave del proceso
- [ ] Documentación para desarrollo de plugins
- [ ] Repositorio de plugins comunitarios

#### Interfaz Gráfica (GUI)

**Estado:** 💭 Idea

**Descripción:**
GUI con PyQt6 o Tkinter para uso más intuitivo.

**Características:**
- Drag & drop de archivos
- Vista previa de subtítulos
- Editor de timing
- Configuración visual de voces
- Barra de progreso en tiempo real
- Vista previa del resultado

#### Procesamiento en la Nube

**Estado:** 💭 Idea

**Descripción:**
API REST para procesar videos en servidores remotos.

**Casos de uso:**
- Videos muy largos
- Procesamiento masivo
- Hardware limitado localmente

**Stack sugerido:**
- FastAPI para la API
- Celery para workers
- Redis para cola de tareas
- S3 para almacenamiento

## 🤝 Contribuciones

¡Las contribuciones son bienvenidas! Si quieres implementar alguna de las funcionalidades pendientes:

1. Fork el repositorio
2. Crea una rama para tu feature (`git checkout -b feature/nueva-funcionalidad`)
3. Commit tus cambios (`git commit -m 'Add: nueva funcionalidad'`)
4. Push a la rama (`git push origin feature/nueva-funcionalidad`)
5. Abre un Pull Request

## 📝 Licencia

[Especificar licencia]

## 👥 Autores

[Agregar autores y colaboradores]

## 🙏 Agradecimientos

- FFmpeg por el procesamiento multimedia
- Google TTS (gTTS) por el motor de síntesis de voz
- OpenAI Whisper (futuro) para transcripción
- Comunidad de código abierto

---

**Última actualización:** 2025-01-26
**Versión:** 2.0.0 (Python rewrite)
