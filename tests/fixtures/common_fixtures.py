"""
Test fixture factory for common test patterns.

Consolidates duplicate fixture creation patterns across test suite.
"""

from datetime import datetime
from pathlib import Path
from typing import Any

from src.models.transcription import (
    TranscriptionChapter,
    TranscriptionResult,
    TranscriptionSpeaker,
    TranscriptionUtterance,
)


class ProviderTestFixtureFactory:
    """Factory for creating consistent test fixtures across tests."""

    @staticmethod
    def create_mock_result(
        transcript: str = "Test transcript",
        duration: float = 10.0,
        audio_file: str = "test.mp3",
        provider_name: str = "mock",
        features: list[str] | None = None,
    ) -> TranscriptionResult:
        """Create a mock TranscriptionResult with common defaults.

        Replaces 29+ duplicate TranscriptionResult creation patterns.
        """
        return TranscriptionResult(
            transcript=transcript,
            duration=duration,
            generated_at=datetime.now(),
            audio_file=audio_file,
            provider_name=provider_name,
            provider_features=features or [],
        )

    @staticmethod
    def create_mock_utterance(
        text: str = "Hello world",
        speaker: int = 0,
        start: float = 0.0,
        end: float = 1.0,
    ) -> TranscriptionUtterance:
        """Create a mock TranscriptionUtterance with common defaults."""
        return TranscriptionUtterance(
            text=text,
            speaker=speaker,
            start=start,
            end=end,
        )

    @staticmethod
    def create_mock_speaker(
        id: int = 0,
        total_time: float = 10.0,
        percentage: float = 100.0,
    ) -> TranscriptionSpeaker:
        """Create a mock TranscriptionSpeaker with common defaults."""
        return TranscriptionSpeaker(
            id=id,
            total_time=total_time,
            percentage=percentage,
        )

    @staticmethod
    def create_mock_chapter(
        start_time: float = 0.0,
        end_time: float = 10.0,
        topics: list[str] | None = None,
        confidence_scores: list[float] | None = None,
    ) -> TranscriptionChapter:
        """Create a mock TranscriptionChapter with common defaults."""
        return TranscriptionChapter(
            start_time=start_time,
            end_time=end_time,
            topics=topics or [],
            confidence_scores=confidence_scores or [],
        )

    @staticmethod
    def create_mock_object(**attrs: Any) -> Any:
        """Create a mock object with specified attributes.

        Replaces 9+ duplicate mock response building patterns.
        """
        from unittest.mock import Mock

        mock_obj = Mock()
        for key, value in attrs.items():
            setattr(mock_obj, key, value)
        return mock_obj
