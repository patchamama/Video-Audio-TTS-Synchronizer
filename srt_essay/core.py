"""Dominio y adaptadores para convertir SRT en prosa fiel al original."""

from __future__ import annotations

import hashlib
import json
import re
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable

DEFAULT_MODEL = "gemma4:31b"
DEFAULT_OLLAMA_URL = "http://localhost:11434"
DEFAULT_CHUNK_SIZE = 3500
SUPPORTED_INPUT_SUFFIXES = frozenset({".srt", ".md", ".txt"})
DEFAULT_REWRITE_SYSTEM_PROMPT = "Sos un corrector de estilo, no un autor. La fidelidad es obligatoria."
DEFAULT_REWRITE_INSTRUCTIONS = (
    "Devolvé exclusivamente Markdown en párrafos. Conservá TODO el significado, los hechos, "
    "la incertidumbre y el idioma original. No agregues, elimines, resumas ni interpretes ideas. "
    "Podés corregir ortografía, puntuación, fluidez, y unir o separar párrafos cuando sea necesario. "
    "Corregí incoherencias accidentales de género, número y persona gramatical cuando el referente sea inequívoco "
    "en el contexto (por ejemplo, interlocutoras mujeres referidas erróneamente en masculino). No fuerces una "
    "corrección si el referente es ambiguo. "
    "No uses títulos, listas ni comentarios editoriales salvo que ya existan en el texto fuente."
)
DEFAULT_GUIDE_INSTRUCTIONS = (
    "Redactá una guía factual, breve y acumulativa de temas, entidades y transición. "
    "No agregues datos ni conclusiones que no aparezcan en el texto fuente."
)
TRANSLATION_ES_SYSTEM_PROMPT = (
    "Sos traductor y editor profesional especializado en convertir textos al castellano claro. "
    "Tu prioridad absoluta es la fidelidad semántica al texto fuente."
)
TRANSLATION_ES_INSTRUCTIONS = (
    "Traducí el texto fuente completo al castellano en prosa clara con formato de ensayo. Conservá todos los "
    "hechos, matices, grados de certeza, tono, nombres propios, cifras, fechas, citas y relaciones entre ideas. "
    "No agregues explicaciones, ejemplos, opiniones, contexto externo ni conclusiones; no omitas ni resumas "
    "contenido. Adaptá únicamente la sintaxis, puntuación y división de párrafos para que la redacción en castellano "
    "sea natural y cohesionada. Mantené coherencia de género, número, persona y referencias cuando el contexto sea "
    "inequívoco; preservá la ambigüedad cuando exista. Devolvé exclusivamente Markdown en párrafos, sin prefacios, "
    "notas del traductor, títulos nuevos ni listas que no existan en la fuente."
)
TRANSLATION_ES_GUIDE_INSTRUCTIONS = (
    "Construí una guía factual breve y acumulativa de ideas, entidades, referentes, género, número y transiciones "
    "del texto fuente. No traduzcas ni agregues datos; la guía solo debe preservar información para una traducción "
    "fiel posterior."
)
GERMAN_TRANSCRIPTION_TRANSLATION_SYSTEM_PROMPT = (
    "Sos traductor y editor profesional especializado en traducción del alemán al castellano, "
    "con experiencia en textos ensayísticos, académicos, divulgativos, autobiográficos y literarios. "
    "La fidelidad semántica al texto fuente tiene prioridad absoluta sobre el embellecimiento estilístico."
)
GERMAN_TRANSCRIPTION_TRANSLATION_INSTRUCTIONS = (
    "Traducí el significado, no simplemente las palabras. Devolvé un castellano natural, profesional y fluido, "
    "como texto originalmente escrito en buen castellano, pero sin introducir ideas, interpretaciones, "
    "explicaciones ni matices que no estén presentes o claramente implícitos en el original. Evitá tanto el "
    "calco de sintaxis alemana como la adaptación libre.\n\n"
    "Traducí íntegramente el texto proporcionado. Conservá hechos, afirmaciones, argumentos, relaciones lógicas, "
    "matices, grados de certeza, contradicciones, dudas, ambigüedades, ejemplos, comparaciones, metáforas, "
    "repeticiones con función discursiva, tono, registro, voz, personas gramaticales, nombres propios, cifras, "
    "fechas, cantidades, citas, referencias culturales, terminología, cambios de perspectiva, advertencias, "
    "títulos y subtítulos existentes. No agregues explicaciones, comentarios, ejemplos propios, opiniones, "
    "interpretaciones, contexto externo, aclaraciones editoriales, conclusiones ni información ausente. "
    "No omitas, resumas, suavices ni censures contenido.\n\n"
    "Adaptá orden de palabras, estructura de oraciones, puntuación, conectores, división o unión de párrafos y "
    "referencias pronominales únicamente cuando eso exprese con mayor fidelidad el original en castellano. "
    "No simplifiques el vocabulario ni la complejidad conceptual. Conservá la personalidad discursiva: precisión "
    "académica, reflexión ensayística, coloquialidad, cercanía autobiográfica, ironía, intensidad emocional o "
    "aspereza deliberada cuando corresponda.\n\n"
    "El material procede de una transcripción automática de audio y puede contener errores ortográficos, palabras "
    "mal reconocidas, partidas o fusionadas, puntuación defectuosa, falsos cortes de oración, nombres propios "
    "mal transcritos, anglicismos deformados o palabras compuestas alemanas defectuosas. Cuando el contexto "
    "permita identificar inequívocamente la forma correcta, reconstruí silenciosamente el significado previsto "
    "antes de traducir. No reproduzcas errores evidentes que destruyan el sentido; tampoco inventes correcciones, "
    "completes información ausente ni resuelvas ambigüedades con varias interpretaciones plausibles. Si un pasaje "
    "es irresoluble, conservá el mayor grado posible de ambigüedad.\n\n"
    "Usá equivalentes castellanos precisos y naturales. Conservá en cursiva un término extranjero con valor "
    "conceptual, académico, cultural o terminológico solo cuando corresponda; agregá una traducción breve integrada "
    "únicamente si es necesaria para comprender la frase. No agregues notas del traductor. Mantené una terminología "
    "consistente. Cuidá género, número, persona, sujetos implícitos, referentes pronominales y relaciones entre "
    "personas y entidades cuando el contexto sea inequívoco; si no lo es, preservá la ambigüedad sin deducir identidad, "
    "cargo, parentesco u otras características.\n\n"
    "Considerá cada fragmento como parte de un texto mayor y respetá la continuidad de nombres, terminología, "
    "género, número, referentes, tono, voz, acontecimientos, argumentos y transiciones. Devolvé exclusivamente "
    "la traducción en Markdown, usando solo la estructura que ya esté presente o sea prudentemente necesaria para "
    "su legibilidad: párrafos, títulos, subtítulos, cursivas, negritas y citas. No agregues prefacios, comentarios, "
    "notas, resúmenes, títulos inventados, conclusiones ni listas injustificadas."
)
GERMAN_TRANSCRIPTION_TRANSLATION_GUIDE_INSTRUCTIONS = (
    "Construí y actualizá internamente una guía factual, breve y acumulativa para sostener la continuidad de la "
    "traducción: personas y entidades, nombres propios, género y número inequívocos, relaciones entre referentes, "
    "terminología y equivalencias ya adoptadas, acontecimientos, argumentos, referentes pronominales, transiciones "
    "y secciones activas. No interpretes, no resumas creativamente, no agregues información ni resuelvas ambigüedades "
    "no resueltas por la fuente. No muestres esta guía en la respuesta."
)


