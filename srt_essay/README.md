# SRT Essay

Convierte subtítulos `.srt` o documentos `.md`/`.txt` en prosa Markdown mediante Ollama, preservando estrictamente el significado original.

```bash
python3 -m srt_essay video.srt
```

## Interfaz web

Además del CLI, podés abrir una interfaz visual local con carga de archivo, configuración de Ollama, progreso por bloque, logs y descarga del Markdown final:

```bash
python3 -m srt_essay --web
```

Abrí `http://127.0.0.1:8768`. Para otro puerto: `python3 -m srt_essay --web --port 9000`.

La interfaz acepta `.srt`, `.md` y `.txt`, y también permite elegir archivos de esos tipos ya existentes en el directorio del proyecto. Antes de invocar al modelo, reduce la entrada a párrafos de texto plano: limpia metadatos y marcas Markdown o SRT.

La interfaz presenta el Markdown parcial después de cada bloque. Lo renderiza con Marked, lo sanea con DOMPurify y resalta bloques de código con highlight.js, todos cargados desde CDN.

Después de cada respuesta del modelo, el pipeline aplica una limpieza conservadora por expresiones regulares: normaliza saltos excesivos y elimina líneas o párrafos de prosa idénticos que estén inmediatamente repetidos. No toca títulos, listas ni repeticiones no consecutivas. Cuando realiza una corrección, queda registrada en los logs y en Debug conserva la respuesta cruda del modelo.

Al finalizar una traducción, el Markdown traducido (`<entrada>.essay.md`) se preserva y descarga como salida; el archivo de entrada se conserva aparte únicamente como referencia.

En modo **Calidad**, cada bloque actualiza primero su guía de continuidad y se redacta inmediatamente después; por eso la vista previa aparece desde el primer bloque, sin esperar que termine la guía de todo el documento.

Activá **Modo Debug** para descargar el texto limpio de entrada, el Markdown de cada bloque y el prompt final enviado a Ollama. Los prompts de sistema, corrección y guía se pueden editar desde la interfaz antes de iniciar el trabajo.

Debug también registra por bloque el texto enviado y el devuelto por Ollama. La interfaz permite abrir una comparación lado a lado y un diff a nivel de palabra: rojo es contenido retirado y verde contenido añadido.

Con **Guardar prompts en backend**, la configuración queda en `.srt-essay-prompts.json`, se versiona con Git y se carga en posteriores ejecuciones. Podés seleccionar perfiles distintos, crear uno desde el actual y editarlo; se incluyen **Corrección fiel del original**, **Traducción al castellano · ensayo fiel** y **Traducción alemán - español a partir de transcripciones**. Este último prioriza la fidelidad semántica, reconstituye solo errores inequívocos de transcripción automática y conserva las ambigüedades que no pueda resolver con seguridad.

La interfaz guarda en `localStorage` los valores elegidos (modelo, URL, modo, tamaño de bloque, Debug, prompts y archivo local) para restaurarlos al refrescar. Por seguridad del navegador, un archivo subido manualmente debe volver a seleccionarse.

En **Generar audio de salida** podés generar un MP3 mediante los motores TTS que ya detecta `create_video_tts_from_srt.py`. Solo se muestran idiomas europeos disponibles. Elegí idioma, motor, voz, velocidad (200 WPM por defecto), pausa entre párrafos y si debe narrar el Markdown corregido o el texto limpio de entrada. El botón **Test** junto a Voz genera una muestra corta en el idioma seleccionado. El audio se une en lotes de 50 fragmentos por defecto y la barra informa cada lote; ajustá ese tamaño si necesitás otro equilibrio entre detalle de progreso y velocidad. **Modo test · primeros N fragmentos** limita el audio a N fragmentos (0 procesa todo). Si activás **Separar capítulos de salida**, cada encabezado Markdown `#` o `##` crea un MP3 independiente, enumerado con dos dígitos hasta 99 capítulos y tres hasta 999 (por ejemplo, `01. Introducción.mp3`; desde 100 capítulos, `001. Introducción.mp3`). Los separadores horizontales de Markdown (`---`, `***`, `___`), aislados o insertados entre frases por una transcripción, se excluyen del texto narrable; una regla `---` inicial sólo se trata como frontmatter si contiene claves YAML, por lo que no puede borrar una sección completa. Antes de traducir, el preprocesamiento une cortes de prosa cuya línea termina en minúscula, coma o punto y coma y cuya continuación empieza en minúscula, incluso cuando hay líneas vacías con espacios o tabuladores entre ambas; el mismo criterio se aplica tras la respuesta del modelo. Al seleccionar un archivo existente, la interfaz muestra su ruta local enlazada y revisa automáticamente el caché asociado; **Check caché** vuelve a escanearlo con la velocidad elegida y **Eliminar caché** borra los fragmentos de esa velocidad tras pedir confirmación. Al iniciar la narración, los WAV válidos encontrados se copian al directorio temporal del trabajo y se reutilizan, por lo que no vuelven a generarse. El botón **Generar audio desde el archivo de entrada** omite Ollama: limpia el `.srt`, `.md` o `.txt` una sola vez y narra directamente ese resultado validado. Si separás por capítulos, encabezados Markdown consecutivos se narran juntos como título y subtítulo; los que sólo contengan un separador Markdown se omiten sin cancelar el trabajo. Cada fragmento WAV válido queda en la carpeta temporal y se reutiliza en una reanudación; si ElevenLabs devuelve `quota_exceeded`, el proceso continúa automáticamente con el primer TTS gratuito/local disponible. Ante otro corte, el botón **Reanudar audio desde caché** reutiliza lo ya generado y aplica el motor/voz actualmente elegidos. El reproductor y la descarga aparecen al finalizar.

