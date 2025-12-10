"""Base class for transcription providers.

Provides async/sync transcription interfaces with optional circuit breaker
for production environments. Circuit breaker disabled by default for CLI use.
"""

from __future__ import annotations

import asyncio
import atexit
import concurrent.futures
import time
from abc import ABC, abstractmethod
from asyncio import timeout as asyncio_timeout
from collections.abc import Awaitable
from dataclasses import dataclass, field
from threading import Lock
from typing import TYPE_CHECKING, Any, ClassVar, TypeVar

from src.utils.logger import get_logger

T = TypeVar("T")

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from ..models.transcription import TranscriptionResult

from ..utils.constants import Limits, RetryDefaults, Timeouts
from ..utils.retry import RetryConfig, retry_async

logger = get_logger(__name__)
_WAIT_FOR = asyncio.wait_for


@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration (optional, disabled by default)."""

    enabled: bool = False  # Disabled by default for CLI use
    failure_threshold: int = 5
    recovery_timeout: float = 60.0


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


class CircuitBreakerError(Exception):
    """Raised when circuit breaker is open (too many failures)."""

    pass


class CircuitBreakerMixin:
    """Optional circuit breaker for providers (disabled by default)."""

    def __init__(self, circuit_config: CircuitBreakerConfig | None = None) -> None:
        self._circuit_config = circuit_config or CircuitBreakerConfig()
        self._failure_count = 0
        self._last_failure_time = 0.0
        self._is_open = False
        self._lock = Lock()

    def _record_success(self) -> None:
        """Reset failure count on success."""
        if not self._circuit_config.enabled:
            return
        with self._lock:
            self._failure_count = 0
            self._is_open = False

    def _record_failure(self, exception: Exception) -> None:
        """Track failures and open circuit if threshold exceeded."""
        if not self._circuit_config.enabled:
            return

        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()

            if self._failure_count >= self._circuit_config.failure_threshold:
                self._is_open = True
                logger.warning(f"Circuit breaker opened after {self._failure_count} failures")

    def _check_circuit_state(self) -> None:
        """Raise if circuit is open (unless recovery timeout passed)."""
        if not self._circuit_config.enabled:
            return

        with self._lock:
            if self._is_open:
                if time.time() - self._last_failure_time >= self._circuit_config.recovery_timeout:
                    self._is_open = False
                    logger.info("Circuit breaker reset, retrying")
                else:
                    raise CircuitBreakerError("Too many failures, circuit open")

    async def circuit_breaker_call_async(
        self, func: Callable[..., Awaitable[T]], *args: object, **kwargs: object
    ) -> T:
        """Execute an async function with circuit breaker protection."""
        self._check_circuit_state()

        try:
            result = await func(*args, **kwargs)
            self._record_success()
            return result
        except Exception as e:
            self._record_failure(e)
            raise


class BaseTranscriptionProvider(ABC, CircuitBreakerMixin):
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

    DEFAULT_CIRCUIT_CONFIG = CircuitBreakerConfig(
        failure_threshold=Limits.CIRCUIT_FAILURE_THRESHOLD,
        recovery_timeout=Limits.CIRCUIT_RECOVERY_TIMEOUT,
    )
    _SYNC_EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=Limits.DEFAULT_MAX_WORKERS)
    atexit.register(_SYNC_EXECUTOR.shutdown, wait=False)
    _DEFAULT_TIMEOUT_SECONDS = Timeouts.TRANSCRIPTION_DEFAULT

    def __init__(
        self,
        api_key: str | None = None,
        circuit_config: CircuitBreakerConfig | None = None,
        retry_config: RetryConfig | None = None,
    ) -> None:
        """Initialize the transcription provider."""
        self.api_key = api_key
        self._retry_config = retry_config or self.DEFAULT_RETRY_CONFIG
        self._transcribe_timeout = self._DEFAULT_TIMEOUT_SECONDS
        CircuitBreakerMixin.__init__(self, circuit_config or self.DEFAULT_CIRCUIT_CONFIG)

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
        """Internal implementation of transcription."""
        pass

    async def transcribe_async(
        self, audio_file_path: Path, language: str = "en", *, timeout: float | None = None
    ) -> TranscriptionResult | None:
        """Transcribe audio file asynchronously with retry and circuit breaker."""

        @retry_async(config=self._retry_config)
        async def _transcribe_with_retry() -> TranscriptionResult | None:
            return await self._transcribe_impl(audio_file_path, language)

        async def _execute() -> TranscriptionResult | None:
            return await self.circuit_breaker_call_async(_transcribe_with_retry)

        effective_timeout = timeout if timeout is not None else self._transcribe_timeout
        async with asyncio_timeout(effective_timeout):
            return await _execute()

    def transcribe(
        self, audio_file_path: Path, language: str = "en", *, timeout: float | None = None
    ) -> TranscriptionResult | None:
        """Transcribe audio file synchronously with retry and circuit breaker."""
        effective_timeout = timeout if timeout is not None else self._transcribe_timeout

        async def _run() -> TranscriptionResult | None:
            return await self.transcribe_async(audio_file_path, language, timeout=effective_timeout)

        try:
            asyncio.get_running_loop()

            def _runner() -> TranscriptionResult | None:
                return asyncio.run(_run())

            future = self._SYNC_EXECUTOR.submit(_runner)
            return future.result(timeout=effective_timeout)
        except RuntimeError:
            return asyncio.run(_run())

    def validate_configuration(self) -> bool:
        """Validate that the provider is properly configured.
        
        Default implementation checks API key for cloud providers.
        Local providers or those with custom validation should override.
        """
        if self.META:
            if self.META.is_local:
                return True  # Local providers override with dependency checks
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
    ) -> dict[str, Any]:
        """Build a standardized health check response dictionary."""
        return {
            "healthy": healthy,
            "status": status,
            "response_time_ms": response_time_ms,
            "details": {"provider": self.get_provider_name(), **details},
        }

    async def _run_health_check(
        self, check_fn: Callable[[], Awaitable[dict[str, Any]]]
    ) -> dict[str, Any]:
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
    async def health_check_async(self) -> dict[str, Any]:
        """Perform asynchronous health check for the provider."""
        pass

    def health_check(self) -> dict[str, Any]:
        """Perform synchronous health check for the provider."""
        try:
            asyncio.get_running_loop()
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, self.health_check_async())
                return future.result(timeout=Timeouts.HEALTH_CHECK)
        except RuntimeError:
            return asyncio.run(self.health_check_async())

    def update_transcription_timeout(self, timeout_seconds: float) -> None:
        """Update per-call transcription timeout."""
        if timeout_seconds <= 0:
            raise ValueError("Transcription timeout must be positive")
        self._transcribe_timeout = timeout_seconds