class SRTEssayError(RuntimeError):
    """Error accionable del flujo de conversión."""


@dataclass(frozen=True)
class Cue:
    number: int
    start: float
    end: float
    text: str


def _seconds(timestamp: str) -> float:
    match = re.fullmatch(r"(\d{2}):(\d{2}):(\d{2})[,.](\d{3})", timestamp.strip())
    if not match:
        raise ValueError(f"Timestamp SRT inválido: {timestamp!r}")
    hours, minutes, seconds, milliseconds = map(int, match.groups())
    return hours * 3600 + minutes * 60 + seconds + milliseconds / 1000


def clean_text(text: str) -> str:
    """Elimina formato de subtítulo sin modificar las palabras."""
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\{\\[^}]+\}", "", text)  # etiquetas ASS frecuentes
    return re.sub(r"\s+", " ", text).strip()


_EXCESS_BLANK_LINES_RE = re.compile(r"\n[ \t]*\n(?:[ \t]*\n)+")
_MARKDOWN_STRUCTURAL_LINE_RE = re.compile(r"^\s*(?:#{1,6}\s|[-*+]\s|\d+[.)]\s|>|```)")


def _canonical_markdown_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _is_plain_markdown_text(text: str) -> bool:
    return bool(text.strip()) and not _MARKDOWN_STRUCTURAL_LINE_RE.match(text)


