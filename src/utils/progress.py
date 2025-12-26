"""Progress reporting protocol for decoupling UI from services.

This module provides a unified interface for progress callbacks,
used across audio extraction, transcription, and pipeline stages.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, runtime_checkable


@runtime_checkable
class ProgressReporter(Protocol):
    """Protocol for progress reporting callbacks.
    
    Implementations can be console progress bars, TUI widgets,
    or any other progress visualization.
    """
    
    def update(self, completed: int, total: int, message: str | None = None) -> None:
        """Update progress.
        
        Args:
            completed: Number of completed units
            total: Total number of units (use 100 for percentage)
            message: Optional status message
        """
        ...


class CallbackAdapter:
    """Adapts a simple callback function to ProgressReporter protocol."""
    
    def __init__(self, callback: Callable[[int, int], None] | None = None) -> None:
        self._callback = callback
    
    def update(self, completed: int, total: int, message: str | None = None) -> None:
        if self._callback:
            self._callback(completed, total)


class NullReporter:
    """No-op progress reporter for when progress is not needed."""
    
    def update(self, completed: int, total: int, message: str | None = None) -> None:
        pass
