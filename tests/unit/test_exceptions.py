"""
Tests for custom exception hierarchy.

This module tests the exception hierarchy defined in src.exceptions,
verifying that all exceptions can be created, inherit correctly,
and preserve context and error chaining.
"""

from __future__ import annotations
import pytest

from src.exceptions import (
    # Base
    AudioAnalysisError,
    # Audio Extraction
    AudioExtractionError,
    FFmpegNotFoundError,
    FFmpegExecutionError,
    AudioExtractionTimeout,
    UnsupportedAudioFormatError,
    AudioFileCorruptedError,
    # Transcription
    TranscriptionError,
    ProviderError,
    ProviderNotAvailableError,
    ProviderAuthenticationError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderAPIError,
    TranscriptionFormatError,
    # Validation
    ValidationError,
    FileNotFoundError,
    FileAccessError,
    FileSizeError,
    PathTraversalError,
    # Cache
    CacheError,
    CacheWriteError,
    CacheReadError,
    CacheCorruptionError,
    # URL Ingestion
    UrlIngestionError,
    UrlDownloadError,
    UnsupportedUrlError,
    # Configuration
    ConfigurationError,
    InvalidConfigError,
    MissingConfigError,
    # Analysis
    AnalysisError,
    AnalysisTimeoutError,
    AnalysisFormatError,
)


class TestBaseException:
    """Test base AudioAnalysisError exception."""

    def test_create_with_message_only(self):
        """Test creating exception with just a message."""
        error = AudioAnalysisError("Something went wrong")

        assert str(error) == "Something went wrong"
        assert error.message == "Something went wrong"
        assert error.context == {}
        assert error.original_error is None

    def test_create_with_context(self):
        """Test creating exception with context dictionary."""
        error = AudioAnalysisError(
            "Processing failed", context={"file": "test.mp3", "size_mb": 10.5}
        )

        assert error.message == "Processing failed"
        assert error.context["file"] == "test.mp3"
        assert error.context["size_mb"] == 10.5

    def test_create_with_original_error(self):
        """Test creating exception with original error chaining."""
        original = ValueError("Invalid input")
        error = AudioAnalysisError("Failed to process", original_error=original)

        assert error.original_error is original
        assert isinstance(error.original_error, ValueError)

    def test_create_with_all_parameters(self):
        """Test creating exception with all parameters."""
        original = IOError("File not found")
        error = AudioAnalysisError(
            "Complete failure",
            context={"path": "/test/file.mp3", "operation": "read"},
            original_error=original,
        )

        assert error.message == "Complete failure"
        assert error.context["path"] == "/test/file.mp3"
        assert error.context["operation"] == "read"
        assert error.original_error is original


class TestAudioExtractionExceptions:
    """Test audio extraction exception hierarchy."""

    def test_ffmpeg_not_found_error_creation(self):
        """Test FFmpegNotFoundError can be created with context."""
        error = FFmpegNotFoundError("FFmpeg not in PATH", context={"video_path": "/test/video.mp4"})

        assert error.message == "FFmpeg not in PATH"
        assert error.context["video_path"] == "/test/video.mp4"
        assert isinstance(error, AudioExtractionError)
        assert isinstance(error, AudioAnalysisError)

    def test_ffmpeg_execution_error_with_details(self):
        """Test FFmpegExecutionError stores execution details."""
        error = FFmpegExecutionError(
            "FFmpeg failed",
            context={
                "return_code": 1,
                "stderr": "Invalid codec",
                "command": ["ffmpeg", "-i", "test.mp4"],
            },
        )

        assert error.context["return_code"] == 1
        assert "Invalid codec" in error.context["stderr"]

    def test_audio_extraction_timeout(self):
        """Test AudioExtractionTimeout."""
        error = AudioExtractionTimeout("Extraction timed out", context={"timeout_seconds": 300})

        assert error.context["timeout_seconds"] == 300
        assert isinstance(error, AudioExtractionError)

    def test_unsupported_format_error(self):
        """Test UnsupportedAudioFormatError."""
        error = UnsupportedAudioFormatError(
            "Format not supported", context={"format": "unknown", "file": "test.xyz"}
        )

        assert error.context["format"] == "unknown"

    def test_audio_file_corrupted_error(self):
        """Test AudioFileCorruptedError."""
        error = AudioFileCorruptedError("File is corrupted", context={"file": "broken.mp3"})

        assert "broken.mp3" in error.context["file"]


