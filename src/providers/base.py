"""Base class for transcription providers.

Provides async/sync transcription interfaces with optional circuit breaker
for production environments. Circuit breaker disabled by default for CLI use.
"""

from __future__ import annotations

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from threading import Lock
from typing import TYPE_CHECKING, Any, Awaitable, TypeVar

T = TypeVar("T")

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from ..models.transcription import TranscriptionResult

from ..utils.retry import RetryConfig, retry_async

logger = logging.getLogger(__name__)


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

    def circuit_breaker_call(self, func: Callable[..., T], *args: object, **kwargs: object) -> T:
        """Execute a function with circuit breaker protection.

        Args:
            func: Function to execute
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
            result = func(*args, **kwargs)
            self._record_success()
            return result
        except Exception as e:
            self._record_failure(e)
            raise

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

    def get_circuit_state(self) -> dict[str, str | int | float]:
        """Get current circuit breaker state information.

        Returns:
            Dictionary containing:
                - state (str): Current circuit state ('closed' or 'open')
                - failure_count (int): Number of consecutive failures recorded
                - failure_threshold (int): Threshold before circuit opens
                - last_failure_time (float): Timestamp of most recent failure
                - recovery_timeout (float): Seconds to wait before attempting recovery
                - time_until_retry (float): Seconds until next retry attempt (0 if not open)
        """
        with self._lock:
            return {
                "state": "open" if self._is_open else "closed",
                "failure_count": self._failure_count,
                "failure_threshold": self._circuit_config.failure_threshold,
                "last_failure_time": self._last_failure_time,
                "recovery_timeout": self._circuit_config.recovery_timeout,
                "time_until_retry": (
                    max(
                        0,
                        self._last_failure_time
                        + self._circuit_config.recovery_timeout
                        - time.time(),
                    )
                    if self._is_open
                    else 0
                ),
            }


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
        max_attempts=3, base_delay=1.0, exponential_base=2, max_delay=30.0, jitter=True
    )

    DEFAULT_CIRCUIT_CONFIG = CircuitBreakerConfig(
        failure_threshold=5,
        recovery_timeout=60.0,
    )

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
        self, audio_file_path: Path, language: str = "en"
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
        async def _transcribe_with_retry() -> TranscriptionResult:
            return await self._transcribe_impl(audio_file_path, language)

        # Let exceptions propagate - circuit breaker and retry handle retries
        return await self.circuit_breaker_call_async(_transcribe_with_retry)

    def transcribe(self, audio_file_path: Path, language: str = "en") -> TranscriptionResult | None:
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
        try:
            # Check if there's a running event loop
            asyncio.get_running_loop()
            # We're in async context - run in thread pool to avoid conflict
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run, self.transcribe_async(audio_file_path, language)
                )
                return future.result(timeout=300)  # 5 min timeout for transcription
        except RuntimeError:
            # No running loop - safe to use asyncio.run()
            return asyncio.run(self.transcribe_async(audio_file_path, language))

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
                return future.result(timeout=30)  # 30s timeout for health check
        except RuntimeError:
            # No running loop - safe to use asyncio.run()
            return asyncio.run(self.health_check_async())

    def supports_feature(self, feature: str) -> bool:
        """Check if provider supports a specific feature.

        Args:
            feature: Feature name to check

        Returns:
            True if feature is supported, False otherwise
        """
        return feature in self.get_supported_features()

    def get_retry_config(self) -> RetryConfig:
        """Get retry configuration for this provider.

        Returns:
            RetryConfig instance
        """
        return self._retry_config

    def update_retry_config(self, config: RetryConfig) -> None:
        """Update retry configuration for this provider.

        Args:
            config: New retry configuration
        """
        self._retry_config = config

    # ---------------------- Progress Helper ----------------------
    def _report_progress(self, callback: Callable[[int, int], None] | None, completed: int, total: int) -> None:
        """Helper to safely report progress if a callback is provided.

        This method wraps the progress callback in exception handling to ensure
        that errors in user-provided callbacks don't interrupt the transcription
        process. Any exceptions from the callback are silently ignored.

        Args:
            callback: Optional callable taking (completed, total) as arguments
            completed: Number of completed units (e.g., processed chunks)
            total: Total number of units to process
        """
        if callback:
            try:
                callback(completed, total)
            except Exception:
                # Never let a progress callback break the provider
                pass
