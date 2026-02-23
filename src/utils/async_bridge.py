"""Async-to-sync bridging utilities.

Provides a unified way to run async coroutines from synchronous contexts,
handling the case where an event loop may or may not already be running.
"""

from __future__ import annotations

import asyncio
import atexit
from collections.abc import Coroutine
from concurrent.futures import ThreadPoolExecutor
from typing import Any, TypeVar

from src.utils.constants import Limits

T = TypeVar("T")

_EXECUTOR: ThreadPoolExecutor | None = None


def _get_executor() -> ThreadPoolExecutor:
    """Get or create the shared executor for async bridging."""
    global _EXECUTOR
    if _EXECUTOR is None:
        _EXECUTOR = ThreadPoolExecutor(max_workers=Limits.DEFAULT_MAX_WORKERS)
        atexit.register(_shutdown_executor)
    return _EXECUTOR


def _shutdown_executor() -> None:
    """Shutdown the shared executor on exit."""
    global _EXECUTOR
    if _EXECUTOR is not None:
        _EXECUTOR.shutdown(wait=False)
        _EXECUTOR = None


def _has_running_loop() -> bool:
    """Check if there's a running event loop in the current thread."""
    try:
        asyncio.get_running_loop()
        return True
    except RuntimeError:
        return False


def run_async_in_sync(coro: Coroutine[Any, Any, T], timeout: float | None = None) -> T:
    """Run an async coroutine from a synchronous context.

    Handles two cases:
    - If already in an event loop: runs via ThreadPoolExecutor to avoid nesting
    - If not in an event loop: uses asyncio.run directly

    Args:
        coro: The coroutine to execute.
        timeout: Optional timeout in seconds (only applies when using executor).

    Returns:
        The result of the coroutine.

    Raises:
        TimeoutError: If the operation exceeds the timeout.
        Any exception raised by the coroutine.
    """
    if _has_running_loop():
        future = _get_executor().submit(asyncio.run, coro)
        return future.result(timeout=timeout)
    if timeout is not None:
        return asyncio.run(asyncio.wait_for(coro, timeout=timeout))
    return asyncio.run(coro)


__all__ = ["run_async_in_sync"]
