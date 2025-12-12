"""Stage reporter abstraction for pipeline event emission.

Replaces manual _emit_stage_start/progress/end helpers with a cleaner
reporter.stage("transcribe").progress(...) pattern.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, cast

from src.utils.logger import get_logger

from ..models import events as event_models
from ..models.events import Event, EventSink, EventType, get_current_run_id
from .events import (
    PipelineEvent,
    PipelineEventType,
    StageEndEvent,
    StageEndStatus,
    StageProgressEvent,
    StageStartEvent,
)

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)

# Type alias for event callbacks
EventCallback = Callable[[PipelineEvent], None]


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
    _start_timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    def progress(self, completed: int, message: str = "") -> StageContext:
        """Update progress for this stage.

        Args:
            completed: Number of units completed
            message: Optional progress message

        Returns:
            Self for chaining
        """
        self.completed = completed

        # Create typed event
        progress_event = StageProgressEvent(
            stage=self.name,
            completed=completed,
            total=self.total,
            message=message if message else None,
        )

        # Emit via reporter
        self.reporter._emit_typed_event("stage_progress", progress_event)

        # Also emit raw event for backward compatibility
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

        # Create typed event
        end_status: StageEndStatus = (
            cast(StageEndStatus, status)
            if status in ("complete", "error", "skipped")
            else "complete"
        )
        end_event = StageEndEvent(
            stage=self.name,
            status=end_status,
            duration_seconds=duration,
            output=None,
            error=None if status != "error" else None,
        )

        # Emit typed event
        self.reporter._emit_typed_event("stage_end", end_event)

        # Also emit raw event for backward compatibility
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

        # Create typed end event with error
        duration = time.time() - self.start_time
        if not self._ended:
            end_event = StageEndEvent(
                stage=self.name,
                status="error",
                duration_seconds=duration,
                output=None,
                error=message,
            )
            self.reporter._emit_typed_event("stage_end", end_event)

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
    _event_history: list[PipelineEvent] = field(default_factory=list)
    _event_callbacks: list[EventCallback] = field(default_factory=list)

    def add_callback(self, callback: EventCallback) -> None:
        """Register a callback for real-time event consumption.

        Args:
            callback: Function to call with each PipelineEvent
        """
        self._event_callbacks.append(callback)

    def remove_callback(self, callback: EventCallback) -> None:
        """Remove a previously registered callback.

        Args:
            callback: The callback to remove
        """
        if callback in self._event_callbacks:
            self._event_callbacks.remove(callback)

    def get_events(self) -> list[PipelineEvent]:
        """Get all recorded pipeline events.

        Returns:
            List of PipelineEvent instances
        """
        return list(self._event_history)

    def get_events_as_dicts(self) -> list[dict[str, object]]:
        """Get all recorded events as JSON-serializable dicts.

        Returns:
            List of dictionaries ready for JSON serialization
        """
        return [event.to_dict() for event in self._event_history]

    def clear_events(self) -> None:
        """Clear the event history."""
        self._event_history.clear()

    def _emit_typed_event(
        self,
        event_type: PipelineEventType,
        event_data: StageStartEvent | StageProgressEvent | StageEndEvent,
    ) -> None:
        """Emit a typed pipeline event.

        Args:
            event_type: Type of event (stage_start, stage_progress, stage_end)
            event_data: The typed event data
        """
        pipeline_event = PipelineEvent(
            event_type=event_type,
            data=event_data,
            run_id=self.run_id,
        )

        # Record in history
        self._event_history.append(pipeline_event)

        # Notify callbacks
        for callback in self._event_callbacks:
            try:
                callback(pipeline_event)
            except Exception as e:
                logger.warning(f"Event callback error: {e}")

    def _emit(
        self,
        event_type: EventType,
        stage: str | None,
        data: dict[str, Any],
    ) -> None:
        """Emit event via direct sink or thread-local fallback.

        Resolves run_id in order: self.run_id -> current context -> fallback.
        """
        # Resolve run_id: explicit > context > empty (let Event handle it)
        resolved_run_id = self.run_id
        if not resolved_run_id:
            resolved_run_id = get_current_run_id()

        if self.event_sink is not None:
            event = Event(
                type=event_type,
                stage=stage,
                data=data,
                run_id=resolved_run_id or "",  # Event will generate if empty
            )
            self.event_sink.emit(event)
        else:
            event_models.emit_event(
                event_type,
                stage=stage,
                data=data,
                run_id=resolved_run_id,
            )

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

        # Create typed start event
        start_event = StageStartEvent(
            stage=name,
            description=description or name.title(),
            total=total,
        )
        self._emit_typed_event("stage_start", start_event)

        # Emit stage start (raw event for backward compatibility)
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
    "EventCallback",
    "StageContext",
    "StageReporter",
    "create_reporter",
]
