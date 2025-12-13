"""Parakeet dependency management and lazy imports."""

from __future__ import annotations

from src.utils.logger import get_logger

logger = get_logger(__name__)

# PyTorch availability
TORCH_AVAILABLE: bool
torch = None

try:
    import torch as _torch

    torch = _torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    logger.warning("PyTorch not available. GPU features will be disabled.")

# NeMo availability (lazy loaded)
nemo_asr = None
NEMO_AVAILABLE: bool | None = None


def _ensure_nemo() -> bool:
    """Ensure NeMo is available for model loading."""
    global NEMO_AVAILABLE, nemo_asr
    if NEMO_AVAILABLE is not None:
        return NEMO_AVAILABLE
    try:
        import nemo.collections.asr as _nemo_asr

        nemo_asr = _nemo_asr
        NEMO_AVAILABLE = True
    except Exception:
        NEMO_AVAILABLE = False
        logger.warning("NeMo toolkit not available. Parakeet features will be disabled.")
    return NEMO_AVAILABLE


# Audio processing libraries
AUDIO_LIBS_AVAILABLE: bool
librosa = None
sf = None

try:
    import librosa as _librosa
    import soundfile as _sf

    librosa = _librosa
    sf = _sf
    AUDIO_LIBS_AVAILABLE = True
except ImportError:
    AUDIO_LIBS_AVAILABLE = False
    logger.warning("Audio processing libraries (librosa, soundfile) not available")


__all__ = [
    "AUDIO_LIBS_AVAILABLE",
    "NEMO_AVAILABLE",
    "TORCH_AVAILABLE",
    "_ensure_nemo",
    "librosa",
    "nemo_asr",
    "sf",
    "torch",
]