class TestTranscriptionExceptions:
    """Test transcription exception hierarchy."""

    def test_provider_not_available_error(self):
        """Test ProviderNotAvailableError with provider context."""
        error = ProviderNotAvailableError(
            "Whisper not installed",
            context={
                "provider": "whisper",
                "missing_module": "whisper",
                "install_command": "pip install openai-whisper",
            },
        )

        assert error.context["provider"] == "whisper"
        assert "whisper" in error.context["missing_module"]
        assert isinstance(error, ProviderError)
        assert isinstance(error, TranscriptionError)

    def test_provider_authentication_error(self):
        """Test ProviderAuthenticationError."""
        error = ProviderAuthenticationError("Invalid API key", context={"provider": "deepgram"})

        assert error.context["provider"] == "deepgram"
        assert isinstance(error, ProviderError)

    def test_provider_rate_limit_error(self):
        """Test ProviderRateLimitError."""
        error = ProviderRateLimitError(
            "Rate limit exceeded",
            context={"provider": "elevenlabs", "retry_after": 60},
        )

        assert error.context["retry_after"] == 60

    def test_provider_timeout_error(self):
        """Test ProviderTimeoutError."""
        error = ProviderTimeoutError(
            "Request timed out", context={"provider": "deepgram", "timeout": 30}
        )

        assert error.context["timeout"] == 30

    def test_provider_api_error_with_http_details(self):
        """Test ProviderAPIError stores HTTP status code and response."""
        error = ProviderAPIError(
            "API request failed",
            status_code=429,
            response_body='{"error": "rate_limit_exceeded"}',
            context={"provider": "deepgram"},
        )

        assert error.status_code == 429
        assert "rate_limit_exceeded" in error.response_body
        assert error.context["provider"] == "deepgram"
        assert isinstance(error, ProviderError)

    def test_transcription_format_error(self):
        """Test TranscriptionFormatError."""
        error = TranscriptionFormatError(
            "Invalid response format", context={"expected": "json", "received": "text"}
        )

        assert error.context["expected"] == "json"


class TestValidationExceptions:
    """Test validation exception hierarchy."""

    def test_file_not_found_error(self):
        """Test FileNotFoundError."""
        error = FileNotFoundError("File not found", context={"path": "/missing.mp3"})

        assert error.context["path"] == "/missing.mp3"
        assert isinstance(error, ValidationError)

    def test_file_access_error(self):
        """Test FileAccessError."""
        error = FileAccessError(
            "Permission denied", context={"path": "/restricted/file.mp3", "mode": "read"}
        )

        assert error.context["mode"] == "read"

    def test_file_size_error(self):
        """Test FileSizeError."""
        error = FileSizeError(
            "File too large",
            context={"path": "huge.mp4", "size_mb": 5000, "limit_mb": 1000},
        )

        assert error.context["size_mb"] == 5000
        assert error.context["limit_mb"] == 1000

    def test_path_traversal_error(self):
        """Test PathTraversalError."""
        error = PathTraversalError("Path traversal detected", context={"path": "../../etc/passwd"})

        assert "../../etc/passwd" in error.context["path"]


class TestCacheExceptions:
    """Test cache exception hierarchy."""

    def test_cache_write_error(self):
        """Test CacheWriteError."""
        error = CacheWriteError(
            "Failed to write cache", context={"key": "test_key", "backend": "redis"}
        )

        assert error.context["backend"] == "redis"
        assert isinstance(error, CacheError)

    def test_cache_read_error(self):
        """Test CacheReadError."""
        error = CacheReadError("Cache miss", context={"key": "missing_key"})

        assert error.context["key"] == "missing_key"

    def test_cache_corruption_error(self):
        """Test CacheCorruptionError."""
        error = CacheCorruptionError(
            "Cache data corrupted", context={"key": "corrupted", "error": "decode_error"}
        )

        assert "corrupted" in error.context["key"]


class TestUrlIngestionExceptions:
    """Test URL ingestion exception hierarchy."""

    def test_url_download_error(self):
        """Test UrlDownloadError."""
        error = UrlDownloadError(
            "Download failed",
            context={"url": "https://youtube.com/watch?v=123", "status_code": 404},
        )

        assert "youtube.com" in error.context["url"]
        assert isinstance(error, UrlIngestionError)

    def test_unsupported_url_error(self):
        """Test UnsupportedUrlError."""
        error = UnsupportedUrlError(
            "URL not supported", context={"url": "https://unknown.com/video"}
        )

        assert "unknown.com" in error.context["url"]


class TestConfigurationExceptions:
    """Test configuration exception hierarchy."""

    def test_invalid_config_error(self):
        """Test InvalidConfigError."""
        error = InvalidConfigError(
            "Invalid quality setting",
            context={"key": "quality", "value": "invalid", "allowed": ["low", "high"]},
        )

        assert error.context["key"] == "quality"
        assert isinstance(error, ConfigurationError)

    def test_missing_config_error(self):
        """Test MissingConfigError."""
        error = MissingConfigError(
            "Required config missing", context={"key": "api_key", "config_file": ".env"}
        )

        assert error.context["key"] == "api_key"


