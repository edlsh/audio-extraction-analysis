"""Test transcription provider for offline testing."""

from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

from src.utils.logger import get_logger

from ..models.transcription import TranscriptionResult, TranscriptionUtterance
from .base import BaseTranscriptionProvider, HealthCheckResult, ProviderMeta

if TYPE_CHECKING:
    from ..utils.retry import RetryConfig

logger = get_logger(__name__)


@dataclass
class TestProviderConfig:
    """Configuration for test provider behavior."""

    transcript_text: str = (
        "This is a test transcription. "
        "The quick brown fox jumps over the lazy dog. "
        "This text is generated for testing purposes only."
    )
    confidence: float = 0.95
    language: str = "en"
    duration_seconds: float = 15.0
    simulate_delay_seconds: float = 0.1
    fail_on_files: list[str] = field(default_factory=list)
    error_message: str = "Simulated test provider error"
    include_utterances: bool = True
    include_speakers: bool = True


class TestTranscriptionProvider(BaseTranscriptionProvider):
    """Test provider for offline/no-network testing."""

    META: ClassVar[ProviderMeta | None] = ProviderMeta(
        name="Test Provider",
        provider_key="test",
        supported_features=["testing", "offline", "timestamps", "basic"],
        is_local=True,
    )

    def __init__(
        self,
        config: TestProviderConfig | None = None,
        api_key: str | None = None,
        retry_config: RetryConfig | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(api_key=api_key, retry_config=retry_config)
        self.config = config or TestProviderConfig()

    def validate_configuration(self) -> bool:
        return True

    def get_provider_name(self) -> str:
        return "test"

    def get_supported_features(self) -> list[str]:
        return ["basic", "timestamps", "testing", "offline"]

    async def _transcribe_impl(
        self, audio_file_path: Path, language: str = "en", **kwargs: Any
    ) -> TranscriptionResult:
        if not audio_file_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_file_path}")

        filename = audio_file_path.name
        if (
            filename in self.config.fail_on_files
            or str(audio_file_path) in self.config.fail_on_files
        ):
            raise RuntimeError(self.config.error_message)

        if self.config.simulate_delay_seconds > 0:
            await asyncio.sleep(self.config.simulate_delay_seconds)

        file_hash = self._compute_file_hash(audio_file_path)

        result_kwargs: dict[str, Any] = {
            "transcript": self.config.transcript_text,
            "audio_file": audio_file_path,
            "duration": self.config.duration_seconds,
            "metadata": {
                "file_hash": file_hash,
                "test_provider": True,
                "confidence": self.config.confidence,
                "language": language or self.config.language,
            },
        }

        if self.config.include_utterances:
            result_kwargs["utterances"] = self._generate_mock_utterances()

        if self.config.include_speakers:
            result_kwargs["speakers"] = self._generate_mock_speakers()

        result_kwargs["summary"] = "Test transcription summary for testing"

        return self._build_transcription_result(**result_kwargs)

    def _generate_mock_utterances(self) -> list[TranscriptionUtterance]:
        duration = self.config.duration_seconds
        return [
            TranscriptionUtterance(
                speaker=0,
                start=0.0,
                end=duration * 0.33,
                text="This is a test transcription.",
            ),
            TranscriptionUtterance(
                speaker=0,
                start=duration * 0.33,
                end=duration * 0.67,
                text="The quick brown fox jumps over the lazy dog.",
            ),
            TranscriptionUtterance(
                speaker=1,
                start=duration * 0.67,
                end=duration,
                text="This text is generated for testing purposes only.",
            ),
        ]

    def _generate_mock_speakers(self) -> list[dict[str, Any]]:
        return [
            {"id": 0, "total_time": self.config.duration_seconds * 0.67, "percentage": 66.7},
            {"id": 1, "total_time": self.config.duration_seconds * 0.33, "percentage": 33.3},
        ]

    def _compute_file_hash(self, path: Path) -> str:
        if not path.exists():
            return "nonexistent"
        try:
            h = hashlib.sha256()
            h.update(path.read_bytes()[:4096])
            return h.hexdigest()[:16]
        except OSError:
            return "unreadable"

    async def health_check_async(self) -> HealthCheckResult:
        async def _check() -> dict[str, Any]:
            return {
                "healthy": True,
                "status": "operational",
                "test_mode": True,
            }

        return await self._run_health_check(_check)


MockTranscriber = TestTranscriptionProvider
StubTranscriptionProvider = TestTranscriptionProvider
StubProviderConfig = TestProviderConfig


__all__ = [
    "MockTranscriber",
    "StubProviderConfig",
    "StubTranscriptionProvider",
    "TestProviderConfig",
    "TestTranscriptionProvider",
]
