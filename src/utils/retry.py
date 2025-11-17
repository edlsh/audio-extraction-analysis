"""Unified retry utilities combining legacy and tenacity-based implementations.

This module provides both:
1. Legacy retry utilities (RetryConfig, retry_async, etc.) for backward compatibility
2. New tenacity-based retry decorators with exponential backoff and jitter

For new code, prefer the tenacity-based decorators (retry_on_network_error, etc.).
Legacy functions are maintained for compatibility with existing code.
"""

# Import legacy retry utilities for backward compatibility
from .retry_legacy import (
    RetryBudget,  # Import but not export in __all__
    RetryConfig,
    RetryExhaustedError,
    calculate_delay,
    is_retriable_exception,
    retry_async,
    retry_on_network_error_async,
    retry_sync,
)

# Import new tenacity-based retry decorators
from .retry_tenacity import (
    DEFAULT_MAX_NETWORK_ATTEMPTS,
    DEFAULT_MAX_RATE_LIMIT_ATTEMPTS,
    FFMPEG_MAX_ATTEMPTS,
    PERMANENT_EXCEPTIONS,
    PROVIDER_MAX_ATTEMPTS,
    create_custom_retry,
    log_retry_attempt,
    retry_ffmpeg_operation,
    retry_on_network_error,
    retry_on_rate_limit,
    retry_on_transient_error,
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