def _ends_broken_line(text: str) -> bool:
    """Reconoce un corte de prosa que puede unirse sin inferir puntuación."""
    ending = text.rstrip()
    if not ending:
        return False
    last = ending[-1]
    return last in {",", ";"} or (last.isalpha() and last.islower())


def _starts_lowercase_text(text: str) -> bool:
    beginning = text.lstrip()
    return bool(beginning) and beginning[0].isalpha() and beginning[0].islower()


def join_broken_prose_lines(text: str) -> str:
    """Une sólo cortes de prosa minúscula, incluso si entre ellos hay líneas vacías.

    El criterio es deliberadamente conservador: la primera línea debe terminar
    en minúscula, coma o punto y coma; la siguiente línea de prosa debe empezar
    con minúscula. Las líneas estructurales de Markdown no se modifican.
    """
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    result: list[str] = []
    index = 0
    while index < len(lines):
        current = lines[index]
        # Una cadena puede abarcar más de dos líneas: seguí evaluándola antes
        # de emitirla para no dejar un corte intermedio sin unir.
        while True:
            next_index = index + 1
            while next_index < len(lines) and not lines[next_index].strip():
                next_index += 1
            if not (
                current.strip()
                and next_index < len(lines)
                and _is_plain_markdown_text(current)
                and _is_plain_markdown_text(lines[next_index])
                and _ends_broken_line(current)
                and _starts_lowercase_text(lines[next_index])
            ):
                break
            current = current.rstrip() + " " + lines[next_index].lstrip()
            index = next_index
        result.append(current.rstrip())
        index += 1
    return "\n".join(result)


def postprocess_markdown(markdown: str) -> tuple[str, int]:
    """Elimina duplicaciones consecutivas sin reescribir contenido del modelo.

    Solo compara líneas y párrafos de prosa adyacentes con igualdad exacta al
    normalizar espacios. De ese modo no elimina estribillos, listas o títulos
    que puedan ser intencionales.
    """
    text = join_broken_prose_lines(markdown).strip()
    text = _EXCESS_BLANK_LINES_RE.sub("\n\n", text)
    lines: list[str] = []
    removed = 0
    previous_line: str | None = None
    for line in text.split("\n"):
        if not line.strip():
            lines.append("")
            previous_line = None
            continue
        if (
            previous_line is not None
            and _is_plain_markdown_text(line)
            and _is_plain_markdown_text(previous_line)
            and _canonical_markdown_text(line) == _canonical_markdown_text(previous_line)
        ):
            removed += 1
            continue
        lines.append(line.rstrip())
        previous_line = line
    paragraphs: list[str] = []
    for paragraph in re.split(r"\n\n+", "\n".join(lines).strip()):
        if not paragraph.strip():
            continue
        if (
            paragraphs
            and _is_plain_markdown_text(paragraph)
            and _is_plain_markdown_text(paragraphs[-1])
            and _canonical_markdown_text(paragraph) == _canonical_markdown_text(paragraphs[-1])
        ):
            removed += 1
            continue
        paragraphs.append(paragraph.strip())
    return "\n\n".join(paragraphs).strip(), removed


