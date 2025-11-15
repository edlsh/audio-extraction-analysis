"""Cross-platform file/folder opener utility."""

from __future__ import annotations

import logging
import platform
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def open_path(path: Path) -> bool:
    """Open file or folder in default application.

    Uses platform-specific commands to open files/folders:
    - macOS: `open`
    - Windows: `start`
    - Linux: `xdg-open`

    Args:
        path: Path to file or folder to open

    Returns:
        True if successful, False otherwise

    Example:
        >>> from pathlib import Path
        >>> output_dir = Path("/Users/user/output")
        >>> if open_path(output_dir):
        ...     print("Folder opened successfully")
        ... else:
        ...     print("Failed to open folder")

    Security:
        Path is validated to exist before opening. Subprocess is called
        with shell=False for security.
    """
    # Validate path exists
    if not path.exists():
        logger.warning(f"Cannot open nonexistent path: {path}")
        return False

    system = platform.system()

    try:
        if system == "Darwin":  # macOS
            subprocess.run(["open", str(path)], check=True)

        elif system == "Windows":
            # Windows requires special handling for 'start' command
            subprocess.run(["cmd", "/c", "start", "", str(path)], check=True)

        elif system == "Linux":
            subprocess.run(["xdg-open", str(path)], check=True)

        else:
            logger.warning(f"Unsupported platform: {system}")
            return False

        logger.info(f"Opened path: {path}")
        return True

    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to open path {path}: {e}")
        return False

    except FileNotFoundError as e:
        logger.error(f"Opener command not found on {system}: {e}")
        return False

    except Exception as e:
        logger.error(f"Unexpected error opening path {path}: {e}")
        return False
