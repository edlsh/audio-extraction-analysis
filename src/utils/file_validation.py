"""File validation utilities for audio/video files."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.utils.logger import get_logger

from ..exceptions import ValidationError
from .formatting import get_file_size_bytes
from .sanitization import PathSanitizer

logger = get_logger(__name__)


class FileValidator:
    """File validation utilities for audio/video files."""

    AUDIO_EXTENSIONS = {".wav", ".mp3", ".flac", ".aac", ".ogg", ".m4a", ".wma"}
    VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".webm", ".flv", ".wmv", ".m4v", ".3gp"}
    MEDIA_EXTENSIONS = AUDIO_EXTENSIONS | VIDEO_EXTENSIONS
    DEFAULT_MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024  # 2GB

    @classmethod
    def _check_file_existence(cls, file_path: Path) -> None:
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

    @classmethod
    def _check_file_extension(cls, file_path: Path, allowed_extensions: set[str]) -> None:
        if file_path.suffix.lower() not in allowed_extensions:
            raise ValueError(
                f"Unsupported file extension: {file_path.suffix}. "
                f"Allowed: {', '.join(sorted(allowed_extensions))}"
            )

    @classmethod
    def _check_file_size(cls, file_path: Path, max_size: int) -> None:
        file_size = get_file_size_bytes(file_path)
        if file_size > max_size:
            raise ValueError(f"File size {file_size:,} bytes exceeds maximum {max_size:,} bytes")

    @classmethod
    def _check_file_type(cls, file_path: Path) -> None:
        try:
            isf = file_path.is_file()
        except Exception as e:
            logger.debug(f"File stat check failed, deferring to permission check: {e}")
            isf = True
        if not isf:
            raise ValueError(f"Path is not a file: {file_path}")

    @classmethod
    def _check_file_permissions(cls, file_path: Path) -> None:
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
        """Validate a file path with comprehensive checks."""
        file_path = Path(file_path)
        PathSanitizer.validate_path_security(file_path)

        if must_exist:
            cls._check_file_existence(file_path)
            cls._check_file_type(file_path)
            cls._check_file_permissions(file_path)

        if allowed_extensions:
            cls._check_file_extension(file_path, allowed_extensions)

        if must_exist and max_size is not None:
            cls._check_file_size(file_path, max_size)

    @classmethod
    def validate_path_security(cls, file_path: Path) -> None:
        """Validate a path for security issues."""
        PathSanitizer.validate_path_security(file_path)

    @classmethod
    def validate_audio_file(
        cls, file_path: Path, max_file_size: int | None = None, must_exist: bool = True
    ) -> None:
        """Validate an audio file path."""
        cls.validate_file_path(
            file_path,
            allowed_extensions=cls.AUDIO_EXTENSIONS,
            max_size=max_file_size or cls.DEFAULT_MAX_FILE_SIZE,
            must_exist=must_exist,
        )

    @classmethod
    def validate_video_file(cls, file_path: Path, max_file_size: int | None = None) -> None:
        """Validate a video file path."""
        cls.validate_file_path(
            file_path,
            allowed_extensions=cls.VIDEO_EXTENSIONS,
            max_size=max_file_size or cls.DEFAULT_MAX_FILE_SIZE,
            must_exist=True,
        )

    @classmethod
    def validate_media_file(cls, file_path: Path, max_size: int | None = None) -> None:
        """Validate a media file (audio or video)."""
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
        """Validate an output file path."""
        output_path = Path(output_path)
        PathSanitizer.validate_path_security(output_path)

        if output_path.exists() and not force:
            raise FileExistsError(
                f"Output file already exists: {output_path}. Use force=True to overwrite."
            )

        if create_parents:
            output_path.parent.mkdir(parents=True, exist_ok=True)
        elif not output_path.parent.exists():
            raise ValueError(f"Output directory does not exist: {output_path.parent}")

        if not output_path.parent.is_dir():
            raise ValueError(f"Parent path is not a directory: {output_path.parent}")

        test_file = output_path.parent / f".write_test_{output_path.name}"
        try:
            test_file.touch()
            test_file.unlink()
        except (PermissionError, OSError) as e:
            raise PermissionError(f"Cannot write to directory: {output_path.parent}") from e

    @classmethod
    def is_valid_extension(cls, file_path: Path, extensions: set[str]) -> bool:
        """Check if a file has a valid extension."""
        return file_path.suffix.lower() in extensions

    @classmethod
    def get_file_size_mb(cls, file_path: Path) -> float:
        """Get file size in megabytes."""
        try:
            if file_path.exists():
                return file_path.stat().st_size / (1024 * 1024)
        except (OSError, PermissionError) as e:
            logger.debug(f"File size check failed for {file_path}: {e}")
        return 0.0


class ConfigValidator:
    """Validation for configuration values."""

    @staticmethod
    def validate_positive_number(value: float, name: str) -> None:
        """Validate that a value is a positive number."""
        if value <= 0:
            raise ValueError(f"{name} must be positive, got {value}")

    @staticmethod
    def validate_range(
        value: float,
        min_val: float | None = None,
        max_val: float | None = None,
        name: str = "Value",
    ) -> None:
        """Validate that a value is within a range."""
        if min_val is not None and value < min_val:
            raise ValueError(f"{name} must be at least {min_val}, got {value}")
        if max_val is not None and value > max_val:
            raise ValueError(f"{name} must be at most {max_val}, got {value}")

    @staticmethod
    def validate_enum(value: str, allowed: set[str], name: str = "Value") -> None:
        """Validate that a value is in an allowed set."""
        if value not in allowed:
            raise ValueError(f"{name} must be one of {sorted(allowed)}, got '{value}'")


# Provider size limits
_PROVIDER_SIZE_LIMITS = {
    "elevenlabs": 50 * 1024 * 1024,  # 50MB
    "deepgram": 2 * 1024 * 1024 * 1024,  # 2GB
}


def _get_provider_size_limit(provider_name: str) -> int | None:
    """Get provider-specific file size limit."""
    return _PROVIDER_SIZE_LIMITS.get(provider_name.lower())


def _wrap_validation_error(e: Exception, file_path: Path | str, file_type: str = "audio") -> None:
    """Wrap validation exceptions in ValidationError."""
    file_path_str = str(file_path)

    if isinstance(e, FileNotFoundError):
        logger.error(f"{file_type.capitalize()} file not found: {file_path}")
        raise ValidationError(
            f"{file_type.capitalize()} file not found: {file_path}",
            context={"file_path": file_path_str, "error_type": "not_found"},
            original_error=e,
        ) from e
    elif isinstance(e, PermissionError):
        logger.error(f"Permission denied accessing file: {file_path}")
        raise ValidationError(
            f"Cannot access file: {file_path}",
            context={"file_path": file_path_str, "error_type": "permission_denied"},
            original_error=e,
        ) from e
    elif isinstance(e, ValueError):
        logger.error(f"Invalid {file_type} file: {e}")
        raise ValidationError(
            str(e),
            context={"file_path": file_path_str, "error_type": "invalid_file"},
            original_error=e,
        ) from e
    else:
        logger.error(f"Unexpected validation error: {e}")
        raise ValidationError(
            f"Validation failed: {e}",
            context={"file_path": file_path_str, "error_type": "unexpected"},
            original_error=e,
        ) from e


# Convenience functions
def validate_file_path(file_path: Path, **kwargs: Any) -> None:
    """Validate a file path."""
    FileValidator.validate_file_path(file_path, **kwargs)


def validate_output_path(output_path: Path, **kwargs: Any) -> None:
    """Validate an output path."""
    FileValidator.validate_output_path(output_path, **kwargs)


def validate_audio_file(
    audio_file_path: Path | str, max_file_size: int | None = None, provider_name: str | None = None
) -> Path:
    """Validate an audio file exists and is accessible. Returns Path on success."""
    try:
        file_path = Path(audio_file_path)
        if provider_name and not max_file_size:
            max_file_size = _get_provider_size_limit(provider_name)
        FileValidator.validate_audio_file(file_path, max_file_size=max_file_size, must_exist=True)
        return file_path
    except Exception as e:
        _wrap_validation_error(e, audio_file_path, "audio")
        raise


def validate_media_file(
    media_file_path: Path | str,
    max_file_size: int | None = None,
    max_size: int | None = None,
) -> Path:
    """Validate a media file (audio or video) exists and is accessible. Returns Path on success."""
    try:
        file_path = Path(media_file_path)
        if max_size is not None:
            max_file_size = max_size
        FileValidator.validate_media_file(file_path, max_size=max_file_size)
        return file_path
    except Exception as e:
        _wrap_validation_error(e, media_file_path, "media")
        raise


def safe_validate_media_file(
    media_file_path: Path | str, max_file_size: int | None = None
) -> Path | None:
    """Validate media file, returning None on failure instead of raising."""
    try:
        return validate_media_file(media_file_path, max_file_size)
    except ValidationError:
        return None


def safe_validate_audio_file(
    audio_file_path: Path | str, max_file_size: int | None = None, provider_name: str | None = None
) -> Path | None:
    """Validate audio file, returning None on failure instead of raising."""
    try:
        return validate_audio_file(audio_file_path, max_file_size, provider_name)
    except ValidationError:
        return None


def validate_audio_file_or_raise(
    audio_file_path: Path | str,
    max_file_size: int | None = None,
    provider_name: str | None = None,
) -> Path:
    """Validate audio file and raise ValidationError with context if invalid."""
    validated_path = safe_validate_audio_file(audio_file_path, max_file_size, provider_name)
    if validated_path is None:
        context: dict[str, str] = {"file_path": str(audio_file_path)}
        if provider_name:
            context["provider"] = provider_name
        raise ValidationError(
            f"Audio file validation failed: {audio_file_path}",
            context=context,
        )
    return validated_path


def validate_media_file_or_raise(
    media_file_path: Path | str,
    max_file_size: int | None = None,
) -> Path:
    """Validate media file and raise ValidationError with context if invalid."""
    validated_path = safe_validate_media_file(media_file_path, max_file_size)
    if validated_path is None:
        raise ValidationError(
            f"Media file validation failed: {media_file_path}",
            context={"file_path": str(media_file_path)},
        )
    return validated_path
