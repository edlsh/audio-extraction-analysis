"""Data models for the audio extraction analysis system.

This module provides data structures for representing transcription results,
including speaker diarization, chapter segmentation, and utterance tracking.
"""

from .transcription import (
    TranscriptionChapter,
    TranscriptionResult,
    TranscriptionSpeaker,
    TranscriptionUtterance,
)

__all__ = [
    "TranscriptionChapter",
    "TranscriptionResult",
    "TranscriptionSpeaker",
    "TranscriptionUtterance",
]
