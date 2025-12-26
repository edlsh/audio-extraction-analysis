"""Path utilities for safe file IO and directory handling.

Functions here centralize sanitization, containment checks, and safe writes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .sanitization import PathSanitizer

# Re-export for backward compatibility
sanitize_dirname = PathSanitizer.sanitize_dirname


def ensure_subpath(root: Path, sub: Path | str) -> Path:
    """Return absolute path for `root/sub` ensuring it stays within `root`.

    Raises ValueError if the resolved path escapes the root directory.
    """
    root_resolved = Path(root).resolve()
    candidate = (root_resolved / Path(sub)).resolve()
    try:
        # Will raise ValueError if candidate is not within root
        candidate.relative_to(root_resolved)
    except ValueError as e:
        raise ValueError(f"Path escapes root: {candidate} not in {root_resolved}") from e
    return candidate


def safe_write_json(path: Path, data: Any, *, encoding: str = "utf-8", indent: int = 2) -> None:
    """Safely write JSON to file with atomic write for crash safety.

    Uses atomic write (temp file + rename) to prevent partial writes.
    Propagates OSError/PermissionError to caller for handling.

    Args:
        path: Target file path
        data: JSON-serializable data
        encoding: Encoding for the file (default: utf-8)
        indent: JSON indentation (default: 2)
    """
    from .secure_file import atomic_write_json

    # Delegate to atomic implementation for crash safety
    atomic_write_json(path, data, indent=indent, encoding=encoding)
