"""
Tests for CLI error handlers.

This module tests the error handling functions in src.cli.error_handlers,
verifying that exceptions are properly handled and user-friendly messages
are displayed.
"""

from __future__ import annotations

import sys
from io import StringIO

import pytest

from src.error_handlers import (
    handle_audio_extraction_error,
    handle_cli_error,
    handle_ffmpeg_error,
    handle_provider_api_error,
    handle_provider_error,
    handle_validation_error,
)
from src.exceptions import (
    AudioExtractionError,
    FFmpegExecutionError,
    FFmpegNotFoundError,
    FileNotFoundError,
    ProviderAPIError,
    ProviderAuthenticationError,
    ProviderNotAvailableError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ValidationError,
)


class TestValidationErrorHandler:
    """Test validation error handling."""

    def test_handle_file_not_found(self, capsys):
        """Test handling of file not found errors."""
        error = FileNotFoundError("File not found", context={"path": "/missing.mp3"})

        handle_validation_error(error)

        captured = capsys.readouterr()
        assert "Invalid input" in captured.err
        assert "File not found" in captured.err
        assert "Check that the file path is correct" in captured.err

    def test_handle_permission_error(self, capsys):
        """Test handling of permission errors."""
        error = ValidationError("Permission denied", context={"path": "/restricted/file.mp3"})

        handle_validation_error(error)

        captured = capsys.readouterr()
        assert "Invalid input" in captured.err
        assert "Permission denied" in captured.err
        assert "Check file permissions" in captured.err

    def test_handle_file_size_error(self, capsys):
        """Test handling of file size errors."""
        error = ValidationError("File size exceeds limit", context={"size_mb": 5000, "limit": 1000})

        handle_validation_error(error)

        captured = capsys.readouterr()
        assert "Invalid input" in captured.err
        assert "size" in captured.err.lower()


class TestFFmpegErrorHandler:
    """Test FFmpeg error handling."""

    def test_handle_ffmpeg_not_found(self, capsys):
        """Test handling of FFmpeg not found errors."""
        error = FFmpegNotFoundError("FFmpeg not in PATH", context={"video_path": "/test/video.mp4"})

        handle_ffmpeg_error(error)

        captured = capsys.readouterr()
        assert "FFmpeg Error" in captured.err
        assert "required but not installed" in captured.err
        assert "brew install ffmpeg" in captured.err

    def test_handle_ffmpeg_execution_error(self, capsys):
        """Test handling of FFmpeg execution errors."""
        error = FFmpegExecutionError(
            "FFmpeg failed", context={"video_path": "/test/video.mp4", "stderr": "Invalid codec"}
        )

        handle_ffmpeg_error(error)

        captured = capsys.readouterr()
        assert "FFmpeg Error" in captured.err
        assert "FFmpeg failed" in captured.err
        assert "Invalid codec" in captured.err


class TestAudioExtractionErrorHandler:
    """Test audio extraction error handling."""

    def test_handle_extraction_error_with_context(self, capsys):
        """Test handling extraction errors with context."""
        error = AudioExtractionError(
            "Extraction failed", context={"video_path": "/test/video.mp4", "timeout": 300}
        )

        handle_audio_extraction_error(error)

        captured = capsys.readouterr()
        assert "Extraction Error" in captured.err
        assert "Extraction failed" in captured.err
        assert "/test/video.mp4" in captured.err
        assert "300" in captured.err


class TestProviderErrorHandler:
    """Test provider error handling."""

    def test_handle_provider_not_available(self, capsys):
        """Test handling of provider not available errors."""
        error = ProviderNotAvailableError(
            "Whisper not installed",
            context={
                "provider_name": "whisper",
                "missing_module": "whisper",
                "available_providers": ["deepgram", "elevenlabs"],
            },
        )

        handle_provider_error(error)

        captured = capsys.readouterr()
        assert "Provider Error" in captured.err
        assert "Whisper not installed" in captured.err
        assert "deepgram, elevenlabs" in captured.err
        assert "Missing dependency: whisper" in captured.err

    def test_handle_provider_authentication_error(self, capsys):
        """Test handling of provider authentication errors."""
        error = ProviderAuthenticationError(
            "Invalid API key", context={"provider_name": "deepgram"}
        )

        handle_provider_error(error)

        captured = capsys.readouterr()
        assert "Provider Error" in captured.err
        assert "Invalid API key" in captured.err
        assert "Check your API key configuration" in captured.err
        assert "DEEPGRAM_API_KEY" in captured.err


