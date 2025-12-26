"""Provider logging patterns and helpers.

This module provides standardized logging patterns for providers,
ensuring consistent log format across all implementations.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.utils.logger import get_logger, log_api_call

logger = get_logger(__name__)


class ProviderLogger:
    """Standardized logger for transcription providers.

    This class provides consistent logging patterns across providers:
    - Operation logging (transcribe, health_check)
    - API call logging
    - Error context logging
    - Performance metrics logging
    """

    def __init__(self, provider_name: str) -> None:
        """Initialize provider logger.

        Args:
            provider_name: Name of the provider (e.g., "deepgram", "elevenlabs")
        """
        self.provider_name = provider_name
        self._logger = get_logger(f"src.providers.{provider_name}")

    def log_transcribe_start(self, file_path: Path, language: str = "en") -> None:
        """Log transcription operation start.

        Args:
            file_path: Path to audio file
            language: Language code
        """
        log_api_call(
            self._logger,
            provider=self.provider_name,
            method="transcribe",
            status="started",
            file_path=str(file_path),
            language=language,
        )

    def log_transcribe_complete(
        self, file_path: Path, duration_seconds: float, word_count: int | None = None
    ) -> None:
        """Log transcription operation completion.

        Args:
            file_path: Path to audio file
            duration_seconds: Audio duration in seconds
            word_count: Optional word count
        """
        log_api_call(
            self._logger,
            provider=self.provider_name,
            method="transcribe",
            status="completed",
            file_path=str(file_path),
            duration_seconds=duration_seconds,
            word_count=word_count,
        )

    def log_transcribe_error(self, file_path: Path, error: Exception) -> None:
        """Log transcription operation error.

        Args:
            file_path: Path to audio file
            error: Exception that occurred
        """
        log_api_call(
            self._logger,
            provider=self.provider_name,
            method="transcribe",
            status="failed",
            file_path=str(file_path),
            error=str(error),
            error_type=type(error).__name__,
        )

    def log_health_check_start(self) -> None:
        """Log health check operation start."""
        log_api_call(
            self._logger,
            provider=self.provider_name,
            method="health_check",
            status="started",
        )

    def log_health_check_result(self, healthy: bool, **details: Any) -> None:
        """Log health check result.

        Args:
            healthy: Whether provider is healthy
            **details: Additional details (latency, version, etc.)
        """
        log_api_call(
            self._logger,
            provider=self.provider_name,
            method="health_check",
            status="success" if healthy else "failed",
            **details,
        )

    def log_api_error(self, method: str, error: Exception, **context: Any) -> None:
        """Log API error with context.

        Args:
            method: API method name
            error: Exception that occurred
            **context: Additional context
        """
        self._logger.error(
            {
                "api_call": True,
                "provider": self.provider_name,
                "method": method,
                "status": "failed",
                "error": str(error),
                "error_type": type(error).__name__,
                **context,
            }
        )


def get_provider_logger(provider_name: str) -> ProviderLogger:
    """Get a provider logger instance.

    Args:
        provider_name: Name of the provider

    Returns:
        ProviderLogger instance

    Usage:
        from src.providers.logging import get_provider_logger

        logger = get_provider_logger("deepgram")
        logger.log_transcribe_start(audio_file)
    """
    return ProviderLogger(provider_name)


__all__ = ["ProviderLogger", "get_provider_logger"]
