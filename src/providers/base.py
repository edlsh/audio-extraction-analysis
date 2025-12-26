"""Base class for transcription providers.

Provides async/sync transcription interfaces with standardized error handling
and retry logic for production environments.
"""

from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod
from asyncio import timeout as asyncio_timeout
from collections.abc import Awaitable
from dataclasses import dataclass, field
from typing import Any, ClassVar, TypedDict, TypeVar

from src.utils.logger import get_logger

T = TypeVar("T")

from collections.abc import Callable
from pathlib import Path

from ..models.transcription import TranscriptionResult
from ..utils.async_bridge import run_async_in_sync
from ..utils.constants import RetryDefaults, Timeouts
from ..utils.retry import RetryConfig, retry_async

logger = get_logger(__name__)
_WAIT_FOR = asyncio.wait_for


class HealthCheckDetails(TypedDict, total=False):
    """Details returned in health check response."""

    provider: str
    error: str
    error_type: str
    api_accessible: bool
    authentication: str
    user_id: str


class HealthCheckResult(TypedDict):
    """Standardized health check response."""

    healthy: bool
    status: str
    response_time_ms: float
    details: HealthCheckDetails


@dataclass
class ProviderMeta:
    """Provider metadata for unified configuration and behavior.

    This dataclass centralizes provider-specific configuration that was
    previously duplicated across provider implementations.
    """

    name: str
    """Human-readable provider name (e.g., 'Deepgram Nova 3')"""

    provider_key: str
    """Short identifier for error messages (e.g., 'deepgram')"""

    supported_features: list[str] = field(default_factory=list)
    """List of features supported by this provider"""

    api_key_env: str | None = None
    """Config attribute name for API key (e.g., 'DEEPGRAM_API_KEY'), None for local providers"""

    api_key_min_length: int = 10
    """Minimum valid API key length for validation"""

    sdk_imports: list[str] = field(default_factory=list)
    """Module paths required for this provider (e.g., ['deepgram'])"""

    install_command: str | None = None
    """Install command for missing SDK (e.g., 'uv add deepgram-sdk')"""

    is_local: bool = False
    """True for local providers (Whisper, Parakeet) that don't need API keys"""

    estimated_speed_mb_per_sec: float = 1.5
    """Estimated processing speed in MB/second for progress estimation"""

    display_name: str | None = None
    """Human-friendly display name (falls back to name if None)"""

    def get_display_name(self) -> str:
        """Get display name, falling back to name."""
        return self.display_name or self.name


