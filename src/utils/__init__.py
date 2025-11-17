"""Utility modules for audio extraction and analysis."""

from .retry import (
    # Configuration constants
    DEFAULT_MAX_NETWORK_ATTEMPTS,
    DEFAULT_MAX_RATE_LIMIT_ATTEMPTS,
    FFMPEG_MAX_ATTEMPTS,
    PERMANENT_EXCEPTIONS,
    PROVIDER_MAX_ATTEMPTS,
    # Legacy utilities (for backward compatibility)
    RetryConfig,
    RetryExhaustedError,
    calculate_delay,
    create_custom_retry,
    is_retriable_exception,
    log_retry_attempt,
    retry_async,
    retry_ffmpeg_operation,
    # New tenacity-based decorators (recommended for new code)
    retry_on_network_error,
    retry_on_network_error_async,
    retry_on_rate_limit,
    retry_on_transient_error,
    retry_sync,
)

__all__ = [
    # Configuration constants
    "DEFAULT_MAX_NETWORK_ATTEMPTS",
    "DEFAULT_MAX_RATE_LIMIT_ATTEMPTS",
    "FFMPEG_MAX_ATTEMPTS",
    "PERMANENT_EXCEPTIONS",
    "PROVIDER_MAX_ATTEMPTS",
    # Legacy utilities (for backward compatibility)
    "RetryConfig",
    "RetryExhaustedError",
    "calculate_delay",
    # New tenacity-based decorators (recommended for new code)
    "create_custom_retry",
    "is_retriable_exception",
    "log_retry_attempt",
    "retry_async",
    "retry_ffmpeg_operation",
    "retry_on_network_error",
    "retry_on_network_error_async",
    "retry_on_rate_limit",
    "retry_on_transient_error",
    "retry_sync",
]
