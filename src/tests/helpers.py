"""Test helper utilities for provider and integration tests.

This module provides:
- Mock response generators for API tests
- Test file generators (audio files)
- Test data fixtures

Usage:
    from src.tests.helpers import create_mock_transcription_result

    result = create_mock_transcription_result(
        text="Hello world",
        duration=10.5,
    )
"""

from __future__ import annotations

import random
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


def create_mock_transcription_result(
    text: str = "Hello world",
    duration: float = 10.0,
    language: str = "en",
    word_count: int | None = None,
    speaker_count: int = 0,
) -> dict[str, object]:
    """Create a mock transcription result for testing.

    Args:
        text: Transcript text
        duration: Audio duration in seconds
        language: Language code
        word_count: Optional word count (calculated from text if not provided)
        speaker_count: Number of speakers

    Returns:
        Mock transcription result dictionary
    """
    if word_count is None:
        word_count = len(text.split())

    result = {
        "transcript": text,
        "duration": duration,
        "language": language,
        "word_count": word_count,
        "speaker_count": speaker_count,
        "utterances": [],
        "speakers": [],
        "chapters": [],
        "metadata": {
            "provider": "mock",
            "model": "test-model",
            "created_at": datetime.now().isoformat(),
        },
    }

    if speaker_count > 0:
        result["speakers"] = [
            {"id": f"speaker_{i}", "name": f"Speaker {i}", "duration": 0.0}
            for i in range(speaker_count)
        ]

    return result


def create_mock_utterance(
    text: str,
    start: float = 0.0,
    end: float = 1.0,
    speaker: str | None = None,
    confidence: float = 0.95,
) -> dict[str, object]:
    """Create a mock transcription utterance.

    Args:
        text: Utterance text
        start: Start time in seconds
        end: End time in seconds
        speaker: Optional speaker ID
        confidence: Confidence score

    Returns:
        Mock utterance dictionary
    """
    return {
        "text": text,
        "start": start,
        "end": end,
        "speaker": speaker,
        "confidence": confidence,
    }


def create_test_audio_file(
    duration_seconds: float = 1.0,
    sample_rate: int = 16000,
    channels: int = 1,
    format: str = "wav",
) -> Path:
    """Create a test audio file.

    This function generates silent audio using python's wave module.

    Args:
        duration_seconds: Duration in seconds
        sample_rate: Sample rate in Hz
        channels: Number of audio channels
        format: Audio format (wav)

    Returns:
        Path to created audio file
    """
    import wave

    num_samples = int(duration_seconds * sample_rate)
    num_bytes = num_samples * channels * 2  # 16-bit samples

    with tempfile.NamedTemporaryFile(suffix=f".{format}", delete=False, prefix="test_audio_") as f:
        with wave.open(f.name, "wb") as wav:
            wav.setnchannels(channels)
            wav.setsampwidth(2)  # 16-bit
            wav.setframerate(sample_rate)
            wav.writeframes(b"\\x00" * num_bytes)

        return Path(f.name)


def generate_test_data(
    count: int = 10,
    text_source: list[str] | None = None,
) -> list[dict[str, object]]:
    """Generate test transcription data.

    Args:
        count: Number of test items to generate
        text_source: List of text strings to use (random if not provided)

    Returns:
        List of mock transcription results
    """
    default_texts = [
        "Hello world",
        "This is a test",
        "Another sample text",
        "Testing audio transcription",
        "Sample utterance",
    ]

    source = text_source or default_texts

    return [
        create_mock_transcription_result(
            text=random.choice(source),
            duration=random.uniform(1.0, 30.0),
            word_count=random.randint(5, 50),
        )
        for _ in range(count)
    ]


@dataclass
class MockApiResponse:
    """Mock API response for testing.

    Attributes:
        status_code: HTTP status code
        json_data: Response data
        headers: Response headers
        delay: Artificial delay in seconds
    """

    status_code: int = 200
    json_data: dict[str, object] | None = None
    headers: dict[str, str] = field(default_factory=dict)
    delay: float = 0.0

    def apply_delay(self) -> None:
        """Apply artificial delay."""
        if self.delay > 0:
            time.sleep(self.delay)


def create_mock_api_response(
    transcript: str = "Mock transcript",
    duration: float = 10.0,
    status_code: int = 200,
) -> MockApiResponse:
    """Create a mock API response.

    Args:
        transcript: Transcript text
        duration: Audio duration
        status_code: HTTP status code

    Returns:
        MockApiResponse instance
    """
    return MockApiResponse(
        status_code=status_code,
        json_data=create_mock_transcription_result(transcript, duration),
    )


__all__ = [
    "MockApiResponse",
    "create_mock_api_response",
    "create_mock_transcription_result",
    "create_mock_utterance",
    "create_test_audio_file",
    "generate_test_data",
]