class BaseTranscriptionProvider(ABC):
    """Abstract base class for all transcription service providers.

    This class defines the common interface that all transcription providers
    must implement, ensuring consistency across different services like
    Deepgram, ElevenLabs, etc.

    Subclasses should define a META class variable with ProviderMeta to enable
    automatic configuration handling, or override the relevant methods manually.
    """

    # Provider metadata - subclasses should override with their specific config
    META: ClassVar[ProviderMeta | None] = None

    # Default configurations for all providers
    DEFAULT_RETRY_CONFIG = RetryConfig(
        max_attempts=RetryDefaults.MAX_ATTEMPTS,
        base_delay=RetryDefaults.BASE_DELAY,
        exponential_base=RetryDefaults.EXPONENTIAL_BASE,
        max_delay=RetryDefaults.NETWORK_MAX_DELAY,
        jitter=RetryDefaults.JITTER,
    )

    _DEFAULT_TIMEOUT_SECONDS = Timeouts.TRANSCRIPTION_DEFAULT

    def __init__(
        self,
        api_key: str | None = None,
        retry_config: RetryConfig | None = None,
    ) -> None:
        """Initialize the transcription provider."""
        self.api_key = api_key
        self._retry_config = retry_config or self.DEFAULT_RETRY_CONFIG
        self._transcribe_timeout = self._DEFAULT_TIMEOUT_SECONDS

    def _resolve_api_key(self) -> str | None:
        """Resolve API key from instance or config based on META.

        Returns:
            Resolved API key or None if not found/not applicable.
        """
        if self.api_key:
            return self.api_key
        if self.META and self.META.api_key_env:
            from ..config import get_config

            return getattr(get_config(), self.META.api_key_env, None)
        return None

    @abstractmethod
    async def _transcribe_impl(
        self, audio_file_path: Path, language: str = "en"
    ) -> TranscriptionResult | None:
        """Internal implementation of transcription.

        This method must be implemented by all provider subclasses.
        It should contain only the provider-specific transcription logic.
        Retry, timeout, and error handling are handled by the base class.

        Decorate this method with @provider_error_handler for automatic
        error mapping to ProviderAPIError, ValidationError, etc.

        Args:
            audio_file_path: Path to audio file to transcribe
            language: Language code (e.g., "en", "es", "fr")

        Returns:
            TranscriptionResult with transcript, utterances, etc.
            None if transcription fails (error already raised by decorator)

        Raises:
            ProviderAPIError: If API call fails (mapped by decorator)
            ValidationError: If input validation fails (mapped by decorator)
            FileNotFoundError: If audio file doesn't exist (mapped by decorator)
            PermissionError: If file is not accessible (mapped by decorator)
        """
        pass

    async def transcribe_async(
        self, audio_file_path: Path, language: str = "en", *, timeout: float | None = None
    ) -> TranscriptionResult | None:
        """Transcribe audio file asynchronously with retry."""

        @retry_async(config=self._retry_config)
        async def _transcribe_with_retry() -> TranscriptionResult | None:
            return await self._transcribe_impl(audio_file_path, language)

        effective_timeout = timeout if timeout is not None else self._transcribe_timeout
        async with asyncio_timeout(effective_timeout):
            return await _transcribe_with_retry()

    def transcribe(
        self, audio_file_path: Path, language: str = "en", *, timeout: float | None = None
    ) -> TranscriptionResult | None:
        """Transcribe audio file synchronously with retry."""
        effective_timeout = timeout if timeout is not None else self._transcribe_timeout
        return run_async_in_sync(
            self.transcribe_async(audio_file_path, language, timeout=effective_timeout),
            timeout=effective_timeout,
        )

    def validate_configuration(self) -> bool:
        """Validate that the provider is properly configured.

        Default implementation checks API key for cloud providers.
        Local providers MUST override this method to check dependencies.

        Raises:
            NotImplementedError: If this is a local provider that hasn't overridden validation
        """
        if self.META:
            if self.META.is_local:
                # Local providers must implement their own validation to check dependencies
                raise NotImplementedError(
                    f"Local provider {self.META.name} must implement validate_configuration() "
                    "to check for required dependencies (e.g., ffmpeg, model files)"
                )
            if self.META.api_key_env:
                key = self._resolve_api_key()
                return bool(key and len(key) >= self.META.api_key_min_length)
        return bool(self.api_key)

    def get_provider_name(self) -> str:
        """Get the name of this transcription provider."""
        if self.META:
            return self.META.name
        return self.__class__.__name__

    def get_supported_features(self) -> list[str]:
        """Get list of features supported by this provider."""
        if self.META:
            return self.META.supported_features
        return []

    def _build_health_response(
        self,
        healthy: bool,
        status: str,
        response_time_ms: float,
        **details: Any,
    ) -> HealthCheckResult:
        """Build a standardized health check response dictionary."""
        return {
            "healthy": healthy,
            "status": status,
            "response_time_ms": response_time_ms,
            "details": {"provider": self.get_provider_name(), **details},
        }

    async def _run_health_check(
        self, check_fn: Callable[[], Awaitable[dict[str, Any]]]
    ) -> HealthCheckResult:
        """Template method for health checks with standardized error handling.

        Wraps provider-specific health check logic with timing and error handling.

        Args:
            check_fn: Async function that performs provider-specific health check.
                      Should return dict with 'healthy', 'status', and optional details.

        Returns:
            Standardized health check response dict.
        """
        start_time = time.time()
        try:
            result = await check_fn()
            return self._build_health_response(
                healthy=result.pop("healthy", True),
                status=result.pop("status", "operational"),
                response_time_ms=(time.time() - start_time) * 1000,
                **result,
            )
        except ImportError:
            sdk_name = self.META.name if self.META else self.get_provider_name()
            return self._build_health_response(
                healthy=False,
                status="sdk_not_available",
                response_time_ms=(time.time() - start_time) * 1000,
                error=f"{sdk_name} SDK not installed",
            )
        except Exception as e:
            return self._build_health_response(
                healthy=False,
                status="error",
                response_time_ms=(time.time() - start_time) * 1000,
                error=str(e),
                error_type=type(e).__name__,
            )

    @abstractmethod
    async def health_check_async(self) -> HealthCheckResult:
        """Perform asynchronous health check for the provider."""
        pass

    def health_check(self) -> HealthCheckResult:
        """Perform synchronous health check for the provider."""
        return run_async_in_sync(self.health_check_async(), timeout=Timeouts.HEALTH_CHECK)

    def _build_transcription_result(
        self,
        transcript: str,
        audio_file: Path,
        duration: float | None = None,
        **kwargs: Any,
    ) -> TranscriptionResult:
        """Build a TranscriptionResult with common fields populated.

        Consolidates duplicate result construction pattern across providers.

        Args:
            transcript: Transcribed text
            audio_file: Audio file path
            duration: Audio duration in seconds
            **kwargs: Additional provider-specific fields

        Returns:
            TranscriptionResult with common fields populated
        """
        from datetime import datetime

        return TranscriptionResult(
            transcript=transcript,
            duration=duration,
            generated_at=datetime.now(),
            audio_file=str(audio_file),
            provider_name=self.get_provider_name(),
            provider_features=self.get_supported_features(),
            **kwargs,
        )

    def update_transcription_timeout(self, timeout_seconds: float) -> None:
        """Update per-call transcription timeout."""
        if timeout_seconds <= 0:
            raise ValueError("Transcription timeout must be positive")
        self._transcribe_timeout = timeout_seconds
