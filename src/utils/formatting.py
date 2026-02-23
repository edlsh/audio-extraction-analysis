"""Shared formatting utilities for duration, timestamps, file sizes, and other common formats.

This module consolidates duplicate formatting functions that were scattered
across multiple modules (analyzers, formatters, etc.) to ensure consistent
formatting throughout the application.
"""

from __future__ import annotations

from pathlib import Path


class FileSizeUnits:
    """Constant multipliers for file size calculations."""

    BYTES_PER_KB = 1024
    BYTES_PER_MB = 1024 * 1024
    BYTES_PER_GB = 1024 * 1024 * 1024


def format_duration(seconds: float | int | None, style: str = "compact") -> str:
    """Format seconds as human-readable duration string.

    Args:
        seconds: Duration in seconds (may include fractional seconds).
            Returns placeholder if None.
        style: Output style:
            - "compact": MM:SS or HH:MM:SS (e.g., "02:05", "01:30:45")
            - "verbose": Xh Xm Xs format (e.g., "1h 30m 45.0s")
            - "full": Always HH:MM:SS even for short durations

    Returns:
        Formatted duration string.

    Examples:
        >>> format_duration(45.0)
        '00:45'
        >>> format_duration(125.5)
        '02:05'
        >>> format_duration(3661.0)
        '01:01:01'
        >>> format_duration(90.5, style="verbose")
        '1m 30.5s'
        >>> format_duration(None)
        '—'
    """
    if seconds is None:
        return "—"

    try:
        seconds = float(seconds)
    except (TypeError, ValueError):
        return str(seconds)

    if seconds < 0:
        seconds = 0

    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60

    if style == "verbose":
        if hours:
            return f"{hours:d}h {minutes:02d}m {secs:04.1f}s"
        if minutes:
            return f"{minutes:d}m {secs:04.1f}s"
        return f"{secs:.1f}s"

    elif style == "full":
        return f"{hours:02d}:{minutes:02d}:{int(secs):02d}"

    else:  # compact (default)
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{int(secs):02d}"
        return f"{minutes:02d}:{int(secs):02d}"


def format_timestamp(seconds: float) -> str:
    """Format seconds as HH:MM:SS timestamp string.

    Always returns full HH:MM:SS format regardless of duration,
    suitable for timestamp displays in transcripts.

    Args:
        seconds: Time position in seconds.

    Returns:
        Formatted timestamp string in HH:MM:SS format.

    Examples:
        >>> format_timestamp(45.0)
        '00:00:45'
        >>> format_timestamp(3661.0)
        '01:01:01'
    """
    if seconds < 0:
        seconds = 0

    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)

    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def format_file_size(size_bytes: int | float, precision: int = 2) -> str:
    """Format file size in bytes to human-readable string.

    Args:
        size_bytes: Size in bytes.
        precision: Number of decimal places.

    Returns:
        Formatted size string (e.g., "1.5 MB", "256 KB").

    Examples:
        >>> format_file_size(1024)
        '1.00 KB'
        >>> format_file_size(1536000)
        '1.46 MB'
    """
    if size_bytes < 0:
        return "0 B"

    units = ["B", "KB", "MB", "GB", "TB"]
    unit_index = 0
    size = float(size_bytes)

    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1

    return f"{size:.{precision}f} {units[unit_index]}"


def get_file_size_bytes(path: Path | str) -> int:
    """Get file size in bytes, returns 0 on error."""
    try:
        p = Path(path)
        return p.stat().st_size
    except (OSError, ValueError, TypeError):
        return 0


def get_file_size_mb(path: Path | str) -> float:
    """Get file size in megabytes, returns 0.0 on error."""
    return get_file_size_bytes(path) / FileSizeUnits.BYTES_PER_MB


def format_file_size_bytes(size_bytes: int) -> str:
    """Format bytes as human-readable string (e.g., '1.5 KB', '2.00 MB')."""
    if size_bytes < 0:
        return "0 B"

    if size_bytes < FileSizeUnits.BYTES_PER_KB:
        return f"{size_bytes} B"
    elif size_bytes < FileSizeUnits.BYTES_PER_MB:
        kb = size_bytes / FileSizeUnits.BYTES_PER_KB
        return f"{kb:.1f} KB"
    elif size_bytes < FileSizeUnits.BYTES_PER_GB:
        mb = size_bytes / FileSizeUnits.BYTES_PER_MB
        return f"{mb:.2f} MB"
    else:
        gb = size_bytes / FileSizeUnits.BYTES_PER_GB
        return f"{gb:.2f} GB"


def format_file_size_mb(size_bytes: int) -> str:
    """Format bytes as megabytes with two decimal places."""
    mb = size_bytes / FileSizeUnits.BYTES_PER_MB
    return f"{mb:.2f} MB"


__all__ = [
    "FileSizeUnits",
    "format_duration",
    "format_file_size",
    "format_file_size_bytes",
    "format_file_size_mb",
    "format_timestamp",
    "get_file_size_bytes",
    "get_file_size_mb",
]
