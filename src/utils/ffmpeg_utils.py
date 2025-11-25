"""Common FFmpeg utilities and error handling."""

from __future__ import annotations

import logging
import subprocess
from collections.abc import Coroutine
from functools import wraps
from typing import TYPE_CHECKING, Any, ParamSpec, TypeVar

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)

P = ParamSpec("P")
T = TypeVar("T")


def handle_ffmpeg_errors(
    operation_name: str = "FFmpeg operation",
) -> Callable[[Callable[P, T]], Callable[P, T | None]]:
    """Decorator to handle common FFmpeg errors consistently.

    This decorator catches FFmpeg-related exceptions and returns None instead of
    propagating the error. All errors are logged with appropriate severity levels.

    **IMPORTANT**: Decorated functions return `T | None` instead of `T`.
    Callers MUST check for None return values before using the result.

    Args:
        operation_name: Description of the operation for error messages (default: "FFmpeg operation")

    Returns:
        Decorator that wraps functions to return `T | None` instead of `T`.
        Returns None when any of the following exceptions occur:
        - subprocess.CalledProcessError: FFmpeg command failed
        - subprocess.TimeoutExpired: FFmpeg command timed out
        - FileNotFoundError: Required file not found
        - PermissionError: Permission denied accessing file
        - OSError: System-level error
        - ValueError: Invalid input parameter

    Example:
        >>> @handle_ffmpeg_errors("video info extraction")
        ... def get_video_info(path: Path) -> dict[str, Any]:
        ...     # This function normally returns dict[str, Any]
        ...     # But with decorator, it returns dict[str, Any] | None
        ...     return run_ffprobe(path)
        ...
        >>> info = get_video_info(video_path)
        >>> if info is None:
        ...     print("Failed to get video info")
        ... else:
        ...     print(f"Duration: {info['duration']}")

    Note:
        This changes the function's error handling contract from raising exceptions
        to returning None. Ensure all callers are updated to handle None returns.
    """

    def decorator(func: Callable[P, T]) -> Callable[P, T | None]:
        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T | None:
            try:
                return func(*args, **kwargs)
            except subprocess.CalledProcessError as e:
                logger.error(f"{operation_name} failed: {getattr(e, 'stderr', str(e))}")
                return None
            except subprocess.TimeoutExpired as e:
                logger.error(f"{operation_name} timed out: {e}")
                return None
            except FileNotFoundError as e:
                logger.error(f"Required file not found during {operation_name}: {e}")
                return None
            except PermissionError as e:
                logger.error(f"Permission denied during {operation_name}: {e}")
                return None
            except OSError as e:
                logger.error(f"System error during {operation_name}: {e}")
                return None
            except ValueError as e:
                logger.error(f"Invalid input for {operation_name}: {e}")
                return None

        return wrapper

    return decorator


def handle_ffmpeg_errors_async(
    operation_name: str = "FFmpeg operation",
) -> Callable[
    [Callable[P, Coroutine[object, object, T]]], Callable[P, Coroutine[object, object, T | None]]
]:
    """Async decorator to handle common FFmpeg errors consistently.

    This decorator catches FFmpeg-related exceptions in async functions and returns
    None instead of propagating the error. All errors are logged with appropriate
    severity levels.

    **IMPORTANT**: Decorated async functions return `T | None` instead of `T`.
    Callers MUST check for None return values before using the result.

    Args:
        operation_name: Description of the operation for error messages (default: "FFmpeg operation")

    Returns:
        Decorator that wraps async functions to return `T | None` instead of `T`.
        Returns None when any of the following exceptions occur:
        - subprocess.CalledProcessError: FFmpeg command failed
        - subprocess.TimeoutExpired: FFmpeg command timed out
        - FileNotFoundError: Required file not found
        - PermissionError: Permission denied accessing file
        - OSError: System-level error
        - ValueError: Invalid input parameter

    Example:
        >>> @handle_ffmpeg_errors_async("async audio extraction")
        ... async def extract_audio_async(path: Path) -> Path:
        ...     # This function normally returns Path
        ...     # But with decorator, it returns Path | None
        ...     return await run_ffmpeg_async(path)
        ...
        >>> output = await extract_audio_async(video_path)
        >>> if output is None:
        ...     print("Failed to extract audio")
        ... else:
        ...     print(f"Audio saved to: {output}")

    Note:
        This changes the function's error handling contract from raising exceptions
        to returning None. Ensure all callers are updated to handle None returns.
        For async operations, this is particularly important as errors in background
        tasks may go unnoticed without proper None-checking.
    """

    def decorator(
        func: Callable[P, Coroutine[object, object, T]],
    ) -> Callable[P, Coroutine[object, object, T | None]]:
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T | None:
            try:
                return await func(*args, **kwargs)
            except subprocess.CalledProcessError as e:
                logger.error(f"{operation_name} failed: {getattr(e, 'stderr', str(e))}")
                return None
            except subprocess.TimeoutExpired as e:
                logger.error(f"{operation_name} timed out: {e}")
                return None
            except FileNotFoundError as e:
                logger.error(f"Required file not found during {operation_name}: {e}")
                return None
            except PermissionError as e:
                logger.error(f"Permission denied during {operation_name}: {e}")
                return None
            except OSError as e:
                logger.error(f"System error during {operation_name}: {e}")
                return None
            except ValueError as e:
                logger.error(f"Invalid input for {operation_name}: {e}")
                return None

        return wrapper

    return decorator
