"""Validation package for file and configuration validation.

This package consolidates validation logic that was previously scattered
across multiple modules, providing a single source of truth for validation
rules and validators.

Public API:
    - FileValidator: Core file validation utilities
    - ConfigValidator: Configuration value validation
    - validate_file_path: Standalone file path validator
    - validate_audio_file: Audio file validator
    - validate_media_file: Media file validator
"""

from .file_validators import (
    validate_audio_file,
    validate_audio_file_or_raise,
    validate_file_path,
    validate_media_file,
    validate_output_path,
)
from .rules import (
    AUDIO_EXTENSIONS,
    DEFAULT_MAX_FILE_SIZE,
    MEDIA_EXTENSIONS,
    VIDEO_EXTENSIONS,
)
from .validators import ConfigValidator, FileValidator

__all__ = [
    "AUDIO_EXTENSIONS",
    "DEFAULT_MAX_FILE_SIZE",
    "MEDIA_EXTENSIONS",
    "VIDEO_EXTENSIONS",
    "ConfigValidator",
    "FileValidator",
    "validate_audio_file",
    "validate_audio_file_or_raise",
    "validate_file_path",
    "validate_media_file",
    "validate_output_path",
]
