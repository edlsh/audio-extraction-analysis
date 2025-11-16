"""
Custom exception hierarchy for audio-extraction-analysis.

This module defines the exception hierarchy used throughout the application.
All custom exceptions should inherit from AudioAnalysisError.
"""

from __future__ import annotations
from typing import Any, Optional


class AudioAnalysisError(Exception):
    """Base exception for all audio-extraction-analysis errors.

    All custom exceptions in this application should inherit from this class.
    This enables catching all application-specific errors with a single except clause.
    """

    def __init__(
        self,
        message: str,
        *,
        context: Optional[dict[str, Any]] = None,
        original_error: Optional[Exception] = None,
    ) -> None:
        """Initialize exception with message and optional context.

        Args:
            message: Human-readable error message
            context: Additional context for debugging (file paths, IDs, etc.)
            original_error: Original exception that caused this error

        Example:
            >>> raise AudioAnalysisError(
            ...     "Processing failed",
            ...     context={"file": "audio.mp3", "size_mb": 150},
            ...     original_error=original_exc
            ... )
        """
        super().__init__(message)
        self.message = message
        self.context = context or {}
        self.original_error = original_error


# ============================================================================
# Audio Extraction Errors
# ============================================================================


class AudioExtractionError(AudioAnalysisError):
    """Base exception for audio extraction operations."""


class FFmpegNotFoundError(AudioExtractionError):
    """FFmpeg executable not found in PATH.

    Raised when FFmpeg is required but not installed or not accessible.
    """


class FFmpegExecutionError(AudioExtractionError):
    """FFmpeg execution failed.

    Raised when FFmpeg returns a non-zero exit code or fails to process audio.
    """


class AudioExtractionTimeout(AudioExtractionError):
    """Audio extraction operation timed out.

    Raised when audio extraction exceeds the configured timeout period.
    """


class UnsupportedAudioFormatError(AudioExtractionError):
    """Audio format not supported.

    Raised when attempting to process an unsupported audio/video format.
    """


class AudioFileCorruptedError(AudioExtractionError):
    """Audio file is corrupted or unreadable.

    Raised when FFmpeg cannot parse the input file due to corruption.
    """


# ============================================================================
# Transcription Errors
# ============================================================================


class TranscriptionError(AudioAnalysisError):
    """Base exception for transcription operations."""


class ProviderError(TranscriptionError):
    """Base exception for transcription provider errors."""


class ProviderNotAvailableError(ProviderError):
    """Transcription provider is not available or not installed.

    Raised when a provider is requested but its dependencies are not installed.
    """


class ProviderAuthenticationError(ProviderError):
    """Provider authentication failed.

    Raised when API key is invalid, missing, or expired.
    """


class ProviderRateLimitError(ProviderError):
    """Provider rate limit exceeded.

    Raised when the provider's rate limit is hit. Requests should be retried
    after a backoff period.
    """


class ProviderTimeoutError(ProviderError):
    """Provider request timed out.

    Raised when a provider request exceeds the timeout period.
    """


class ProviderAPIError(ProviderError):
    """Provider API returned an error.

    Raised when the provider API returns an error response.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: Optional[int] = None,
        response_body: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize provider API error with HTTP details.

        Args:
            message: Error message
            status_code: HTTP status code
            response_body: Response body content
            **kwargs: Additional context
        """
        super().__init__(message, **kwargs)
        self.status_code = status_code
        self.response_body = response_body


class TranscriptionFormatError(TranscriptionError):
    """Transcription result format is invalid.

    Raised when the provider returns a response in an unexpected format.
    """


class TranscriptionServiceError(TranscriptionError):
    """Service-level transcription errors.

    Raised for errors in the TranscriptionService layer (not provider-specific).
    """


class ProviderSelectionError(TranscriptionServiceError):
    """Failed to auto-select a suitable provider.

    Raised when the service cannot automatically select a provider
    (e.g., no providers available, no providers support the file format).
    """