def parse_srt(content: str) -> list[Cue]:
    """Parsea bloques SRT tolerando BOM y el último bloque sin línea vacía."""
    content = content.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
    cues: list[Cue] = []
    for block in re.split(r"\n\s*\n", content.strip()):
        lines = [line.strip() for line in block.split("\n") if line.strip()]
        if len(lines) < 3 or not lines[0].isdigit():
            continue
        timing = re.fullmatch(r"(.+?)\s+-->\s+(.+?)(?:\s+.*)?", lines[1])
        if not timing:
            continue
        try:
            start, end = _seconds(timing.group(1)), _seconds(timing.group(2))
        except ValueError:
            continue
        text = clean_text(" ".join(lines[2:]))
        if text and end >= start:
            cues.append(Cue(int(lines[0]), start, end, text))
    if not cues:
        raise SRTEssayError("No se encontraron subtítulos SRT válidos en el archivo.")
    return cues


def _ends_sentence(text: str) -> bool:
    return bool(re.search(r"[.!?…][\"'”»)]?$", text))


def make_paragraphs(cues: Iterable[Cue], max_chars: int = 900) -> list[str]:
    """Agrupa cues por continuidad temporal y cierre de oración.

    La IA mejora estos límites luego; esta fase no intenta inventar semántica.
    """
    paragraphs: list[str] = []
    current: list[str] = []
    current_length = 0
    previous: Cue | None = None
    for cue in cues:
        gap = cue.start - previous.end if previous else 0
        # El corte se produce ANTES del cue nuevo: la pausa pertenece a la
        # transición entre ambos, no al final de la frase que vamos a agregar.
        if current and previous and gap >= 1.2 and _ends_sentence(previous.text):
            paragraphs.append(" ".join(current))
            current, current_length = [], 0
        current.append(cue.text)
        current_length += len(cue.text) + 1
        should_break = _ends_sentence(cue.text) and current_length >= max_chars
        if should_break:
            paragraphs.append(" ".join(current))
            current, current_length = [], 0
        previous = cue
    if current:
        paragraphs.append(" ".join(current))
    return paragraphs


def parse_plain_document(content: str) -> list[str]:
    """Reduce TXT/Markdown a párrafos de texto antes de enviarlos al modelo."""
    content = content.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
    content = join_broken_prose_lines(content)
    # Frontmatter, enlaces y marcas de presentación no son parte de la prosa.
    # Una regla horizontal también usa `---`: sólo se considera frontmatter si
    # contiene al menos una clave YAML, para no borrar el texto hasta la próxima
    # regla horizontal del documento.
    frontmatter = re.match(r"\A---[ \t]*\n(.*?)\n(?:---|\.\.\.)[ \t]*(?:\n|\Z)", content, flags=re.DOTALL)
    if frontmatter and re.search(r"^[A-Za-z][A-Za-z0-9_-]*[ \t]*:", frontmatter.group(1), flags=re.MULTILINE):
        content = content[frontmatter.end():]
    content = re.sub(r"!?(?:\[([^\]]*)\])\([^)]*\)", r"\1", content)
    # Los separadores horizontales son presentación Markdown, no texto narrable.
    content = re.sub(r"^[ \t]*(?:-{3,}|\*{3,}|_{3,})[ \t]*$", "", content, flags=re.MULTILINE)
    # Algunas transcripciones insertan la regla entre frases; tampoco debe llegar al TTS.
    content = re.sub(r"(?<!\S)(?:-{3,}|\*{3,}|_{3,})(?!\S)", "", content)
    content = re.sub(r"^[ \t]*```[^\n]*$", "", content, flags=re.MULTILINE)
    # No usar `\s` aquí: también consume saltos de línea y fusiona párrafos.
    content = re.sub(r"^[ \t]*(?:#{1,6}[ \t]+|>[ \t]?|[-*+][ \t]+|\d+[.)][ \t]+)", "", content, flags=re.MULTILINE)
    content = re.sub(r"(?<!\w)[*_~`]+|[*_~`]+(?!\w)", "", content)
    paragraphs = [clean_text(block) for block in re.split(r"\n\s*\n", content)]
    paragraphs = [paragraph for paragraph in paragraphs if paragraph]
    if not paragraphs:
        raise SRTEssayError("El archivo no contiene texto legible después de la limpieza.")
    return paragraphs


