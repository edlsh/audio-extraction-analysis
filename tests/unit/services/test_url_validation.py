"""Tests for URL ingestion SSRF protection and host validation."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlparse

import pytest

from src.exceptions import UnsupportedUrlError
from src.services.url_ingestion import UrlIngestionService


class TestUrlValidation:
    """Test URL validation and SSRF protection."""

    def test_rejects_localhost(self) -> None:
        """Localhost URLs should be rejected."""
        url = "http://localhost:8080/video.mp4"
        parsed = urlparse(url)
        with pytest.raises(UnsupportedUrlError) as exc_info:
            UrlIngestionService._validate_url(parsed, url)
        assert "localhost" in exc_info.value.context.get("reason", "").lower()

    def test_rejects_localhost_localdomain(self) -> None:
        """localhost.localdomain should be rejected."""
        url = "http://localhost.localdomain/video.mp4"
        parsed = urlparse(url)
        with pytest.raises(UnsupportedUrlError):
            UrlIngestionService._validate_url(parsed, url)

    @pytest.mark.parametrize(
        "ip",
        [
            "127.0.0.1",
            "127.0.0.2",
            "127.255.255.255",
        ],
    )
    def test_rejects_loopback_ipv4(self, ip: str) -> None:
        """IPv4 loopback addresses should be rejected."""
        url = f"http://{ip}:8080/video.mp4"
        parsed = urlparse(url)
        with pytest.raises(UnsupportedUrlError) as exc_info:
            UrlIngestionService._validate_url(parsed, url)
        assert "loopback" in exc_info.value.context.get("reason", "").lower()

    def test_rejects_loopback_ipv6(self) -> None:
        """IPv6 loopback (::1) should be rejected."""
        url = "http://[::1]:8080/video.mp4"
        parsed = urlparse(url)
        with pytest.raises(UnsupportedUrlError) as exc_info:
            UrlIngestionService._validate_url(parsed, url)
        assert "loopback" in exc_info.value.context.get("reason", "").lower()

    @pytest.mark.parametrize(
        "ip",
        [
            "10.0.0.1",
            "10.255.255.255",
            "172.16.0.1",
            "172.31.255.255",
            "192.168.0.1",
            "192.168.255.255",
        ],
    )
    def test_rejects_private_ipv4(self, ip: str) -> None:
        """Private IPv4 addresses should be rejected."""
        url = f"http://{ip}/video.mp4"
        parsed = urlparse(url)
        with pytest.raises(UnsupportedUrlError) as exc_info:
            UrlIngestionService._validate_url(parsed, url)
        assert "private" in exc_info.value.context.get("reason", "").lower()

    @pytest.mark.parametrize(
        "ip",
        [
            "169.254.0.1",
            "169.254.255.255",
        ],
    )
    def test_rejects_link_local_ipv4(self, ip: str) -> None:
        """Link-local IPv4 addresses should be rejected."""
        url = f"http://{ip}/video.mp4"
        parsed = urlparse(url)
        with pytest.raises(UnsupportedUrlError) as exc_info:
            UrlIngestionService._validate_url(parsed, url)
        assert "link_local" in exc_info.value.context.get("reason", "").lower()

    def test_rejects_unspecified_ipv4(self) -> None:
        """0.0.0.0 should be rejected."""
        url = "http://0.0.0.0/video.mp4"
        parsed = urlparse(url)
        with pytest.raises(UnsupportedUrlError) as exc_info:
            UrlIngestionService._validate_url(parsed, url)
        assert "unspecified" in exc_info.value.context.get("reason", "").lower()

    def test_rejects_unspecified_ipv6(self) -> None:
        """:: (IPv6 unspecified) should be rejected."""
        url = "http://[::]/video.mp4"
        parsed = urlparse(url)
        with pytest.raises(UnsupportedUrlError) as exc_info:
            UrlIngestionService._validate_url(parsed, url)
        assert "unspecified" in exc_info.value.context.get("reason", "").lower()

    @pytest.mark.parametrize(
        "ip",
        [
            "224.0.0.1",  # All hosts multicast
            "239.255.255.255",  # Admin scoped multicast
        ],
    )
    def test_rejects_multicast_ipv4(self, ip: str) -> None:
        """Multicast IPv4 addresses should be rejected."""
        url = f"http://{ip}/video.mp4"
        parsed = urlparse(url)
        with pytest.raises(UnsupportedUrlError) as exc_info:
            UrlIngestionService._validate_url(parsed, url)
        assert "multicast" in exc_info.value.context.get("reason", "").lower()

    def test_rejects_file_scheme(self) -> None:
        """file:// URLs should be rejected."""
        url = "file:///etc/passwd"
        parsed = urlparse(url)
        with pytest.raises(UnsupportedUrlError) as exc_info:
            UrlIngestionService._validate_url(parsed, url)
        assert "scheme" in exc_info.value.context.get("reason", "").lower()

    def test_rejects_ftp_scheme(self) -> None:
        """ftp:// URLs should be rejected."""
        url = "ftp://example.com/video.mp4"
        parsed = urlparse(url)
        with pytest.raises(UnsupportedUrlError) as exc_info:
            UrlIngestionService._validate_url(parsed, url)
        assert "scheme" in exc_info.value.context.get("reason", "").lower()

    def test_allows_public_http(self) -> None:
        """Public HTTP URLs should be allowed."""
        url = "http://example.com/video.mp4"
        parsed = urlparse(url)
        # Should not raise
        UrlIngestionService._validate_url(parsed, url)

    def test_allows_public_https(self) -> None:
        """Public HTTPS URLs should be allowed."""
        url = "https://youtube.com/watch?v=abc123"
        parsed = urlparse(url)
        # Should not raise
        UrlIngestionService._validate_url(parsed, url)

    def test_allows_public_ipv4(self) -> None:
        """Public IPv4 addresses should be allowed."""
        url = "http://8.8.8.8/video.mp4"
        parsed = urlparse(url)
        # Should not raise
        UrlIngestionService._validate_url(parsed, url)


