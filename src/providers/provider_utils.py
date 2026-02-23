"""Provider configuration and error handling utilities.

Exception Handling Policy:
    - Re-raise: Network errors (ConnectionError, TimeoutError) for retry logic
    - Wrap and log: Provider API errors (mapped to ProviderAPIError)
    - Wrap and raise: Validation errors (mapped to ValidationError)
    - Log only: Cache errors (non-critical)

Decorator Usage:
    @provider_error_handler("deepgram", "uv add deepgram-sdk")
    async def _transcribe_impl(self, audio_file_path: Path, language: str = "en"):
        # Provider-specific logic only - no try/except needed
        ...
"""

from __future__ import annotations

import importlib.util
import threading
from functools import wraps
from pathlib import Path
from typing import TYPE_CHECKING, Any, ParamSpec, TypeVar

from src.utils.logger import get_logger

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

    from .base import ProviderMeta

from ..config import get_config
from ..exceptions import (
    AudioFileNotFoundError,
    FileAccessError,
    ProviderAPIError,
    ProviderNotAvailableError,
    ValidationError,
)
from ..utils.retry import RetryConfig

logger = get_logger(__name__)

P = ParamSpec("P")
T = TypeVar("T")

_sdk_availability_cache: dict[tuple[str, ...], bool] = {}
_sdk_warning_emitted: set[tuple[str, ...]] = set()
_sdk_cache_lock = threading.Lock()


def check_sdk_available(meta: ProviderMeta) -> bool:
    """Check if required SDK modules are available for a provider.

    Results are memoized per module list to avoid repeated import probing on
    hot paths like provider selection and health checks.

    Args:
        meta: ProviderMeta with sdk_imports list

    Returns:
        True if all required modules can be imported, False otherwise
    """
    if not meta.sdk_imports:
        return True

    cache_key = tuple(meta.sdk_imports)

    with _sdk_cache_lock:
        cached = _sdk_availability_cache.get(cache_key)
        if cached is not None:
            return cached

    missing_modules: list[str] = []
    for module in cache_key:
        try:
            if importlib.util.find_spec(module) is None:
                missing_modules.append(module)
        except (ImportError, AttributeError, ValueError):
            missing_modules.append(module)

    available = not missing_modules

    with _sdk_cache_lock:
        _sdk_availability_cache[cache_key] = available
        should_warn = not available and cache_key not in _sdk_warning_emitted
        if should_warn:
            _sdk_warning_emitted.add(cache_key)

    if not available and should_warn:
        logger.warning(
            f"{meta.name} provider dependencies not installed: "
            f"missing {', '.join(missing_modules)}"
        )

    return available


def require_sdk(meta: ProviderMeta) -> None:
    """Raise ImportError if SDK is not available.

    Args:
        meta: ProviderMeta with sdk_imports and install_command

    Raises:
        ImportError: If required SDK modules are not installed
    """
    if not check_sdk_available(meta):
        install_hint = f" Install with: {meta.install_command}" if meta.install_command else ""
        raise ImportError(f"{meta.name} SDK not available.{install_hint}")


def get_default_configs(retry_config: RetryConfig | None = None) -> RetryConfig:
    """Get retry config with defaults from global config."""
    config = get_config()

    if retry_config is None:
        retry_config = RetryConfig(
            max_attempts=config.max_retries,
            base_delay=config.retry_delay,
            max_delay=config.max_retry_delay,
            exponential_base=config.retry_exponential_base,
            jitter=config.retry_jitter,
        )

    return retry_config


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
        return AudioFileNotFoundError(
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
    if isinstance(
        exc,
        (
            ValidationError,
            ProviderAPIError,
            ProviderNotAvailableError,
            FileAccessError,
            AudioFileNotFoundError,
        ),
    ):
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
) -> Callable[[Callable[P, Coroutine[Any, Any, T]]], Callable[P, Coroutine[Any, Any, T]]]:
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

    def decorator(func: Callable[P, Coroutine[Any, Any, T]]) -> Callable[P, Coroutine[Any, Any, T]]:
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            # Extract file_path from args (typically second arg after self)
            file_path: Path | None = None
            if len(args) >= 2 and isinstance(args[1], Path):
                file_path = args[1]
            elif "audio_file_path" in kwargs and isinstance(kwargs["audio_file_path"], Path):
                file_path = kwargs["audio_file_path"]

            try:
                return await func(*args, **kwargs)
            except (
                ValidationError,
                ProviderAPIError,
                ProviderNotAvailableError,
                FileAccessError,
                AudioFileNotFoundError,
            ):
                # Already properly typed exceptions - re-raise as-is
                raise
            except Exception as exc:
                raise map_provider_error(exc, provider_name, file_path, install_command) from exc

        return wrapper

    return decorator


# Shorter alias for common usage
handle_provider_errors = provider_error_handler
