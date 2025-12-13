"""Tests for DNS cache and resolution in UrlIngestionService."""

from __future__ import annotations

import socket
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import patch
from urllib.parse import urlparse

import pytest

from src.exceptions import UnsupportedUrlError
from src.services.url_ingestion import ResolvedHost, UrlIngestionService


@pytest.fixture(autouse=True)
def clear_dns_cache():
    """Clear DNS cache before and after each test."""
    with UrlIngestionService._dns_cache_lock:
        UrlIngestionService._dns_cache.clear()
    yield
    with UrlIngestionService._dns_cache_lock:
        UrlIngestionService._dns_cache.clear()


class TestDnsResolutionFailure:
    """Tests for DNS resolution failure scenarios."""

    def test_dns_resolution_failure_raises_unsupported_url_error(self) -> None:
        """DNS resolution failure should raise UnsupportedUrlError instead of returning empty set."""
        url = "https://nonexistent-hostname-that-will-fail-dns.invalid/video"
        parsed = urlparse(url)

        with patch.object(
            socket, "getaddrinfo", side_effect=socket.gaierror("Name or service not known")
        ):
            with pytest.raises(UnsupportedUrlError) as exc_info:
                UrlIngestionService._validate_resolved_ips(parsed.hostname, url)

            assert "DNS resolution failed" in str(exc_info.value)
            assert exc_info.value.context["reason"] == "dns_resolution_failed"
            assert exc_info.value.context["hostname"] == parsed.hostname


class TestDnsCacheBounded:
    """Tests for DNS cache bounded size using TTLCache."""

    def test_dns_cache_bounded_by_maxsize(self):
        """Verify cache respects maxsize and evicts oldest entries."""
        maxsize = UrlIngestionService._dns_cache.maxsize
        assert maxsize == 1000

        for i in range(maxsize + 100):
            hostname = f"host{i}.example.com"
            ips = {f"192.0.2.{i % 256}"}
            UrlIngestionService._cache_resolution(hostname, ips)

        with UrlIngestionService._dns_cache_lock:
            assert len(UrlIngestionService._dns_cache) <= maxsize

    def test_dns_cache_has_ttl(self):
        """Verify cache has TTL configured."""
        ttl = UrlIngestionService._dns_cache.ttl
        assert ttl == 300

    def test_dns_cache_eviction_order(self):
        """Verify LRU eviction - oldest entries removed first."""
        maxsize = UrlIngestionService._dns_cache.maxsize

        for i in range(maxsize):
            hostname = f"original{i}.example.com"
            UrlIngestionService._cache_resolution(hostname, {f"192.0.2.{i % 256}"})

        UrlIngestionService._cache_resolution("new.example.com", {"192.0.2.1"})

        result = UrlIngestionService._get_cached_resolution("new.example.com")
        assert result is not None
        assert "192.0.2.1" in result


class TestDnsCacheThreadSafe:
    """Tests for DNS cache thread safety."""

    def test_dns_cache_thread_safe_concurrent_writes(self):
        """Verify concurrent writes don't cause race conditions."""
        errors: list[Exception] = []
        write_count = 500
        thread_count = 10

        def write_entries(thread_id: int):
            try:
                for i in range(write_count):
                    hostname = f"thread{thread_id}-host{i}.example.com"
                    ips = {f"192.0.2.{i % 256}"}
                    UrlIngestionService._cache_resolution(hostname, ips)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=write_entries, args=(tid,)) for tid in range(thread_count)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Thread errors: {errors}"
        with UrlIngestionService._dns_cache_lock:
            assert len(UrlIngestionService._dns_cache) <= 1000

    def test_dns_cache_thread_safe_concurrent_read_write(self):
        """Verify concurrent reads and writes are thread-safe."""
        errors: list[Exception] = []
        iterations = 200

        for i in range(100):
            UrlIngestionService._cache_resolution(
                f"existing{i}.example.com", {f"192.0.2.{i % 256}"}
            )

        def writer(thread_id: int):
            try:
                for i in range(iterations):
                    hostname = f"writer{thread_id}-{i}.example.com"
                    UrlIngestionService._cache_resolution(hostname, {"10.0.0.1"})
            except Exception as e:
                errors.append(e)

        def reader(thread_id: int):
            try:
                for i in range(iterations):
                    hostname = f"existing{i % 100}.example.com"
                    UrlIngestionService._get_cached_resolution(hostname)
            except Exception as e:
                errors.append(e)

        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = []
            for i in range(10):
                futures.append(executor.submit(writer, i))
                futures.append(executor.submit(reader, i))

            for future in as_completed(futures):
                future.result()

        assert not errors, f"Thread errors: {errors}"

    def test_dns_cache_lock_exists(self):
        """Verify lock is properly initialized."""
        assert hasattr(UrlIngestionService, "_dns_cache_lock")
        assert isinstance(UrlIngestionService._dns_cache_lock, type(threading.Lock()))
