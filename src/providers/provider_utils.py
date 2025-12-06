"""Provider configuration and error handling utilities."""

from __future__ import annotations

import logging
from functools import wraps
from pathlib import Path
from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

from ..config import get_config
from ..exceptions import (
    FileAccessError,
    ProviderAPIError,
    ProviderNotAvailableError,
    ValidationError,
)
from ..utils.retry import RetryConfig
from .base import CircuitBreakerConfig

logger = logging.getLogger(__name__)

T = TypeVar("T")


def get_default_configs(
    retry_config: RetryConfig | None = None,
    circuit_config: CircuitBreakerConfig | None = None,
) -> tuple[RetryConfig, CircuitBreakerConfig]:
    """Get retry and circuit breaker configs with defaults from global config."""
    config = get_config()

    if retry_config is None:
        retry_config = RetryConfig(
            max_attempts=config.max_retries,
            base_delay=config.retry_delay,
            max_delay=config.max_retry_delay,
            exponential_base=config.retry_exponential_base,
            jitter=config.retry_jitter,
        )

    if circuit_config is None:
        circuit_config = CircuitBreakerConfig(
            failure_threshold=config.circuit_breaker_failure_threshold,
            recovery_timeout=config.circuit_breaker_recovery_timeout,
        )

    return retry_config, circuit_config


def map_provider_error(
    exc: Exception,
    provider_name: str,
    file_path: Path | None = None,
    install_command: str | None = None,
) -> Exception:
    """Map common exceptions to provider-specific exception types.

    This centralizes error handling logic that was duplicated across providers.

    Args:
        exc: The original exception
        provider_name: Name of the provider (e.g., "deepgram", "elevenlabs")
        file_path: Optional file path for context
        install_command: Optional install command for SDK not available errors

    Returns:
        Mapped exception with appropriate context

    Example:
        >>> try:
        ...     result = await provider.transcribe(...)
        ... except Exception as e:
        ...     raise map_provider_error(e, "deepgram", audio_path) from e
    """
    context: dict[str, str | int | float] = {"provider": provider_name}
    if file_path is not None:
        context["file_path"] = str(file_path)

    if isinstance(exc, ImportError):
        logger.error(f"{provider_name} SDK not installed: {exc}")
        ctx = {"provider": provider_name}
        if install_command:
            ctx["install_command"] = install_command
        return ProviderNotAvailableError(
            f"{provider_name} SDK not available",
            context=ctx,
        )

    if isinstance(exc, FileNotFoundError):
        logger.error(f"Audio file not found: {exc}")
        return ValidationError(
            f"Audio file not found: {file_path}",
            context={"file_path": str(file_path) if file_path else "unknown"},
        )

    if isinstance(exc, PermissionError):
        logger.error(f"Permission denied accessing file: {exc}")
        return FileAccessError(
            f"Permission denied: {file_path}",
            context={"file_path": str(file_path) if file_path else "unknown"},
        )

    if isinstance(exc, MemoryError):
        logger.error(f"Insufficient memory to process file: {exc}")
        return ProviderAPIError(
            "Insufficient memory to process file",
            context=context,
        )

    if isinstance(exc, (ConnectionError, TimeoutError)):
        # Let these propagate directly for retry logic
        logger.error(f"{provider_name} API connection/timeout error")
        return exc

    if isinstance(exc, OSError):
        logger.error(f"System error during {provider_name} transcription: {exc}")
        return ProviderAPIError(
            f"{provider_name} API system error",
            context={**context, "error": str(exc)},
        )

    # Re-raise already-mapped exceptions
    if isinstance(exc, (ValidationError, ProviderAPIError, ProviderNotAvailableError, FileAccessError)):
        return exc

    # Catch-all for unexpected errors
    logger.error(f"Unexpected {provider_name} transcription error: {exc}")
    return ProviderAPIError(
        f"Unexpected {provider_name} error: {exc}",
        context={**context, "error_type": type(exc).__name__},
    )


def provider_error_handler(
    provider_name: str,
    install_command: str | None = None,
) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
    """Decorator to handle common provider errors in _transcribe_impl methods.

    Usage:
        @provider_error_handler("deepgram", "uv add deepgram-sdk")
        async def _transcribe_impl(self, audio_file_path: Path, language: str = "en"):
            # Provider-specific logic only - no try/except needed
            ...

    Args:
        provider_name: Name of the provider for error messages
        install_command: Optional install command for SDK errors

    Returns:
        Decorated async function with standardized error handling
    """
    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @wraps(func)
        async def wrapper(*args: object, **kwargs: object) -> T:
            # Extract file_path from args (typically second arg after self)
            file_path: Path | None = None
            if len(args) >= 2 and isinstance(args[1], Path):
                file_path = args[1]
            elif "audio_file_path" in kwargs and isinstance(kwargs["audio_file_path"], Path):
                file_path = kwargs["audio_file_path"]

            try:
                return await func(*args, **kwargs)
            except (ValidationError, ProviderAPIError, ProviderNotAvailableError, FileAccessError):
                # Already properly typed exceptions - re-raise as-is
                raise
            except Exception as exc:
                raise map_provider_error(
                    exc, provider_name, file_path, install_command
                ) from exc

        return wrapper
    return decorator
