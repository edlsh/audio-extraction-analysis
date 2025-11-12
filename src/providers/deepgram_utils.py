"""Utilities for Deepgram provider: options, mimetypes, and client helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def detect_mimetype(path: Path) -> str:
    suffix = path.suffix.lower()
    mapping = {
        ".mp3": "audio/mp3",
        ".wav": "audio/wav",
        ".m4a": "audio/mp4",
        ".mp4": "audio/mp4",
        ".aac": "audio/aac",
        ".flac": "audio/flac",
        ".ogg": "audio/ogg",
        ".webm": "audio/webm",
    }
    return mapping.get(suffix, "audio/mp3")


def build_prerecorded_options(language: str) -> Any:
    from deepgram import PrerecordedOptions  # type: ignore

    return PrerecordedOptions(
        model="nova-3",
        smart_format=True,
        utterances=True,
        punctuate=True,
        paragraphs=True,
        diarize=True,
        summarize="v2",
        topics=True,
        intents=True,
        sentiment=True,
        language=language,
        detect_language=True,
        alternatives=1,
    )
