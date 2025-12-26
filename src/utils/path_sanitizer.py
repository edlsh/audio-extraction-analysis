"""Path sanitization utilities for error messages."""

from pathlib import Path


def sanitize_path_for_display(path: Path | str) -> str:
    """
    Return only the filename from a path for error messages.

    Prevents leaking directory structure, usernames, or project paths.

    Args:
        path: File path to sanitize

    Returns:
        Filename only, or "[unknown]" if path is invalid
    """
    try:
        p = Path(path)
        if p.name:
            return p.name
        return str(p)
    except (TypeError, ValueError, OSError):
        return "[unknown]"


def sanitize_path_in_message(message: str, path: Path | str | None = None) -> str:
    """
    Replace full file paths with filename-only versions in error messages.

    Args:
        message: Original error message
        path: Optional path to sanitize and insert

    Returns:
        Sanitized message with paths replaced by filenames
    """
    if path is not None:
        filename = sanitize_path_for_display(path)
        message = message.replace(str(path), filename)

    return message
