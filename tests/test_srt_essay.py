from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from srt_essay.core import Cue, SRTEssayError, chunk_paragraphs, input_paragraphs, make_paragraphs, parse_srt, parse_plain_document


def test_parse_srt_joins_lines_and_removes_formatting():
    cues = parse_srt("\ufeff1\n00:00:00,000 --> 00:00:01,000\n<i>Hola</i>\nmundo.\n\n2\n00:00:02,000 --> 00:00:03,000\nAdiós.")
    assert [cue.text for cue in cues] == ["Hola mundo.", "Adiós."]


def test_parse_srt_rejects_files_without_valid_cues():
    with pytest.raises(SRTEssayError, match="válidos"):
        parse_srt("no es un subtítulo")


def test_paragraphs_wait_for_sentence_and_pause():
    cues = [
        Cue(1, 0, 1, "Esto continúa"),
        Cue(2, 1.1, 2, "en una oración."),
        Cue(3, 4, 5, "Este ya es otro tema."),
    ]
    assert make_paragraphs(cues) == ["Esto continúa en una oración.", "Este ya es otro tema."]


def test_chunking_never_splits_a_paragraph():
    paragraphs = ["a" * 400, "b" * 400, "c" * 400]
    assert chunk_paragraphs(paragraphs, 800) == [["a" * 400], ["b" * 400], ["c" * 400]]


def test_chunking_rejects_unsafe_tiny_limit():
    with pytest.raises(SRTEssayError, match="al menos 500"):
        chunk_paragraphs(["texto"], 10)


def test_broken_lowercase_lines_are_joined_before_translation_and_postprocessing():
    from srt_essay.core import postprocess_markdown

    source = "Primera línea que continúa,\n \t\n\tsegunda línea;\n\n tercera línea.\n\nNuevo párrafo."
    assert parse_plain_document(source) == ["Primera línea que continúa, segunda línea; tercera línea.", "Nuevo párrafo."]
    assert postprocess_markdown(source)[0] == "Primera línea que continúa, segunda línea; tercera línea.\n\nNuevo párrafo."


def test_broken_line_normalization_preserves_sentence_and_markdown_boundaries():
    from srt_essay.core import join_broken_prose_lines

    source = "Termina en punto.\ncontinúa separado.\n\n# Título\ntexto siguiente"
    assert join_broken_prose_lines(source) == source


def test_markdown_is_cleaned_to_plain_paragraphs_before_processing():
    source = "---\ntitle: Ejemplo\n---\n\n# Título\n\n**Texto** con [enlace](https://example.com).\n\n- Otro punto."
    assert parse_plain_document(source) == ["Título", "Texto con enlace.", "Otro punto."]


def test_postprocess_markdown_removes_only_adjacent_duplicate_prose():
    from srt_essay.core import postprocess_markdown

    cleaned, removed = postprocess_markdown("La misma línea.\nLa misma línea.\n\nPárrafo repetido.\n\nPárrafo repetido.\n\n- Ítem\n- Ítem")
    assert cleaned == "La misma línea.\n\nPárrafo repetido.\n\n- Ítem\n- Ítem"
    assert removed == 2


def test_input_paragraphs_accepts_txt_files():
    assert input_paragraphs(Path("entrada.txt"), "Primero.\n\nSegundo.") == ["Primero.", "Segundo."]


def test_default_prompt_includes_grammatical_agreement_correction():
    from srt_essay.core import DEFAULT_REWRITE_INSTRUCTIONS
    assert "género, número y persona gramatical" in DEFAULT_REWRITE_INSTRUCTIONS


def test_prompt_profiles_include_translations_and_persist_selected_profile(tmp_path):
    from srt_essay.web_server import JobStore

    store = JobStore()
    store.prompt_path = tmp_path / ".srt-essay-prompts.json"
    document = store.prompts()
    assert "traduccion-castellano-ensayo" in document["profiles"]
    german_profile = document["profiles"]["traduccion-aleman-espanol-transcripciones"]
    assert german_profile["label"] == "Traducción alemán - español a partir de transcripciones"
    assert "transcripción automática" in german_profile["rewrite_instructions"]

    saved = store.save_prompts({
        "profile_id": "prueba",
        "label": "Perfil de prueba",
        "rewrite_system_prompt": "Sistema",
        "rewrite_instructions": "Redactá fielmente.",
        "guide_instructions": "Guía factual.",
    })
    assert saved["active_profile"] == "prueba"
    selected_id, selected = store.prompt_profile("prueba")
    assert selected_id == "prueba"
    assert selected["label"] == "Perfil de prueba"


def test_audio_source_uses_clean_paragraphs_from_markdown_or_input():
    from srt_essay.web_server import Job, JobStore

    job = Job(id="job", name="entrada.txt", markdown="# Título\n\n**Texto** final.", cleaned_text="Entrada\n\nlimpia.")
    assert JobStore._audio_source(job, "markdown") == "Título\n\nTexto final."
    assert JobStore._audio_source(job, "input") == "Entrada\n\nlimpia."


