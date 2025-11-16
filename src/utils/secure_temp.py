"""Secure temporary file handling utilities.

This module provides secure patterns for temporary file creation with:
- Restrictive file permissions (0600)
- Guaranteed cleanup via context managers
- No predictable filenames
- Proper error handling
"""

from __future__ import annotations

import logging
import tempfile
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

logger = logging.getLogger(__name__)


@contextmanager
def secure_temp_file(
    suffix: str = "", prefix: str = "audio-", dir: Path | None = None, permissions: int = 0o600
) -> Generator[Path, None, None]:
    """Create secure temporary file with restrictive permissions.

    This context manager ensures:
    - Secure file creation via mkstemp (no race conditions)
    - Restrictive permissions (default 0600 = owner read/write only)
    - Guaranteed cleanup even on exceptions
    - No predictable filenames

    Args:
        suffix: Filename suffix (e.g., ".mp3")
        prefix: Filename prefix (e.g., "audio-")
        dir: Directory for temp file (defaults to system temp dir)
        permissions: File permissions in octal (default 0o600)

    Yields:
        Path to secure temporary file

    Example:
        >>> with secure_temp_file(suffix=".mp3") as temp_path:
        ...     # Use temp file
        ...     process_audio(temp_path)
        ... # File automatically deleted here
    """
    # Create secure temp file
    fd, path_str = tempfile.mkstemp(suffix=suffix, prefix=prefix, dir=str(dir) if dir else None)

    # Close file descriptor immediately (we only need the path)
    import os

    os.close(fd)

    temp_path = Path(path_str)

    # Set restrictive permissions
    try:
        temp_path.chmod(permissions)
    except OSError as e:
        logger.warning(f"Failed to set permissions on {temp_path}: {e}")

    try:
        yield temp_path
    finally:
        # Guaranteed cleanup even on exceptions
        try:
            if temp_path.exists():
                temp_path.unlink()
                logger.debug(f"Cleaned up temporary file: {temp_path}")
        except FileNotFoundError:
            pass  # Already deleted
        except Exception as e:
            logger.warning(f"Failed to cleanup temp file {temp_path}: {e}")


@contextmanager
def secure_temp_directory(
    suffix: str = "", prefix: str = "audio-", permissions: int = 0o700
) -> Generator[Path, None, None]:
    """Create secure temporary directory with restrictive permissions.

    Args:
        suffix: Directory name suffix
        prefix: Directory name prefix
        permissions: Directory permissions in octal (default 0o700)

    Yields:
        Path to secure temporary directory

    Example:
        >>> with secure_temp_directory() as temp_dir:
        ...     # Use temp directory
        ...     output = temp_dir / "output.mp3"
        ... # Directory automatically deleted here
    """
    temp_dir = Path(tempfile.mkdtemp(suffix=suffix, prefix=prefix))

    # Set restrictive permissions
    try:
        temp_dir.chmod(permissions)
    except OSError as e:
        logger.warning(f"Failed to set permissions on {temp_dir}: {e}")

    try:
        yield temp_dir
    finally:
        # Guaranteed cleanup even on exceptions
        try:
            if temp_dir.exists():
                import shutil

                shutil.rmtree(temp_dir)
                logger.debug(f"Cleaned up temporary directory: {temp_dir}")
        except Exception as e:
            logger.warning(f"Failed to cleanup temp directory {temp_dir}: {e}")


def validate_temp_file_security(file_path: Path) -> bool:
    """Validate that a file has secure permissions.

    Args:
        file_path: Path to file to check

    Returns:
        True if file has restrictive permissions (0600 or stricter)
    """
    import stat

    if not file_path.exists():
        return False

    mode = file_path.stat().st_mode
    # Check that file is readable/writable only by owner
    # Reject if group or others have any permissions
    return (mode & (stat.S_IRWXG | stat.S_IRWXO)) == 0