class TestIpv4MappedIpv6:
    """Test IPv4-mapped IPv6 address handling."""

    def test_rejects_ipv4_mapped_loopback(self) -> None:
        """IPv4-mapped loopback (::ffff:127.0.0.1) should be rejected."""
        import ipaddress

        ip = ipaddress.ip_address("::ffff:127.0.0.1")
        with pytest.raises(UnsupportedUrlError) as exc_info:
            UrlIngestionService._check_ip_is_safe(ip, "http://test/", "test")
        assert "loopback" in exc_info.value.context.get("reason", "").lower()

    def test_rejects_ipv4_mapped_private(self) -> None:
        """IPv4-mapped private (::ffff:192.168.1.1) should be rejected."""
        import ipaddress

        ip = ipaddress.ip_address("::ffff:192.168.1.1")
        with pytest.raises(UnsupportedUrlError) as exc_info:
            UrlIngestionService._check_ip_is_safe(ip, "http://test/", "test")
        assert "private" in exc_info.value.context.get("reason", "").lower()

    def test_allows_ipv4_mapped_public(self) -> None:
        """IPv4-mapped public addresses should be allowed."""
        import ipaddress

        ip = ipaddress.ip_address("::ffff:8.8.8.8")
        # Should not raise
        UrlIngestionService._check_ip_is_safe(ip, "http://test/", "test")


class TestDnsResolutionValidation:
    """Test DNS resolution validation (requires mocking for some tests)."""

    def test_validate_resolved_ips_skips_ip_literals(self) -> None:
        """IP literals should skip DNS resolution validation."""
        # This should return without doing DNS lookup
        UrlIngestionService._validate_resolved_ips("8.8.8.8", "http://8.8.8.8/")

    def test_validate_resolved_ips_handles_dns_failure(self) -> None:
        """DNS resolution failure should raise UnsupportedUrlError for SSRF protection."""
        with pytest.raises(UnsupportedUrlError) as exc_info:
            UrlIngestionService._validate_resolved_ips(
                "this-domain-definitely-does-not-exist-12345.invalid",
                "http://this-domain-definitely-does-not-exist-12345.invalid/",
            )
        assert "DNS resolution failed" in str(exc_info.value)


class TestPlaylistRejection:
    """Test playlist URL rejection."""

    @patch("src.services.url_ingestion.AudioExtractor")
    def test_rejects_playlist_url(self, mock_extractor, tmp_path: Path) -> None:
        """Playlist URLs should be rejected."""
        service = UrlIngestionService(tmp_path)
        with pytest.raises(UnsupportedUrlError) as exc_info:
            service._reject_playlist("https://youtube.com/playlist?list=abc123")
        assert "playlist" in str(exc_info.value).lower()


__all__ = [
    "TestDnsResolutionValidation",
    "TestIpv4MappedIpv6",
    "TestPlaylistRejection",
    "TestUrlValidation",
]
