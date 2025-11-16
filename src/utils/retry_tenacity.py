"""Retry utilities using tenacity library.

This module provides reusable retry decorators for different failure scenarios:
- Network operations with exponential backoff and jitter
- API calls with rate limit awareness
- FFmpeg operations with minimal retry
- Provider calls with transient error handling

Based on best practices from:
- AWS: Timeouts, Retries, and Backoff with Jitter
- OpenAI: How to Handle Rate Limits
- Tenacity documentation

Example Usage:
    ```python
    from src.utils.retry import retry_on_network_error, retry_on_rate_limit
    from src.exceptions import ProviderTimeoutError, ProviderRateLimitError

    @retry_on_network_error(max_attempts=3)
    async def fetch_transcription(url: str):
        response = await client.get(url)
        if response.status_code >= 500:
            raise ProviderTimeoutError("Service unavailable")
        return response.json()

    @retry_on_rate_limit(max_wait=60)
    def call_api_with_limit():
        response = api_client.request()
        if response.status_code == 429:
            retry_after = response.headers.get('Retry-After', 5)
            raise ProviderRateLimitError(f"Rate limited, retry after {retry_after}s")
        return response
    ```
"""

from __future__ import annotations

import logging
from typing import Callable, TypeVar, Any

from tenacity import (
    retry,
    stop_after_attempt,
    stop_after_delay,
    wait_exponential,
    wait_exponential_jitter,
    wait_fixed,
    retry_if_exception_type,
    retry_if_not_exception_type,
    before_sleep_log,
    RetryCallState,
)

from src.exceptions import (
    ProviderTimeoutError,
    ProviderRateLimitError,
    ProviderAuthenticationError,
    ValidationError,
    AudioFileCorruptedError,
)

logger = logging.getLogger(__name__)

# Type variable for generic retry decorators
T = TypeVar("T")

# === Configuration Constants ===

# Network retry configuration
DEFAULT_MAX_NETWORK_ATTEMPTS = 3
DEFAULT_MAX_NETWORK_DELAY = 120  # seconds
NETWORK_INITIAL_WAIT = 1  # seconds
NETWORK_MAX_WAIT = 30  # seconds

# Rate limit retry configuration
DEFAULT_MAX_RATE_LIMIT_ATTEMPTS = 5
DEFAULT_MAX_RATE_LIMIT_WAIT = 60  # seconds
RATE_LIMIT_INITIAL_WAIT = 5  # seconds
RATE_LIMIT_MAX_WAIT = 60  # seconds

# FFmpeg retry configuration (minimal - FFmpeg is deterministic)
FFMPEG_MAX_ATTEMPTS = 2
FFMPEG_WAIT = 1  # seconds

# Provider retry configuration
PROVIDER_MAX_ATTEMPTS = 3
PROVIDER_INITIAL_WAIT = 1
PROVIDER_MAX_WAIT = 30

# === Permanent Exception Types (Don't Retry) ===

PERMANENT_EXCEPTIONS = (
    ProviderAuthenticationError,  # Invalid credentials
    ValidationError,  # Bad request data
    AudioFileCorruptedError,  # Corrupted input file
    PermissionError,  # Access denied
    FileNotFoundError,  # Resource doesn't exist
    ValueError,  # Invalid value
)


# === Retry Decorators ===


