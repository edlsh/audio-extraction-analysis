"""Adapter for shared media probing without static layer coupling.

This module intentionally resolves probing helpers at runtime so providers can
reuse the shared ffprobe cache implementation without importing from
``src.services`` at module import time.
"""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any


def probe_media_sync(path: Path, timeout: float = 30.0) -> Any:
    """Probe media metadata via shared ffmpeg_core implementation."""
    ffmpeg_core = importlib.import_module("src.services.ffmpeg_core")
    return ffmpeg_core.probe_media_sync(path, timeout)


def probe_media_async(path: Path, timeout: float = 30.0) -> Any:
    """Probe media metadata asynchronously via shared ffmpeg_core implementation."""
    ffmpeg_core = importlib.import_module("src.services.ffmpeg_core")
    return ffmpeg_core.probe_media_async(path, timeout)
