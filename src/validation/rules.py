"""Validation rules for file size limits and allowed formats.

This module re-exports constants from the canonical FileValidator implementation
to provide a convenient access point for validation rules.
"""

from __future__ import annotations

from src.utils.file_validation import FileValidator

# File extension rules - re-exported from FileValidator
AUDIO_EXTENSIONS = FileValidator.AUDIO_EXTENSIONS
VIDEO_EXTENSIONS = FileValidator.VIDEO_EXTENSIONS
MEDIA_EXTENSIONS = FileValidator.MEDIA_EXTENSIONS

# File size rules (in bytes) - re-exported from FileValidator
DEFAULT_MAX_FILE_SIZE = FileValidator.DEFAULT_MAX_FILE_SIZE

# Additional size limits for specific use cases
AUDIO_MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024  # 2GB
VIDEO_MAX_FILE_SIZE = 10 * 1024 * 1024 * 1024  # 10GB

__all__ = [
    "AUDIO_EXTENSIONS",
    "AUDIO_MAX_FILE_SIZE",
    "DEFAULT_MAX_FILE_SIZE",
    "MEDIA_EXTENSIONS",
    "VIDEO_EXTENSIONS",
    "VIDEO_MAX_FILE_SIZE",
]
