# 🔍 Guía de Verificación del Sistema

## 📋 Descripción

Antes de procesar videos con TTS, es **crucial verificar** que todos los componentes del sistema funcionen correctamente. Los scripts de verificación prueban:

- ✅ Versión de Python
- ✅ FFmpeg instalado y funcional
- ✅ Paquetes Python necesarios
- ✅ Voces TTS disponibles
- ✅ Generación de audio TTS
- ✅ Traducción automática
- ✅ Transcripción con Whisper
- ✅ Operaciones de video
- ✅ Lectura de subtítulos
- ✅ Espacio en disco
- ✅ GPU (opcional, para Colab)

---

## 🪟 VERSIÓN WINDOWS

### Archivo: `test_system_windows.py`

### Ejecución:

```cmd
python test_system_windows.py
```

### Salida esperada:

```
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║           VERIFICACIÓN DE SISTEMA - WINDOWS                  ║
║           Video TTS Synchronizer                             ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝

================================================================================
🎬 VERIFICACIÓN DEL SISTEMA - Video TTS Synchronizer
================================================================================

▶ Verificando Python
  ℹ Versión: Python 3.10.5
  ℹ Ejecutable: C:\Python310\python.exe
  ℹ Plataforma: Windows 10
  ✓ Versión de Python compatible (3.8+)

▶ Verificando FFmpeg
  ℹ ffmpeg version 5.1.2
  ✓ FFmpeg instalado y funcionando

▶ Verificando paquetes de Python
  ✓ pysrt instalado
  ✓ pyttsx3 instalado
  ✓ pydub instalado

▶ Verificando voces TTS del sistema
  ✓ Encontradas 8 voces en el sistema
  ℹ Voces en español: 2
    • Microsoft Helena Desktop - Spanish (Spain)
    • Microsoft Pablo Desktop - Spanish (Spain)
  ℹ Voces en inglés: 3
    • Microsoft David Desktop - English (United States)
    • Microsoft Zira Desktop - English (United States)
    • Microsoft Mark Mobile - English (United States)
  ℹ Voces en alemán: 1
    • Microsoft Hedda Desktop - German (Germany)

▶ Probando generación de TTS
  ℹ Generando audio de prueba...
  ✓ Audio generado correctamente (2.34s)
  ℹ Archivo: test_temp\test_tts.wav

▶ Probando operaciones de FFmpeg
  ℹ Creando video de prueba...
  ✓ Video de prueba creado
  ℹ Extrayendo frame...
  ✓ Frame extraído correctamente
  ℹ Extrayendo audio...
  ✓ Audio extraído correctamente

▶ Probando lectura de subtítulos SRT
  ℹ Archivo SRT de prueba creado
  ✓ Archivo SRT leído correctamente (3 subtítulos)
  ℹ Duración primer subtítulo: 3000ms

▶ Probando procesamiento de audio
  ℹ Generando tono de prueba...
  ✓ Tono generado
  ✓ Silencio generado
  ✓ Audio combinado
  ✓ Audio exportado (2500ms)

▶ Verificando espacio en disco
  ℹ Espacio total: 500.00 GB
  ℹ Espacio libre: 150.00 GB
  ✓ Espacio suficiente: 150.00 GB

================================================================================
RESUMEN DE VERIFICACIÓN
================================================================================

Resultados:
  Total de tests: 9
  Exitosos: 9
  Fallidos: 0

================================================================================
✓ TODOS LOS TESTS PASARON
El sistema está listo para procesar videos
================================================================================

¡Puedes proceder a usar video_tts_windows.py!
```

### Si hay errores:

```
================================================================================
RESUMEN DE VERIFICACIÓN
================================================================================

Resultados:
  Total de tests: 9
  Exitosos: 6
  Fallidos: 3

Tests fallidos:
  ✗ FFmpeg (No instalado)
  ✗ Paquetes Python (Faltan: pysrt, pydub)
  ✗ Voces TTS (Sin voces)

================================================================================
✗ ALGUNOS TESTS FALLARON
Por favor corrige los errores antes de continuar
================================================================================

Corrige los errores y vuelve a ejecutar este script.
```

### Solución de Problemas Comunes:

#### Error: FFmpeg no encontrado

**Síntoma:**
```
✗ FFmpeg no encontrado en el sistema
```

**Solución:**
1. Descarga FFmpeg: https://ffmpeg.org/download.html
2. Extrae el archivo ZIP
3. Agrega la carpeta `bin` al PATH del sistema:
   - Panel de Control → Sistema → Configuración avanzada
   - Variables de entorno → PATH → Agregar ruta a `bin`
4. Reinicia el terminal
5. Ejecuta el test de nuevo

#### Error: Paquetes Python faltantes

**Síntoma:**
```
✗ pysrt NO instalado
✗ pydub NO instalado
```

**Solución:**
```cmd
pip install pysrt pyttsx3 pydub
```

#### Error: No hay voces TTS

**Síntoma:**
```
✗ No se encontraron voces en el sistema
```

