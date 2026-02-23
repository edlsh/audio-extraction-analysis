"""Centralized constants for timeouts, limits, and other magic numbers.

This module consolidates hardcoded values that were scattered across the codebase.
These constants can be overridden via environment variables through the Config class.

Usage:
    from src.utils.constants import Timeouts, Limits

    # Or access via config for env-overridable values:
    from src.config import get_config
    config = get_config()
    timeout = config.global_timeout
"""

from __future__ import annotations


class Timeouts:
    """Timeout constants in seconds.

    These are fallback defaults. For configurable timeouts, use Config class.
    """

    # FFmpeg operations
    FFMPEG_VERSION_CHECK: int = 10  # Quick version check
    FFMPEG_PROBE: int = 30  # Probing media files
    FFMPEG_EXTRACTION: int = 600  # Audio extraction (10 minutes)
    FFMPEG_TERMINATE_GRACE: int = 5  # Grace period before kill

    # Provider operations
    TRANSCRIPTION_DEFAULT: float = 300.0  # 5 minutes
    HEALTH_CHECK: int = 30  # Health check timeout

    # Network operations
    CONNECT: int = 10
    READ: int = 30
    WRITE: int = 30

    # URL ingestion
    URL_INGEST: int = 600  # 10 minutes for downloading


class AnalysisConstants:
    """Constants for analysis heuristics."""

    # Action item detection (tuple for immutability)
    ACTION_KEYWORDS: tuple[str, ...] = (
        "should",
        "need to",
        "must",
        "will",
        "plan to",
        "going to",
        "have to",
        "recommend",
        "priority",
        "action",
        "ensure",
        "verify",
    )

    # Summary generation
    SUMMARY_SENTENCE_COUNT: int = 3
    SUMMARY_CHAR_LIMIT: int = 300

    # Highlight extraction
    MIN_SENTENCE_WORDS: int = 15
    MAX_SENTENCE_CHARS: int = 200
    TOP_HIGHLIGHTS_COUNT: int = 5


class MediaLimits:
    """Media file limits and constraints."""

    MAX_FILE_SIZE_BYTES: int = 2 * 1024 * 1024 * 1024  # 2GB

    ALLOWED_VIDEO_EXTENSIONS: set[str] = {
        ".mp4",
        ".avi",
        ".mov",
        ".mkv",
        ".webm",
        ".flv",
        ".wmv",
        ".m4v",
        ".3gp",
    }

    ALLOWED_AUDIO_EXTENSIONS: set[str] = {
        ".mp3",
        ".wav",
        ".flac",
        ".m4a",
        ".aac",
        ".ogg",
        ".wma",
        ".opus",
    }

    @classmethod
    def get_allowed_extensions(cls) -> set[str]:
        return cls.ALLOWED_VIDEO_EXTENSIONS | cls.ALLOWED_AUDIO_EXTENSIONS


class Limits:
    """Size and count limits."""

    # File sizes (in bytes unless noted)
    MAX_FILE_SIZE_MB: int = 50  # ElevenLabs limit
    CHUNK_SIZE: int = 1024 * 1024  # 1MB chunks for streaming
    FILE_HASH_CHUNK_SIZE: int = 65536  # 64KB chunks for file hashing
    MAX_MEMORY_BUFFER: int = 50 * 1024 * 1024  # 50MB max in-memory

    # Retry limits
    MAX_RETRY_ATTEMPTS: int = 10  # Absolute maximum
    MAX_RETRY_DELAY: int = 300  # 5 minutes max delay

    # Concurrency
    DEFAULT_THREAD_POOL_SIZE: int = 4
    DEFAULT_MAX_WORKERS: int = 4

    # Content limits
    MAX_CHAPTERS: int = 300
    MAX_TOPICS: int = 100

    # Cache limits
    PROBE_CACHE_TTL: float = 60.0  # FFmpeg probe cache TTL in seconds


class UIConstants:
    """UI-related constants."""

    # Log ring buffer
    MAX_LOG_ENTRIES: int = 2000  # Maximum log entries to keep in TUI state

    # Chapter generation
    CHAPTER_INTERVAL_SECONDS: int = 300  # 5 minutes between chapter markers


class PathSanitizationConstants:
    """Path and filename sanitization constants."""

    MAX_FILENAME_LENGTH: int = 200  # Maximum length for sanitized filenames
    MAX_DIRNAME_LENGTH: int = 100  # Maximum length for sanitized directory names


class RetryDefaults:
    """Default retry configuration values."""

    MAX_ATTEMPTS: int = 3
    BASE_DELAY: float = 1.0
    MAX_DELAY: float = 60.0
    EXPONENTIAL_BASE: float = 2.0
    JITTER: bool = True

    # Network-specific retry settings
    NETWORK_MAX_DELAY: float = 30.0


class HTTPStatusCodes:
    """HTTP status codes that trigger specific behaviors."""

    # Retriable status codes (temporary failures)
    RETRIABLE: frozenset[int] = frozenset({
        408,  # Request Timeout
        429,  # Too Many Requests
        500,  # Internal Server Error
        502,  # Bad Gateway
        503,  # Service Unavailable
        504,  # Gateway Timeout
    })

    # Authentication errors
    UNAUTHORIZED: int = 401
    FORBIDDEN: int = 403

    # Rate limiting
    TOO_MANY_REQUESTS: int = 429


__all__ = [
    "AnalysisConstants",
    "HTTPStatusCodes",
    "Limits",
    "MediaLimits",
    "PathSanitizationConstants",
    "RetryDefaults",
    "Timeouts",
    "UIConstants",
]
