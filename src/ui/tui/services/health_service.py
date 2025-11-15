"""Provider health check service with caching."""

from __future__ import annotations

import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any


class HealthService:
    """Provider health check service with caching.

    Performs asynchronous health checks on transcription providers using
    a thread pool executor (since the underlying API is synchronous).
    Results are cached for 60 seconds to avoid redundant checks.

    Usage:
        >>> service = HealthService()
        >>> health = await service.check_all_providers()
        >>> print(health["deepgram"]["status"])
        'ok'

    Example:
        >>> service = HealthService()
        >>>
        >>> # Check all providers
        >>> results = await service.check_all_providers()
        >>> for provider, status in results.items():
        ...     print(f"{provider}: {status['status']}")
        ...
        >>> # Check single provider with caching
        >>> status = await service._check_provider("deepgram")
        >>> # Second call uses cache (within 60s)
        >>> cached_status = await service._check_provider("deepgram")
    """

    def __init__(self):
        """Initialize health service with cache and thread pool."""
        self._cache: dict[str, tuple[dict[str, Any], float]] = {}
        self._cache_ttl = 60.0  # 60 second cache TTL
        self._executor = ThreadPoolExecutor(max_workers=4)

    async def check_all_providers(self) -> dict[str, dict[str, Any]]:
        """Check health of all registered providers.

        Runs checks in parallel using thread pool and returns a dictionary
        mapping provider names to their health status.

        Returns:
            Dictionary of provider health statuses:
            {
                "provider_name": {
                    "status": "ok" | "error",
                    "message": "Status message",
                    ...additional provider-specific fields...
                }
            }

        Example:
            >>> service = HealthService()
            >>> health = await service.check_all_providers()
            >>> health["deepgram"]
            {'status': 'ok', 'message': 'API key configured'}
        """
        from ....providers.factory import TranscriptionProviderFactory

        providers = TranscriptionProviderFactory.get_available_providers()

        # Run checks in parallel
        tasks = [self._check_provider(name) for name in providers]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Build result dict, converting exceptions to error status
        return {
            name: (
                result
                if not isinstance(result, Exception)
                else {"status": "error", "message": str(result)}
            )
            for name, result in zip(providers, results)
        }

    async def _check_provider(self, name: str) -> dict[str, Any]:
        """Check single provider with caching.

        Args:
            name: Provider name to check

        Returns:
            Provider health status dictionary

        Example:
            >>> service = HealthService()
            >>> status = await service._check_provider("whisper")
            >>> status["status"]
            'ok'
        """
        now = time.time()

        # Check cache
        if name in self._cache:
            result, timestamp = self._cache[name]
            if now - timestamp < self._cache_ttl:
                return result

        # Run in thread pool (blocking API)
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(self._executor, self._sync_check, name)

        # Update cache
        self._cache[name] = (result, now)
        return result

    def _sync_check(self, name: str) -> dict[str, Any]:
        """Synchronous health check (runs in thread pool).

        Args:
            name: Provider name to check

        Returns:
            Provider health status dictionary

        Raises:
            Exception: If health check fails
        """
        from ....providers.factory import TranscriptionProviderFactory

        try:
            return TranscriptionProviderFactory.check_provider_health_sync(name)
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def clear_cache(self) -> None:
        """Clear the health check cache.

        Useful for forcing fresh health checks on next call.
        """
        self._cache.clear()

    def __del__(self):
        """Clean up thread pool on deletion."""
        self._executor.shutdown(wait=False)