class TestProviderAPIErrorHandler:
    """Test provider API error handling."""

    def test_handle_api_error_with_status_code(self, capsys):
        """Test handling API errors with HTTP status codes."""
        error = ProviderAPIError(
            "API request failed", status_code=429, context={"provider": "deepgram"}
        )

        handle_provider_api_error(error)

        captured = capsys.readouterr()
        assert "API Error" in captured.err
        assert "429" in captured.err
        assert "Rate limit" in captured.err

    def test_handle_api_error_401(self, capsys):
        """Test handling 401 unauthorized errors."""
        error = ProviderAPIError("Unauthorized", status_code=401)

        handle_provider_api_error(error)

        captured = capsys.readouterr()
        assert "API Error" in captured.err
        assert "Check your API key" in captured.err

    def test_handle_api_error_503(self, capsys):
        """Test handling 503 service unavailable errors."""
        error = ProviderAPIError("Service unavailable", status_code=503)

        handle_provider_api_error(error)

        captured = capsys.readouterr()
        assert "API Error" in captured.err
        assert "temporarily unavailable" in captured.err


class TestCLIErrorHandler:
    """Test main CLI error handler dispatcher."""

    def test_handle_keyboard_interrupt(self):
        """Test handling of KeyboardInterrupt."""
        error = KeyboardInterrupt()

        with pytest.raises(SystemExit) as exc_info:
            handle_cli_error(error, "test")

        assert exc_info.value.code == 130  # Standard SIGINT exit code

    def test_handle_validation_error_dispatch(self, capsys):
        """Test that ValidationError is dispatched correctly."""
        error = ValidationError("Test error")

        exit_code = handle_cli_error(error, "test")

        assert exit_code == 1
        captured = capsys.readouterr()
        assert "Invalid input" in captured.err

    def test_handle_ffmpeg_not_found_dispatch(self, capsys):
        """Test that FFmpegNotFoundError is dispatched correctly."""
        error = FFmpegNotFoundError("FFmpeg missing")

        exit_code = handle_cli_error(error, "test")

        assert exit_code == 1
        captured = capsys.readouterr()
        assert "FFmpeg Error" in captured.err

    def test_handle_provider_not_available_dispatch(self, capsys):
        """Test that ProviderNotAvailableError is dispatched correctly."""
        error = ProviderNotAvailableError("Provider missing")

        exit_code = handle_cli_error(error, "test")

        assert exit_code == 1
        captured = capsys.readouterr()
        assert "Provider Error" in captured.err

    def test_handle_rate_limit_error(self, capsys):
        """Test handling of rate limit errors."""
        error = ProviderRateLimitError("Rate limit exceeded")

        exit_code = handle_cli_error(error, "test")

        assert exit_code == 1
        captured = capsys.readouterr()
        assert "Rate Limit" in captured.err
        assert "Wait a few minutes" in captured.err

    def test_handle_timeout_error(self, capsys):
        """Test handling of timeout errors."""
        error = ProviderTimeoutError("Request timed out")

        exit_code = handle_cli_error(error, "test")

        assert exit_code == 1
        captured = capsys.readouterr()
        assert "Timeout" in captured.err

    def test_handle_unexpected_error(self, capsys):
        """Test handling of unexpected errors."""
        error = RuntimeError("Unexpected error")

        exit_code = handle_cli_error(error, "test_command")

        assert exit_code == 1
        captured = capsys.readouterr()
        assert "unexpected error" in captured.err.lower()
        assert "test_command" in captured.err
        assert "report this issue" in captured.err.lower()
