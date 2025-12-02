"""Base class for transcription providers.

Provides async/sync transcription interfaces with optional circuit breaker
for production environments. Circuit breaker disabled by default for CLI use.
"""

from __future__ import annotations

import asyncio
import atexit
import concurrent.futures
import logging
import time
from abc import ABC, abstractmethod
from asyncio import timeout as asyncio_timeout
from collections.abc import Awaitable
from dataclasses import dataclass
from threading import Lock
from typing import TYPE_CHECKING, Any, TypeVar

T = TypeVar("T")

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from ..models.transcription import TranscriptionResult

from ..utils.constants import Limits, RetryDefaults, Timeouts
from ..utils.retry import RetryConfig, retry_async

logger = logging.getLogger(__name__)
_WAIT_FOR = asyncio.wait_for


@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration (optional, disabled by default)."""

    enabled: bool = False  # Disabled by default for CLI use
    failure_threshold: int = 5
    recovery_timeout: float = 60.0


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
        """Execute an async function with circuit breaker protection.

        Args:
            func: Async function to execute
            *args: Positional arguments for function
            **kwargs: Keyword arguments for function

        Returns:
            Function result

        Raises:
            CircuitBreakerError: If circuit is open
            Exception: Any exception raised by the function
        """
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

    Combines two resilience patterns:
    - Retry logic: Handles transient failures with exponential backoff
    - Circuit breaker: Prevents overwhelming a failing service by failing fast

    The circuit breaker wraps the retry logic, so:
    1. Circuit checks if service is healthy (fails fast if open)
    2. Retry logic attempts operation with backoff on transient failures
    3. Circuit tracks overall success/failure to manage state transitions
    """

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
        """Initialize the transcription provider.

        Args:
            api_key: Optional API key for the service
            circuit_config: Circuit breaker configuration (uses DEFAULT_CIRCUIT_CONFIG if None)
            retry_config: Retry configuration (uses DEFAULT_RETRY_CONFIG if None)
        """
        self.api_key = api_key
        self._retry_config = retry_config or self.DEFAULT_RETRY_CONFIG
        self._transcribe_timeout = self._DEFAULT_TIMEOUT_SECONDS

        # Initialize circuit breaker with default config if not provided
        CircuitBreakerMixin.__init__(self, circuit_config or self.DEFAULT_CIRCUIT_CONFIG)

    @abstractmethod
    async def _transcribe_impl(
        self, audio_file_path: Path, language: str = "en"
    ) -> TranscriptionResult | None:
        """Internal implementation of transcription.

        This method should contain the actual transcription logic
        without retry or circuit breaker handling.

        Args:
            audio_file_path: Path to the audio file to transcribe
            language: Language code for transcription (e.g., 'en', 'es')

        Returns:
            TranscriptionResult object with all available features, or None if failed
        """
        pass

    async def transcribe_async(
        self, audio_file_path: Path, language: str = "en", *, timeout: float | None = None
    ) -> TranscriptionResult | None:
        """Transcribe audio file asynchronously with retry and circuit breaker.

        This method applies retry logic and circuit breaker protection.
        Exceptions from the provider implementation are allowed to propagate.

        Args:
            audio_file_path: Path to the audio file to transcribe
            language: Language code for transcription (e.g., 'en', 'es')

        Returns:
            TranscriptionResult object with all available features

        Raises:
            ValidationError: If audio file validation fails
            ProviderNotAvailableError: If provider SDK not installed
            ProviderAuthenticationError: If API key invalid
            ProviderRateLimitError: If rate limit exceeded
            ProviderTimeoutError: If request times out
            ProviderAPIError: If provider API fails
            CircuitBreakerError: If circuit breaker is open
        """

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
        """Transcribe audio file synchronously with retry and circuit breaker.

        This is a convenience wrapper around transcribe_async() for synchronous
        contexts. For async code, prefer using transcribe_async() directly to
        avoid blocking the event loop.

        Handles nested event loops by running async code in a thread pool when
        called from an async context.

        Args:
            audio_file_path: Path to the audio file to transcribe
            language: Language code for transcription (e.g., 'en', 'es')

        Returns:
            TranscriptionResult object with all available features

        Raises:
            ValidationError: If audio file validation fails
            ProviderNotAvailableError: If provider SDK not installed
            ProviderAuthenticationError: If API key invalid
            ProviderRateLimitError: If rate limit exceeded
            ProviderTimeoutError: If request times out
            ProviderAPIError: If provider API fails
            CircuitBreakerError: If circuit breaker is open
        """
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
            # No running loop - safe to use asyncio.run()
            return asyncio.run(_run())

    @abstractmethod
    def validate_configuration(self) -> bool:
        """Validate that the provider is properly configured.

        Returns:
            True if configuration is valid, False otherwise
        """
        pass

    @abstractmethod
    def get_provider_name(self) -> str:
        """Get the name of this transcription provider.

        Returns:
            Human-readable name of the provider (e.g., 'Deepgram Nova 3', 'ElevenLabs')
        """
        pass

    @abstractmethod
    def get_supported_features(self) -> list[str]:
        """Get list of features supported by this provider.

        Returns:
            List of feature names like 'speaker_diarization', 'topic_detection',
            'sentiment_analysis', 'timestamps', etc.
        """
        pass

    def _build_health_response(
        self,
        healthy: bool,
        status: str,
        response_time_ms: float,
        **details: Any,
    ) -> dict[str, Any]:
        """Build a standardized health check response dictionary.

        This helper ensures consistent health check response format across all
        providers. Subclasses should use this method in their health_check_async
        implementations.

        Args:
            healthy: Whether the provider is healthy and operational.
            status: Status string (e.g., 'operational', 'error', 'sdk_not_available').
            response_time_ms: Time taken for the health check in milliseconds.
            **details: Additional provider-specific details to include.

        Returns:
            Standardized health check response dictionary with keys:
            - healthy (bool)
            - status (str)
            - response_time_ms (float)
            - details (dict) including provider name and any additional details
        """
        return {
            "healthy": healthy,
            "status": status,
            "response_time_ms": response_time_ms,
            "details": {"provider": self.get_provider_name(), **details},
        }

    @abstractmethod
    async def health_check_async(self) -> dict[str, Any]:
        """Perform asynchronous health check for the provider.

        This should verify API connectivity, authentication, and service availability.

        Returns:
            Dictionary containing health check results:
            {
                "healthy": bool,
                "status": str,
                "response_time_ms": float,
                "details": dict
            }
        """
        pass

    def health_check(self) -> dict[str, Any]:
        """Perform synchronous health check for the provider.

        This is a convenience wrapper around health_check_async() for synchronous
        contexts. For async code, prefer using health_check_async() directly.

        Handles nested event loops by running async code in a thread pool when
        called from an async context.

        Returns:
            Dictionary containing health check results (see health_check_async for format)
        """
        try:
            # Check if there's a running event loop
            asyncio.get_running_loop()
            # We're in async context - run in thread pool to avoid conflict
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, self.health_check_async())
                return future.result(timeout=Timeouts.HEALTH_CHECK)
        except RuntimeError:
            # No running loop - safe to use asyncio.run()
            return asyncio.run(self.health_check_async())

    def update_transcription_timeout(self, timeout_seconds: float) -> None:
        """Update per-call transcription timeout."""
        if timeout_seconds <= 0:
            raise ValueError("Transcription timeout must be positive")
        self._transcribe_timeout = timeout_seconds
