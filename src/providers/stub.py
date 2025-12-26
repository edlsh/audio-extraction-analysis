"""Stub transcription provider for testing without network access.

This provider returns predictable, deterministic responses for testing
pipelines end-to-end without requiring real API keys or network calls.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

from ..models.transcription import TranscriptionResult
from ..utils.retry import RetryConfig
from .base import BaseTranscriptionProvider, HealthCheckResult, ProviderMeta

if TYPE_CHECKING:
    pass


@dataclass
class StubProviderConfig:
    """Configuration for stub provider behavior."""

    transcript_text: str = "This is a stub transcription for testing purposes."
    confidence: float = 0.95
    language: str = "en"
    duration_seconds: float = 5.0
    simulate_delay_seconds: float = 0.0
    fail_on_files: list[str] = field(default_factory=list)
    error_message: str = "Simulated stub provider error"


class StubTranscriptionProvider(BaseTranscriptionProvider):
    """Stub provider for offline/no-network testing.

    Returns deterministic responses based on input file hash, enabling
    reproducible tests without external dependencies.
    """

    META: ClassVar[ProviderMeta] = ProviderMeta(
        name="Stub Provider",
        provider_key="stub",
        supported_features=["testing", "offline"],
        is_local=True,
    )

    def __init__(
        self,
        config: StubProviderConfig | None = None,
        api_key: str | None = None,
        retry_config: RetryConfig | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(api_key=api_key, retry_config=retry_config)
        self.config = config or StubProviderConfig()

    async def _transcribe_impl(
        self, audio_file_path: Path, language: str = "en"
    ) -> TranscriptionResult | None:
        """Return deterministic stub transcription."""
        import asyncio

        if self.config.simulate_delay_seconds > 0:
            await asyncio.sleep(self.config.simulate_delay_seconds)

        filename = audio_file_path.name
        if (
            filename in self.config.fail_on_files
            or str(audio_file_path) in self.config.fail_on_files
        ):
            raise RuntimeError(self.config.error_message)

        file_hash = self._compute_file_hash(audio_file_path)

        return self._build_transcription_result(
            transcript=self.config.transcript_text,
            audio_file=audio_file_path,
            duration=self.config.duration_seconds,
            metadata={
                "file_hash": file_hash,
                "stub_provider": True,
                "confidence": self.config.confidence,
                "language": language or self.config.language,
            },
        )

    def _compute_file_hash(self, path: Path) -> str:
        """Compute SHA-256 hash prefix for reproducibility tracking."""
        if not path.exists():
            return "nonexistent"
        h = hashlib.sha256()
        h.update(path.read_bytes()[:4096])
        return h.hexdigest()[:16]

    async def health_check_async(self) -> HealthCheckResult:
        """Stub health check always succeeds."""
        return await self._run_health_check(self._do_health_check)

    async def _do_health_check(self) -> dict[str, Any]:
        return {"healthy": True, "status": "operational"}

    def validate_configuration(self) -> bool:
        """Stub provider is always valid (no external deps)."""
        return True


__all__ = ["StubProviderConfig", "StubTranscriptionProvider"]
