"""Tests for provider error mapping utilities.

Tests cover:
- All exception type mappings in map_provider_error
- provider_error_handler decorator behavior
- File path extraction from args/kwargs
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.exceptions import (
    AudioFileNotFoundError,
    FileAccessError,
    ProviderAPIError,
    ProviderNotAvailableError,
    ValidationError,
)
from src.providers.provider_utils import map_provider_error, provider_error_handler


class TestMapProviderError:
    """Test map_provider_error function with all exception types."""

    def test_import_error_maps_to_provider_not_available(self):
        """ImportError should map to ProviderNotAvailableError."""
        exc = ImportError("No module named 'deepgram'")
        result = map_provider_error(exc, "deepgram", install_command="uv add deepgram-sdk")

        assert isinstance(result, ProviderNotAvailableError)
        assert "deepgram" in result.message.lower()
        assert result.context.get("install_command") == "uv add deepgram-sdk"

    def test_import_error_without_install_command(self):
        """ImportError without install_command should still work."""
        exc = ImportError("No module named 'custom_provider'")
        result = map_provider_error(exc, "custom")

        assert isinstance(result, ProviderNotAvailableError)
        assert "install_command" not in result.context

    def test_file_not_found_error_maps_to_audio_file_not_found(self):
        """FileNotFoundError should map to AudioFileNotFoundError."""
        file_path = Path("/audio/test.mp3")
        exc = FileNotFoundError(f"No such file: {file_path}")
        result = map_provider_error(exc, "deepgram", file_path)

        assert isinstance(result, AudioFileNotFoundError)
        assert "not found" in result.message.lower()
        assert str(file_path) in result.context.get("file_path", "")

    def test_file_not_found_without_file_path(self):
        """FileNotFoundError without file_path should handle gracefully."""
        exc = FileNotFoundError("No such file")
        result = map_provider_error(exc, "elevenlabs")

        assert isinstance(result, AudioFileNotFoundError)
        assert result.context.get("file_path") == "unknown"

    def test_permission_error_maps_to_file_access_error(self):
        """PermissionError should map to FileAccessError."""
        file_path = Path("/protected/audio.mp3")
        exc = PermissionError(f"Permission denied: {file_path}")
        result = map_provider_error(exc, "deepgram", file_path)

        assert isinstance(result, FileAccessError)
        assert "permission" in result.message.lower()
        assert str(file_path) in result.context.get("file_path", "")

    def test_memory_error_maps_to_provider_api_error(self):
        """MemoryError should map to ProviderAPIError."""
        exc = MemoryError("Cannot allocate memory")
        result = map_provider_error(exc, "whisper")

        assert isinstance(result, ProviderAPIError)
        assert "memory" in result.message.lower()
        assert result.context.get("provider") == "whisper"

    def test_connection_error_passes_through(self):
        """ConnectionError should pass through for retry logic."""
        exc = ConnectionError("Connection refused")
        result = map_provider_error(exc, "deepgram")

        assert result is exc
        assert isinstance(result, ConnectionError)

    def test_timeout_error_passes_through(self):
        """TimeoutError should pass through for retry logic."""
        exc = TimeoutError("Connection timed out")
        result = map_provider_error(exc, "elevenlabs")

        assert result is exc
        assert isinstance(result, TimeoutError)

    def test_os_error_maps_to_provider_api_error(self):
        """OSError should map to ProviderAPIError with system error context."""
        exc = OSError("Disk full")
        result = map_provider_error(exc, "deepgram")

        assert isinstance(result, ProviderAPIError)
        assert "system error" in result.message.lower()
        assert "Disk full" in result.context.get("error", "")

    def test_validation_error_passes_through(self):
        """ValidationError should pass through unchanged."""
        original = ValidationError("Invalid file format")
        result = map_provider_error(original, "deepgram")

        assert result is original

    def test_provider_api_error_passes_through(self):
        """ProviderAPIError should pass through unchanged."""
        original = ProviderAPIError("API error", status_code=500)
        result = map_provider_error(original, "deepgram")

        assert result is original

    def test_provider_not_available_passes_through(self):
        """ProviderNotAvailableError should pass through unchanged."""
        original = ProviderNotAvailableError("Provider unavailable")
        result = map_provider_error(original, "deepgram")

        assert result is original

    def test_file_access_error_passes_through(self):
        """FileAccessError should pass through unchanged."""
        original = FileAccessError("Cannot access file")
        result = map_provider_error(original, "deepgram")

        assert result is original

    def test_audio_file_not_found_error_passes_through(self):
        """AudioFileNotFoundError should pass through unchanged."""
        original = AudioFileNotFoundError("Audio file not found")
        result = map_provider_error(original, "deepgram")

        assert result is original

    def test_unexpected_error_maps_to_provider_api_error(self):
        """Unexpected exceptions should map to ProviderAPIError with error_type."""
        exc = RuntimeError("Something unexpected")
        result = map_provider_error(exc, "deepgram")

        assert isinstance(result, ProviderAPIError)
        assert "unexpected" in result.message.lower()
        assert result.context.get("error_type") == "RuntimeError"

    def test_context_includes_provider_and_file_path(self):
        """Context should include provider and file_path when provided."""
        file_path = Path("/test/audio.mp3")
        exc = RuntimeError("Test error")
        result = map_provider_error(exc, "deepgram", file_path)

        assert isinstance(result, ProviderAPIError)
        assert result.context.get("provider") == "deepgram"
        assert str(file_path) in result.context.get("file_path", "")


class TestProviderErrorHandler:
    """Test provider_error_handler decorator."""

    @pytest.mark.asyncio
    async def test_decorator_passes_through_on_success(self):
        """Decorator should not modify successful results."""

        @provider_error_handler("test_provider")
        async def success_func(self, audio_file_path: Path, language: str = "en"):
            return "success"

        mock_self = MagicMock()
        result = await success_func(mock_self, Path("/test.mp3"))
        assert result == "success"

    @pytest.mark.asyncio
    async def test_decorator_extracts_file_path_from_args(self):
        """Decorator should extract file_path from positional args."""
        @provider_error_handler("test")
        async def failing_func(self, audio_file_path: Path, language: str = "en"):
            raise RuntimeError("Test error")

        mock_self = MagicMock()
        file_path = Path("/test/audio.mp3")

        with pytest.raises(ProviderAPIError) as exc_info:
            await failing_func(mock_self, file_path)

        assert str(file_path) in exc_info.value.context.get("file_path", "")

    @pytest.mark.asyncio
    async def test_decorator_extracts_file_path_from_kwargs(self):
        """Decorator should extract file_path from kwargs."""

        @provider_error_handler("test")
        async def failing_func(self, audio_file_path: Path, language: str = "en"):
            raise RuntimeError("Test error")

        mock_self = MagicMock()
        file_path = Path("/kwargs/audio.mp3")

        with pytest.raises(ProviderAPIError) as exc_info:
            await failing_func(mock_self, audio_file_path=file_path)

        assert str(file_path) in exc_info.value.context.get("file_path", "")

    @pytest.mark.asyncio
    async def test_decorator_passes_install_command(self):
        """Decorator should pass install_command for ImportError."""

        @provider_error_handler("deepgram", "uv add deepgram-sdk")
        async def import_failing_func(self, audio_file_path: Path, language: str = "en"):
            raise ImportError("No module named 'deepgram'")

        mock_self = MagicMock()

        with pytest.raises(ProviderNotAvailableError) as exc_info:
            await import_failing_func(mock_self, Path("/test.mp3"))

        assert exc_info.value.context.get("install_command") == "uv add deepgram-sdk"

    @pytest.mark.asyncio
    async def test_decorator_reraises_already_mapped_exceptions(self):
        """Already mapped exceptions should pass through unchanged."""
        original = ValidationError("Already mapped")

        @provider_error_handler("test")
        async def validation_failing_func(self, audio_file_path: Path, language: str = "en"):
            raise original

        mock_self = MagicMock()

        with pytest.raises(ValidationError) as exc_info:
            await validation_failing_func(mock_self, Path("/test.mp3"))

        assert exc_info.value is original

    @pytest.mark.asyncio
    async def test_decorator_preserves_exception_chain(self):
        """Decorator should preserve the exception chain with 'from exc'."""

        @provider_error_handler("test")
        async def chained_failing_func(self, audio_file_path: Path, language: str = "en"):
            raise RuntimeError("Original error")

        mock_self = MagicMock()

        with pytest.raises(ProviderAPIError) as exc_info:
            await chained_failing_func(mock_self, Path("/test.mp3"))

        assert exc_info.value.__cause__ is not None
        assert isinstance(exc_info.value.__cause__, RuntimeError)
