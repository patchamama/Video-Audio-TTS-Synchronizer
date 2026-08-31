"""Servidor local, sin dependencias externas, para el conversor SRT Essay."""

from __future__ import annotations

import base64
import difflib
import http.server
import json
import mimetypes
import re
import shutil
import subprocess
import threading
import unicodedata
import uuid
from datetime import datetime
from dataclasses import dataclass, field
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from urllib.parse import parse_qs, quote, unquote, urlparse

from create_video_tts_from_srt import LANGUAGE_NAMES, generate_api_audio, get_available_tts

from .core import DEFAULT_CHUNK_SIZE, DEFAULT_GUIDE_INSTRUCTIONS, DEFAULT_MODEL, DEFAULT_OLLAMA_URL, DEFAULT_REWRITE_INSTRUCTIONS, DEFAULT_REWRITE_SYSTEM_PROMPT, GERMAN_TRANSCRIPTION_TRANSLATION_GUIDE_INSTRUCTIONS, GERMAN_TRANSCRIPTION_TRANSLATION_INSTRUCTIONS, GERMAN_TRANSCRIPTION_TRANSLATION_SYSTEM_PROMPT, REWRITE_SCHEMA, SUPPORTED_INPUT_SUFFIXES, TRANSLATION_ES_GUIDE_INSTRUCTIONS, TRANSLATION_ES_INSTRUCTIONS, TRANSLATION_ES_SYSTEM_PROMPT, OllamaClient, SRTEssayError, SRTEssayPipeline, input_paragraphs, model_client, parse_plain_document

WEB_ROOT = Path(__file__).with_name("web")
EUROPEAN_LANGUAGE_CODES = {"de", "en", "es", "fi", "fr", "it", "nl", "pt", "sv"}
TTS_PREVIEW_TEXTS = {
    "de": "Guten Tag. Dies ist eine kurze Stimmprobe für die Audioausgabe.",
    "en": "Hello. This is a short voice preview for the audio output.",
    "es": "Hola. Esta es una breve prueba de voz para la salida de audio.",
    "fi": "Hei. Tämä on lyhyt ääninäyte ääniulostuloa varten.",
    "fr": "Bonjour. Ceci est un court aperçu de voix pour la sortie audio.",
    "it": "Ciao. Questa è una breve prova della voce per l'uscita audio.",
    "nl": "Hallo. Dit is een korte stemtest voor de audio-uitvoer.",
    "pt": "Olá. Esta é uma breve amostra de voz para a saída de áudio.",
    "sv": "Hej. Detta är ett kort röstprov för ljudutmatningen.",
}


def _is_cached_wav(path: Path) -> bool:
    try:
        if not path.is_file():
            return False
        with path.open("rb") as stream:
            header = stream.read(12)
        return header[:4] == b"RIFF" and header[8:12] == b"WAVE"
    except OSError:
        return False


def audio_cache_summary_at(audio_root: Path, rate: int) -> dict[str, Any]:
    """Resume los WAV consecutivos y el primer fragmento pendiente por capítulo sin invocar ffprobe."""
    chapters = sorted(path for path in audio_root.glob("chapter-*") if path.is_dir())
    result = []
    for chapter in chapters:
        rate_dir = chapter / f"rate_{rate}"
        cached = 0
        while _is_cached_wav(rate_dir / f"{cached}.wav"):
            cached += 1
        if cached:
            result.append({"chapter": int(chapter.name.rsplit("-", 1)[-1]), "fragments": cached, "next_fragment": cached + 1, "rate": rate})
    return {"fragments": sum(item["fragments"] for item in result), "chapters": result}


def audio_cache_summary(workspace: TemporaryDirectory[str] | None, payload: dict[str, Any]) -> dict[str, Any]:
    """Resume los fragmentos WAV válidos y el primer fragmento pendiente por capítulo."""
    if not workspace:
        return {"fragments": 0, "chapters": []}
    try:
        rate = int(payload.get("audio_rate") or 200)
    except (TypeError, ValueError):
        rate = 200
    return audio_cache_summary_at(Path(workspace.name) / "audio", rate)


@dataclass
class Job:
    id: str
    name: str
    mode: str = "quality"
    status: str = "queued"
    progress: int = 0
    logs: list[str] = field(default_factory=list)
    error: str | None = None
    output: Path | None = None
    audio: Path | None = None
    audio_metadata: dict[str, Any] | None = None
    audio_files: list[dict[str, str]] = field(default_factory=list)
    audio_requested: bool = False
    audio_payload: dict[str, Any] = field(default_factory=dict)
    cleaned_text: str = ""
    markdown: str = ""
    debug: bool = False
    artifacts: list[dict[str, str]] = field(default_factory=list)
    comparisons: list[dict[str, str | int]] = field(default_factory=list)
    workspace: TemporaryDirectory[str] | None = None
    generated_dir: Path | None = None

    def snapshot(self) -> dict[str, Any]:
        return {
            "id": self.id, "name": self.name, "status": self.status, "progress": self.progress,
            "logs": self.logs, "error": self.error,
            "markdown": self.markdown,
            "artifacts": self.artifacts if self.debug else [],
            "comparisons": self.comparisons if self.debug else [],
            "download_url": f"/api/jobs/{self.id}/download" if self.output else None,
            "output_name": self.output.name if self.output else None,
            "audio_url": f"/api/jobs/{self.id}/audio" if self.audio else None,
            "audio_name": self.audio.name if self.audio else None,
            "audio_metadata": self.audio_metadata,
            "audio_files": self.audio_files,
            "can_resume_audio": self.status == "failed" and bool(self.workspace and self.audio_payload),
            "audio_cache": audio_cache_summary(self.workspace, self.audio_payload),
            "workspace_path": self.workspace.name if self.workspace else None,
            "workspace_uri": Path(self.workspace.name).as_uri() if self.workspace else None,
            "generated_path": str(self.generated_dir) if self.generated_dir else None,
            "generated_uri": self.generated_dir.as_uri() if self.generated_dir else None,
        }


