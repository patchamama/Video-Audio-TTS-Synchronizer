"""CLI de srt_essay."""

from __future__ import annotations

import argparse
from pathlib import Path

from .core import DEFAULT_CHUNK_SIZE, DEFAULT_MODEL, DEFAULT_OLLAMA_URL, OllamaClient, SRTEssayError, SRTEssayPipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Convierte un SRT en prosa Markdown fiel usando Ollama.")
    parser.add_argument("srt_file", type=Path, nargs="?", help="Archivo .srt de entrada")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Modelo Ollama (default: {DEFAULT_MODEL})")
    parser.add_argument("--ollama-url", default=DEFAULT_OLLAMA_URL, help="URL base de Ollama")
    parser.add_argument("--mode", choices=("fast", "quality"), default="quality", help="fast: una pasada; quality: guía y redacción")
    parser.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK_SIZE, help="Máximo de caracteres fuente por bloque")
    parser.add_argument("--output", type=Path, help="Salida .md (default: <entrada>.essay.md)")
    parser.add_argument("--resume", action="store_true", help="Reanuda desde el checkpoint existente")
    parser.add_argument("--web", action="store_true", help="Inicia la interfaz web local")
    parser.add_argument("--port", type=int, default=8768, help="Puerto para --web (default: 8768)")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.web:
        from .web_server import start_web_ui
        start_web_ui(args.port)
        return 0
    if args.srt_file is None:
        build_parser().error("srt_file es obligatorio salvo que uses --web")
    source = args.srt_file
    if not source.is_file():
        print(f"Error: no existe el archivo SRT: {source}")
        return 2
    output = args.output or source.with_name(f"{source.stem}.essay.md")
    checkpoint = output.with_name(f".{output.stem}.checkpoint.json")
    if checkpoint.exists() and not args.resume:
        print(f"Error: existe un checkpoint en {checkpoint}. Usá --resume o eliminálo.")
        return 2
    try:
        pipeline = SRTEssayPipeline(
            OllamaClient(args.ollama_url, args.model), mode=args.mode, chunk_size=args.chunk_size,
            progress=print,
        )
        pipeline.run(source, output, checkpoint)
    except SRTEssayError as exc:
        print(f"Error: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
