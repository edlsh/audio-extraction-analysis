"""Stage reporter abstraction for pipeline event emission.

Replaces manual _emit_stage_start/progress/end helpers with a cleaner
reporter.stage("transcribe").progress(...) pattern.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from src.utils.logger import get_logger

from ..models import events as event_models
from ..models.events import Event, EventSink

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


@dataclass
class StageContext:
    """Context for a single pipeline stage.

    Provides a fluent interface for emitting stage events.
    """

    name: str
    reporter: StageReporter
    total: int = 100
    start_time: float = field(default_factory=time.time)
    completed: int = 0
    _ended: bool = field(default=False, repr=False)

    def progress(self, completed: int, message: str = "") -> StageContext:
        """Update progress for this stage.

        Args:
            completed: Number of units completed
            message: Optional progress message

        Returns:
            Self for chaining
        """
        self.completed = completed
        self.reporter._emit(
            "stage_progress",
            self.name,
            {"completed": completed, "total": self.total, "message": message},
        )
        return self

    def percent(self, pct: float, message: str = "") -> StageContext:
        """Update progress as percentage (0-100).

        Args:
            pct: Progress percentage (0-100)
            message: Optional progress message

        Returns:
            Self for chaining
        """
        return self.progress(int(pct), message)

    def log(self, message: str, level: str = "INFO") -> StageContext:
        """Emit a log event for this stage.

        Args:
            message: Log message
            level: Log level (INFO, DEBUG, WARNING, ERROR)

        Returns:
            Self for chaining
        """
        self.reporter._emit(
            "log",
            None,
            {"message": message, "level": level, "logger": self.name, "stage": self.name},
        )
        return self

    def artifact(self, path: str, artifact_type: str = "file") -> StageContext:
        """Register an artifact produced by this stage.

        Args:
            path: Path to the artifact
            artifact_type: Type of artifact (file, directory, etc.)

        Returns:
            Self for chaining
        """
        self.reporter._emit(
            "artifact",
            self.name,
            {"path": path, "type": artifact_type, "stage": self.name},
        )
        return self

    def complete(self, status: str = "complete") -> float:
        """Mark stage as complete and return duration.

        Args:
            status: Completion status

        Returns:
            Duration in seconds
        """
        if self._ended:
            return time.time() - self.start_time

        self._ended = True
        duration = time.time() - self.start_time
        self.reporter._emit(
            "stage_end",
            self.name,
            {"duration": duration, "status": status},
        )
        return duration

    def error(self, message: str) -> float:
        """Mark stage as failed with error.

        Args:
            message: Error message

        Returns:
            Duration in seconds
        """
        self.reporter._emit(
            "error",
            self.name,
            {"message": message, "stage": self.name},
        )
        return self.complete("error")


@dataclass
class StageReporter:
    """Reporter for emitting pipeline stage events.

    Provides a clean interface for stage lifecycle management:
    - stage(name).progress(50, "Processing...")
    - stage(name).complete()
    - stage(name).error("Failed")

    Supports both direct EventSink and thread-local emission.
    """

    run_id: str | None = None
    event_sink: EventSink | None = None
    _active_stages: dict[str, StageContext] = field(default_factory=dict)

    def _emit(
        self,
        event_type: str,
        stage: str | None,
        data: dict[str, Any],
    ) -> None:
        """Emit event via direct sink or thread-local fallback."""
        if self.event_sink is not None:
            event = Event(
                type=event_type,  # type: ignore[arg-type]
                stage=stage,
                data=data,
                run_id=self.run_id or "",
            )
            self.event_sink.emit(event)
        else:
            event_models.emit_event(event_type, stage=stage, data=data, run_id=self.run_id)

    def stage(self, name: str, description: str = "", total: int = 100) -> StageContext:
        """Start or get a stage context.

        Args:
            name: Stage identifier (e.g., "extract", "transcribe", "analyze")
            description: Human-readable description
            total: Total units for progress tracking

        Returns:
            StageContext for this stage
        """
        # End any existing stage with same name
        if name in self._active_stages:
            existing = self._active_stages[name]
            if not existing._ended:
                existing.complete()

        # Emit stage start
        self._emit(
            "stage_start",
            name,
            {"description": description or name.title(), "total": total},
        )

        # Create and track new context
        ctx = StageContext(name=name, reporter=self, total=total)
        self._active_stages[name] = ctx
        return ctx

    @contextmanager
    def stage_context(
        self,
        name: str,
        description: str = "",
        total: int = 100,
    ) -> Iterator[StageContext]:
        """Context manager for automatic stage lifecycle.

        Usage:
            with reporter.stage_context("transcribe", "Transcribing audio") as stage:
                stage.progress(50, "Half done")
                # ... do work ...
            # Stage auto-completes on exit

        Args:
            name: Stage identifier
            description: Human-readable description
            total: Total units for progress

        Yields:
            StageContext for the stage
        """
        ctx = self.stage(name, description, total)
        try:
            yield ctx
        except Exception as e:
            ctx.error(str(e))
            raise
        finally:
            if not ctx._ended:
                ctx.complete()

    def log(self, message: str, level: str = "INFO", logger_name: str = "") -> None:
        """Emit a log event.

        Args:
            message: Log message
            level: Log level
            logger_name: Logger name
        """
        self._emit(
            "log",
            None,
            {"message": message, "level": level, "logger": logger_name or __name__},
        )

    def error(self, message: str, stage: str | None = None) -> None:
        """Emit an error event.

        Args:
            message: Error message
            stage: Optional stage where error occurred
        """
        self._emit("error", stage, {"message": message})

    def warning(self, message: str, stage: str | None = None) -> None:
        """Emit a warning event.

        Args:
            message: Warning message
            stage: Optional stage for context
        """
        self._emit("warning", stage, {"message": message})

    def summary(self, data: dict[str, Any]) -> None:
        """Emit a summary event with pipeline results.

        Args:
            data: Summary data dictionary
        """
        self._emit("summary", None, data)

    def cancelled(self) -> None:
        """Emit a cancellation event."""
        self._emit("cancelled", None, {})


def create_reporter(
    run_id: str | None = None,
    event_sink: EventSink | None = None,
) -> StageReporter:
    """Create a stage reporter with optional event sink.

    Args:
        run_id: Optional run identifier
        event_sink: Optional direct event sink (bypasses thread-local)

    Returns:
        Configured StageReporter
    """
    return StageReporter(run_id=run_id, event_sink=event_sink)


__all__ = [
    "StageContext",
    "StageReporter",
    "create_reporter",
]
