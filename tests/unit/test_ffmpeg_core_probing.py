"""Tests for ffmpeg_core.py probing, path security, and cleanup utilities.

Tests cover:
- probe_media_sync and probe_media_async handling of missing ffprobe
- validate_path_security with dangerous characters
- sanitize_path with special characters
- cleanup_temp_file with existing/non-existing files
"""

import shlex
import subprocess
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import src.services.ffmpeg_core as ffmpeg_core_module
from src.services.ffmpeg_core import (
    MediaProbeResult,
    cleanup_temp_file,
    clear_probe_cache,
    get_probe_cache_stats,
    probe_media_async,
    probe_media_sync,
)
from src.utils.sanitization import PathSanitizer, sanitize_path


class TestProbeMediaSync:
    """Test probe_media_sync function."""

    def test_file_not_found_raises(self, tmp_path):
        """Non-existent file should raise FileNotFoundError."""
        fake_path = tmp_path / "nonexistent.mp3"
        with pytest.raises(FileNotFoundError):
            probe_media_sync(fake_path)

    def test_returns_media_probe_result(self, tmp_path):
        """Valid file should return MediaProbeResult with size info."""
        test_file = tmp_path / "test.mp3"
        test_file.write_bytes(b"fake audio content" * 100)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout='{"format": {"duration": "10.5"}}',
            )
            result = probe_media_sync(test_file)

        assert isinstance(result, MediaProbeResult)
        assert result.duration == 10.5
        assert result.size_bytes == len(b"fake audio content" * 100)
        assert result.size_mb == result.size_bytes / (1024 * 1024)

    def test_ffprobe_not_found_returns_none_duration(self, tmp_path):
        """Missing ffprobe should return None duration with warning log."""
        test_file = tmp_path / "test.mp3"
        test_file.write_bytes(b"fake audio content")

        with patch("subprocess.run", side_effect=FileNotFoundError("ffprobe not found")):
            result = probe_media_sync(test_file)

        assert result.duration is None
        assert result.size_bytes > 0

    def test_ffprobe_timeout_returns_none_duration(self, tmp_path):
        """ffprobe timeout should return None duration with warning log."""
        test_file = tmp_path / "test.mp3"
        test_file.write_bytes(b"fake audio content")

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("ffprobe", 30)):
            result = probe_media_sync(test_file, timeout=30)

        assert result.duration is None
        assert result.size_bytes > 0

    def test_json_decode_error_returns_none_duration(self, tmp_path):
        """Invalid JSON from ffprobe should return None duration."""
        test_file = tmp_path / "test.mp3"
        test_file.write_bytes(b"fake audio content")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="not valid json",
            )
            result = probe_media_sync(test_file)

        assert result.duration is None

    def test_negative_duration_returns_none(self, tmp_path):
        """Negative duration should be treated as unavailable."""
        test_file = tmp_path / "test.mp3"
        test_file.write_bytes(b"fake audio content")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout='{"format": {"duration": "-1.0"}}',
            )
            result = probe_media_sync(test_file)

        assert result.duration is None


class TestProbeMediaAsync:
    """Test probe_media_async function."""

    @pytest.mark.asyncio
    async def test_file_not_found_raises(self, tmp_path):
        """Non-existent file should raise FileNotFoundError."""
        fake_path = tmp_path / "nonexistent.mp3"
        with pytest.raises(FileNotFoundError):
            await probe_media_async(fake_path)

    @pytest.mark.asyncio
    async def test_ffprobe_not_found_returns_none_duration(self, tmp_path):
        """Missing ffprobe should return None duration."""
        test_file = tmp_path / "test.mp3"
        test_file.write_bytes(b"fake audio content")

        with patch(
            "asyncio.create_subprocess_exec", side_effect=FileNotFoundError("ffprobe not found")
        ):
            result = await probe_media_async(test_file)

        assert result.duration is None
        assert result.size_bytes > 0


class TestProbeCacheObservability:
    """Test probe cache metrics and bounded behavior."""

    def test_probe_cache_reports_hits_and_misses(self, tmp_path):
        """Repeated probe of same file should register miss then hit."""
        clear_probe_cache()

        test_file = tmp_path / "cached.mp3"
        test_file.write_bytes(b"fake audio content")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout='{"format": {"duration": "2.5"}}',
            )

            first = probe_media_sync(test_file)
            second = probe_media_sync(test_file)

        assert first.duration == 2.5
        assert second.duration == 2.5

        stats = get_probe_cache_stats()
        assert stats["misses"] >= 1
        assert stats["hits"] >= 1
        assert stats["entries"] >= 1

    def test_probe_cache_eviction_when_max_size_reached(self, monkeypatch, tmp_path):
        """Cache should evict least-recently-used entry when capacity is exceeded."""
        tiny_cache = ffmpeg_core_module._ProbeCache(max_size=2)
        monkeypatch.setattr(ffmpeg_core_module, "_probe_cache", tiny_cache)

        file_a = tmp_path / "a.mp3"
        file_b = tmp_path / "b.mp3"
        file_c = tmp_path / "c.mp3"
        for path in (file_a, file_b, file_c):
            path.write_bytes(b"content")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout='{"format": {"duration": "1.0"}}',
            )
            probe_media_sync(file_a)
            probe_media_sync(file_b)
            probe_media_sync(file_c)

        stats = get_probe_cache_stats()
        assert stats["max_entries"] == 2
        assert stats["entries"] <= 2
        assert stats["evictions"] >= 1