def input_paragraphs(source: Path, content: str) -> list[str]:
    suffix = source.suffix.lower()
    if suffix == ".srt":
        return make_paragraphs(parse_srt(content))
    if suffix in {".md", ".txt"}:
        return parse_plain_document(content)
    raise SRTEssayError("Formato no compatible. Usá un archivo .srt, .md o .txt.")


def chunk_paragraphs(paragraphs: list[str], max_chars: int = DEFAULT_CHUNK_SIZE) -> list[list[str]]:
    if max_chars < 500:
        raise SRTEssayError("--chunk-size debe ser de al menos 500 caracteres.")
    chunks: list[list[str]] = []
    current: list[str] = []
    length = 0
    for paragraph in paragraphs:
        if current and length + len(paragraph) + 2 > max_chars:
            chunks.append(current)
            current, length = [], 0
        current.append(paragraph)
        length += len(paragraph) + 2
    if current:
        chunks.append(current)
    return chunks


REWRITE_SCHEMA = {
    "type": "object",
    "properties": {"markdown": {"type": "string"}},
    "required": ["markdown"],
    "additionalProperties": False,
}
GUIDE_SCHEMA = {
    "type": "object",
    "properties": {"guide": {"type": "string"}},
    "required": ["guide"],
    "additionalProperties": False,
}