**Solución:**
1. Configuración → Hora e idioma → Idioma
2. Agregar idioma → Español/Inglés/Alemán
3. Opciones → Descargar paquete de voz
4. Reiniciar el script de verificación

---

## 🌐 VERSIÓN GOOGLE COLAB

### Archivo: `test_system_colab_cell.py`

### Integración en el Notebook:

Esta celda debe ejecutarse **DESPUÉS** de la instalación de dependencias y **ANTES** de configurar parámetros.

**Estructura del notebook:**

```
1. Instalación de dependencias (Celda 1)
2. Importar librerías (Celda 2)
3. ✨ VERIFICACIÓN DEL SISTEMA (Celda 3 - NUEVA)
4. Definir funciones (Celdas 4-5)
5. Configuración (Celda 6)
6. Ejecución (Celda 7)
```

### Ejecución en Colab:

1. Ejecuta la celda de instalación
2. Ejecuta la celda de importación
3. **Ejecuta la celda de verificación** ← NUEVO
4. Espera los resultados (30-60 segundos)

### Salida esperada:

```
================================================================================
🔍 VERIFICACIÓN DEL SISTEMA - Google Colab
================================================================================

▶ Test 1: Verificando Python
  Versión: Python 3.10.12
  ✓ Versión compatible

▶ Test 2: Verificando FFmpeg
  ffmpeg version 4.4.2
  ✓ FFmpeg instalado

▶ Test 3: Verificando paquetes Python
  ✓ pysrt (Subtítulos SRT)
  ✓ whisper (Whisper transcripción)
  ✓ pydub (Procesamiento audio)
  ✓ edge_tts (Edge TTS)
  ✓ deep_translator (Traducción)
  ✓ langdetect (Detección de idioma)
  ✓ yt_dlp (Descarga de YouTube)
  ✓ Todos los paquetes instalados

▶ Test 4: Probando Edge TTS
  ✓ 412 voces disponibles
    • Español: 48 voces
    • English: 125 voces
    • Deutsch: 18 voces

▶ Test 5: Probando generación de audio TTS
  ✓ Audio generado correctamente (1.85s)

▶ Test 6: Probando traducción automática
  Original: 'Hello world, this is a test'
  Traducido: 'Hola mundo, esto es una prueba'
  ✓ Traducción funcionando

▶ Test 7: Verificando Whisper
  Cargando modelo 'tiny' para prueba...
  ✓ Whisper disponible (modelo 'tiny' cargado)
  ℹ Modelos disponibles: tiny, base, small, medium, large

▶ Test 8: Verificando yt-dlp
  ✓ yt-dlp versión: 2023.11.16

▶ Test 9: Probando operaciones de FFmpeg
  ✓ Creación de video
  ✓ Extracción de frames
  ✓ Extracción de audio
  ✓ Todas las operaciones FFmpeg OK

▶ Test 10: Probando lectura de subtítulos
  ✓ Archivo SRT leído correctamente (2 subtítulos)

▶ Test 11: Verificando espacio en disco
  Espacio libre: 25.34 GB
  ✓ Espacio suficiente

▶ Test 12: Verificando GPU (opcional para Whisper)
  ✓ GPU disponible: Tesla T4
  ℹ Whisper será más rápido con GPU

================================================================================
📊 RESUMEN DE VERIFICACIÓN
================================================================================

Total de tests: 12
Exitosos: 12
Fallidos: 0
```

### Visualización HTML:

Después de los tests, se mostrará una tabla HTML con:

| Estado | Test |
|--------|------|
| ✓ | Python |
| ✓ | FFmpeg |
| ✓ | Paquetes Python |
| ✓ | Edge TTS |
| ✓ | Generación TTS |
| ✓ | Google Translate |
| ✓ | Whisper |
| ✓ | yt-dlp |
| ✓ | Operaciones FFmpeg |
| ✓ | Lectura SRT |
| ✓ | Espacio disco |
| ✓ | GPU |

Y un banner verde:

```
✓ SISTEMA LISTO
Todos los componentes están funcionando correctamente.
Puedes proceder a configurar y ejecutar el procesamiento de video.
```

### Si hay errores en Colab:

```
⚠ TESTS FALLIDOS:
  ✗ Edge TTS (Error de conexión)
  ✗ Google Translate (Sin internet)

⚠ ACCIÓN REQUERIDA
Algunos tests fallaron. Por favor:
1. Revisa los errores arriba
2. Ejecuta de nuevo la celda de instalación (Celda 1)
3. Vuelve a ejecutar esta verificación
```

### Solución de Problemas en Colab:

#### Error: Paquetes faltantes

**Solución:**
```python
# Ejecutar en una celda nueva
!pip install pysrt edge-tts deep-translator langdetect yt-dlp
```

#### Error: Sin GPU

**Solución:**
1. Runtime → Change runtime type
2. Hardware accelerator → GPU
3. Save
4. Reconectar
5. Re-ejecutar verificación

#### Error: Whisper falla

**Solución:**
```python
# Reinstalar Whisper
!pip uninstall -y openai-whisper
!pip install -U openai-whisper
```

#### Error: Traducción falla

