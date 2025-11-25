"""TUI screens/views."""

from __future__ import annotations

__all__ = []

# Conditionally import screens if textual is available
try:
    from .config import ConfigScreen
    from .help import HelpScreen
    from .home import HomeScreen
    from .run import RunScreen
    from .theme_selector import ThemeSelectorScreen

    __all__.extend(["ConfigScreen", "HelpScreen", "HomeScreen", "RunScreen", "ThemeSelectorScreen"])
except ImportError:
    # Textual not installed
    pass