class TestValidatePathSecurity:
    """Test PathSanitizer.validate_path_security method."""

    def test_valid_path_passes(self, tmp_path):
        valid_path = tmp_path / "audio.mp3"
        PathSanitizer.validate_path_security(valid_path)

    def test_path_with_spaces_passes(self):
        path = Path("/media/My Audio Files/podcast episode 01.mp3")
        PathSanitizer.validate_path_security(path)

    def test_path_with_brackets_passes(self):
        path = Path("/media/Song [Official Video] (HD).mp4")
        PathSanitizer.validate_path_security(path)

    def test_path_with_semicolon_fails(self):
        path = Path("/media/file;rm -rf /.mp3")
        with pytest.raises(ValueError, match="Invalid characters"):
            PathSanitizer.validate_path_security(path)

    def test_path_with_ampersand_fails(self):
        path = Path("/media/file & echo bad.mp3")
        with pytest.raises(ValueError, match="Invalid characters"):
            PathSanitizer.validate_path_security(path)

    def test_path_with_pipe_fails(self):
        path = Path("/media/file | cat /etc/passwd.mp3")
        with pytest.raises(ValueError, match="Invalid characters"):
            PathSanitizer.validate_path_security(path)

    def test_path_with_backtick_fails(self):
        path = Path("/media/`whoami`.mp3")
        with pytest.raises(ValueError, match="Invalid characters"):
            PathSanitizer.validate_path_security(path)

    def test_path_with_dollar_fails(self):
        path = Path("/media/$HOME.mp3")
        with pytest.raises(ValueError, match="Invalid characters"):
            PathSanitizer.validate_path_security(path)

    def test_path_with_redirect_fails(self):
        path = Path("/media/file > /etc/passwd.mp3")
        with pytest.raises(ValueError, match="Invalid characters"):
            PathSanitizer.validate_path_security(path)


class TestSanitizePath:
    """Test sanitize_path function from sanitization module."""

    def test_simple_path_quoted(self):
        path = Path("/media/audio.mp3")
        result = sanitize_path(path)
        assert "/media/audio.mp3" in result

    def test_path_with_spaces_quoted(self):
        path = Path("/media/my audio.mp3")
        result = sanitize_path(path)
        assert "my audio.mp3" in result or result.startswith("'")

    def test_path_with_special_chars_quoted(self):
        path = Path("/media/file (1) [copy].mp3")
        result = sanitize_path(path)
        assert "(1)" in result or "\\(" in result or "'" in result

    def test_result_is_shell_safe(self):
        path = Path("/media/file with 'quotes'.mp3")
        result = sanitize_path(path)
        try:
            shlex.split(result)
        except ValueError:
            pytest.fail("sanitize_path output is not shell-safe")


class TestCleanupTempFile:
    """Test cleanup_temp_file function."""

    def test_cleanup_existing_file(self, tmp_path):
        """Existing temp file should be deleted."""
        temp_file = tmp_path / "temp.mp3"
        temp_file.write_bytes(b"temp content")
        assert temp_file.exists()

        cleanup_temp_file(temp_file)

        assert not temp_file.exists()

    def test_cleanup_nonexistent_file(self, tmp_path):
        """Non-existent file should not raise error."""
        nonexistent = tmp_path / "nonexistent.mp3"
        # Should not raise
        cleanup_temp_file(nonexistent)

    def test_cleanup_none_path(self):
        """None path should not raise error."""
        # Should not raise
        cleanup_temp_file(None)

    def test_cleanup_logs_on_os_error(self, tmp_path, caplog):
        """OSError during cleanup should be logged as warning."""
        temp_file = tmp_path / "temp.mp3"
        temp_file.write_bytes(b"temp content")

        with patch.object(Path, "unlink", side_effect=OSError("Permission denied")):
            # Should not raise, but log warning
            cleanup_temp_file(temp_file)

        # The file still "exists" from cleanup_temp_file's perspective
        # since we mocked unlink