def retry_on_network_error(
    max_attempts: int = DEFAULT_MAX_NETWORK_ATTEMPTS,
    max_delay: int = DEFAULT_MAX_NETWORK_DELAY,
    exceptions: tuple[type[Exception], ...] = (ProviderTimeoutError,),
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Retry decorator for network operations with exponential backoff and jitter.

    Uses exponential backoff with full jitter to prevent synchronized retry storms.
    Recommended for transient network errors, service overloads, and connection issues.

    Args:
        max_attempts: Maximum number of retry attempts (default: 3)
        max_delay: Maximum total delay in seconds (default: 120)
        exceptions: Tuple of exception types to retry on (default: ProviderTimeoutError)

    Returns:
        Decorator function that applies retry logic

    Example:
        ```python
        @retry_on_network_error(max_attempts=5)
        async def fetch_data(url: str):
            response = await http_client.get(url)
            if response.status >= 500:
                raise ProviderTimeoutError(f"Server error: {response.status}")
            return response.json()
        ```

    Best Practices:
        - Use for transient network failures (timeouts, connection errors)
        - Don't use for client errors (4xx) - those are permanent
        - Combine with circuit breaker for cascading failure protection
    """
    return retry(
        retry=retry_if_exception_type(exceptions),
        wait=wait_exponential_jitter(
            initial=NETWORK_INITIAL_WAIT,
            max=NETWORK_MAX_WAIT,
        ),
        stop=stop_after_attempt(max_attempts) | stop_after_delay(max_delay),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )


def retry_on_rate_limit(
    max_attempts: int = DEFAULT_MAX_RATE_LIMIT_ATTEMPTS,
    max_wait: int = DEFAULT_MAX_RATE_LIMIT_WAIT,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Retry decorator for API calls with rate limit awareness.

    Uses exponential backoff with jitter. If the exception contains a `retry_after`
    attribute, it will be respected for the first retry attempt.

    Args:
        max_attempts: Maximum number of retry attempts (default: 5)
        max_wait: Maximum wait time per retry in seconds (default: 60)

    Returns:
        Decorator function that applies retry logic

    Example:
        ```python
        @retry_on_rate_limit(max_attempts=5)
        def call_api():
            response = api_client.request()
            if response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', 5))
                error = ProviderRateLimitError("Rate limit exceeded")
                error.retry_after = retry_after
                raise error
            return response
        ```

    Best Practices:
        - Set retry_after attribute on ProviderRateLimitError when available
        - Use reasonable max_wait to avoid blocking for too long
        - Monitor rate limit usage to optimize request patterns
    """
    return retry(
        retry=retry_if_exception_type(ProviderRateLimitError),
        wait=wait_exponential_jitter(
            initial=RATE_LIMIT_INITIAL_WAIT,
            max=RATE_LIMIT_MAX_WAIT,
        ),
        stop=stop_after_attempt(max_attempts),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )


def retry_on_transient_error(
    max_attempts: int = PROVIDER_MAX_ATTEMPTS,
    exceptions: tuple[type[Exception], ...] = (ProviderTimeoutError, ProviderRateLimitError),
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Retry decorator for transient errors while failing fast on permanent errors.

    This decorator retries only on specified transient exceptions and immediately
    fails on permanent errors (authentication, validation, file not found, etc.).

    Args:
        max_attempts: Maximum number of retry attempts (default: 3)
        exceptions: Tuple of transient exception types to retry on

    Returns:
        Decorator function that applies retry logic

    Example:
        ```python
        from src.exceptions import ProviderAPIError

        @retry_on_transient_error(
            max_attempts=3,
            exceptions=(ProviderTimeoutError, ProviderAPIError)
        )
        async def transcribe_audio(file_path: Path):
            result = await provider.transcribe(file_path)
            return result
        ```

    Best Practices:
        - Use for provider API calls where you need to distinguish errors
        - Don't retry on authentication or validation errors
        - Combine with circuit breaker for better resilience
    """
    return retry(
        retry=retry_if_exception_type(exceptions)
        & retry_if_not_exception_type(PERMANENT_EXCEPTIONS),
        wait=wait_exponential_jitter(
            initial=PROVIDER_INITIAL_WAIT,
            max=PROVIDER_MAX_WAIT,
        ),
        stop=stop_after_attempt(max_attempts),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )


def retry_ffmpeg_operation(
    max_attempts: int = FFMPEG_MAX_ATTEMPTS,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Retry decorator for FFmpeg operations with minimal retry.

    FFmpeg is largely deterministic, so we only retry once to handle
    transient I/O issues. Corrupted files and invalid parameters won't
    benefit from retries.

    Args:
        max_attempts: Maximum number of retry attempts (default: 2)

    Returns:
        Decorator function that applies retry logic

    Example:
        ```python
        from src.exceptions import FFmpegExecutionError

        @retry_ffmpeg_operation(max_attempts=2)
        def extract_audio(input_path: Path, output_path: Path):
            result = subprocess.run(
                ["ffmpeg", "-i", str(input_path), str(output_path)],
                capture_output=True,
                check=True
            )
            if result.returncode != 0:
                raise FFmpegExecutionError("Extraction failed")
            return output_path
        ```

    Best Practices:
        - Use only for transient I/O issues (disk full, temp file conflicts)
        - Don't retry corrupted files - they won't get better
        - Keep max_attempts low (2 is usually sufficient)
    """
    from src.exceptions import FFmpegExecutionError, AudioFileCorruptedError

    return retry(
        retry=retry_if_exception_type(FFmpegExecutionError)
        & retry_if_not_exception_type(AudioFileCorruptedError),
        wait=wait_fixed(FFMPEG_WAIT),
        stop=stop_after_attempt(max_attempts),
        before_sleep=before_sleep_log(logger, logging.INFO),
        reraise=True,
    )


def create_custom_retry(
    exceptions: tuple[type[Exception], ...],
    max_attempts: int = 3,
    initial_wait: float = 1.0,
    max_wait: float = 30.0,
    use_jitter: bool = True,
    exclude_exceptions: tuple[type[Exception], ...] = (),
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Create a custom retry decorator with specific configuration.

    This is a flexible factory function for creating custom retry decorators
    when the predefined ones don't fit your use case.

    Args:
        exceptions: Tuple of exception types to retry on
        max_attempts: Maximum number of retry attempts (default: 3)
        initial_wait: Initial wait time in seconds (default: 1.0)
        max_wait: Maximum wait time in seconds (default: 30.0)
        use_jitter: Whether to use jitter in exponential backoff (default: True)
        exclude_exceptions: Exceptions to never retry (default: empty)

    Returns:
        Decorator function that applies retry logic

    Example:
        ```python
        custom_retry = create_custom_retry(
            exceptions=(TimeoutError, ConnectionError),
            max_attempts=5,
            initial_wait=2.0,
            max_wait=60.0,
            exclude_exceptions=(ValueError,)
        )

        @custom_retry
        def my_operation():
            # Your code here
            pass
        ```

    Best Practices:
        - Use predefined decorators when possible (more readable)
        - Always exclude permanent errors (auth, validation)
        - Enable jitter for distributed systems
        - Document why custom configuration is needed
    """
    # Build retry condition
    retry_condition = retry_if_exception_type(exceptions)
    if exclude_exceptions:
        retry_condition = retry_condition & retry_if_not_exception_type(exclude_exceptions)

    # Choose wait strategy
    if use_jitter:
        wait_strategy = wait_exponential_jitter(initial=initial_wait, max=max_wait)
    else:
        wait_strategy = wait_exponential(multiplier=initial_wait, max=max_wait)

    return retry(
        retry=retry_condition,
        wait=wait_strategy,
        stop=stop_after_attempt(max_attempts),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )


# === Utility Functions ===


def log_retry_attempt(retry_state: RetryCallState) -> None:
    """Log retry attempt with context information.

    This can be used as a custom callback for retry decorators to provide
    more detailed logging about retry attempts.

    Args:
        retry_state: Tenacity retry state object

    Example:
        ```python
        @retry(
            retry=retry_if_exception_type(ProviderTimeoutError),
            stop=stop_after_attempt(3),
            before_sleep=log_retry_attempt
        )
        def my_function():
            pass
        ```
    """
    exception = retry_state.outcome.exception() if retry_state.outcome else None
    logger.warning(
        f"Retry attempt {retry_state.attempt_number} after "
        f"{retry_state.seconds_since_start:.2f}s due to {type(exception).__name__}: {exception}"
    )


__all__ = [
    # Retry decorators
    "retry_on_network_error",
    "retry_on_rate_limit",
    "retry_on_transient_error",
    "retry_ffmpeg_operation",
    "create_custom_retry",
    # Utility functions
    "log_retry_attempt",
    # Configuration constants
    "DEFAULT_MAX_NETWORK_ATTEMPTS",
    "DEFAULT_MAX_RATE_LIMIT_ATTEMPTS",
    "FFMPEG_MAX_ATTEMPTS",
    "PROVIDER_MAX_ATTEMPTS",
    "PERMANENT_EXCEPTIONS",
]