class JobStore:
    def __init__(self) -> None:
        self.jobs: dict[str, Job] = {}
        self.lock = threading.Lock()
        self.input_root = Path.cwd().resolve()
        self.prompt_path = self.input_root / ".srt-essay-prompts.json"
        self.secrets_path = self.input_root / ".srt-essay-secrets.json"
        self.generated_root = self.input_root / "trabajos-generados"
        self.tts_previews: dict[str, tuple[Path, TemporaryDirectory[str]]] = {}

    def model_secrets(self) -> dict[str, Any]:
        try:
            data = json.loads(self.secrets_path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def models(self, provider: str, ollama_url: str) -> dict[str, Any]:
        client = model_client(provider, "", ollama_url=ollama_url, secrets=self.model_secrets())
        if provider == "ollama":
            models = client.list_models()
            default = DEFAULT_MODEL
        else:
            models = client.list_models()
            default = models[0]["name"] if models else ""
        return {"models": models, "default_model": default, "provider": provider,
                "credits": "El proveedor no expone saldo de créditos mediante esta API; se mostrarán los tokens usados por cada prueba." if provider in {"openai", "anthropic"} else None}

    def test_prompt(self, payload: dict[str, Any]) -> dict[str, Any]:
        text = str(payload.get("text") or "").strip()
        if not text:
            raise SRTEssayError("Ingresá un texto de prueba.")
        provider = str(payload.get("provider") or "ollama")
        model = str(payload.get("model") or "").strip()
        profile = {key: str(payload.get(key) or "").strip() for key in self._profile_fields()}
        if not model or not all(profile.values()):
            raise SRTEssayError("Seleccioná un modelo y completá los tres prompts antes de probar.")
        client = model_client(provider, model, ollama_url=str(payload.get("ollama_url") or DEFAULT_OLLAMA_URL), secrets=self.model_secrets())
        client.verify_model()
        prompt = (
            "Texto fuente que debés devolver corregido:\n" + text + "\n\n" + profile["rewrite_instructions"]
            + "\n\nFORMATO TÉCNICO OBLIGATORIO: devolvé un objeto JSON con una única propiedad "
            + '"markdown", cuyo valor es exclusivamente el texto final.'
        )
        result = client.chat_json(profile["rewrite_system_prompt"], prompt, REWRITE_SCHEMA)
        markdown = result.get("markdown") if isinstance(result, dict) else None
        if not isinstance(markdown, str) or not markdown.strip():
            raise SRTEssayError("El modelo no devolvió el campo Markdown esperado.")
        return {"markdown": markdown.strip(), "usage": getattr(client, "last_usage", {}),
                "credits": "Saldo no disponible: OpenAI y Anthropic devuelven uso por respuesta, no créditos restantes." if provider in {"openai", "anthropic"} else None}

    @staticmethod
    def tts_options() -> list[dict[str, Any]]:
        options: list[dict[str, Any]] = []
        for engine in get_available_tts():
            languages = [language for language in engine.get("languages", []) if language in EUROPEAN_LANGUAGE_CODES]
            if not languages:
                continue
            item = {**engine, "languages": languages}
            if isinstance(engine.get("voices"), list):
                item["voices"] = [
                    voice for voice in engine["voices"]
                    if voice.get("language") in EUROPEAN_LANGUAGE_CODES
                    or any(language in EUROPEAN_LANGUAGE_CODES for language in voice.get("languages", []))
                ]
            options.append(item)
        return options

    def create_tts_preview(self, payload: dict[str, Any]) -> dict[str, str]:
        language = str(payload.get("lang") or "")
        if language not in EUROPEAN_LANGUAGE_CODES:
            raise SRTEssayError("Seleccioná uno de los idiomas europeos disponibles.")
        workspace = TemporaryDirectory(prefix="srt-essay-voice-test-")
        try:
            audio, _metadata = generate_api_audio({
                "text": TTS_PREVIEW_TEXTS[language], "lang": language,
                "tts": payload.get("tts") or None, "voice": payload.get("voice") or None,
                "rate": int(payload.get("rate") or 200), "fixed_rate": True,
                "merge_batch_size": 1, "output_format": "mp3",
            }, Path(workspace.name))
        except Exception as exc:
            workspace.cleanup()
            raise SRTEssayError(f"La prueba de voz falló: {exc}") from exc
        preview_id = uuid.uuid4().hex
        self.tts_previews[preview_id] = (audio, workspace)
        return {"url": f"/api/tts/previews/{preview_id}", "text": TTS_PREVIEW_TEXTS[language]}

    def tts_preview(self, preview_id: str) -> Path | None:
        item = self.tts_previews.get(preview_id)
        return item[0] if item and item[0].is_file() else None

    @staticmethod
    def _default_profiles() -> dict[str, dict[str, str]]:
        return {
            "correccion-fiel": {
                "label": "Corrección fiel del original",
                "rewrite_system_prompt": DEFAULT_REWRITE_SYSTEM_PROMPT,
                "rewrite_instructions": DEFAULT_REWRITE_INSTRUCTIONS,
                "guide_instructions": DEFAULT_GUIDE_INSTRUCTIONS,
            },
            "traduccion-castellano-ensayo": {
                "label": "Traducción al castellano · ensayo fiel",
                "rewrite_system_prompt": TRANSLATION_ES_SYSTEM_PROMPT,
                "rewrite_instructions": TRANSLATION_ES_INSTRUCTIONS,
                "guide_instructions": TRANSLATION_ES_GUIDE_INSTRUCTIONS,
            },
            "traduccion-aleman-espanol-transcripciones": {
                "label": "Traducción alemán - español a partir de transcripciones",
                "rewrite_system_prompt": GERMAN_TRANSCRIPTION_TRANSLATION_SYSTEM_PROMPT,
                "rewrite_instructions": GERMAN_TRANSCRIPTION_TRANSLATION_INSTRUCTIONS,
                "guide_instructions": GERMAN_TRANSCRIPTION_TRANSLATION_GUIDE_INSTRUCTIONS,
            },
        }

    @staticmethod
    def _profile_fields() -> tuple[str, ...]:
        return "rewrite_system_prompt", "rewrite_instructions", "guide_instructions"

    def prompts(self) -> dict[str, Any]:
        profiles = self._default_profiles()
        active_profile = "correccion-fiel"
        if not self.prompt_path.is_file():
            return {"active_profile": active_profile, "profiles": profiles}
        try:
            saved = json.loads(self.prompt_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"active_profile": active_profile, "profiles": profiles}
        if not isinstance(saved, dict):
            return {"active_profile": active_profile, "profiles": profiles}
        # Migración automática desde el perfil único usado en versiones previas.
        if isinstance(saved.get("profiles"), dict):
            for profile_id, profile in saved["profiles"].items():
                if not isinstance(profile_id, str) or not isinstance(profile, dict):
                    continue
                candidate = {"label": str(profile.get("label") or profile_id)}
                for key in self._profile_fields():
                    if isinstance(profile.get(key), str) and profile[key].strip():
                        candidate[key] = profile[key]
                if all(key in candidate for key in self._profile_fields()):
                    profiles[profile_id] = candidate
            if saved.get("active_profile") in profiles:
                active_profile = saved["active_profile"]
        else:
            legacy = profiles["correccion-fiel"]
            for key in self._profile_fields():
                if isinstance(saved.get(key), str) and saved[key].strip():
                    legacy[key] = saved[key]
        return {"active_profile": active_profile, "profiles": profiles}

    def save_prompts(self, payload: dict[str, Any]) -> dict[str, Any]:
        profile_id = str(payload.get("profile_id") or "").strip()
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", profile_id):
            raise SRTEssayError("El identificador del perfil debe usar minúsculas, números o guiones.")
        label = str(payload.get("label") or "").strip()
        if not label:
            raise SRTEssayError("El perfil debe tener un nombre visible.")
        document = self.prompts()
        profile = {"label": label}
        for key in self._profile_fields():
            value = payload.get(key)
            if not isinstance(value, str) or not value.strip():
                raise SRTEssayError(f"El campo {key} debe contener texto.")
            profile[key] = value.strip()
        document["profiles"][profile_id] = profile
        document["active_profile"] = profile_id
        temporary = self.prompt_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(self.prompt_path)
        return document

    def prompt_profile(self, profile_id: str | None) -> tuple[str, dict[str, str]]:
        document = self.prompts()
        selected = profile_id if profile_id in document["profiles"] else document["active_profile"]
        return selected, document["profiles"][selected]

    @staticmethod
    def _valid_suffix(path: Path) -> bool:
        return path.suffix.lower() in SUPPORTED_INPUT_SUFFIXES

    def input_files(self) -> list[str]:
        ignored = {".git", ".venv", "__pycache__"}
        files: list[str] = []
        for path in self.input_root.rglob("*"):
            if any(part in ignored or part.startswith("temp_") for part in path.relative_to(self.input_root).parts):
                continue
            if path.is_file() and self._valid_suffix(path):
                files.append(path.relative_to(self.input_root).as_posix())
        return sorted(files, key=str.casefold)

    def _local_path(self, relative_path: str) -> Path:
        input_root = self.input_root.resolve()
        candidate = (input_root / relative_path).resolve()
        if input_root not in candidate.parents or not candidate.is_file() or not self._valid_suffix(candidate):
            raise SRTEssayError("El archivo local seleccionado no es válido.")
        return candidate

    def _local_input(self, relative_path: str) -> tuple[str, bytes]:
        candidate = self._local_path(relative_path)
        return candidate.name, candidate.read_bytes()

    def _local_audio_cache_roots(self, candidate: Path) -> list[Path]:
        """Devuelve directorios de caché asociados a una fuente local, sin duplicados."""
        candidates = [
            self.input_root / "_work" / "audio",
            candidate.parent / "_work" / "audio",
            candidate.parent / "audio",
        ]
        roots: list[Path] = []
        for root in candidates:
            root = root.resolve()
            if root.is_dir() and root not in roots:
                roots.append(root)
        return roots

    def local_audio_caches(self, relative_path: str, rate: int) -> dict[str, Any]:
        """Busca caché reutilizable asociada a un archivo local, sin crear un trabajo."""
        candidate = self._local_path(relative_path)
        caches: list[dict[str, Any]] = []
        for root in self._local_audio_cache_roots(candidate):
            summary = audio_cache_summary_at(root, rate)
            if summary["fragments"]:
                caches.append({**summary, "path": str(root), "uri": root.as_uri()})
        return {
            "source": {"path": str(candidate), "uri": candidate.as_uri(), "name": candidate.name},
            "rate": rate,
            "caches": caches,
            "fragments": sum(cache["fragments"] for cache in caches),
        }

    def delete_local_audio_cache(self, relative_path: str, rate: int) -> dict[str, int]:
        """Elimina solamente la caché de la velocidad seleccionada para una fuente local."""
        candidate = self._local_path(relative_path)
        removed_fragments = 0
        removed_directories = 0
        for cache_root in self._local_audio_cache_roots(candidate):
            for chapter in cache_root.glob("chapter-*"):
                rate_directory = chapter / f"rate_{rate}"
                if not rate_directory.is_dir():
                    continue
                removed_fragments += sum(
                    1 for path in rate_directory.glob("*.wav")
                    if path.stem.isdigit() and _is_cached_wav(path)
                )
                shutil.rmtree(rate_directory)
                removed_directories += 1
                try:
                    chapter.rmdir()
                except OSError:
                    pass
        return {"fragments": removed_fragments, "directories": removed_directories}

    def seed_audio_cache(self, relative_path: str | None, rate: int, destination: Path) -> dict[str, int]:
        """Copia fragmentos WAV reutilizables al temporal antes de ejecutar el TTS."""
        if not relative_path:
            return {"fragments": 0, "chapters": 0}
        candidate = self._local_path(relative_path)
        copied, chapters = 0, set()
        for cache_root in self._local_audio_cache_roots(candidate):
            for chapter in cache_root.glob("chapter-*"):
                source_rate = chapter / f"rate_{rate}"
                if not source_rate.is_dir():
                    continue
                target_rate = destination / chapter.name / source_rate.name
                for source_file in source_rate.glob("*.wav"):
                    if not re.fullmatch(r"(?:\d+|pause_\d+)\.wav", source_file.name) or not _is_cached_wav(source_file):
                        continue
                    target = target_rate / source_file.name
                    if target.exists():
                        continue
                    target_rate.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source_file, target)
                    if source_file.stem.isdigit():
                        copied += 1
                        chapters.add(chapter.name)
        return {"fragments": copied, "chapters": len(chapters)}

    def create(self, payload: dict[str, Any]) -> Job:
        local_path = payload.get("source_path")
        if isinstance(local_path, str) and local_path:
            name, content = self._local_input(local_path)
        else:
            encoded = payload.get("source_data")
            name = Path(str(payload.get("source_name") or "document.srt")).name
            if not isinstance(encoded, str) or not self._valid_suffix(Path(name)):
                raise SRTEssayError("Seleccioná un archivo .srt, .md o .txt válido.")
            try:
                content = base64.b64decode(encoded, validate=True)
            except ValueError as exc:
                raise SRTEssayError("No se pudo leer el archivo enviado.") from exc
        job = Job(
            id=uuid.uuid4().hex, name=name, mode=str(payload.get("mode") or "quality"),
            debug=bool(payload.get("debug")), audio_requested=bool(payload.get("generate_audio") or payload.get("audio_only")),
            workspace=TemporaryDirectory(prefix="srt-essay-"),
        )
        root = Path(job.workspace.name)
        (root / name).write_bytes(content)
        with self.lock:
            self.jobs[job.id] = job
        thread = threading.Thread(target=self._run, args=(job, payload), daemon=True)
        thread.start()
        return job

    @staticmethod
    def _progress(job: Job, message: str) -> None:
        match = re.search(r"bloque (\d+)/(\d+)", message)
        limit = 85 if job.audio_requested else 100
        if match:
            current, total = map(int, match.groups())
            if message.startswith("Guía"):
                job.progress = max(job.progress, round(((current - 1) + 0.5) / total * limit))
            elif message.startswith("Redacción"):
                job.progress = max(job.progress, round(current / total * limit))
        job.logs.append(message)

    @staticmethod
    def _artifact(job: Job, name: str, content: str) -> dict[str, str] | None:
        if not job.debug or not job.workspace:
            return None
        directory = Path(job.workspace.name) / "debug"
        directory.mkdir(exist_ok=True)
        target = directory / name
        target.write_text(content, encoding="utf-8")
        item = {"name": name, "url": f"/api/jobs/{job.id}/artifacts/{name}"}
        job.artifacts[:] = [existing for existing in job.artifacts if existing["name"] != name]
        job.artifacts.append(item)
        return item

    @staticmethod
    def _comparison_item(job: Job, index: int) -> dict[str, str | int]:
        existing = next((item for item in job.comparisons if item["index"] == index), None)
        if existing is None:
            existing = {"index": index}
            job.comparisons.append(existing)
        return existing

    def _source(self, job: Job, index: int, source: str, provider: str = "modelo") -> None:
        artifact = self._artifact(job, f"chunk-{index:03d}-sent.txt", source)
        job.logs.append(f"Bloque {index}: texto enviado a {provider} ({len(source)} caracteres).")
        if artifact:
            self._comparison_item(job, index)["source_url"] = artifact["url"]

    def _comparison(self, job: Job, index: int, source: str, corrected: str) -> None:
        corrected_artifact = self._artifact(job, f"chunk-{index:03d}-corrected.md", corrected)
        patch = "".join(difflib.unified_diff(
            source.splitlines(keepends=True), corrected.splitlines(keepends=True),
            fromfile="enviado.txt", tofile="corregido.md",
        ))
        diff_artifact = self._artifact(job, f"chunk-{index:03d}.diff", patch)
        if corrected_artifact:
            item = self._comparison_item(job, index)
            item["corrected_url"] = corrected_artifact["url"]
            if diff_artifact:
                item["diff_url"] = diff_artifact["url"]
        job.logs.append(f"Bloque {index}: texto corregido recibido ({len(corrected)} caracteres).")

    def _cleaned(self, job: Job, content: str) -> None:
        job.cleaned_text = content
        self._artifact(job, "cleaned-input.txt", content)

    @staticmethod
    def _markdown(job: Job, content: str) -> None:
        job.markdown = content
        job.logs.append(f"Vista previa Markdown actualizada ({len(content)} caracteres).")

    @staticmethod
    def _audio_source(job: Job, source_kind: str) -> str:
        # `cleaned_text` ya pasó por input_paragraphs al crear el trabajo. No
        # lo proceses por segunda vez: además de ser redundante, una limpieza
        # posterior no debe poder convertir una entrada validada en texto vacío.
        if source_kind == "input":
            text = job.cleaned_text.strip()
        else:
            paragraphs = parse_plain_document(job.markdown)
            text = "\n\n".join(paragraphs).strip()
        if not text:
            raise SRTEssayError("No hay texto disponible para generar el audio.")
        return text

    @staticmethod
    def _chapter_sources(job: Job, source_kind: str, root: Path) -> list[tuple[str, str]]:
        """Separa por encabezados Markdown de nivel 1 y 2, preservando el texto narrable."""
        if source_kind == "markdown":
            document = job.markdown
        elif Path(job.name).suffix.lower() == ".md":
            document = (root / job.name).read_text(encoding="utf-8-sig")
        else:
            document = job.cleaned_text
        chapters: list[tuple[str, str]] = []
        title = "Introducción"
        content: list[str] = []

        def append_chapter() -> None:
            body = "\n".join(content).strip()
            if not body:
                return
            try:
                paragraphs = parse_plain_document(body)
            except SRTEssayError as error:
                # Un título puede contener sólo una regla horizontal Markdown.
                # No es un capítulo narrable y no debe abortar todo el trabajo.
                if "no contiene texto legible" not in str(error):
                    raise
                job.logs.append(f"Audio: se omitió el capítulo sin texto narrable: {title}.")
                return
            text = "\n\n".join([title, *paragraphs]).strip()
            chapters.append((title, text))

        for line in document.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
            header = re.match(r"^#{1,2}\s+(.+?)\s*#*\s*$", line)
            if header:
                append_chapter()
                title, content = header.group(1).strip(), []
            else:
                content.append(line)
        append_chapter()
        return chapters or [("Documento completo", JobStore._audio_source(job, source_kind))]

    @staticmethod
    def _chapter_filename(index: int, total: int, title: str) -> str:
        width = 2 if total < 100 else 3 if total < 1000 else len(str(total))
        # Conserva espacios y acentos: el nombre es legible también fuera de la web.
        safe_title = re.sub(r'[\\/:*?"<>|\x00-\x1f]+', "-", title).strip() or "Capítulo"
        return f"{index:0{width}d}. {safe_title}.mp3"

    def _generate_audio(self, job: Job, payload: dict[str, Any], root: Path) -> None:
        source_kind = str(payload.get("audio_source") or "markdown")
        if source_kind not in {"markdown", "input"}:
            raise SRTEssayError("La fuente de audio no es válida.")
        job.audio_payload = {**payload, "audio_source": source_kind}
        try:
            rate = int(payload.get("audio_rate") or 200)
        except (TypeError, ValueError) as exc:
            raise SRTEssayError("La velocidad de audio debe ser un número entero en WPM.") from exc
        if not 80 <= rate <= 500:
            raise SRTEssayError("La velocidad de audio debe estar entre 80 y 500 WPM.")
        try:
            batch_size = int(payload.get("audio_merge_batch_size") or 50)
            test_fragments = int(payload.get("audio_test_fragments") or 0)
        except (TypeError, ValueError) as exc:
            raise SRTEssayError("El tamaño de lote y el modo test deben usar números enteros.") from exc
        if not 1 <= batch_size <= 500:
            raise SRTEssayError("El tamaño de lote debe estar entre 1 y 500 fragmentos.")
        if test_fragments < 0:
            raise SRTEssayError("La cantidad de fragmentos de prueba no puede ser negativa.")
        split_chapters = bool(payload.get("audio_split_chapters"))
        sources = self._chapter_sources(job, source_kind, root) if split_chapters else [("Audio completo", self._audio_source(job, source_kind))]
        job.logs.append(f"Audio: preparando {len(sources)} {'capítulo(s)' if split_chapters else 'archivo'} para TTS.")
        audio_directory = root / "audio"
        audio_directory.mkdir(exist_ok=True)
        seeded = self.seed_audio_cache(str(payload.get("source_path") or "") or None, rate, audio_directory)
        if seeded["fragments"]:
            job.logs.append(f"Audio: {seeded['fragments']} fragmento(s) existente(s) copiado(s) al temporal desde la caché local ({seeded['chapters']} capítulo(s)); no se regenerarán.")
        job.audio_files = []
        progress_start = 85 if job.audio_requested and not bool(payload.get("audio_only")) else 0
        progress_span = 100 - progress_start
        for chapter_index, (title, text) in enumerate(sources, 1):
            def report_audio_progress(message: str, current_chapter: int = chapter_index) -> None:
                job.logs.append(f"{'Capítulo ' + str(current_chapter) + '/' + str(len(sources)) + ' · ' if split_chapters else ''}{message}")
                fragment = re.search(r"fragmento (\d+)/(\d+)", message)
                batch = re.search(r"lote (\d+)/(\d+)", message)
                local = 0.0
                if fragment:
                    current, total = map(int, fragment.groups())
                    local = current / total * .70
                elif batch:
                    current, total = map(int, batch.groups())
                    local = .70 + current / total * .15
                elif "pista final" in message or "codificando" in message:
                    local = .92
                elif "final preparado" in message:
                    local = 1
                job.progress = max(job.progress, round(progress_start + ((current_chapter - 1 + local) / len(sources)) * progress_span))
            chapter_directory = audio_directory / f"chapter-{chapter_index:04d}"
            chapter_directory.mkdir(exist_ok=True)
            audio, metadata = generate_api_audio({
                "text": text, "lang": str(payload.get("audio_lang") or "es"),
                "tts": payload.get("audio_tts") or None, "voice": payload.get("audio_voice") or None,
                "pause_ms": max(0, int(payload.get("audio_pause_ms") or 0)), "fixed_rate": True,
                "rate": rate, "_progress": report_audio_progress, "merge_batch_size": batch_size,
                "max_fragments": test_fragments or None, "output_format": "mp3",
            }, chapter_directory)
            if split_chapters:
                target = audio_directory / self._chapter_filename(chapter_index, len(sources), title)
                target.write_bytes(audio.read_bytes())
                item = {"name": target.name, "title": title, "url": f"/api/jobs/{job.id}/audio/{quote(target.name)}"}
                job.audio_files.append(item)
            else:
                target = audio
            job.audio, job.audio_metadata = target, metadata
            job.logs.append(f"Audio: {'capítulo ' + str(chapter_index) if split_chapters else 'archivo'} generado con {metadata['tts_used']} ({metadata['duration']:.1f} s).")

    def resume_audio(self, job_id: str, overrides: dict[str, Any]) -> Job:
        """Reintenta un audio fallido usando su misma carpeta y los fragmentos ya guardados."""
        job = self.get(job_id)
        if not job or not job.workspace or not job.audio_payload:
            raise SRTEssayError("El trabajo de audio ya no está disponible para reanudar.")
        if job.status == "running":
            raise SRTEssayError("El trabajo de audio ya está en ejecución.")
        allowed = {"audio_lang", "audio_tts", "audio_voice", "audio_rate", "audio_pause_ms", "audio_merge_batch_size", "audio_test_fragments", "audio_split_chapters"}
        payload = {**job.audio_payload, **{key: value for key, value in overrides.items() if key in allowed}}
        job.status, job.error = "queued", None
        job.logs.append("Audio: reanudando desde la caché de fragmentos existente.")

        def retry() -> None:
            job.status = "running"
            try:
                root = Path(job.workspace.name)
                self._generate_audio(job, payload, root)
                self._persist_results(job, root)
                job.progress, job.status = 100, "completed"
            except (SRTEssayError, ValueError) as exc:
                job.error, job.status = str(exc), "failed"
                job.logs.append(f"Error: {exc}")
            except Exception as exc:
                job.error, job.status = f"Error inesperado: {exc}", "failed"
                job.logs.append(job.error)

        threading.Thread(target=retry, daemon=True).start()
        return job

    def _persist_results(self, job: Job, root: Path) -> None:
        """Preserva salida, fuente y Debug fuera del temporal antes de abrir Finder."""
        self.generated_root.mkdir(parents=True, exist_ok=True)
        stem = re.sub(r"[^A-Za-z0-9_.-]+", "-", Path(job.name).stem).strip(".-") or "trabajo"
        destination = self.generated_root / f"{datetime.now():%Y%m%d-%H%M%S}-{stem}-{job.id[:8]}"
        destination.mkdir()
        source = root / job.name
        if source.is_file():
            shutil.copy2(source, destination / source.name)
        if job.output and job.output.is_file():
            copied_output = destination / job.output.name
            shutil.copy2(job.output, copied_output)
            job.output = copied_output
        elif job.cleaned_text:
            cleaned_output = destination / f"{Path(job.name).stem}.limpio.md"
            cleaned_output.write_text(job.cleaned_text + "\n", encoding="utf-8")
            job.output = cleaned_output
        if job.audio and job.audio.is_file():
            audio_destination = destination / "audio"
            audio_destination.mkdir()
            for audio in (root / "audio").glob("*.mp3") if (root / "audio").is_dir() else []:
                shutil.copy2(audio, audio_destination / audio.name)
            if not any(audio_destination.iterdir()):
                shutil.copy2(job.audio, audio_destination / job.audio.name)
            job.audio = audio_destination / job.audio.name
        if job.debug and (root / "debug").is_dir():
            shutil.copytree(root / "debug", destination / "debug")
        job.generated_dir = destination
        job.logs.append(f"Salida preservada en: {destination}")
        try:
            subprocess.run(["open", str(destination)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
            job.logs.append("Carpeta del trabajo generado abierta en Finder.")
        except (OSError, subprocess.CalledProcessError) as exc:
            job.logs.append(f"No se pudo abrir Finder automáticamente: {exc}")

    def _run(self, job: Job, payload: dict[str, Any]) -> None:
        job.status = "running"
        job.logs.append("Procesamiento iniciado.")
        root = Path(job.workspace.name)  # se mantiene vivo hasta descarga/salida del proceso
        source = root / job.name
        output = root / f"{source.stem}.essay.md"
        try:
            if payload.get("audio_only"):
                job.logs.append("Audio: limpiando archivo de entrada, sin usar Ollama.")
                cleaned = "\n\n".join(input_paragraphs(source, source.read_text(encoding="utf-8-sig")))
                self._cleaned(job, cleaned)
                job.markdown = cleaned
                self._generate_audio(job, {**payload, "audio_source": "input"}, root)
                self._persist_results(job, root)
                job.progress, job.status = 100, "completed"
                return
            model = str(payload.get("model") or DEFAULT_MODEL)
            provider = str(payload.get("provider") or "ollama")
            mode = str(payload.get("mode") or "quality")
            size = int(payload.get("chunk_size") or DEFAULT_CHUNK_SIZE)
            url = str(payload.get("ollama_url") or DEFAULT_OLLAMA_URL)
            profile_id, prompts = self.prompt_profile(payload.get("prompt_id"))
            job.logs.append(f"Perfil de prompt: {profile_id}.")
            rewrite_system = prompts["rewrite_system_prompt"]
            rewrite_instructions = prompts["rewrite_instructions"]
            guide_instructions = prompts["guide_instructions"]
            job.logs.append(f"Proveedor de modelo: {provider}.")
            pipeline = SRTEssayPipeline(
                model_client(provider, model, ollama_url=url, secrets=self.model_secrets()), mode=mode, chunk_size=size,
                progress=lambda message: self._progress(job, message),
                on_markdown=lambda markdown: self._markdown(job, markdown),
                on_block=lambda index, markdown: self._artifact(job, f"rewrite-{index:03d}.md", markdown),
                on_source=lambda index, source: self._source(job, index, source, provider),
                on_comparison=lambda index, source, corrected: self._comparison(job, index, source, corrected),
                on_cleaned=lambda content: self._cleaned(job, content),
                on_debug=lambda name, content: self._artifact(job, name, content),
                rewrite_system_prompt=rewrite_system,
                rewrite_instructions=rewrite_instructions,
                guide_instructions=guide_instructions,
            )
            job.output = pipeline.run(source, output, root / ".checkpoint.json")
            if payload.get("generate_audio"):
                self._generate_audio(job, payload, root)
            self._persist_results(job, root)
            job.progress, job.status = 100, "completed"
        except (SRTEssayError, ValueError) as exc:
            job.error, job.status = str(exc), "failed"
            job.logs.append(f"Error: {exc}")
        except Exception as exc:  # evita que la UI quede esperando ante fallos no previstos
            job.error, job.status = f"Error inesperado: {exc}", "failed"
            job.logs.append(job.error)

    def get(self, job_id: str) -> Job | None:
        with self.lock:
            return self.jobs.get(job_id)


def start_web_ui(port: int = 8768) -> None:
    store = JobStore()

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, _format: str, *_args: Any) -> None:
            return

        def send_json(self, status: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            path = unquote(urlparse(self.path).path)
            if path == "/api/health":
                self.send_json(200, {"status": "ok", "default_model": DEFAULT_MODEL})
                return
            if path == "/api/models":
                query = parse_qs(urlparse(self.path).query)
                ollama_url = query.get("ollama_url", [DEFAULT_OLLAMA_URL])[0]
                provider = str(query.get("provider", ["ollama"])[0])
                try:
                    result = store.models(provider, str(ollama_url))
                except SRTEssayError as exc:
                    self.send_json(502, {"error": str(exc)})
                    return
                self.send_json(200, result)
                return
            if path == "/api/input-files":
                self.send_json(200, {"files": store.input_files(), "root": str(store.input_root)})
                return
            if path == "/api/audio-cache":
                query = parse_qs(urlparse(self.path).query)
                relative_path = str(query.get("source_path", [""])[0])
                try:
                    rate = int(query.get("rate", ["200"])[0])
                    if not 80 <= rate <= 500:
                        raise ValueError
                    self.send_json(200, store.local_audio_caches(relative_path, rate))
                except (ValueError, SRTEssayError):
                    self.send_json(400, {"error": "Indicá un archivo local válido y una velocidad entre 80 y 500 WPM."})
                return
            if path == "/api/prompts":
                self.send_json(200, store.prompts())
                return
            if path == "/api/tts":
                self.send_json(200, {"engines": store.tts_options(), "language_names": {code: LANGUAGE_NAMES[code] for code in sorted(EUROPEAN_LANGUAGE_CODES)}})
                return
            match = re.fullmatch(r"/api/tts/previews/([0-9a-f]+)", path)
            if match:
                audio = store.tts_preview(match.group(1))
                if not audio:
                    self.send_json(404, {"error": "La prueba de voz ya no está disponible."})
                    return
                body = audio.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "audio/mpeg")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            match = re.fullmatch(r"/api/jobs/([0-9a-f]+)/?$", path)
            if match:
                job = store.get(match.group(1))
                if not job:
                    self.send_json(404, {"error": "Trabajo no encontrado."})
                else:
                    self.send_json(200, job.snapshot())
                return
            match = re.fullmatch(r"/api/jobs/([0-9a-f]+)/download", path)
            if match:
                job = store.get(match.group(1))
                if not job or not job.output or not job.output.is_file():
                    self.send_json(404, {"error": "La salida todavía no está disponible."})
                    return
                body = job.output.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/markdown; charset=utf-8")
                self.send_header("Content-Disposition", f'attachment; filename="{job.output.name}"')
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            match = re.fullmatch(r"/api/jobs/([0-9a-f]+)/audio", path)
            if match:
                job = store.get(match.group(1))
                if not job or not job.audio or not job.audio.is_file():
                    self.send_json(404, {"error": "El audio todavía no está disponible."})
                    return
                body = job.audio.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", mimetypes.guess_type(job.audio.name)[0] or "application/octet-stream")
                self.send_header("Content-Disposition", f'attachment; filename="{job.audio.name}"')
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            match = re.fullmatch(r"/api/jobs/([0-9a-f]+)/audio/([^/]+)", path)
            if match:
                job = store.get(match.group(1))
                if not job or not job.workspace:
                    self.send_json(404, {"error": "El audio no está disponible."})
                    return
                output_root = job.generated_dir if job.generated_dir else Path(job.workspace.name)
                target = (output_root / "audio" / match.group(2)).resolve()
                audio_root = (output_root / "audio").resolve()
                if audio_root not in target.parents or not target.is_file():
                    self.send_json(404, {"error": "El audio no está disponible."})
                    return
                body = target.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", mimetypes.guess_type(target.name)[0] or "application/octet-stream")
                self.send_header("Content-Disposition", f'attachment; filename="{target.name}"')
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            match = re.fullmatch(r"/api/jobs/([0-9a-f]+)/artifacts/([A-Za-z0-9_.-]+)", path)
            if match:
                job = store.get(match.group(1))
                if not job or not job.workspace or not job.debug:
                    self.send_json(404, {"error": "Archivo intermedio no encontrado."})
                    return
                target = (Path(job.workspace.name) / "debug" / match.group(2)).resolve()
                debug_root = (Path(job.workspace.name) / "debug").resolve()
                if debug_root not in target.parents or not target.is_file():
                    self.send_json(404, {"error": "Archivo intermedio no encontrado."})
                    return
                body = target.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Disposition", f'attachment; filename="{target.name}"')
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            relative = "index.html" if path in {"/", "/index.html"} else path.lstrip("/")
            target = (WEB_ROOT / relative).resolve()
            if WEB_ROOT.resolve() not in target.parents or not target.is_file():
                self.send_error(404)
                return
            body = target.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", mimetypes.guess_type(target.name)[0] or "application/octet-stream")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            resume_match = re.fullmatch(r"/api/jobs/([0-9a-f]+)/resume-audio", path)
            if resume_match:
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    payload = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
                    self.send_json(202, store.resume_audio(resume_match.group(1), payload).snapshot())
                except (ValueError, json.JSONDecodeError, SRTEssayError) as exc:
                    self.send_json(400, {"error": str(exc)})
                return
            if path == "/api/audio-cache/delete":
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    payload = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
                    relative_path = str(payload.get("source_path") or "")
                    rate = int(payload.get("rate") or 200)
                    if not 80 <= rate <= 500:
                        raise ValueError
                    self.send_json(200, store.delete_local_audio_cache(relative_path, rate))
                except (ValueError, json.JSONDecodeError, SRTEssayError):
                    self.send_json(400, {"error": "Indicá un archivo local válido y una velocidad entre 80 y 500 WPM."})
                return
            match = re.fullmatch(r"/api/jobs/([0-9a-f]+)/open-workspace", path)
            if match:
                job = store.get(match.group(1))
                location = job.generated_dir if job and job.generated_dir else Path(job.workspace.name) if job and job.workspace else None
                if not location or not location.is_dir():
                    self.send_json(404, {"error": "La carpeta temporal ya no está disponible."})
                    return
                try:
                    subprocess.run(["open", str(location)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
                except (OSError, subprocess.CalledProcessError) as exc:
                    self.send_json(500, {"error": f"No se pudo abrir la carpeta temporal: {exc}"})
                    return
                self.send_json(200, {"path": str(location)})
                return
            if path not in {"/api/jobs", "/api/prompts", "/api/prompts/test", "/api/tts/test"}:
                self.send_json(404, {"error": "Ruta no encontrada."})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
                if path == "/api/tts/test":
                    self.send_json(200, store.create_tts_preview(payload))
                    return
                if path == "/api/prompts":
                    self.send_json(200, store.save_prompts(payload))
                    return
                if path == "/api/prompts/test":
                    self.send_json(200, store.test_prompt(payload))
                    return
                job = store.create(payload)
            except (ValueError, json.JSONDecodeError, SRTEssayError) as exc:
                self.send_json(400, {"error": str(exc)})
                return
            self.send_json(202, job.snapshot())

    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"SRT Essay disponible en http://127.0.0.1:{port} (Ctrl+C para detenerlo)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
