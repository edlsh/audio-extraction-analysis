"""Simplified configuration management using environment variables."""

import os
import tempfile
import threading
from dataclasses import dataclass, field
from pathlib import Path

from src.utils.logger import get_logger

logger = get_logger(__name__)


def _parse_bool(value: str | bool | None) -> bool:
    """Parse boolean value from various formats."""
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, str):
        return value.lower() in ("true", "1", "yes", "on", "enabled")
    return bool(value)


def _parse_list(value: str | list[str] | None, delimiter: str = ",") -> list[str]:
    """Parse list value from string or return as-is if already a list."""
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        return [item.strip() for item in value.split(delimiter) if item.strip()]
    return [] if value is None else [value]


def _getenv(key: str, default: str = "") -> str:
    """Get environment variable with default."""
    return os.getenv(key, default)


def _getenv_int(key: str, default: int) -> int:
    """Get integer environment variable with validation.

    Args:
        key: Environment variable name
        default: Default value if not set

    Returns:
        Parsed integer value

    Raises:
        ValueError: If value cannot be parsed as integer
    """
    value = os.getenv(key)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError as e:
        raise ValueError(
            f"Invalid integer value for {key}='{value}'. Expected integer, got: {value}"
        ) from e


def _getenv_float(key: str, default: float) -> float:
    """Get float environment variable with validation.

    Args:
        key: Environment variable name
        default: Default value if not set

    Returns:
        Parsed float value

    Raises:
        ValueError: If value cannot be parsed as float
    """
    value = os.getenv(key)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError as e:
        raise ValueError(
            f"Invalid float value for {key}='{value}'. Expected float, got: {value}"
        ) from e


