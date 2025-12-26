"""Transcription service providers.

Provider implementations are lazily loaded by the factory to avoid importing
heavyweight dependencies (torch, nemo) at module import time. The factory uses
full module path strings (e.g., "src.providers.deepgram.DeepgramTranscriber")
and imports providers on first use via dynamic module loading.

Available providers:
- deepgram: Deepgram Nova 3 cloud API
- elevenlabs: ElevenLabs cloud API
- whisper: OpenAI Whisper local model (requires torch)
- parakeet: NVIDIA NeMo Parakeet local model (requires nemo)
"""

# Only import essential components; providers are lazy-loaded by factory
from .base import BaseTranscriptionProvider
from .factory import TranscriptionProviderFactory
from .policy import (
    ProviderSelectionPolicy,
    TranscriptionPolicy,
)

__all__ = [
    "BaseTranscriptionProvider",
    "ProviderSelectionPolicy",
    "TranscriptionPolicy",
    "TranscriptionProviderFactory",
]
