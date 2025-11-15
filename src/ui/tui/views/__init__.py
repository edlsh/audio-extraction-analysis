"""TUI screens/views."""

from __future__ import annotations

__all__ = []

# Conditionally import screens if textual is available
try:
    from .config import ConfigScreen
    from .home import HomeScreen

    __all__.extend(["ConfigScreen", "HomeScreen"])
except ImportError:
    # Textual not installed
    pass
