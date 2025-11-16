"""Compression helpers for cache value serialization."""

from __future__ import annotations

import json
import zlib


def compress_value(value: object) -> bytes:
    """Compress value using JSON + zlib.

    Attempts to serialize using a to_dict() method if available,
    otherwise falls back to JSON or string representation.
    """
    # Convert to dictionary if possible, otherwise to string/JSON
    if hasattr(value, "to_dict") and callable(value.to_dict):
        value_dict = {"type": type(value).__name__, "data": value.to_dict()}
    else:
        try:
            json.dumps(value)
            value_dict = {"type": type(value).__name__, "data": value}
        except (TypeError, ValueError):
            value_dict = {"type": "str", "data": str(value)}

    json_bytes = json.dumps(value_dict).encode("utf-8")
    return zlib.compress(json_bytes, level=6)


def decompress_value(data: bytes) -> object | None:
    """Decompress value using zlib + JSON with safe reconstruction."""
    try:
        raw = zlib.decompress(data)
        value_dict = json.loads(raw.decode("utf-8"))

        value_type = value_dict.get("type", "dict")
        value_data = value_dict.get("data")

        if value_type == "TranscriptionResult" and isinstance(value_data, dict):
            try:
                from ..models.transcription import TranscriptionResult
            except (ImportError, ValueError):
                try:
                    from src.models.transcription import TranscriptionResult
                except ImportError:
                    return value_data
            return TranscriptionResult.from_dict(value_data)
        elif value_type == "str":
            return str(value_data)
        else:
            # Return as object (dict, list, etc.)
            return (
                value_data
                if isinstance(value_data, (dict, list, str, int, float, bool, type(None)))
                else None
            )
    except Exception:
        # Caller will handle logging
        return None
