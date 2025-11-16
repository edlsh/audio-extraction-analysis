"""Common FFmpeg utilities and error handling."""

from __future__ import annotations

import logging
import subprocess
from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


def handle_ffmpeg_errors(operation_name: str = "FFmpeg operation") -> Callable:
    """Decorator to handle common FFmpeg errors consistently.

    Args:
        operation_name: Description of the operation for error messages

    Returns:
        Decorated function that handles FFmpeg errors
    """

    def decorator(func: Callable[..., T | None]) -> Callable[..., T | None]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T | None:
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


def handle_ffmpeg_errors_async(operation_name: str = "FFmpeg operation") -> Callable:
    """Async decorator to handle common FFmpeg errors consistently.

    Args:
        operation_name: Description of the operation for error messages

    Returns:
        Decorated async function that handles FFmpeg errors
    """

    def decorator(func: Callable[..., T | None]) -> Callable[..., T | None]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T | None:
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
