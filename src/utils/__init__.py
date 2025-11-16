"""Utility modules for audio extraction and analysis."""

from .retry import (
    # Legacy utilities (for backward compatibility)
    RetryConfig,
    RetryExhaustedError,
    calculate_delay,
    is_retriable_exception,
    retry_async,
    retry_on_network_error_async,
    retry_sync,
    # New tenacity-based decorators (recommended for new code)
    retry_on_network_error,
    retry_on_rate_limit,
    retry_on_transient_error,
    retry_ffmpeg_operation,
    create_custom_retry,
    log_retry_attempt,
    # Configuration constants
    DEFAULT_MAX_NETWORK_ATTEMPTS,
    DEFAULT_MAX_RATE_LIMIT_ATTEMPTS,
    FFMPEG_MAX_ATTEMPTS,
    PROVIDER_MAX_ATTEMPTS,
    PERMANENT_EXCEPTIONS,
)

__all__ = [
    # Legacy utilities (for backward compatibility)
    "RetryConfig",
    "RetryExhaustedError",
    "calculate_delay",
    "is_retriable_exception",
    "retry_async",
    "retry_on_network_error_async",
    "retry_sync",
    # New tenacity-based decorators (recommended for new code)
    "retry_on_network_error",
    "retry_on_rate_limit",
    "retry_on_transient_error",
    "retry_ffmpeg_operation",
    "create_custom_retry",
    "log_retry_attempt",
    # Configuration constants
    "DEFAULT_MAX_NETWORK_ATTEMPTS",
    "DEFAULT_MAX_RATE_LIMIT_ATTEMPTS",
    "FFMPEG_MAX_ATTEMPTS",
    "PROVIDER_MAX_ATTEMPTS",
    "PERMANENT_EXCEPTIONS",
]