class ProviderValidationError(TranscriptionServiceError):
    """Provider cannot handle the requested file.

    Raised when a specific provider is requested but cannot process
    the given audio file (e.g., unsupported format, file too large).
    """


# ============================================================================
# File Validation Errors
# ============================================================================


class ValidationError(AudioAnalysisError):
    """Base exception for validation errors."""


class FileNotFoundError(ValidationError):  # noqa: A001
    """File not found at specified path.

    Note: This shadows the builtin FileNotFoundError for consistency.
    """


class FileAccessError(ValidationError):
    """Cannot access file (permissions).

    Raised when the file exists but cannot be read or written due to permissions.
    """


class FileSizeError(ValidationError):
    """File size exceeds limits.

    Raised when a file is too large to process.
    """


class PathTraversalError(ValidationError):
    """Path traversal attempt detected.

    Raised when a path contains components that would escape the allowed directory.
    """


# ============================================================================
# Cache Errors
# ============================================================================


class CacheError(AudioAnalysisError):
    """Base exception for cache operations."""


class CacheWriteError(CacheError):
    """Failed to write to cache.

    Raised when a cache write operation fails.
    """


class CacheReadError(CacheError):
    """Failed to read from cache.

    Raised when a cache read operation fails.
    """


class CacheCorruptionError(CacheError):
    """Cache data is corrupted.

    Raised when cached data cannot be deserialized or is invalid.
    """


# ============================================================================
# URL Ingestion Errors
# ============================================================================


class UrlIngestionError(AudioAnalysisError):
    """Error during URL ingestion.

    Raised when downloading or processing content from a URL fails.
    """


class UrlDownloadError(UrlIngestionError):
    """Failed to download from URL.

    Raised when yt-dlp or other download mechanism fails.
    """


class UnsupportedUrlError(UrlIngestionError):
    """URL format not supported.

    Raised when the URL is not a supported video/audio platform.
    """


# ============================================================================
# Configuration Errors
# ============================================================================


class ConfigurationError(AudioAnalysisError):
    """Base exception for configuration errors."""


class InvalidConfigError(ConfigurationError):
    """Configuration value is invalid.

    Raised when a configuration value fails validation.
    """


class MissingConfigError(ConfigurationError):
    """Required configuration is missing.

    Raised when a required configuration key is not present.
    """


# ============================================================================
# Analysis Errors
# ============================================================================


class AnalysisError(AudioAnalysisError):
    """Base exception for analysis operations."""


class AnalysisTimeoutError(AnalysisError):
    """Analysis operation timed out.

    Raised when transcript analysis exceeds timeout.
    """


class AnalysisFormatError(AnalysisError):
    """Analysis output format is invalid.

    Raised when the analysis result cannot be properly formatted.
    """


# ============================================================================
# Public API
# ============================================================================

__all__ = [
    # Base
    "AudioAnalysisError",
    # Audio Extraction
    "AudioExtractionError",
    "FFmpegNotFoundError",
    "FFmpegExecutionError",
    "AudioExtractionTimeout",
    "UnsupportedAudioFormatError",
    "AudioFileCorruptedError",
    # Transcription
    "TranscriptionError",
    "ProviderError",
    "ProviderNotAvailableError",
    "ProviderAuthenticationError",
    "ProviderRateLimitError",
    "ProviderTimeoutError",
    "ProviderAPIError",
    "TranscriptionFormatError",
    "TranscriptionServiceError",
    "ProviderSelectionError",
    "ProviderValidationError",
    # Validation
    "ValidationError",
    "FileNotFoundError",
    "FileAccessError",
    "FileSizeError",
    "PathTraversalError",
    # Cache
    "CacheError",
    "CacheWriteError",
    "CacheReadError",
    "CacheCorruptionError",
    # URL Ingestion
    "UrlIngestionError",
    "UrlDownloadError",
    "UnsupportedUrlError",
    # Configuration
    "ConfigurationError",
    "InvalidConfigError",
    "MissingConfigError",
    # Analysis
    "AnalysisError",
    "AnalysisTimeoutError",
    "AnalysisFormatError",
]
