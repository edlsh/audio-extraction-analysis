"""Provider test fixtures and mock implementations.

This module provides:
- Mock provider implementations for testing
- Test audio fixtures
- Provider test helpers
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


class MockTranscriptionProvider:
    """Mock transcription provider for testing.

    This provider returns predefined mock responses based on
    file path patterns, enabling deterministic test behavior.
    """

    def __init__(
        self,
        api_key: str | None = None,
        mock_response: dict[str, Any] | None = None,
        mock_delay: float = 0.0,
    ) -> None:
        """Initialize mock provider.

        Args:
            api_key: API key (ignored in mock)
            mock_response: Predefined response to return
            mock_delay: Artificial delay in seconds
        """
        self.api_key = api_key
        self._mock_response = mock_response
        self._mock_delay = mock_delay

    async def transcribe(
        self,
        audio_file_path: Path,
        language: str = "en",
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Mock transcription with optional delay.

        Args:
            audio_file_path: Path to audio file (ignored in mock)
            language: Language code (ignored in mock)
            **kwargs: Additional parameters (ignored in mock)

        Returns:
            Mock transcription result
        """
        import asyncio

        if self._mock_delay > 0:
            await asyncio.sleep(self._mock_delay)

        if self._mock_response:
            return self._mock_response

        # Default mock response
        from .helpers import create_mock_transcription_result

        return create_mock_transcription_result(
            text=f"Mock transcription for {audio_file_path.name}",
            duration=5.0,
            language=language,
        )

    async def health_check(self) -> dict[str, Any]:
        """Mock health check.

        Returns:
            Mock health status
        """
        return {"status": "healthy", "provider": "mock"}


class FailingMockProvider(MockTranscriptionProvider):
    """Mock provider that always fails.

    Useful for testing error handling and retry logic.
    """

    def __init__(self, fail_on_nth_call: int = 1, error_type: str = "api_error") -> None:
        """Initialize failing mock provider.

        Args:
            fail_on_nth_call: Fail after this many calls
            error_type: Type of error to raise (api_error, timeout, rate_limit)
        """
        super().__init__()
        self._call_count = 0
        self._fail_on_nth_call = fail_on_nth_call
        self._error_type = error_type

    async def transcribe(self, audio_file_path: Path, **kwargs: Any) -> dict[str, Any]:
        """Mock transcription that fails after N calls.

        Args:
            audio_file_path: Path to audio file
            **kwargs: Additional parameters

        Raises:
            Exception: Based on error_type configuration
        """
        self._call_count += 1

        if self._call_count >= self._fail_on_nth_call:
            if self._error_type == "api_error":
                raise RuntimeError("Mock API error")
            elif self._error_type == "timeout":
                raise TimeoutError("Mock timeout")
            elif self._error_type == "rate_limit":
                raise RuntimeError("Rate limit exceeded")
            else:
                raise RuntimeError("Unknown error")

        return await super().transcribe(audio_file_path, **kwargs)


class SlowMockProvider(MockTranscriptionProvider):
    """Mock provider with artificial delay.

    Useful for testing timeout handling and progress indicators.
    """

    def __init__(self, delay_seconds: float = 5.0) -> None:
        """Initialize slow mock provider.

        Args:
            delay_seconds: Delay to add to each call
        """
        super().__init__(mock_delay=delay_seconds)


# Audio fixtures
TEST_AUDIO_FIXTURES = {
    "short_1s_wav": {
        "path": Path("tests/fixtures/audio/short_1s.wav"),
        "duration": 1.0,
        "size_bytes": 16000,
    },
    "medium_10s_mp3": {
        "path": Path("tests/fixtures/audio/medium_10s.mp3"),
        "duration": 10.0,
        "size_bytes": 320000,
    },
    "long_60s_wav": {
        "path": Path("tests/fixtures/audio/long_60s.wav"),
        "duration": 60.0,
        "size_bytes": 960000,
    },
}


def get_test_audio_fixture(name: str) -> dict[str, Any]:
    """Get test audio fixture by name.

    Args:
        name: Fixture name (short_1s_wav, medium_10s_mp3, long_60s_wav)

    Returns:
        Fixture dictionary with path, duration, size_bytes

    Raises:
        ValueError: If fixture name not found
    """
    if name not in TEST_AUDIO_FIXTURES:
        raise ValueError(f"Unknown fixture '{name}'. Available: {list(TEST_AUDIO_FIXTURES.keys())}")
    return TEST_AUDIO_FIXTURES[name]


def create_mock_provider_config(
    provider_name: str,
    mock_delay: float = 0.0,
    fail_after: int | None = None,
) -> dict[str, Any]:
    """Create mock provider configuration for testing.

    Args:
        provider_name: Name of provider to mock
        mock_delay: Artificial delay in seconds
        fail_after: Fail after this many calls (None for no failure)

    Returns:
        Configuration dictionary
    """
    config = {
        "provider_name": provider_name,
        "mock_delay": mock_delay,
    }

    if fail_after is not None:
        config["fail_after"] = fail_after
        config["error_type"] = "api_error"

    return config


__all__ = [
    "TEST_AUDIO_FIXTURES",
    "FailingMockProvider",
    "MockTranscriptionProvider",
    "SlowMockProvider",
    "create_mock_provider_config",
    "get_test_audio_fixture",
]
