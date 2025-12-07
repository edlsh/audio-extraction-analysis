"""Retry utilities using tenacity for robust API calls.

This module provides retry decorators and configuration using tenacity,
replacing the legacy custom implementation with a battle-tested library.
"""

from __future__ import annotations

from src.utils.logger import get_logger
import random
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, ParamSpec, TypeVar, cast

from tenacity import (
    AsyncRetrying,
    RetryError,
    Retrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

logger = get_logger(__name__)

P = ParamSpec("P")
R = TypeVar("R")
F = TypeVar("F", bound=Callable[..., Any])
AsyncF = TypeVar("AsyncF", bound=Callable[..., Any])

# Default retriable exceptions
DEFAULT_RETRIABLE_EXCEPTIONS: tuple[type[Exception], ...] = (
    ConnectionError,
    TimeoutError,
    OSError,
)


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""

    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True
    retriable_exceptions: tuple[type[Exception], ...] = field(
        default_factory=lambda: DEFAULT_RETRIABLE_EXCEPTIONS
    )

    def __post_init__(self) -> None:
        """Validate configuration parameters."""
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if self.base_delay < 0:
            raise ValueError("base_delay must be non-negative")
        if self.max_delay < self.base_delay:
            raise ValueError("max_delay must be >= base_delay")
        if self.exponential_base < 1:
            raise ValueError("exponential_base must be >= 1")
        if self.max_attempts > 10:
            raise ValueError("max_attempts should not exceed 10 for practical purposes")
        if self.max_delay > 300:
            raise ValueError("max_delay should not exceed 300 seconds for practical purposes")


class RetryExhaustedError(Exception):
    """Raised when all retry attempts have been exhausted."""

    def __init__(self, attempts: int, last_exception: Exception, total_delay: float = 0.0) -> None:
        self.attempts = attempts
        self.last_exception = last_exception
        self.total_delay = total_delay
        super().__init__(f"Retry exhausted after {attempts} attempts. Last error: {last_exception}")


def _build_tenacity_kwargs(config: RetryConfig) -> dict[str, Any]:
    """Build tenacity retry kwargs from RetryConfig."""
    kwargs: dict[str, Any] = {
        "stop": stop_after_attempt(config.max_attempts),
        "retry": retry_if_exception_type(config.retriable_exceptions),
        "reraise": False,  # Let RetryError be raised so we can wrap it
    }

    if config.jitter:
        kwargs["wait"] = wait_exponential_jitter(
            initial=config.base_delay,
            max=config.max_delay,
            exp_base=config.exponential_base,
        )
    else:
        from tenacity import wait_exponential

        kwargs["wait"] = wait_exponential(
            multiplier=config.base_delay,
            max=config.max_delay,
            exp_base=config.exponential_base,
        )

    return kwargs


def retry_sync(
    config: RetryConfig | None = None,
    max_attempts: int | None = None,
    base_delay: float | None = None,
    max_delay: float | None = None,
    exponential_base: float | None = None,
    jitter: bool | None = None,
    retriable_exceptions: tuple[type[Exception], ...] | None = None,
) -> Callable[[F], F]:
    """Decorator for synchronous functions with retry logic using tenacity."""
    cfg = config or RetryConfig(
        max_attempts=max_attempts or 3,
        base_delay=base_delay or 1.0,
        max_delay=max_delay or 60.0,
        exponential_base=exponential_base or 2.0,
        jitter=jitter if jitter is not None else True,
        retriable_exceptions=retriable_exceptions or DEFAULT_RETRIABLE_EXCEPTIONS,
    )

    def decorator(func: F) -> F:
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                for attempt in Retrying(**_build_tenacity_kwargs(cfg)):
                    with attempt:
                        return func(*args, **kwargs)
            except RetryError as e:
                raise RetryExhaustedError(cfg.max_attempts, e.last_attempt.exception()) from e

        return cast(F, wrapper)

    return decorator


def retry_async(
    config: RetryConfig | None = None,
    max_attempts: int | None = None,
    base_delay: float | None = None,
    max_delay: float | None = None,
    exponential_base: float | None = None,
    jitter: bool | None = None,
    retriable_exceptions: tuple[type[Exception], ...] | None = None,
) -> Callable[[AsyncF], AsyncF]:
    """Decorator for asynchronous functions with retry logic using tenacity."""
    cfg = config or RetryConfig(
        max_attempts=max_attempts or 3,
        base_delay=base_delay or 1.0,
        max_delay=max_delay or 60.0,
        exponential_base=exponential_base or 2.0,
        jitter=jitter if jitter is not None else True,
        retriable_exceptions=retriable_exceptions or DEFAULT_RETRIABLE_EXCEPTIONS,
    )

    def decorator(func: AsyncF) -> AsyncF:
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                async for attempt in AsyncRetrying(**_build_tenacity_kwargs(cfg)):
                    with attempt:
                        return await func(*args, **kwargs)
            except RetryError as e:
                raise RetryExhaustedError(cfg.max_attempts, e.last_attempt.exception()) from e

        return cast(AsyncF, wrapper)

    return decorator


def retry_on_network_error(
    max_attempts: int = 3, base_delay: float = 1.0, max_delay: float = 30.0
) -> Callable[[F], F]:
    """Convenience decorator for network-related errors."""
    return retry_sync(
        max_attempts=max_attempts,
        base_delay=base_delay,
        max_delay=max_delay,
        retriable_exceptions=(ConnectionError, TimeoutError, OSError),
    )


def retry_on_network_error_async(
    max_attempts: int = 3, base_delay: float = 1.0, max_delay: float = 30.0
) -> Callable[[AsyncF], AsyncF]:
    """Convenience decorator for network-related errors (async version)."""
    return retry_async(
        max_attempts=max_attempts,
        base_delay=base_delay,
        max_delay=max_delay,
        retriable_exceptions=(ConnectionError, TimeoutError, OSError),
    )


# Legacy compatibility functions
def calculate_delay(
    attempt: int, base_delay: float, max_delay: float, exponential_base: float, jitter: bool = True
) -> float:
    """Calculate delay for a given retry attempt (legacy compatibility)."""
    if attempt == 0:
        return 0.0
    base_backoff = min(base_delay * (exponential_base ** (attempt - 1)), max_delay)
    if jitter:
        jitter_range = base_backoff * 0.25
        base_backoff += random.uniform(-jitter_range, jitter_range)
    return max(0, min(base_backoff, max_delay))


def is_retriable_exception(
    exception: Exception, retriable_exceptions: tuple[type[Exception], ...]
) -> bool:
    """Check if an exception should trigger a retry (legacy compatibility)."""
    if hasattr(exception, "response") and hasattr(exception.response, "status_code"):
        status_code = exception.response.status_code
        if status_code in {408, 429, 500, 502, 503, 504}:
            return True
        if 400 <= status_code < 500:
            return False
    return isinstance(exception, retriable_exceptions)


class RetryBudget:
    """Manages retry budget across operations (legacy compatibility)."""

    def __init__(self, max_budget: int = 100, window_seconds: int = 60) -> None:
        import threading
        import time

        self.max_budget = max_budget
        self.window_seconds = window_seconds
        self.attempts: list[float] = []
        self._lock = threading.Lock()
        self._time = time

    def can_retry(self) -> bool:
        with self._lock:
            now = self._time.time()
            self.attempts = [t for t in self.attempts if now - t < self.window_seconds]
            if len(self.attempts) < self.max_budget:
                self.attempts.append(now)
                return True
            return False

    def get_budget_status(self) -> dict[str, Any]:
        with self._lock:
            now = self._time.time()
            self.attempts = [t for t in self.attempts if now - t < self.window_seconds]
            return {
                "used_budget": len(self.attempts),
                "max_budget": self.max_budget,
                "remaining_budget": self.max_budget - len(self.attempts),
                "window_seconds": self.window_seconds,
                "budget_available": len(self.attempts) < self.max_budget,
            }


__all__ = [
    "RetryBudget",
    "RetryConfig",
    "RetryExhaustedError",
    "calculate_delay",
    "is_retriable_exception",
    "retry_async",
    "retry_on_network_error",
    "retry_on_network_error_async",
    "retry_sync",
]
