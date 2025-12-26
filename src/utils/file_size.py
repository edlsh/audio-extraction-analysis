"""File size utilities to consolidate duplicate patterns."""

from pathlib import Path


class Units:
    """Constant multipliers for file size calculations."""

    BYTES_PER_KB = 1024
    BYTES_PER_MB = 1024 * 1024
    BYTES_PER_GB = 1024 * 1024 * 1024


def get_file_size_bytes(path: Path | str) -> int:
    """
    Get file size in bytes, returns 0 on error.

    Args:
        path: File path to check

    Returns:
        File size in bytes, or 0 if path doesn't exist or error occurs
    """
    try:
        p = Path(path)
        return p.stat().st_size
    except (OSError, ValueError, TypeError):
        return 0


def get_file_size_mb(path: Path | str) -> float:
    """
    Get file size in megabytes, returns 0.0 on error.

    Args:
        path: File path to check

    Returns:
        File size in megabytes, or 0.0 if path doesn't exist or error occurs
    """
    return get_file_size_bytes(path) / Units.BYTES_PER_MB


def format_file_size_bytes(size_bytes: int) -> str:
    """
    Format bytes as human-readable string.

    Args:
        size_bytes: Size in bytes

    Returns:
        Human-readable string (e.g., "1024" → "1.0 KB", "1536" → "1.5 KB")
    """
    if size_bytes < 0:
        return "0 B"

    if size_bytes < Units.BYTES_PER_KB:
        return f"{size_bytes} B"
    elif size_bytes < Units.BYTES_PER_MB:
        kb = size_bytes / Units.BYTES_PER_KB
        return f"{kb:.1f} KB"
    elif size_bytes < Units.BYTES_PER_GB:
        mb = size_bytes / Units.BYTES_PER_MB
        return f"{mb:.2f} MB"
    else:
        gb = size_bytes / Units.BYTES_PER_GB
        return f"{gb:.2f} GB"


def format_file_size_mb(size_bytes: int) -> str:
    """
    Format bytes as megabytes with two decimal places.

    Args:
        size_bytes: Size in bytes

    Returns:
        String formatted as MB (e.g., "1048576" → "1.00 MB")
    """
    mb = size_bytes / Units.BYTES_PER_MB
    return f"{mb:.2f} MB"