**Solución:**
- Verifica conexión a internet
- Intenta de nuevo en unos minutos
- Google Translate puede tener límites temporales

---

## 📊 Comparación de Tests

| Test | Windows | Colab | Crítico |
|------|---------|-------|---------|
| Python | ✓ | ✓ | ✅ Sí |
| FFmpeg | ✓ | ✓ | ✅ Sí |
| Paquetes | ✓ | ✓ | ✅ Sí |
| TTS | pyttsx3 | edge-tts | ✅ Sí |
| Voces | Sistema | Edge | ✅ Sí |
| Generación TTS | ✓ | ✓ | ✅ Sí |
| Traducción | ❌ | ✓ | ⚠️ Opcional |
| Whisper | ❌ | ✓ | ⚠️ Opcional |
| yt-dlp | ❌ | ✓ | ⚠️ Opcional |
| GPU | N/A | ✓ | ❌ No |
| Espacio | ✓ | ✓ | ✅ Sí |

---

## 🎯 Checklist Pre-Ejecución

### Windows:

- [ ] Python 3.8+ instalado
- [ ] FFmpeg instalado y en PATH
- [ ] Paquetes Python instalados (`pip install ...`)
- [ ] Al menos 1 voz TTS en el idioma objetivo
- [ ] Al menos 2 GB de espacio libre
- [ ] Script de verificación ejecutado exitosamente

### Colab:

- [ ] Dependencias instaladas (Celda 1)
- [ ] Librerías importadas (Celda 2)
- [ ] Verificación ejecutada (Celda 3)
- [ ] Todos los tests en verde
- [ ] GPU activada (recomendado)
- [ ] Conexión a internet estable

---

## 💡 Consejos

### 1. Ejecutar verificación regularmente

```cmd
# Windows - antes de cada procesamiento
python test_system_windows.py
```

```python
# Colab - después de cada reconexión
# Ejecutar celda de verificación
```

### 2. Guardar salida de verificación

**Windows:**
```cmd
python test_system_windows.py > verificacion.txt
```

**Colab:**
- Copiar salida de la celda
- Guardar en Google Drive

### 3. Verificación rápida vs completa

**Windows:**
- Script completo: ~30-60 segundos
- Solo lo crítico: comenta tests opcionales

**Colab:**
- Completo: ~30-60 segundos
- Sin Whisper/GPU: ~20 segundos

### 4. Automatizar verificación

**Windows batch script:**
```batch
@echo off
python test_system_windows.py
if %ERRORLEVEL% EQU 0 (
    echo Tests OK - Iniciando procesamiento
    python video_tts_windows.py %*
) else (
    echo Tests fallaron - Revisa errores
    pause
)
```

---

## 🆘 Soporte

### Tests pasan pero el script falla

**Posibles causas:**
1. Archivo de video corrupto
2. Subtítulos mal formateados
3. Configuración incorrecta
4. Sin espacio durante ejecución

**Solución:**
1. Verifica el video con VLC
2. Valida el SRT con un editor
3. Revisa configuración
4. Libera espacio en disco

### Tests fallan intermitentemente

**Colab:**
- Reconectar a runtime
- Cambiar región del servidor
- Ejecutar en horario menos congestionado

**Windows:**
- Reiniciar terminal
- Ejecutar como administrador
- Verificar antivirus no bloquea

---

## 📝 Registro de Tests

Mantén un registro de verificaciones:

```
Fecha: 2024-11-19
Sistema: Windows 10
Python: 3.10.5
FFmpeg: 5.1.2
Voces: 8 (2 ES, 3 EN, 1 DE)
Resultado: ✓ TODOS PASARON
```

---

## 🎓 Tutorial Completo

### Primera Vez - Windows:

1. **Instalar requisitos**
   - Python 3.8+
   - FFmpeg
   - Voces del sistema

2. **Instalar paquetes**
   ```cmd
   pip install pysrt pyttsx3 pydub
   ```

3. **Ejecutar verificación**
   ```cmd
   python test_system_windows.py
   ```

4. **Corregir errores** (si hay)

5. **Re-ejecutar verificación**

6. **Procesar video**
   ```cmd
   python video_tts_windows.py video.mp4 subs.srt out.mp4 --lang es
   ```

### Primera Vez - Colab:

1. **Abrir notebook** en Colab

2. **Ejecutar instalación** (Celda 1)

3. **Importar librerías** (Celda 2)

4. **Ejecutar verificación** (Celda 3)

5. **Revisar resultados**

6. **Corregir errores** (si hay)

7. **Configurar** (Celda 6)

8. **Ejecutar** (Celda 7)

---

## ✅ Conclusión

Los scripts de verificación son **esenciales** para:

- ✅ Detectar problemas antes de procesar
- ✅ Ahorrar tiempo (no fallar a mitad)
- ✅ Validar instalaciones
- ✅ Probar componentes individualmente
- ✅ Documentar el estado del sistema

**Recomendación:** Ejecuta la verificación cada vez antes de procesar videos importantes.

---

**Versión:** 1.0  
**Fecha:** 2024  
**Archivos:**
- `test_system_windows.py`
- `test_system_colab_cell.py`
