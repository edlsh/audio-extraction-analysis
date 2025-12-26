"""API client wrapper package.

This package provides standardized wrappers around provider SDK clients,
centralizing retry logic, timeout handling, and error processing.

Public API:
    - BaseAPIClient: Base class with shared retry/timeout/error handling
    - DeepgramAPIClient: Wrapper for Deepgram SDK
    - ElevenLabsAPIClient: Wrapper for ElevenLabs SDK
"""

from .base_client import BaseAPIClient
from .deepgram_client import DeepgramAPIClient
from .elevenlabs_client import ElevenLabsAPIClient

__all__ = [
    "BaseAPIClient",
    "DeepgramAPIClient",
    "ElevenLabsAPIClient",
]
