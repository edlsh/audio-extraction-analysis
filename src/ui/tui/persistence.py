"""Settings and recent files persistence for TUI."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

try:
    from platformdirs import user_config_dir

    PLATFORMDIRS_AVAILABLE = True
except ImportError:
    PLATFORMDIRS_AVAILABLE = False
    logger.warning("platformdirs not available; settings persistence disabled")


def get_config_dir() -> Path | None:
    """Get user configuration directory.

    Returns:
        Path to config directory, or None if platformdirs not available

    Example:
        >>> config_dir = get_config_dir()
        >>> if config_dir:
        ...     settings_file = config_dir / "tui_settings.json"
    """
    if not PLATFORMDIRS_AVAILABLE:
        return None

    config_dir = Path(user_config_dir("audio-extraction-analysis", appauthor=False))
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def default_settings() -> dict[str, Any]:
    """Get default settings.

    Returns:
        Dictionary with default TUI settings

    Example:
        >>> settings = default_settings()
        >>> settings["defaults"]["quality"]
        'speech'
    """
    return {
        "version": "1.0",
        "last_input_dir": str(Path.home()),
        "last_output_dir": str(Path.home() / "Documents"),
        "defaults": {
            "quality": "speech",
            "language": "en",
            "provider": "auto",
            "analysis_style": "concise",
        },
        "exports": {
            "markdown": True,
            "html": False,
        },
        "ui": {
            "theme": "dark",
            "verbose_logs": False,
            "log_panel_height": 10,
        },
    }


def load_settings() -> dict[str, Any]:
    """Load TUI settings from disk.

    Returns:
        Settings dictionary (defaults if file doesn't exist or error occurs)

    Example:
        >>> settings = load_settings()
        >>> quality = settings["defaults"]["quality"]
    """
    config_dir = get_config_dir()
    if not config_dir:
        return default_settings()

    settings_file = config_dir / "tui_settings.json"

    if not settings_file.exists():
        return default_settings()

    try:
        with open(settings_file, encoding="utf-8") as f:
            loaded = json.load(f)

        # Merge with defaults to handle missing keys
        defaults = default_settings()
        # Deep merge to preserve nested structures
        for key, value in loaded.items():
            if key in defaults and isinstance(defaults[key], dict) and isinstance(value, dict):
                defaults[key].update(value)
            else:
                defaults[key] = value
        return defaults

    except FileNotFoundError:
        # Expected on first run - no error logging needed
        logger.debug(f"Settings file not found: {settings_file}. Using defaults.")
        return default_settings()

    except json.JSONDecodeError as e:
        # Settings file is corrupted
        logger.error(f"Settings file corrupted: {settings_file}. Error: {e}")
        try:
            backup = settings_file.with_suffix(".json.bak")
            settings_file.rename(backup)
            logger.info(f"Backed up corrupted settings to {backup}")
        except OSError as backup_err:
            logger.error(f"Failed to backup corrupted settings: {backup_err}")
        return default_settings()

    except OSError as e:
        # Other file system errors (permissions, disk errors, etc)
        logger.error(f"Failed to read settings file: {settings_file}. Error: {e}")
        return default_settings()


def save_settings(settings: dict[str, Any]) -> bool:
    """Save TUI settings to disk.

    Args:
        settings: Settings dictionary to save

    Returns:
        True if successful, False otherwise

    Example:
        >>> settings = load_settings()
        >>> settings["defaults"]["quality"] = "high"
        >>> save_settings(settings)
        True
    """
    config_dir = get_config_dir()
    if not config_dir:
        logger.debug("Settings not saved; platformdirs not available")
        return False

    settings_file = config_dir / "tui_settings.json"

    try:
        with open(settings_file, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2, sort_keys=True)
        return True

    except OSError as e:
        logger.error(f"Failed to save settings to {settings_file}: {e}")
        return False


def load_recent_files(max_entries: int = 20) -> list[dict[str, Any]]:
    """Load recent files list.

    Args:
        max_entries: Maximum number of recent files to return

    Returns:
        List of recent file dictionaries (path, last_used, size_mb)

    Example:
        >>> recent = load_recent_files()
        >>> for file in recent[:5]:
        ...     print(file["path"])
    """
    config_dir = get_config_dir()
    if not config_dir:
        return []

    recent_file = config_dir / "recent.json"

    if not recent_file.exists():
        return []

    try:
        with open(recent_file, encoding="utf-8") as f:
            data = json.load(f)

        files = data.get("files", [])

        # Filter out non-existent files and limit to max_entries
        valid_files = [f for f in files if Path(f["path"]).exists()]
        return valid_files[:max_entries]

    except (json.JSONDecodeError, OSError, KeyError) as e:
        logger.warning(f"Failed to load recent files from {recent_file}: {e}")
        return []


def save_recent_files(files: list[dict[str, Any]], max_entries: int = 20) -> bool:
    """Persist recent files list to disk.

    Args:
        files: List of recent file dictionaries.
        max_entries: Maximum entries to retain when saving.

    Returns:
        True if the recent file list was saved successfully.
    """
    config_dir = get_config_dir()
    if not config_dir:
        return False

    recent_file = config_dir / "recent.json"
    payload = {"files": files[:max_entries], "max_entries": max_entries}

    try:
        with open(recent_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        return True

    except OSError as e:
        logger.error(f"Failed to save recent files to {recent_file}: {e}")
        return False


def add_recent_file(file_path: Path) -> bool:
    """Add a file to the recent files list.

    Args:
        file_path: Path to file to add

    Returns:
        True if successful, False otherwise

    Example:
        >>> add_recent_file(Path("/path/to/video.mp4"))
        True
    """
    config_dir = get_config_dir()
    if not config_dir:
        return False

    # Load existing recent files
    existing = load_recent_files(max_entries=100)

    # Remove duplicate if exists
    existing = [f for f in existing if Path(f["path"]) != file_path]

    # Add new entry at the front
    try:
        size_mb = file_path.stat().st_size / (1024 * 1024)
    except OSError:
        size_mb = 0.0

    new_entry = {
        "path": str(file_path.resolve()),
        "last_used": datetime.now().isoformat(),
        "size_mb": round(size_mb, 2),
    }

    existing.insert(0, new_entry)

    # Limit to 20 entries and persist
    return save_recent_files(existing)

def clear_recent_files() -> bool:
    """Clear the recent files list.

    Returns:
        True if successful, False otherwise

    Example:
        >>> clear_recent_files()
        True
    """
    config_dir = get_config_dir()
    if not config_dir:
        return False

    recent_file = config_dir / "recent.json"

    try:
        if recent_file.exists():
            recent_file.unlink()
        return True

    except OSError as e:
        logger.error(f"Failed to clear recent files: {e}")
        return False
