"""Mock transcription provider for testing."""

import asyncio
from pathlib import Path
from typing import Any

from src.utils.logger import get_logger

from ..models.transcription import TranscriptionResult, TranscriptionUtterance
from ..utils.retry import RetryConfig
from .base import BaseTranscriptionProvider, HealthCheckResult

logger = get_logger(__name__)


class MockTranscriber(BaseTranscriptionProvider):
    """Mock transcription provider for testing purposes.

    This provider simulates transcription without requiring external services.
    Useful for CI/CD and unit testing where real providers aren't available.
    """

    def __init__(
        self,
        api_key: str | None = None,
        retry_config: RetryConfig | None = None,
    ) -> None:
        """Initialize mock provider with optional configuration.

        Args:
            api_key: Ignored, included for interface compatibility
            retry_config: Retry configuration
        """
        super().__init__(api_key, retry_config)
        self.transcription_delay = 0.5  # Simulate processing time

    def validate_configuration(self) -> bool:
        """Mock provider is always valid."""
        return True

    def get_provider_name(self) -> str:
        """Return provider name."""
        return "mock"

    def get_supported_features(self) -> list[str]:
        """Return supported features for testing."""
        return ["basic", "timestamps", "test-mode"]

    async def _transcribe_impl(
        self, audio_file_path: Path, language: str = "en", **kwargs: Any
    ) -> TranscriptionResult:
        """Generate mock transcription result.

        Args:
            audio_file_path: Path to audio file (existence checked)
            language: Language code (ignored in mock)
            **kwargs: Additional arguments (ignored)

        Returns:
            Mock TranscriptionResult with test data

        Raises:
            FileNotFoundError: If audio file doesn't exist
        """
        # Validate file exists
        if not audio_file_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_file_path}")

        # Simulate processing time
        await asyncio.sleep(self.transcription_delay)

        # Generate mock transcription
        mock_text = (
            f"This is a mock transcription of {audio_file_path.name}. "
            "The quick brown fox jumps over the lazy dog. "
            "This text is generated for testing purposes only."
        )

        # Create mock utterances
        utterances = [
            TranscriptionUtterance(
                speaker="SPEAKER_00",
                start=0.0,
                end=5.0,
                text="This is a mock transcription.",
            ),
            TranscriptionUtterance(
                speaker="SPEAKER_00",
                start=5.0,
                end=10.0,
                text="The quick brown fox jumps over the lazy dog.",
            ),
            TranscriptionUtterance(
                speaker="SPEAKER_01",
                start=10.0,
                end=15.0,
                text="This text is generated for testing purposes only.",
            ),
        ]

        return self._build_transcription_result(
            transcript=mock_text,
            audio_file=audio_file_path,
            duration=15.0,
            summary="Mock transcription summary for testing",
            chapters=[
                {
                    "start_time": 0.0,
                    "end_time": 15.0,
                    "topics": ["mock", "testing"],
                    "confidence_scores": {"mock": 0.99, "testing": 0.95},
                }
            ],
            speakers=[
                {"id": "SPEAKER_00", "total_time": 10.0, "percentage": 66.7},
                {"id": "SPEAKER_01", "total_time": 5.0, "percentage": 33.3},
            ],
            utterances=utterances,
        )

    async def health_check_async(self) -> HealthCheckResult:
        """Mock health check always returns healthy."""

        async def _check() -> dict[str, Any]:
            return {
                "healthy": True,
                "status": "operational",
                "test_mode": True,
            }

        return await self._run_health_check(_check)