### Proveedores de modelos

Además de Ollama local, el selector **Proveedor** permite usar OpenAI y Anthropic. Copiá `.srt-essay-secrets.example.json` como `.srt-essay-secrets.json` y agregá sus claves en las secciones `openai` o `anthropic`; también se aceptan `OPENAI_API_KEY` y `ANTHROPIC_API_KEY`. Las claves nunca se envían al navegador: el backend obtiene los modelos y realiza las solicitudes. El botón **Test** de *Editar prompts del modelo* usa el proveedor, modelo y texto de prueba seleccionados, y muestra el Markdown resultante y los tokens consumidos cuando el proveedor los devuelve. OpenAI y Anthropic no exponen un saldo de créditos restante en la respuesta de generación, por lo que la interfaz informa esa limitación en vez de inventar un saldo.

### ElevenLabs

Para obtener una API key desde la interfaz en inglés de ElevenLabs:

1. Iniciá sesión y abrí **Developers** en la barra lateral.
2. Abrí la pestaña **API Keys** y creá una clave, por ejemplo `SRT Essay local`.
3. Habilitá **Text to Speech** y **Voices read**. Para mostrar créditos en la interfaz, agregá también **User read**; si aparece, configurá un límite de créditos apropiado.
4. Copiá la clave inmediatamente: ElevenLabs solo la muestra completa una vez.

También podés seleccionar **OpenAI TTS** en Motor TTS para generar pruebas y audios con sus voces. Configurá `OPENAI_API_KEY` o `openai.api_key` (y opcionalmente `openai.tts_model`) en `.srt-essay-secrets.json`; la clave no se expone al frontend.

Para habilitar **ElevenLabs** en este proyecto:

```bash
cp .srt-essay-secrets.example.json .srt-essay-secrets.json
```

Reemplazá `PEGAR_AQUI_TU_API_KEY` por tu clave. Ese archivo está excluido de Git; como alternativa podés exportar `ELEVENLABS_API_KEY` (y opcionalmente `ELEVENLABS_MODEL_ID`). Al reiniciar la web aparecerá ElevenLabs en el selector TTS junto con las voces disponibles. La clave nunca se envía al navegador: se usa solo desde el backend local. La API usa el encabezado `xi-api-key` y la conversión `POST /v1/text-to-speech/:voice_id`; ElevenLabs permite una velocidad entre 0.7 y 1.2, por lo que los WPM extremos se ajustan a ese rango. [Guía oficial para crear claves](https://help.elevenlabs.io/hc/en-us/articles/14599447207697-How-do-I-authorize-myself-using-an-API-key), [autenticación](https://elevenlabs.io/docs/api-reference/authentication), [conversión de voz](https://elevenlabs.io/docs/api-reference/text-to-speech/convert?explorer=true), [control de velocidad](https://elevenlabs.io/docs/api-reference/voices/settings/get).

El modelo por defecto es `gemma4:31b`. La interfaz web carga los modelos instalados en Ollama para elegirlos. Antes de ejecutar, iniciá Ollama e instalá el modelo:

```bash
ollama serve
ollama pull gemma4:31b
```

Usá `--mode fast` para una sola pasada o `--mode quality` (predeterminado) para crear una guía factual acumulativa antes de corregir cada bloque. La salida es `video.essay.md`; si se interrumpe, reanudá con `--resume`.