@dataclass
class Config:
    """Application configuration loaded from environment variables."""

    # ========== Application Settings ==========
    environment: str = field(default_factory=lambda: _getenv("ENVIRONMENT", "production"))

    # ========== Paths ==========
    data_dir: Path = field(default_factory=lambda: Path(_getenv("DATA_DIR", "./data")))
    cache_dir: Path = field(default_factory=lambda: Path(_getenv("CACHE_DIR", "./cache")))
    temp_dir: Path = field(
        default_factory=lambda: Path(_getenv("TEMP_DIR") or tempfile.gettempdir())
    )

    # ========== File Handling ==========
    max_file_size: int = field(default_factory=lambda: _getenv_int("MAX_FILE_SIZE", 100000000))
    allowed_extensions: list[str] = field(
        default_factory=lambda: _parse_list(
            _getenv("ALLOWED_EXTENSIONS", ".mp3,.wav,.m4a,.flac,.ogg,.aac")
        )
    )

    # ========== Logging ==========
    log_level: str = field(default_factory=lambda: _getenv("LOG_LEVEL", "INFO").upper())

    # ========== Provider Settings ==========
    default_provider: str = field(
        default_factory=lambda: _getenv("DEFAULT_TRANSCRIPTION_PROVIDER", "deepgram")
    )
    default_language: str = field(default_factory=lambda: _getenv("DEFAULT_LANGUAGE", "en"))

    # ========== Feature Flags ==========
    enable_health_checks: bool = field(
        default_factory=lambda: _parse_bool(_getenv("ENABLE_HEALTH_CHECKS", "true"))
    )

    # ========== API Keys ==========
    DEEPGRAM_API_KEY: str | None = field(
        default_factory=lambda: _getenv("DEEPGRAM_API_KEY") or None
    )
    ELEVENLABS_API_KEY: str | None = field(
        default_factory=lambda: _getenv("ELEVENLABS_API_KEY") or None
    )
    GEMINI_API_KEY: str | None = field(default_factory=lambda: _getenv("GEMINI_API_KEY") or None)

    # ========== Security Settings ==========
    rate_limit_window: int = field(default_factory=lambda: _getenv_int("RATE_LIMIT_WINDOW", 60))
    rate_limit_max_requests: int = field(
        default_factory=lambda: _getenv_int("RATE_LIMIT_MAX_REQUESTS", 100)
    )

    # ========== Performance Settings ==========
    max_workers: int = field(default_factory=lambda: _getenv_int("MAX_WORKERS", 4))
    max_concurrent_requests: int = field(
        default_factory=lambda: _getenv_int("MAX_CONCURRENT_REQUESTS", 10)
    )
    thread_pool_size: int = field(default_factory=lambda: _getenv_int("THREAD_POOL_SIZE", 10))
    process_pool_size: int = field(default_factory=lambda: _getenv_int("PROCESS_POOL_SIZE", 4))

    # ========== Timeout Settings ==========
    global_timeout: int = field(default_factory=lambda: _getenv_int("GLOBAL_TIMEOUT", 600))
    connect_timeout: int = field(default_factory=lambda: _getenv_int("CONNECT_TIMEOUT", 10))
    read_timeout: int = field(default_factory=lambda: _getenv_int("READ_TIMEOUT", 30))
    write_timeout: int = field(default_factory=lambda: _getenv_int("WRITE_TIMEOUT", 30))
    ffmpeg_timeout_seconds: int = field(
        default_factory=lambda: _getenv_int("FFMPEG_TIMEOUT_SECONDS", 600)
    )
    ffmpeg_terminate_grace_seconds: int = field(
        default_factory=lambda: _getenv_int("FFMPEG_TERMINATE_GRACE_SECONDS", 5)
    )
    transcription_timeout_seconds: int = field(
        default_factory=lambda: _getenv_int("TRANSCRIPTION_TIMEOUT_SECONDS", 300)
    )

    # ========== Retry Settings ==========
    max_retries: int = field(default_factory=lambda: _getenv_int("MAX_API_RETRIES", 3))
    retry_delay: float = field(default_factory=lambda: _getenv_float("API_RETRY_DELAY", 1.0))
    max_retry_delay: float = field(default_factory=lambda: _getenv_float("MAX_RETRY_DELAY", 60.0))
    retry_exponential_base: float = field(
        default_factory=lambda: _getenv_float("RETRY_EXPONENTIAL_BASE", 2.0)
    )
    retry_jitter: bool = field(
        default_factory=lambda: _parse_bool(_getenv("RETRY_JITTER_ENABLED", "true"))
    )

    # ========== Batch Processing ==========
    batch_size: int = field(default_factory=lambda: _getenv_int("BATCH_SIZE", 5))

    # ========== Caching ==========
    cache_ttl: int = field(default_factory=lambda: _getenv_int("CACHE_TTL", 3600))
    cache_max_size: int = field(default_factory=lambda: _getenv_int("CACHE_MAX_SIZE", 1000))

    # ========== UI Settings ==========
    output_format: str = field(default_factory=lambda: _getenv("OUTPUT_FORMAT", "text").lower())
    verbose: bool = field(default_factory=lambda: _parse_bool(_getenv("VERBOSE", "false")))
    debug: bool = field(default_factory=lambda: _parse_bool(_getenv("DEBUG", "false")))

    # ========== URL Ingestion Settings ==========
    url_ingest_enabled: bool = field(
        default_factory=lambda: _parse_bool(_getenv("URL_INGEST_ENABLED", "true"))
    )
    url_ingest_download_dir: Path = field(
        default_factory=lambda: Path(_getenv("URL_INGEST_DOWNLOAD_DIR", "./data/url_downloads"))
    )
    url_ingest_prefer_audio_only: bool = field(
        default_factory=lambda: _parse_bool(_getenv("URL_INGEST_PREFER_AUDIO_ONLY", "true"))
    )
    url_ingest_timeout: int = field(default_factory=lambda: _getenv_int("URL_INGEST_TIMEOUT", 600))
    url_ingest_keep_video_default: bool = field(
        default_factory=lambda: _parse_bool(_getenv("URL_INGEST_KEEP_VIDEO_DEFAULT", "false"))
    )

    # ========== Provider-Specific Settings ==========
    ELEVENLABS_TIMEOUT: int = field(default_factory=lambda: _getenv_int("ELEVENLABS_TIMEOUT", 600))
    WHISPER_MODEL: str = field(default_factory=lambda: _getenv("WHISPER_MODEL", "base"))
    WHISPER_DEVICE: str = field(default_factory=lambda: _getenv("WHISPER_DEVICE", "cpu"))
    WHISPER_COMPUTE_TYPE: str = field(
        default_factory=lambda: _getenv("WHISPER_COMPUTE_TYPE", "int8")
    )

    def __post_init__(self) -> None:
        """Validate configuration and ensure required directories exist."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self._validate_enums()
        self._validate_positive_values()
        self._validate_timeouts()
        self._validate_retry_settings()
        self._validate_environment()

    def _validate_enums(self) -> None:
        """Validate enum-like string fields."""
        valid_log_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if self.log_level not in valid_log_levels:
            raise ValueError(
                f"Invalid LOG_LEVEL='{self.log_level}'. "
                f"Must be one of: {', '.join(sorted(valid_log_levels))}"
            )

        valid_formats = {"text", "json", "markdown", "csv"}
        if self.output_format not in valid_formats:
            raise ValueError(
                f"Invalid OUTPUT_FORMAT='{self.output_format}'. "
                f"Must be one of: {', '.join(sorted(valid_formats))}"
            )

    def _validate_positive_values(self) -> None:
        """Validate fields that must be positive."""
        positive_fields = [
            ("MAX_FILE_SIZE", self.max_file_size),
            ("MAX_WORKERS", self.max_workers),
            ("MAX_CONCURRENT_REQUESTS", self.max_concurrent_requests),
            ("THREAD_POOL_SIZE", self.thread_pool_size),
            ("PROCESS_POOL_SIZE", self.process_pool_size),
            ("RATE_LIMIT_WINDOW", self.rate_limit_window),
            ("RATE_LIMIT_MAX_REQUESTS", self.rate_limit_max_requests),
            ("CACHE_TTL", self.cache_ttl),
            ("CACHE_MAX_SIZE", self.cache_max_size),
            ("BATCH_SIZE", self.batch_size),
            ("FFMPEG_TIMEOUT_SECONDS", self.ffmpeg_timeout_seconds),
            ("FFMPEG_TERMINATE_GRACE_SECONDS", self.ffmpeg_terminate_grace_seconds),
            ("TRANSCRIPTION_TIMEOUT_SECONDS", self.transcription_timeout_seconds),
        ]
        for name, value in positive_fields:
            if value <= 0:
                raise ValueError(f"{name} must be positive, got: {value}")

    def _validate_timeouts(self) -> None:
        """Validate timeout consistency."""
        timeout_checks = [
            ("CONNECT_TIMEOUT", self.connect_timeout),
            ("READ_TIMEOUT", self.read_timeout),
            ("WRITE_TIMEOUT", self.write_timeout),
        ]
        for name, value in timeout_checks:
            if value > self.global_timeout:
                raise ValueError(
                    f"{name} ({value}s) cannot exceed GLOBAL_TIMEOUT ({self.global_timeout}s)"
                )

    def _validate_retry_settings(self) -> None:
        """Validate retry configuration."""
        if self.max_retries < 0:
            raise ValueError(f"MAX_API_RETRIES must be non-negative, got: {self.max_retries}")

        if self.retry_delay < 0:
            raise ValueError(f"API_RETRY_DELAY must be non-negative, got: {self.retry_delay}")

        if self.max_retry_delay < self.retry_delay:
            raise ValueError(
                f"MAX_RETRY_DELAY ({self.max_retry_delay}s) must be >= "
                f"API_RETRY_DELAY ({self.retry_delay}s)"
            )

        if self.retry_exponential_base <= 1.0:
            raise ValueError(
                f"RETRY_EXPONENTIAL_BASE must be > 1.0, got: {self.retry_exponential_base}"
            )

    def _validate_environment(self) -> None:
        """Validate environment setting."""
        valid_environments = {"development", "staging", "production", "test"}
        if self.environment.lower() not in valid_environments:
            import warnings

            warnings.warn(
                f"Environment '{self.environment}' is not standard. "
                f"Consider using: {', '.join(sorted(valid_environments))}",
                UserWarning,
                stacklevel=2,
            )

    def __repr__(self) -> str:
        """Return repr with redacted API keys for security."""
        sensitive_fields = {
            "DEEPGRAM_API_KEY",
            "ELEVENLABS_API_KEY",
            "GEMINI_API_KEY",
        }
        items = []
        for field_name in self.__dataclass_fields__:
            value = getattr(self, field_name)
            if field_name in sensitive_fields and value:
                items.append(f"{field_name}='***REDACTED***'")
            else:
                items.append(f"{field_name}={value!r}")
        return f"Config({', '.join(items)})"

    @property
    def HEALTH_CHECK_ENABLED(self) -> bool:
        """Get health check enabled setting."""
        return self.enable_health_checks


# Singleton instance with thread-safe initialization
_config_instance: Config | None = None
_config_lock = threading.Lock()
_dotenv_loaded = False


def _load_dotenv_once() -> None:
    """Load .env into environment, if present, once per process."""
    global _dotenv_loaded
    if _dotenv_loaded:
        return
    try:
        from dotenv import find_dotenv, load_dotenv

        dotenv_path = find_dotenv(usecwd=True)
        if dotenv_path:
            load_dotenv(dotenv_path, override=False)
        else:
            load_dotenv(override=False)
    except ImportError:
        # python-dotenv is optional at runtime
        logger.debug("python-dotenv not installed, skipping .env loading")
    except Exception as e:
        # Log any other dotenv load errors
        logger.debug("Failed to load .env file: %s", e)
    _dotenv_loaded = True


def get_config() -> Config:
    """Get global config instance (singleton pattern, thread-safe)."""
    global _config_instance
    if _config_instance is None:
        with _config_lock:
            # Double-check pattern to prevent race conditions
            if _config_instance is None:
                _load_dotenv_once()
                _config_instance = Config()
    return _config_instance


def _reset_config() -> None:
    """Reset singleton instance. For testing purposes only."""
    global _config_instance
    with _config_lock:
        _config_instance = None


# For backward compatibility with __init__.py exports
__all__ = ["Config", "_reset_config", "get_config"]
