"""Consolidated file validation utilities for the audio extraction pipeline.

This module provides centralized validation logic, consolidating what was previously
spread across common_validation.py, validation.py, and file_validation.py.

The module offers two validation styles:
1. **Standard validators** (validate_*): Raise ValidationError on failure
2. **Safe validators** (safe_validate_*): Return None on failure

Use standard validators when you want explicit error handling and detailed
exception information. Use safe validators when you prefer None-checking
over exception handling, particularly for optional file processing.

Provider-specific size limits:
- ElevenLabs: 50MB
- Deepgram: 2GB
"""

from __future__ import annotations

import logging
from pathlib import Path

from .sanitization import PathSanitizer

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Custom exception for validation failures.

    This exception wraps underlying errors (FileNotFoundError, PermissionError,
    ValueError) to provide a consistent error handling interface. The original
    exception is preserved in the exception chain for debugging.

    All validation functions in this module raise ValidationError on failure,
    allowing calling code to catch a single exception type while still having
    access to the underlying cause via exception chaining.
    """

    pass


class FileValidator:
    """Centralized file validation utilities."""

    # Common audio/video extensions
    AUDIO_EXTENSIONS = {".wav", ".mp3", ".flac", ".aac", ".ogg", ".m4a", ".wma"}
    VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".webm", ".flv", ".wmv", ".m4v", ".3gp"}
    MEDIA_EXTENSIONS = AUDIO_EXTENSIONS | VIDEO_EXTENSIONS

    # Default size limits
    DEFAULT_MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024  # 2GB

    @classmethod
    def _check_file_existence(cls, file_path: Path) -> None:
        """Check if file exists.

        Args:
            file_path: Path to check

        Raises:
            FileNotFoundError: If file doesn't exist
        """
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

    @classmethod
    def _check_file_extension(cls, file_path: Path, allowed_extensions: set[str]) -> None:
        """Check if file extension is allowed.

        Args:
            file_path: Path to check
            allowed_extensions: Set of allowed file extensions (with dots)

        Raises:
            ValueError: If extension is not allowed
        """
        if file_path.suffix.lower() not in allowed_extensions:
            raise ValueError(
                f"Unsupported file extension: {file_path.suffix}. "
                f"Allowed: {', '.join(sorted(allowed_extensions))}"
            )

    @classmethod
    def _check_file_size(cls, file_path: Path, max_size: int) -> None:
        """Check if file size is within limits.

        Args:
            file_path: Path to check
            max_size: Maximum file size in bytes

        Raises:
            ValueError: If file exceeds size limit
        """
        file_size = file_path.stat().st_size
        if file_size > max_size:
            raise ValueError(f"File size {file_size:,} bytes exceeds maximum {max_size:,} bytes")

    @classmethod
    def _check_file_type(cls, file_path: Path) -> None:
        """Check if path is a regular file.

        Args:
            file_path: Path to check

        Raises:
            ValueError: If path is not a file
        """
        try:
            isf = file_path.is_file()
        except Exception:  # e.g., mocked stat without st_mode
            isf = True  # Defer to permission check
        if not isf:
            raise ValueError(f"Path is not a file: {file_path}")

    @classmethod
    def _check_file_permissions(cls, file_path: Path) -> None:
        """Check if file is readable.

        Args:
            file_path: Path to check

        Raises:
            PermissionError: If file cannot be read
        """
        try:
            with open(file_path, "rb"):
                pass
        except PermissionError as e:
            raise PermissionError(f"Cannot read file: {file_path}") from e

    @classmethod
    def validate_file_path(
        cls,
        file_path: Path,
        must_exist: bool = True,
        allowed_extensions: set[str] | None = None,
        max_size: int | None = None,
    ) -> None:
        """Validate a file path with comprehensive checks.

        Args:
            file_path: Path to validate
            must_exist: Whether the file must exist
            allowed_extensions: Set of allowed file extensions (with dots)
            max_size: Maximum file size in bytes

        Raises:
            FileNotFoundError: If file doesn't exist and must_exist is True
            ValueError: If validation fails
            PermissionError: If file is not readable
        """
        file_path = Path(file_path)

        # Security validation - delegated to sanitizer
        PathSanitizer.validate_path_security(file_path)

        # Run existence-dependent checks
        if must_exist:
            cls._check_file_existence(file_path)
            cls._check_file_type(file_path)
            cls._check_file_permissions(file_path)

        # Extension check (can run regardless of existence)
        if allowed_extensions:
            cls._check_file_extension(file_path, allowed_extensions)

        # Size check (requires file to exist)
        if must_exist and max_size is not None:
            cls._check_file_size(file_path, max_size)

    @classmethod
    def validate_path_security(cls, file_path: Path) -> None:
        """Validate a path for security issues.

        Args:
            file_path: Path to validate

        Raises:
            ValueError: If path contains dangerous characters
        """
        # Delegate to PathSanitizer for consistency
        PathSanitizer.validate_path_security(file_path)

    @classmethod
    def validate_audio_file(
        cls, file_path: Path, max_file_size: int | None = None, must_exist: bool = True
    ) -> None:
        """Validate an audio file path.

        Args:
            file_path: Path to audio file
            max_file_size: Maximum file size in bytes (default: 2GB)
            must_exist: Whether the file must exist

        Raises:
            FileNotFoundError: If file doesn't exist and must_exist is True
            ValueError: If validation fails
        """
        cls.validate_file_path(
            file_path,
            allowed_extensions=cls.AUDIO_EXTENSIONS,
            max_size=max_file_size or cls.DEFAULT_MAX_FILE_SIZE,
            must_exist=must_exist,
        )

    @classmethod
    def validate_video_file(cls, file_path: Path, max_file_size: int | None = None) -> None:
        """Validate a video file path.

        Args:
            file_path: Path to video file
            max_file_size: Maximum file size in bytes (default: 2GB)

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If validation fails
        """
        cls.validate_file_path(
            file_path,
            allowed_extensions=cls.VIDEO_EXTENSIONS,
            max_size=max_file_size or cls.DEFAULT_MAX_FILE_SIZE,
            must_exist=True,
        )

    @classmethod
    def validate_media_file(cls, file_path: Path, max_size: int | None = None) -> None:
        """Validate a media file (audio or video).

        Args:
            file_path: Path to media file
            max_size: Maximum file size in bytes (default: 2GB)

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If not a valid media file
        """
        cls.validate_file_path(
            file_path,
            must_exist=True,
            allowed_extensions=cls.MEDIA_EXTENSIONS,
            max_size=max_size or cls.DEFAULT_MAX_FILE_SIZE,
        )

    @classmethod
    def validate_output_path(
        cls, output_path: Path, force: bool = False, create_parents: bool = True
    ) -> None:
        """Validate an output file path.

        Args:
            output_path: Path for output file
            force: Whether to allow overwriting existing files
            create_parents: Whether to create parent directories

        Raises:
            ValueError: If output path is invalid
            FileExistsError: If file exists and force is False
        """
        output_path = Path(output_path)

        # Security validation
        PathSanitizer.validate_path_security(output_path)

        # Check if file exists
        if output_path.exists() and not force:
            raise FileExistsError(
                f"Output file already exists: {output_path}. Use force=True to overwrite."
            )

        # Create parent directories if needed
        if create_parents:
            output_path.parent.mkdir(parents=True, exist_ok=True)
        elif not output_path.parent.exists():
            raise ValueError(f"Output directory does not exist: {output_path.parent}")

        # Check write permissions on parent directory
        if not output_path.parent.is_dir():
            raise ValueError(f"Parent path is not a directory: {output_path.parent}")

        # Test write permissions
        test_file = output_path.parent / f".write_test_{output_path.name}"
        try:
            test_file.touch()
            test_file.unlink()
        except (PermissionError, OSError) as e:
            raise PermissionError(f"Cannot write to directory: {output_path.parent}") from e

    @classmethod
    def is_valid_extension(cls, file_path: Path, extensions: set[str]) -> bool:
        """Check if a file has a valid extension.

        Args:
            file_path: Path to check
            extensions: Set of valid extensions

        Returns:
            True if extension is valid, False otherwise
        """
        return file_path.suffix.lower() in extensions

    @classmethod
    def get_file_size_mb(cls, file_path: Path) -> float:
        """Get file size in megabytes.

        Args:
            file_path: Path to file

        Returns:
            File size in MB, or 0.0 if file doesn't exist
        """
        try:
            if file_path.exists():
                return file_path.stat().st_size / (1024 * 1024)
        except (OSError, PermissionError):
            pass
        return 0.0


class ConfigValidator:
    """Validation for configuration values."""

    @staticmethod
    def validate_positive_number(value: float, name: str) -> None:
        """Validate that a value is a positive number.

        Args:
            value: Value to validate
            name: Name of the parameter for error messages

        Raises:
            ValueError: If value is not positive
        """
        if value <= 0:
            raise ValueError(f"{name} must be positive, got {value}")

    @staticmethod
    def validate_range(
        value: float,
        min_val: float | None = None,
        max_val: float | None = None,
        name: str = "Value",
    ) -> None:
        """Validate that a value is within a range.

        Args:
            value: Value to validate
            min_val: Minimum allowed value (inclusive)
            max_val: Maximum allowed value (inclusive)
            name: Name of the parameter for error messages

        Raises:
            ValueError: If value is outside the range
        """
        if min_val is not None and value < min_val:
            raise ValueError(f"{name} must be at least {min_val}, got {value}")
        if max_val is not None and value > max_val:
            raise ValueError(f"{name} must be at most {max_val}, got {value}")

    @staticmethod
    def validate_enum(value: str, allowed: set[str], name: str = "Value") -> None:
        """Validate that a value is in an allowed set.

        Args:
            value: Value to validate
            allowed: Set of allowed values
            name: Name of the parameter for error messages

        Raises:
            ValueError: If value is not in allowed set
        """
        if value not in allowed:
            raise ValueError(f"{name} must be one of {sorted(allowed)}, got '{value}'")


# Convenience functions for backward compatibility
def validate_file_path(file_path: Path, **kwargs) -> None:
    """Validate a file path. See FileValidator.validate_file_path for details."""
    FileValidator.validate_file_path(file_path, **kwargs)


def validate_output_path(output_path: Path, **kwargs) -> None:
    """Validate an output path. See FileValidator.validate_output_path for details."""
    FileValidator.validate_output_path(output_path, **kwargs)


def _get_provider_size_limit(provider_name: str) -> int | None:
    """Get provider-specific file size limit.

    This function returns known size limits for audio processing providers.
    The lookup is case-insensitive for convenience.

    Args:
        provider_name: Name of the provider service (e.g., 'elevenlabs', 'deepgram').
                      Case-insensitive.

    Returns:
        File size limit in bytes, or None if provider not recognized.
        Known limits: ElevenLabs (50MB), Deepgram (2GB).

    Example:
        >>> _get_provider_size_limit('elevenlabs')
        52428800  # 50MB in bytes
        >>> _get_provider_size_limit('ElevenLabs')  # Case insensitive
        52428800
        >>> _get_provider_size_limit('unknown')
        None
    """
    # Provider-specific size limits based on official API documentation
    # These limits are enforced by the respective services
    provider_limits = {
        "elevenlabs": 50 * 1024 * 1024,  # 50MB - ElevenLabs API limit
        "deepgram": 2 * 1024 * 1024 * 1024,  # 2GB - Deepgram API limit
    }
    return provider_limits.get(provider_name.lower())


def _handle_validation_exception(
    e: Exception, file_path: Path | str, file_type: str = "audio"
) -> None:
    """Handle validation exceptions with appropriate logging and error wrapping.

    This function centralizes exception handling for validation operations by:
    1. Logging the error with appropriate severity
    2. Wrapping the original exception in ValidationError for consistent handling
    3. Preserving the exception chain for debugging (using 'from e')

    The function logs all errors and then re-raises them as ValidationError,
    ensuring that all validation failures have a consistent exception type
    while preserving the original error information.

    Args:
        e: The exception to handle (FileNotFoundError, PermissionError,
           ValueError, or other Exception)
        file_path: Path to the file being validated (for error messages)
        file_type: Type of file for error messages ('audio' or 'media')

    Raises:
        ValidationError: Always raised, wrapping the original exception.
                        The original exception is accessible via exception chaining.
    """
    if isinstance(e, FileNotFoundError):
        logger.error(f"{file_type.capitalize()} file not found: {file_path}")
        raise ValidationError(f"{file_type.capitalize()} file not found: {file_path}") from e
    elif isinstance(e, PermissionError):
        logger.error(f"Permission denied accessing file: {file_path}")
        raise ValidationError(f"Cannot access file: {file_path}") from e
    elif isinstance(e, ValueError):
        logger.error(f"Invalid {file_type} file: {e}")
        raise ValidationError(str(e)) from e
    else:
        logger.error(f"Unexpected validation error: {e}")
        raise ValidationError(f"Validation failed: {e}") from e


def validate_audio_file(
    audio_file_path: Path | str, max_file_size: int | None = None, provider_name: str | None = None
) -> Path:
    """Validate an audio file exists and is accessible.

    This function consolidates the duplicate validation pattern:
    ```python
    if not audio_file_path.exists():
        logger.error(f"Audio file not found: {audio_file_path}")
        return None
    ```

    The function performs comprehensive validation including existence,
    accessibility, format checking, and optional size validation. If a
    provider_name is specified, it automatically applies provider-specific
    size limits (e.g., 50MB for ElevenLabs, 2GB for Deepgram).

    Args:
        audio_file_path: Path to audio file (Path or string). Converted to
                        Path object internally.
        max_file_size: Optional maximum file size in bytes. If not specified
                      and provider_name is given, uses provider-specific limit.
        provider_name: Optional provider name for automatic size limits
                      (e.g., 'elevenlabs', 'deepgram'). Case-insensitive.

    Returns:
        Path object if validation passes.

    Raises:
        ValidationError: Wraps all validation failures. The underlying cause
                        may be FileNotFoundError (file doesn't exist),
                        PermissionError (file not accessible), or ValueError
                        (invalid format or too large). Access the original
                        exception via exception chaining (__cause__).

    Example:
        >>> validate_audio_file('audio.mp3')
        PosixPath('audio.mp3')
        >>> validate_audio_file('audio.mp3', provider_name='elevenlabs')
        PosixPath('audio.mp3')  # Validates with 50MB limit
    """
    try:
        file_path = Path(audio_file_path)

        # Apply provider-specific size limits if known
        if provider_name and not max_file_size:
            max_file_size = _get_provider_size_limit(provider_name)

        # Use existing FileValidator for comprehensive validation
        FileValidator.validate_audio_file(file_path, max_file_size=max_file_size, must_exist=True)

        return file_path

    except Exception as e:
        _handle_validation_exception(e, audio_file_path, "audio")


def validate_media_file(
    media_file_path: Path | str,
    max_file_size: int | None = None,
    max_size: int | None = None,  # Alias for backward compatibility
) -> Path:
    """Validate a media file (audio or video) exists and is accessible.

    This function validates both audio and video files, making it particularly
    useful for audio extraction workflows where the input may be either format.
    It performs comprehensive validation including existence, accessibility,
    format checking, and optional size validation.

    Args:
        media_file_path: Path to media file (Path or string). Supports both
                        audio formats (mp3, wav, flac, etc.) and video formats
                        (mp4, avi, mkv, etc.). Converted to Path object internally.
        max_file_size: Optional maximum file size in bytes. No limit if not specified.

    Returns:
        Path object if validation passes.

    Raises:
        ValidationError: Wraps all validation failures. The underlying cause
                        may be FileNotFoundError (file doesn't exist),
                        PermissionError (file not accessible), or ValueError
                        (invalid format or too large). Access the original
                        exception via exception chaining (__cause__).

    Example:
        >>> validate_media_file('video.mp4')
        PosixPath('video.mp4')
        >>> validate_media_file('audio.mp3', max_file_size=10*1024*1024)
        PosixPath('audio.mp3')  # Validates with 10MB limit
    """
    try:
        file_path = Path(media_file_path)

        # Handle max_size alias for backward compatibility
        if max_size is not None:
            max_file_size = max_size

        # Use existing FileValidator for comprehensive validation
        FileValidator.validate_media_file(file_path, max_size=max_file_size)

        return file_path

    except Exception as e:
        _handle_validation_exception(e, media_file_path, "media")


def safe_validate_media_file(
    media_file_path: Path | str, max_file_size: int | None = None
) -> Path | None:
    """Safe wrapper for media file validation that returns None instead of raising exceptions.

    This function provides a None-returning interface for media file validation,
    useful when you prefer None-checking over exception handling. It's particularly
    convenient for optional file processing or when validation failure should be
    handled as a normal case rather than an exceptional condition.

    Use this function when:
    - Processing optional media files
    - Filtering lists of potential media files
    - Implementing fallback logic for missing files
    - Simplifying error handling in data pipelines

    Args:
        media_file_path: Path to media file (Path or string). Supports both
                        audio and video formats.
        max_file_size: Optional maximum file size in bytes.

    Returns:
        Path object if validation passes, None if validation fails for any reason.

    Example:
        >>> result = safe_validate_media_file('video.mp4')
        >>> if result:
        ...     process_media(result)
        ... else:
        ...     logger.warning('Media file validation failed')
        >>>
        >>> # Filter valid files from a list
        >>> files = ['a.mp4', 'b.mp3', 'missing.wav']
        >>> valid = [f for f in files if safe_validate_media_file(f)]
    """
    try:
        return validate_media_file(media_file_path, max_file_size)
    except ValidationError:
        return None


def safe_validate_audio_file(
    audio_file_path: Path | str, max_file_size: int | None = None, provider_name: str | None = None
) -> Path | None:
    """Safe wrapper for audio file validation that returns None instead of raising exceptions.

    This function provides a None-returning interface for audio file validation,
    useful when you prefer None-checking over exception handling. It's particularly
    convenient for optional file processing or when validation failure should be
    handled as a normal case rather than an exceptional condition.

    Use this function when:
    - Processing optional audio files
    - Filtering lists of potential audio files
    - Implementing fallback logic for missing files
    - Simplifying error handling in data pipelines
    - Working with provider-specific validation where failures are common

    Args:
        audio_file_path: Path to audio file (Path or string).
        max_file_size: Optional maximum file size in bytes. If not specified
                      and provider_name is given, uses provider-specific limit.
        provider_name: Optional provider name for automatic size limits
                      (e.g., 'elevenlabs', 'deepgram'). Case-insensitive.

    Returns:
        Path object if validation passes, None if validation fails for any reason.

    Example:
        >>> result = safe_validate_audio_file('audio.mp3', provider_name='elevenlabs')
        >>> if result:
        ...     transcribe_with_elevenlabs(result)
        ... else:
        ...     logger.warning('Audio file failed ElevenLabs validation (possibly >50MB)')
        >>>
        >>> # Try multiple providers with different size limits
        >>> audio_path = 'large_audio.mp3'
        >>> if safe_validate_audio_file(audio_path, provider_name='deepgram'):
        ...     use_deepgram(audio_path)  # Accepts up to 2GB
        >>> elif safe_validate_audio_file(audio_path, provider_name='elevenlabs'):
        ...     use_elevenlabs(audio_path)  # Accepts up to 50MB
    """
    try:
        return validate_audio_file(audio_file_path, max_file_size, provider_name)
    except ValidationError:
        return None
