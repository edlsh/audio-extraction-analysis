"""Tests for TUI health service."""

from __future__ import annotations

import time
from unittest.mock import patch

import pytest

from src.ui.tui.services.health_service import HealthService


class TestHealthService:
    """Tests for provider health check service."""

    @pytest.mark.asyncio
    async def test_check_all_providers(self):
        """Test checking all providers returns status dict."""
        service = HealthService()

        with patch("src.providers.factory.TranscriptionProviderFactory") as mock_factory:
            mock_factory.get_available_providers.return_value = [
                "deepgram",
                "whisper",
            ]
            mock_factory.check_provider_health_sync.side_effect = [
                {"status": "ok", "message": "Configured"},
                {"status": "ok", "message": "Available"},
            ]

            health = await service.check_all_providers()

            assert "deepgram" in health
            assert "whisper" in health
            assert health["deepgram"]["status"] == "ok"
            assert health["whisper"]["status"] == "ok"

    @pytest.mark.asyncio
    async def test_check_provider_caching(self):
        """Test that health checks are cached for TTL duration."""
        service = HealthService()

        with patch(
            "src.providers.factory.TranscriptionProviderFactory.check_provider_health_sync"
        ) as mock_check:
            mock_check.return_value = {"status": "ok"}

            # First call
            result1 = await service._check_provider("deepgram")
            assert result1["status"] == "ok"
            assert mock_check.call_count == 1

            # Second call (should use cache)
            result2 = await service._check_provider("deepgram")
            assert result2 == result1
            assert mock_check.call_count == 1  # Still 1, not 2

    @pytest.mark.asyncio
    async def test_check_provider_cache_expiry(self):
        """Test that cache expires after TTL."""
        service = HealthService()
        service._cache_ttl = 0.1  # 100ms TTL for testing

        with patch(
            "src.providers.factory.TranscriptionProviderFactory.check_provider_health_sync"
        ) as mock_check:
            mock_check.return_value = {"status": "ok"}

            # First call
            await service._check_provider("deepgram")
            assert mock_check.call_count == 1

            # Wait for cache to expire
            await asyncio.sleep(0.15)

            # Second call (should refresh)
            await service._check_provider("deepgram")
            assert mock_check.call_count == 2

    @pytest.mark.asyncio
    async def test_check_provider_error_handling(self):
        """Test that provider check errors are converted to error status."""
        service = HealthService()

        with patch(
            "src.providers.factory.TranscriptionProviderFactory.check_provider_health_sync"
        ) as mock_check:
            mock_check.side_effect = ValueError("Missing API key")

            result = await service._check_provider("deepgram")

            assert result["status"] == "error"
            assert "Missing API key" in result["message"]

    @pytest.mark.asyncio
    async def test_check_all_providers_parallel_execution(self):
        """Test that provider checks run in parallel."""
        service = HealthService()

        with patch("src.providers.factory.TranscriptionProviderFactory") as mock_factory:
            mock_factory.get_available_providers.return_value = [
                "deepgram",
                "whisper",
                "elevenlabs",
            ]

            call_times = []

            def slow_check(name):
                call_times.append(time.time())
                time.sleep(0.1)  # Simulate slow check
                return {"status": "ok"}

            mock_factory.check_provider_health_sync.side_effect = slow_check

            start = time.time()
            await service.check_all_providers()
            duration = time.time() - start

            # Should complete in ~0.1s (parallel) not ~0.3s (sequential)
            assert duration < 0.25  # Allow some overhead

    @pytest.mark.asyncio
    async def test_check_all_providers_exception_handling(self):
        """Test that exceptions in individual checks don't fail entire operation."""
        service = HealthService()

        with patch("src.providers.factory.TranscriptionProviderFactory") as mock_factory:
            mock_factory.get_available_providers.return_value = [
                "deepgram",
                "whisper",
            ]

            # First provider succeeds, second fails
            mock_factory.check_provider_health_sync.side_effect = [
                {"status": "ok"},
                RuntimeError("Check failed"),
            ]

            health = await service.check_all_providers()

            # Should have results for both, with error converted
            assert health["deepgram"]["status"] == "ok"
            assert health["whisper"]["status"] == "error"
            assert "Check failed" in health["whisper"]["message"]

    def test_clear_cache(self):
        """Test cache clearing."""
        service = HealthService()
        service._cache["test"] = ({"status": "ok"}, time.time())

        assert len(service._cache) == 1

        service.clear_cache()

        assert len(service._cache) == 0


# Need to import asyncio for the test that uses it
import asyncio
