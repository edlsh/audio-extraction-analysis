"""Secure file utilities for writing sensitive data.

This module provides utilities for writing files with restrictive permissions,
suitable for storing secrets like API keys, cache data, and configuration.

Also provides atomic write helpers for user-facing outputs that don't need
restrictive permissions but still benefit from crash-safe atomic writes.
"""

from __future__ import annotations

import os
import stat
import tempfile
from pathlib import Path
from typing import Any

from src.utils.logger import get_logger

logger = get_logger(__name__)

# File permissions: owner read/write only (0o600)
SECURE_FILE_MODE = stat.S_IRUSR | stat.S_IWUSR

# Directory permissions: owner read/write/execute only (0o700)
SECURE_DIR_MODE = stat.S_IRWXU

# Default permissions for user-facing files (0o644 - owner rw, others r)
DEFAULT_FILE_MODE = stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH


def atomic_write_file(
    path: Path,
    content: str | bytes,
    *,
    encoding: str = "utf-8",
    mode: int | None = None,
) -> None:
    """Write content to file atomically without restrictive permissions.

    Uses atomic write (write to temp file, then rename) to prevent
    partial writes and ensure crash safety. Unlike secure_write_file,
    this preserves normal file permissions suitable for user outputs.

    Args:
        path: Target file path
        content: Content to write (str or bytes)
        encoding: Encoding for string content (default: utf-8)
        mode: Optional file mode (default: system umask or 0o644)

    Raises:
        OSError: If file write fails
    """
    path = Path(path)
    parent = path.parent

    # Ensure parent directory exists
    parent.mkdir(parents=True, exist_ok=True)

    # Write to temp file first, then atomic rename
    fd = None
    tmp_path = None
    try:
        # Create temp file in same directory for atomic rename
        fd, tmp_path_str = tempfile.mkstemp(
            dir=parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
        )
        tmp_path = Path(tmp_path_str)

        # Set permissions if specified (otherwise uses umask)
        if mode is not None:
            os.fchmod(fd, mode)

        # Write content
        if isinstance(content, str):
            content = content.encode(encoding)
        os.write(fd, content)
        os.fsync(fd)
        os.close(fd)
        fd = None

        # Atomic rename
        tmp_path.replace(path)
        tmp_path = None

        logger.debug("Atomically wrote file: %s", path)

    except OSError as e:
        logger.error("Failed to atomically write file %s: %s", path, e)
        raise
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass
        if tmp_path is not None and tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass


def atomic_write_json(
    path: Path,
    data: dict[str, Any] | list[Any],
    *,
    indent: int = 2,
    encoding: str = "utf-8",
) -> None:
    """Write JSON data to file atomically (for user outputs).

    Unlike secure_write_json, this doesn't set restrictive permissions,
    making it suitable for user-facing output files like transcripts and analysis.

    Args:
        path: Target file path
        data: JSON-serializable data
        indent: JSON indentation (default: 2)
        encoding: Encoding (default: utf-8)

    Raises:
        OSError: If file write fails
        TypeError: If data is not JSON-serializable
    """
    import json

    content = json.dumps(data, indent=indent, sort_keys=True)
    atomic_write_file(path, content, encoding=encoding)


def atomic_write_text(
    path: Path,
    content: str,
    *,
    encoding: str = "utf-8",
) -> None:
    """Write text content to file atomically (for user outputs).

    Convenience wrapper around atomic_write_file for text content.

    Args:
        path: Target file path
        content: Text content to write
        encoding: Encoding (default: utf-8)

    Raises:
        OSError: If file write fails
    """
    atomic_write_file(path, content, encoding=encoding)


def secure_write_file(
    path: Path,
    content: str | bytes,
    *,
    encoding: str = "utf-8",
) -> None:
    """Write content to file with restrictive permissions (owner only).

    Uses atomic write (write to temp file, then rename) to prevent
    partial writes and race conditions.

    Args:
        path: Target file path
        content: Content to write (str or bytes)
        encoding: Encoding for string content (default: utf-8)

    Raises:
        OSError: If file write or permission setting fails
    """
    path = Path(path)
    parent = path.parent

    # Ensure parent directory exists with secure permissions
    ensure_secure_directory(parent)

    # Write to temp file first, then atomic rename
    fd = None
    tmp_path = None
    try:
        # Create temp file in same directory for atomic rename
        fd, tmp_path_str = tempfile.mkstemp(
            dir=parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
        )
        tmp_path = Path(tmp_path_str)

        # Set permissions before writing content
        os.fchmod(fd, SECURE_FILE_MODE)

        # Write content
        if isinstance(content, str):
            content = content.encode(encoding)
        os.write(fd, content)
        os.fsync(fd)
        os.close(fd)
        fd = None

        # Atomic rename
        tmp_path.replace(path)
        tmp_path = None

        logger.debug("Securely wrote file: %s (mode=%o)", path, SECURE_FILE_MODE)

    except OSError as e:
        logger.error("Failed to securely write file %s: %s", path, e)
        raise
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass
        if tmp_path is not None and tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass


def ensure_secure_directory(path: Path) -> None:
    """Ensure directory exists with secure permissions (owner only).

    Creates the directory if it doesn't exist, and sets permissions
    to 0o700 (owner read/write/execute only).

    Args:
        path: Directory path

    Raises:
        OSError: If directory creation or permission setting fails
    """
    path = Path(path)

    if path.exists():
        # Check and fix permissions if too permissive
        current_mode = path.stat().st_mode & 0o777
        if current_mode != SECURE_DIR_MODE & 0o777:
            try:
                path.chmod(SECURE_DIR_MODE)
                logger.debug("Fixed directory permissions: %s (mode=%o)", path, SECURE_DIR_MODE)
            except OSError as e:
                logger.warning("Could not set secure permissions on %s: %s", path, e)
    else:
        # Create with secure permissions
        path.mkdir(parents=True, mode=SECURE_DIR_MODE, exist_ok=True)
        logger.debug("Created secure directory: %s (mode=%o)", path, SECURE_DIR_MODE)


def check_file_permissions(path: Path, *, warn_if_too_permissive: bool = True) -> bool:
    """Check if file has secure permissions (owner only).

    Args:
        path: File path to check
        warn_if_too_permissive: Log warning if permissions are too open

    Returns:
        True if permissions are secure (owner-only), False otherwise
    """
    if not path.exists():
        return True  # Non-existent file is "secure"

    mode = path.stat().st_mode
    is_secure = (mode & 0o077) == 0  # No group or other permissions

    if not is_secure and warn_if_too_permissive:
        actual_mode = mode & 0o777
        logger.warning(
            "File %s has permissive permissions (%o), should be %o",
            path,
            actual_mode,
            SECURE_FILE_MODE,
        )

    return is_secure


def secure_write_json(
    path: Path,
    data: dict | list,
    *,
    indent: int = 2,
) -> None:
    """Write JSON data to file with secure permissions.

    Args:
        path: Target file path
        data: JSON-serializable data
        indent: JSON indentation (default: 2)

    Raises:
        OSError: If file write fails
        TypeError: If data is not JSON-serializable
    """
    import json

    content = json.dumps(data, indent=indent, sort_keys=True)
    secure_write_file(path, content)


__all__ = [
    "DEFAULT_FILE_MODE",
    "SECURE_DIR_MODE",
    "SECURE_FILE_MODE",
    "atomic_write_file",
    "atomic_write_json",
    "atomic_write_text",
    "check_file_permissions",
    "ensure_secure_directory",
    "secure_write_file",
    "secure_write_json",
]