def _normalize_structured_response(response: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
    """Tolera nombres razonables cuando un proveedor ignora parcialmente el esquema."""
    required = schema.get("required") if isinstance(schema, dict) else None
    if not isinstance(required, list) or len(required) != 1 or required[0] in response:
        return response
    expected = required[0]
    aliases = {
        "markdown": ("translation", "traduccion", "traducción", "texto", "text", "output", "response"),
        "guide": ("guia", "guía", "summary", "resumen", "text"),
    }.get(expected, ())
    for key in aliases:
        value = response.get(key)
        if isinstance(value, str) and value.strip():
            return {**response, expected: value}
    strings = [value for value in response.values() if isinstance(value, str) and value.strip()]
    return {**response, expected: strings[0]} if len(strings) == 1 else response


class OllamaClient:
    provider = "Ollama"
    def __init__(self, base_url: str, model: str, timeout: float = 180.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def _request(self, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = urllib.request.Request(
            f"{self.base_url}{path}", data=data,
            headers={"Content-Type": "application/json"} if data else {},
            method="POST" if data else "GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            if "failed to load model" in detail or "llama-server process has terminated" in detail:
                raise SRTEssayError(
                    f"Ollama no pudo cargar el modelo {self.model!r}. Reiniciá Ollama y reintentá. "
                    f"Si el problema persiste, reinstalá el modelo con `ollama rm {self.model} && ollama pull {self.model}`."
                ) from exc
            raise SRTEssayError(f"Ollama respondió HTTP {exc.code}: {detail}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise SRTEssayError(
                f"No se puede conectar con Ollama en {self.base_url}. "
                "Iniciá `ollama serve` o indicá --ollama-url."
            ) from exc
        except json.JSONDecodeError as exc:
            raise SRTEssayError("Ollama devolvió una respuesta que no es JSON válido.") from exc

    def list_models(self) -> list[dict[str, Any]]:
        response = self._request("/api/tags")
        models = response.get("models", [])
        if not isinstance(models, list):
            raise SRTEssayError("Ollama devolvió una lista de modelos inválida.")
        return [item for item in models if isinstance(item, dict) and isinstance(item.get("name"), str)]

    def verify_model(self) -> None:
        available = {item["name"] for item in self.list_models()}
        if self.model not in available:
            names = ", ".join(sorted(name for name in available if name)) or "ninguno"
            raise SRTEssayError(
                f"El modelo {self.model!r} no está instalado. Disponibles: {names}. "
                f"Instalalo con: ollama pull {self.model}"
            )

    def chat_json(self, system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        response = self._request("/api/chat", {
            "model": self.model,
            "stream": False,
            "format": schema,
            "keep_alive": "5m",
            "options": {"temperature": 0},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        })
        try:
            return _normalize_structured_response(json.loads(response["message"]["content"]), schema)
        except (KeyError, TypeError, json.JSONDecodeError) as exc:
            raise SRTEssayError("Ollama no devolvió el JSON estructurado esperado.") from exc


class HostedModelClient:
    """Adaptador HTTP mínimo para proveedores compatibles con el pipeline JSON."""

    provider = ""

    def __init__(self, model: str, api_key: str, timeout: float = 180.0) -> None:
        self.model, self.api_key, self.timeout = model, api_key.strip(), timeout
        self.last_usage: dict[str, Any] = {}
        if not self.api_key:
            raise SRTEssayError(f"Configurá la API key de {self.provider} en .srt-essay-secrets.json o en variables de entorno.")

    def _request(self, url: str, payload: dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> dict[str, Any]:
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = urllib.request.Request(url, data=data, headers=headers or {}, method="POST" if data else "GET")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise SRTEssayError(f"{self.provider} respondió HTTP {exc.code}: {detail}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise SRTEssayError(f"No se puede conectar con {self.provider}.") from exc
        except json.JSONDecodeError as exc:
            raise SRTEssayError(f"{self.provider} devolvió una respuesta que no es JSON válido.") from exc

    def verify_model(self) -> None:
        if not self.model:
            raise SRTEssayError("Seleccioná un modelo.")


class OpenAIClient(HostedModelClient):
    provider = "OpenAI"
    base_url = "https://api.openai.com/v1"

    def _headers(self) -> dict[str, str]:
        return {"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"}

    def list_models(self) -> list[dict[str, Any]]:
        data = self._request(f"{self.base_url}/models", headers=self._headers())
        return [{"name": item["id"]} for item in data.get("data", []) if isinstance(item, dict) and isinstance(item.get("id"), str)]

    def chat_json(self, system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        payload = {
            "model": self.model, "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [{"role": "system", "content": system + " Respondé exclusivamente JSON válido conforme al pedido."}, {"role": "user", "content": prompt}],
        }
        try:
            response = self._request(f"{self.base_url}/chat/completions", payload, self._headers())
        except SRTEssayError as exc:
            # Algunos modelos recientes (p. ej. GPT-5.6 Luna) solo admiten la temperatura predeterminada.
            if "temperature" not in str(exc) or "Only the default" not in str(exc):
                raise
            payload.pop("temperature")
            response = self._request(f"{self.base_url}/chat/completions", payload, self._headers())
        self.last_usage = response.get("usage") if isinstance(response.get("usage"), dict) else {}
        try:
            return _normalize_structured_response(json.loads(response["choices"][0]["message"]["content"]), schema)
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise SRTEssayError("OpenAI no devolvió el JSON estructurado esperado.") from exc


class AnthropicClient(HostedModelClient):
    provider = "Anthropic"
    base_url = "https://api.anthropic.com/v1"

    def _headers(self) -> dict[str, str]:
        return {"Content-Type": "application/json", "x-api-key": self.api_key, "anthropic-version": "2023-06-01"}

    def list_models(self) -> list[dict[str, Any]]:
        data = self._request(f"{self.base_url}/models", headers=self._headers())
        return [{"name": item["id"]} for item in data.get("data", []) if isinstance(item, dict) and isinstance(item.get("id"), str)]

    def chat_json(self, system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        instruction = "\n\nRespondé exclusivamente un objeto JSON válido conforme al pedido, sin texto adicional."
        response = self._request(f"{self.base_url}/messages", {
            "model": self.model, "max_tokens": 8192, "temperature": 0,
            "system": system + instruction, "messages": [{"role": "user", "content": prompt}],
        }, self._headers())
        self.last_usage = response.get("usage") if isinstance(response.get("usage"), dict) else {}
        try:
            return _normalize_structured_response(json.loads(response["content"][0]["text"]), schema)
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise SRTEssayError("Anthropic no devolvió el JSON estructurado esperado.") from exc


def configured_api_key(provider: str, secrets: dict[str, Any]) -> str:
    environment = {"openai": "OPENAI_API_KEY", "anthropic": "ANTHROPIC_API_KEY"}.get(provider)
    if environment and os.getenv(environment, "").strip():
        return os.getenv(environment, "").strip()
    section = secrets.get(provider, {}) if isinstance(secrets, dict) else {}
    return str(section.get("api_key", "")).strip() if isinstance(section, dict) else ""


def model_client(provider: str, model: str, *, ollama_url: str = DEFAULT_OLLAMA_URL, secrets: dict[str, Any] | None = None) -> Any:
    if provider == "ollama":
        return OllamaClient(ollama_url, model)
    key = configured_api_key(provider, secrets or {})
    if provider == "openai":
        return OpenAIClient(model, key)
    if provider == "anthropic":
        return AnthropicClient(model, key)
    raise SRTEssayError("El proveedor de modelo no es válido.")


class Checkpoint:
    def __init__(self, path: Path, fingerprint: str, config: dict[str, Any]) -> None:
        self.path, self.fingerprint, self.config = path, fingerprint, config
        self.data: dict[str, Any] = {"fingerprint": fingerprint, "config": config, "guide": "", "results": {}}
        if path.exists():
            self.data = json.loads(path.read_text(encoding="utf-8"))
            if self.data.get("fingerprint") != fingerprint:
                raise SRTEssayError("El checkpoint corresponde a otro archivo SRT; no se puede reanudar.")
            if self.data.get("config") != config:
                raise SRTEssayError("El checkpoint fue creado con otra configuración; usá la misma o eliminá el checkpoint.")

    def save(self) -> None:
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.path)


class SRTEssayPipeline:
    def __init__(self, client: Any, mode: str = "quality", chunk_size: int = DEFAULT_CHUNK_SIZE,
                 progress: Callable[[str], None] | None = None,
                 on_markdown: Callable[[str], None] | None = None,
                 on_block: Callable[[int, str], None] | None = None,
                 on_source: Callable[[int, str], None] | None = None,
                 on_comparison: Callable[[int, str, str], None] | None = None,
                 on_cleaned: Callable[[str], None] | None = None,
                 on_debug: Callable[[str, str], None] | None = None,
                 rewrite_system_prompt: str = DEFAULT_REWRITE_SYSTEM_PROMPT,
                 rewrite_instructions: str = DEFAULT_REWRITE_INSTRUCTIONS,
                 guide_instructions: str = DEFAULT_GUIDE_INSTRUCTIONS) -> None:
        if mode not in {"fast", "quality"}:
            raise SRTEssayError("--mode debe ser 'fast' o 'quality'.")
        self.client, self.mode, self.chunk_size = client, mode, chunk_size
        self.progress = progress or (lambda _: None)
        self.on_markdown = on_markdown or (lambda _: None)
        self.on_block = on_block or (lambda _, __: None)
        self.on_source = on_source or (lambda _, __: None)
        self.on_comparison = on_comparison or (lambda _, __, ___: None)
        self.on_cleaned = on_cleaned or (lambda _: None)
        self.on_debug = on_debug or (lambda _, __: None)
        self.rewrite_system_prompt = rewrite_system_prompt.strip() or DEFAULT_REWRITE_SYSTEM_PROMPT
        self.rewrite_instructions = rewrite_instructions.strip() or DEFAULT_REWRITE_INSTRUCTIONS
        self.guide_instructions = guide_instructions.strip() or DEFAULT_GUIDE_INSTRUCTIONS

    @staticmethod
    def _input(chunks: list[str]) -> str:
        return "\n\n".join(chunks)

    def _guide_chunk(self, index: int, total: int, chunk: list[str], previous_guide: str,
                     checkpoint: Checkpoint) -> str:
        """Actualiza la guía y permite redactar el mismo bloque inmediatamente."""
        key = f"guide-{index}"
        if key in checkpoint.data["results"]:
            return checkpoint.data["results"][key]
        self.progress(f"Guía de continuidad: bloque {index}/{total} · solicitud enviada; esperando respuesta de {getattr(self.client, 'provider', 'modelo')}")
        prompt = (
            "Guía anterior (puede estar vacía):\n" + previous_guide + "\n\n"
            "Texto fuente nuevo:\n" + self._input(chunk) + "\n\n" + self.guide_instructions
        )
        guide_system = "Sos un editor factual y extremadamente conservador."
        self.on_debug(f"guide-{index:03d}-prompt.txt", f"SYSTEM:\n{guide_system}\n\nUSER:\n{prompt}")
        guide = self.client.chat_json(guide_system, prompt, GUIDE_SCHEMA)["guide"].strip()
        self.progress(f"Guía de continuidad: bloque {index}/{total} · respuesta recibida")
        checkpoint.data["guide"] = guide
        checkpoint.data["results"][key] = guide
        checkpoint.save()
        return guide

    def run(self, source: Path, output: Path, checkpoint_path: Path) -> Path:
        raw = source.read_text(encoding="utf-8-sig")
        paragraphs = input_paragraphs(source, raw)
        self.on_cleaned("\n\n".join(paragraphs) + "\n")
        chunks = chunk_paragraphs(paragraphs, self.chunk_size)
        fingerprint = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        checkpoint = Checkpoint(checkpoint_path, fingerprint, {
            "mode": self.mode, "model": self.client.model, "chunk_size": self.chunk_size,
            "rewrite_system_prompt": self.rewrite_system_prompt,
            "rewrite_instructions": self.rewrite_instructions,
            "guide_instructions": self.guide_instructions,
        })
        self.client.verify_model()
        guide = ""
        final_parts: list[str] = []
        final_markdown = ""
        previous_tail = ""
        for index, chunk in enumerate(chunks, 1):
            if self.mode == "quality":
                guide = self._guide_chunk(index, len(chunks), chunk, guide, checkpoint)
            key = f"rewrite-{index}"
            if key in checkpoint.data["results"]:
                rewritten = checkpoint.data["results"][key]
            else:
                self.progress(f"Redacción: bloque {index}/{len(chunks)} · texto enviado; esperando respuesta de {getattr(self.client, 'provider', 'modelo')}")
                source_text = self._input(chunk)
                self.on_source(index, source_text)
                context = f"Guía factual del documento:\n{guide}\n\n" if guide else ""
                if previous_tail:
                    context += f"Último párrafo ya finalizado (solo para continuidad; NO lo repitas):\n{previous_tail}\n\n"
                prompt = (
                    context + "Texto fuente que debés devolver corregido:\n" + source_text + "\n\n" + self.rewrite_instructions
                )
                self.on_debug(f"rewrite-{index:03d}-prompt.txt", f"SYSTEM:\n{self.rewrite_system_prompt}\n\nUSER:\n{prompt}")
                model_markdown = self.client.chat_json(self.rewrite_system_prompt, prompt, REWRITE_SCHEMA)["markdown"].strip()
                self.progress(f"Redacción: bloque {index}/{len(chunks)} · respuesta recibida")
                rewritten, removed = postprocess_markdown(model_markdown)
                if removed:
                    self.on_debug(f"rewrite-{index:03d}-model-raw.md", model_markdown)
                    self.progress(f"Limpieza posgeneración: bloque {index}/{len(chunks)} · {removed} duplicación(es) consecutiva(s) eliminada(s)")
                if not rewritten:
                    raise SRTEssayError(f"{getattr(self.client, 'provider', 'El modelo')} devolvió un bloque vacío ({index}/{len(chunks)}).")
                checkpoint.data["results"][key] = rewritten
                checkpoint.save()
                self.on_comparison(index, source_text, rewritten)
            final_parts.append(rewritten)
            final_markdown, removed = postprocess_markdown("\n\n".join(final_parts))
            if removed:
                self.progress(f"Limpieza posgeneración: documento parcial · {removed} duplicación(es) entre bloques eliminada(s)")
            previous_tail = final_markdown.split("\n\n")[-1]
            # El consumidor puede mostrar resultados parciales sin esperar a que
            # finalice el documento completo. El archivo definitivo se conserva
            # como operación atómica al terminar el loop.
            self.on_markdown(final_markdown)
            self.on_block(index, rewritten)
        output.write_text(final_markdown + "\n", encoding="utf-8")
        checkpoint.path.unlink(missing_ok=True)
        self.progress(f"Archivo generado: {output}")
        return output
