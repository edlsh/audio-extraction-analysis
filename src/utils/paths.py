"""Path utilities for safe file IO and directory handling.

Functions here centralize sanitization, containment checks, and safe writes.
"""

from __future__ import annotations

import json
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
    """Safely write JSON to file with parent creation.

    Propagates OSError/PermissionError to caller for handling.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding=encoding) as f:
        json.dump(data, f, indent=indent)
