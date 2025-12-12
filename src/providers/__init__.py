"""Transcription service providers.

Provider implementations are lazily loaded by the factory to avoid importing
heavyweight dependencies (torch, nemo) at module import time.

Available providers:
- deepgram: Deepgram Nova 3 cloud API
- elevenlabs: ElevenLabs cloud API
- whisper: OpenAI Whisper local model (requires torch)
- parakeet: NVIDIA NeMo Parakeet local model (requires nemo)
"""

# Only import essential components; providers are lazy-loaded by factory
from .base import (
    BaseTranscriptionProvider,
    CircuitBreakerConfig,
    CircuitBreakerError,
    CircuitBreakerMixin,
)
from .factory import TranscriptionProviderFactory
from .policy import (
    ProviderSelectionPolicy,
    TranscriptionPolicy,
)

__all__ = [
    "BaseTranscriptionProvider",
    "CircuitBreakerConfig",
    "CircuitBreakerError",
    "CircuitBreakerMixin",
    "ProviderSelectionPolicy",
    "TranscriptionPolicy",
    "TranscriptionProviderFactory",
]
