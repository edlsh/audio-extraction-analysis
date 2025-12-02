"""Shared formatting utilities for duration, timestamps, and other common formats.

This module consolidates duplicate formatting functions that were scattered
across multiple modules (analyzers, formatters, etc.) to ensure consistent
formatting throughout the application.
"""

from __future__ import annotations


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


def format_percentage(value: float, total: float, precision: int = 1) -> str:
    """Format a ratio as percentage string.

    Args:
        value: The numerator value.
        total: The denominator (total) value.
        precision: Number of decimal places.

    Returns:
        Formatted percentage string.

    Examples:
        >>> format_percentage(25, 100)
        '25.0%'
        >>> format_percentage(1, 3, precision=2)
        '33.33%'
    """
    if total <= 0:
        return "0.0%"
    percentage = (value / total) * 100
    return f"{percentage:.{precision}f}%"


__all__ = [
    "format_duration",
    "format_file_size",
    "format_percentage",
    "format_timestamp",
]
