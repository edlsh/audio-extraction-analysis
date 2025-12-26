"""Standalone validation functions wrapping validator classes.

This module provides convenient standalone functions that wrap the FileValidator
and ConfigValidator classes for backward compatibility and ease of use.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.exceptions import ValidationError
from src.utils.logger import get_logger

from .rules import DEFAULT_MAX_FILE_SIZE
from .validators import FileValidator

logger = get_logger(__name__)


def _get_provider_size_limit(provider_name: str) -> int | None:
    """Get provider-specific file size limit."""
    provider_limits = {
        "elevenlabs": 50 * 1024 * 1024,  # 50MB
        "deepgram": 2 * 1024 * 1024 * 1024,  # 2GB
    }
    return provider_limits.get(provider_name.lower())


def validate_file_path(file_path: Path, **kwargs: Any) -> None:
    """Validate a file path. See FileValidator.validate_file_path for details."""
    FileValidator.validate_file_path(file_path, **kwargs)


def validate_output_path(output_path: Path, **kwargs: Any) -> None:
    """Validate an output path. See FileValidator.validate_output_path for details."""
    FileValidator.validate_output_path(output_path, **kwargs)


def validate_media_file(file_path: Path, max_size: int | None = None) -> None:
    """Validate a media file (audio or video)."""
    FileValidator.validate_media_file(file_path, max_size or DEFAULT_MAX_FILE_SIZE)


def validate_audio_file(
    audio_file_path: Path | str,
    max_file_size: int | None = None,
    provider_name: str | None = None,
) -> Path:
    """Validate an audio file exists and is accessible.

    Args:
        audio_file_path: Path to audio file
        max_file_size: Maximum file size in bytes
        provider_name: Optional provider name for automatic size limits

    Returns:
        Path object if validation passes

    Raises:
        ValidationError: Wraps all validation failures
    """
    try:
        file_path = Path(audio_file_path)

        if provider_name and not max_file_size:
            max_file_size = _get_provider_size_limit(provider_name)

        FileValidator.validate_audio_file(file_path, max_file_size, must_exist=True)
        return file_path
    except (FileNotFoundError, PermissionError, ValueError) as e:
        logger.error(f"Audio file validation failed: {audio_file_path} - {e}")
        raise ValidationError(
            f"Invalid audio file: {e}",
            context={"file_path": str(audio_file_path)},
        ) from e


def validate_audio_file_or_raise(file_path: Path, provider_name: str = "generic") -> Path:
    """Validate an audio file path and raise on failure.

    This function centralizes the validation pattern that was duplicated
    across multiple provider implementations.

    Args:
        file_path: Path to validate
        provider_name: Provider name for error messages

    Returns:
        Validated path object

    Raises:
        ValidationError: If validation fails
        FileNotFoundError: If file doesn't exist
        PermissionError: If file not accessible
    """
    try:
        return validate_audio_file(file_path, provider_name=provider_name)
    except ValidationError:
        raise


__all__ = [
    "validate_audio_file",
    "validate_audio_file_or_raise",
    "validate_file_path",
    "validate_media_file",
    "validate_output_path",
]
