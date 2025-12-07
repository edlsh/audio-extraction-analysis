"""TUI module - optional dependency on textual.

This package provides an interactive terminal interface for the audio extraction
and analysis pipeline, featuring live progress updates, provider health checks,
and artifact management.
"""

from __future__ import annotations

from .state import AppState, apply_event

__all__ = [
    "AppState",
    "apply_event",
]

# Conditionally import app if textual is available
try:
    from .app import AudioExtractionApp, main
    from .persistence import inject_api_keys_to_env

    # Inject stored API keys into environment on module load
    # This ensures keys are available when config module reads them
    inject_api_keys_to_env()

    __all__.extend(["AudioExtractionApp", "main"])
except ImportError:
    # Textual not installed; app components not available
    pass
