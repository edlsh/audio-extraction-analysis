"""Parakeet model definitions and configurations."""

from __future__ import annotations

from typing import TypedDict


class ModelSpec(TypedDict):
    """Specification for a Parakeet model."""

    type: str
    accuracy: str
    speed: str
    memory: str
    languages: list[str]


PARAKEET_MODELS: dict[str, ModelSpec] = {
    "stt_en_conformer_ctc_large": {
        "type": "ctc",
        "accuracy": "high",
        "speed": "fast",
        "memory": "4GB",
        "languages": ["en"],
    },
    "stt_en_conformer_transducer_large": {
        "type": "rnnt",
        "accuracy": "highest",
        "speed": "medium",
        "memory": "6GB",
        "languages": ["en"],
    },
    "stt_en_fastconformer_ctc_large": {
        "type": "ctc",
        "accuracy": "medium",
        "speed": "fastest",
        "memory": "2GB",
        "languages": ["en"],
    },
}

__all__ = ["PARAKEET_MODELS", "ModelSpec"]