class TestAnalysisExceptions:
    """Test analysis exception hierarchy."""

    def test_analysis_timeout_error(self):
        """Test AnalysisTimeoutError."""
        error = AnalysisTimeoutError(
            "Analysis timed out", context={"timeout": 120, "transcript_length": 10000}
        )

        assert error.context["timeout"] == 120
        assert isinstance(error, AnalysisError)

    def test_analysis_format_error(self):
        """Test AnalysisFormatError."""
        error = AnalysisFormatError(
            "Invalid output format", context={"format": "invalid", "expected": "json"}
        )

        assert error.context["format"] == "invalid"


class TestExceptionInheritance:
    """Test exception hierarchy relationships."""

    def test_all_inherit_from_base(self):
        """All custom exceptions should inherit from AudioAnalysisError."""
        exceptions = [
            # Audio Extraction
            AudioExtractionError,
            FFmpegNotFoundError,
            FFmpegExecutionError,
            AudioExtractionTimeout,
            UnsupportedAudioFormatError,
            AudioFileCorruptedError,
            # Transcription
            TranscriptionError,
            ProviderError,
            ProviderNotAvailableError,
            ProviderAuthenticationError,
            ProviderRateLimitError,
            ProviderTimeoutError,
            ProviderAPIError,
            TranscriptionFormatError,
            # Validation
            ValidationError,
            FileNotFoundError,
            FileAccessError,
            FileSizeError,
            PathTraversalError,
            # Cache
            CacheError,
            CacheWriteError,
            CacheReadError,
            CacheCorruptionError,
            # URL Ingestion
            UrlIngestionError,
            UrlDownloadError,
            UnsupportedUrlError,
            # Configuration
            ConfigurationError,
            InvalidConfigError,
            MissingConfigError,
            # Analysis
            AnalysisError,
            AnalysisTimeoutError,
            AnalysisFormatError,
        ]

        for exc_class in exceptions:
            assert issubclass(
                exc_class, AudioAnalysisError
            ), f"{exc_class.__name__} should inherit from AudioAnalysisError"
            assert issubclass(
                exc_class, Exception
            ), f"{exc_class.__name__} should inherit from Exception"

    def test_specific_inheritance_chains(self):
        """Test specific inheritance relationships."""
        # Audio extraction chain
        assert issubclass(FFmpegNotFoundError, AudioExtractionError)
        assert issubclass(AudioExtractionError, AudioAnalysisError)

        # Transcription chain
        assert issubclass(ProviderAuthenticationError, ProviderError)
        assert issubclass(ProviderError, TranscriptionError)
        assert issubclass(TranscriptionError, AudioAnalysisError)

        # Validation chain
        assert issubclass(FileNotFoundError, ValidationError)
        assert issubclass(ValidationError, AudioAnalysisError)

        # Cache chain
        assert issubclass(CacheWriteError, CacheError)
        assert issubclass(CacheError, AudioAnalysisError)


class TestExceptionChaining:
    """Test exception chaining with 'from' keyword."""

    def test_exception_chain_with_original_error(self):
        """Test that original_error preserves exception chain."""
        try:
            raise ValueError("Original error")
        except ValueError as original:
            error = FFmpegNotFoundError("FFmpeg not found", original_error=original)

            assert error.original_error is original
            assert isinstance(error.original_error, ValueError)
            assert str(error.original_error) == "Original error"

    def test_can_raise_with_from_clause(self):
        """Test raising with 'from' clause for proper exception chaining."""
        with pytest.raises(AudioExtractionError) as exc_info:
            try:
                raise IOError("Disk full")
            except IOError as e:
                raise AudioExtractionError("Extraction failed", original_error=e) from e

        # Verify exception chain
        assert exc_info.value.original_error is not None
        assert isinstance(exc_info.value.original_error, IOError)


class TestExceptionMessages:
    """Test exception message handling."""

    def test_exception_str_returns_message(self):
        """Test that str(exception) returns the message."""
        error = AudioAnalysisError("Test message")
        assert str(error) == "Test message"

    def test_exception_repr_contains_class_name(self):
        """Test that repr(exception) contains useful information."""
        error = FFmpegNotFoundError("FFmpeg missing")
        repr_str = repr(error)

        assert "FFmpegNotFoundError" in repr_str

    def test_context_not_in_str(self):
        """Test that context is separate from message string."""
        error = AudioAnalysisError("Message", context={"key": "value"})

        # Message should be clean
        assert str(error) == "Message"
        # But context should be accessible
        assert error.context["key"] == "value"
