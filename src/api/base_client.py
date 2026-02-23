"""Base API client wrapper with shared retry/timeout/error handling.

This module provides a base class for API client wrappers that
centralizes common concerns like:
- Retry logic with exponential backoff
- Timeout configuration
- Error handling and mapping
- Logging of API calls
"""

from __future__ import annotations

from functools import wraps
from typing import TYPE_CHECKING, TypeVar

from src.utils.logger import get_logger
from src.utils.retry import RetryConfig

from ..exceptions import ProviderAPIError

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

T = TypeVar("T")

logger = get_logger(__name__)


def with_timeout(
    timeout: float,
) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
    """Decorator to add timeout to async functions.

    Args:
        timeout: Timeout in seconds

    Returns:
        Decorated async function with timeout
    """

    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @wraps(func)
        async def wrapper(*args: object, **kwargs: object) -> T:
            try:
                import asyncio

                return await asyncio.wait_for(func(*args, **kwargs), timeout=timeout)
            except TimeoutError:
                raise ProviderAPIError(f"API call timed out after {timeout}s")

        return wrapper

    return decorator


class BaseAPIClient:
    """Base class for API client wrappers.

    Subclasses should implement:
        - _create_sdk_client(): Create provider SDK client
        - _make_api_call(): Execute specific API call

    This class provides shared functionality:
        - Retry logic with exponential backoff
        - Timeout handling
        - Error mapping to ProviderAPIError
        - Consistent logging
    """

    def __init__(
        self,
        api_key: str | None = None,
        retry_config: RetryConfig | None = None,
        default_timeout: float = 300.0,
    ) -> None:
        """Initialize API client wrapper.

        Args:
            api_key: API key for provider
            retry_config: Retry configuration
            default_timeout: Default timeout in seconds
        """
        self.api_key = api_key
        self._retry_config = retry_config or RetryConfig()
        self._default_timeout = default_timeout
        self._sdk_client: object | None = None

    def _get_sdk_client(self) -> object:
        """Lazy-load SDK client."""
        if self._sdk_client is None:
            self._sdk_client = self._create_sdk_client()
        return self._sdk_client

    def _create_sdk_client(self) -> object:
        """Create provider SDK client.

        Must be implemented by subclasses.

        Returns:
            SDK client instance
        """
        raise NotImplementedError("Subclasses must implement _create_sdk_client")

    async def _execute_with_retry(
        self, func: Callable[..., Awaitable[T]], *args: object, **kwargs: object
    ) -> T:
        """Execute async function with retry logic.

        Args:
            func: Async function to execute
            *args: Positional arguments
            **kwargs: Keyword arguments (context is extracted and not forwarded)

        Returns:
            Result of function call

        Raises:
            ProviderAPIError: If all retries fail
        """
        from src.utils.retry import retry_async

        # Extract context for logging, don't forward to func
        _context = kwargs.pop("context", None)

        @retry_async(config=self._retry_config)
        async def _call() -> T:
            return await func(*args, **kwargs)

        return await _call()

    def _handle_api_error(self, error: Exception, context: dict[str, str]) -> None:
        """Handle API errors with logging and mapping.

        Args:
            error: The exception that occurred
            context: Context information for error messages

        Raises:
            ProviderAPIError: Always raised with context
        """
        logger.error(f"API error: {context} - {error}")
        raise ProviderAPIError(
            f"API request failed: {error}",
            context=context,
        ) from error


__all__ = ["BaseAPIClient", "with_timeout"]