def test_audio_only_job_cleans_input_without_ollama(tmp_path, monkeypatch):
    from srt_essay.web_server import Job, JobStore

    workspace = TemporaryDirectory(dir=tmp_path)
    root = Path(workspace.name)
    (root / "entrada.txt").write_text("Primero.\n\nSegundo.", encoding="utf-8")
    job = Job(id="job", name="entrada.txt", workspace=workspace)
    monkeypatch.setattr("srt_essay.web_server.generate_api_audio", lambda payload, directory: (root / "audio.wav", {"tts_used": "fake", "duration": 1.0}))
    (root / "audio.wav").write_bytes(b"RIFF")
    store = JobStore()
    store.generated_root = tmp_path / "trabajos-generados"
    monkeypatch.setattr("srt_essay.web_server.subprocess.run", lambda *args, **kwargs: None)
    store._run(job, {"audio_only": True, "audio_lang": "es"})
    assert job.status == "completed"
    assert job.cleaned_text == "Primero.\n\nSegundo."
    assert job.generated_dir and job.generated_dir.parent == store.generated_root
    assert job.output == job.generated_dir / "entrada.limpio.md"
    assert job.audio == job.generated_dir / "audio" / "audio.wav"
    assert job.audio.read_bytes() == b"RIFF"


def test_delete_local_audio_cache_removes_only_selected_rate(tmp_path):
    from srt_essay.web_server import JobStore

    (tmp_path / "documento.md").write_text("Texto.", encoding="utf-8")
    selected = tmp_path / "_work" / "audio" / "chapter-0001" / "rate_200"
    retained = tmp_path / "_work" / "audio" / "chapter-0001" / "rate_220"
    selected.mkdir(parents=True); retained.mkdir(parents=True)
    (selected / "0.wav").write_bytes(b"RIFF\x00\x00\x00\x00WAVE")
    (retained / "0.wav").write_bytes(b"RIFF\x00\x00\x00\x00WAVE")
    store = JobStore(); store.input_root = tmp_path

    assert store.delete_local_audio_cache("documento.md", 200) == {"fragments": 1, "directories": 1}
    assert not selected.exists()
    assert (retained / "0.wav").is_file()


def test_translated_markdown_is_persisted_instead_of_falling_back_to_input(tmp_path, monkeypatch):
    from srt_essay.web_server import Job, JobStore

    class FakePipeline:
        def __init__(self, *_args, **kwargs):
            self.on_markdown = kwargs["on_markdown"]
        def run(self, _source, output, _checkpoint):
            output.write_text("# Traducción\n\nTexto final.\n", encoding="utf-8")
            self.on_markdown("# Traducción\n\nTexto final.")
            return output

    workspace = TemporaryDirectory(dir=tmp_path)
    root = Path(workspace.name)
    (root / "entrada.md").write_text("Texto de entrada.", encoding="utf-8")
    job = Job(id="job", name="entrada.md", workspace=workspace)
    store = JobStore(); store.generated_root = tmp_path / "trabajos-generados"
    monkeypatch.setattr("srt_essay.web_server.SRTEssayPipeline", FakePipeline)
    monkeypatch.setattr("srt_essay.web_server.model_client", lambda *_args, **_kwargs: object())
    monkeypatch.setattr("srt_essay.web_server.subprocess.run", lambda *args, **kwargs: None)
    store._run(job, {"provider": "ollama", "model": "fake", "mode": "fast"})

    assert job.status == "completed"
    assert job.output and job.output.name == "entrada.essay.md"
    assert job.output.read_text(encoding="utf-8") == "# Traducción\n\nTexto final.\n"
    assert (job.generated_dir / "entrada.md").read_text(encoding="utf-8") == "Texto de entrada."


def test_quality_mode_emits_markdown_before_generating_later_guides():
    from srt_essay.core import GUIDE_SCHEMA, REWRITE_SCHEMA, SRTEssayPipeline

    class FakeClient:
        model = "fake"
        def verify_model(self): pass
        def chat_json(self, _system, prompt, schema):
            if schema == GUIDE_SCHEMA:
                events.append("guide")
                return {"guide": "guía"}
            events.append("rewrite")
            return {"markdown": prompt.split("Texto fuente que debés devolver corregido:\n", 1)[1].split("\n\nDevolvé", 1)[0]}

    events, previews = [], []
    with TemporaryDirectory() as directory:
        source = Path(directory) / "entrada.txt"
        source.write_text(f"{'a' * 490}.\n\n{'b' * 490}.", encoding="utf-8")
        SRTEssayPipeline(FakeClient(), mode="quality", chunk_size=500, on_markdown=previews.append).run(
            source, Path(directory) / "salida.md", Path(directory) / ".checkpoint.json"
        )
    assert events == ["guide", "rewrite", "guide", "rewrite"]
    assert len(previews) == 2
