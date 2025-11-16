"""Event model for pipeline instrumentation and TUI integration."""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timezone
from typing import Any, Literal, Protocol

EventType = Literal[
    "stage_start",
    "stage_progress",
    "stage_end",
    "artifact",
    "log",
    "warning",
    "error",
    "summary",
    "cancelled",
]


@dataclass
class Event:
    """Typed event emitted during pipeline execution.

    Attributes:
        type: Event type discriminator
        ts: ISO 8601 timestamp (UTC)
        run_id: Unique identifier for this pipeline run
        stage: Optional stage identifier (e.g., "extract", "transcribe", "analyze")
        data: Type-specific payload (see event_model in task description)
    """

    type: EventType
    ts: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    stage: str | None = None
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict())


class EventSink(Protocol):
    """Protocol for event consumers.

    Implementations can be synchronous or asynchronous; emit() should be non-blocking.
    """

    def emit(self, event: Event) -> None:
        """Emit an event to this sink.

        Args:
            event: Event to emit
        """
        ...

    def close(self) -> None:
        """Close the sink and flush any pending events."""
        ...


class QueueEventSink:
    """Event sink that pushes events to an asyncio.Queue.

    Used by TUI to receive events from pipeline running in background task.
    """

    def __init__(self, queue: asyncio.Queue[Event]) -> None:
        """Initialize with target queue.

        Args:
            queue: Asyncio queue to push events into
        """
        self.queue = queue
        self._loop = None
        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            pass

    def emit(self, event: Event) -> None:
        """Emit event to queue (thread-safe)."""
        if self._loop is None:
            try:
                self._loop = asyncio.get_running_loop()
            except RuntimeError:
                # No event loop; create one in a thread if needed
                logging.warning("QueueEventSink: No event loop found, skipping event")
                return

        # Thread-safe enqueue
        self._loop.call_soon_threadsafe(self.queue.put_nowait, event)

    def close(self) -> None:
        """Close the sink."""
        pass


class JsonLinesSink:
    """Event sink that writes JSONL (newline-delimited JSON) to a file or stream.

    Used for --jsonl CLI flag to stream events to stdout or file.
    """

    def __init__(self, file=None, path: str | None = None) -> None:
        """Initialize sink.

        Args:
            file: File-like object to write to (default: sys.stdout)
            path: Path to file to open for writing (mutually exclusive with file)
        """
        if path:
            self._file = open(path, "w", encoding="utf-8")
            self._owned = True
        else:
            self._file = file or sys.stdout
            self._owned = False
        self._lock = threading.Lock()

    def emit(self, event: Event) -> None:
        """Emit event as JSON line."""
        with self._lock:
            self._file.write(event.to_json() + "\n")
            self._file.flush()

    def close(self) -> None:
        """Close the file if owned."""
        if self._owned and self._file:
            self._file.close()


class CompositeSink:
    """Event sink that forwards events to multiple child sinks.

    Allows simultaneous streaming to JSONL and TUI queue.
    """

    def __init__(self, sinks: list[EventSink]) -> None:
        """Initialize with child sinks.

        Args:
            sinks: List of sinks to forward events to
        """
        self.sinks = sinks

    def emit(self, event: Event) -> None:
        """Emit event to all child sinks."""
        for sink in self.sinks:
            try:
                sink.emit(event)
            except Exception as e:
                logging.error(f"Error emitting event to sink {sink}: {e}")

    def close(self) -> None:
        """Close all child sinks."""
        for sink in self.sinks:
            try:
                sink.close()
            except Exception as e:
                logging.error(f"Error closing sink {sink}: {e}")


class ConsoleEventSink:
    """Event sink that bridges events to existing ConsoleManager.

    Preserves current CLI behavior while emitting events.
    """

    def __init__(self, console_manager) -> None:
        """Initialize with ConsoleManager instance.

        Args:
            console_manager: ConsoleManager to forward events to
        """
        from ..ui.console import ConsoleManager

        self.console: ConsoleManager = console_manager
        self._current_progress_tracker = None
        self._lock = threading.Lock()

    def emit(self, event: Event) -> None:
        """Emit event by translating to ConsoleManager calls."""
        event_type = event.type
        data = event.data
        stage = event.stage

        with self._lock:
            if event_type == "stage_start":
                # Note: ConsoleManager.progress_context is a context manager;
                # we can't directly call it here. Instead, just log the stage start.
                self.console.print_stage(stage or "stage", "starting")

            elif event_type == "stage_progress":
                # Progress updates are handled by ConsoleManager's progress_context
                # This is a no-op here since progress is managed externally
                pass

            elif event_type == "stage_end":
                status = data.get("status", "completed")
                self.console.print_stage(stage or "stage", status)

            elif event_type == "artifact":
                kind = data.get("kind", "file")
                path = data.get("path", "")
                self.console.console.print(f"[green]✓[/green] {kind}: {path}")

            elif event_type in ("log", "warning", "error"):
                message = data.get("message", "")
                if event_type == "error":
                    self.console.console.print(f"[red]ERROR:[/red] {message}", style="bold red")
                elif event_type == "warning":
                    self.console.console.print(f"[yellow]WARNING:[/yellow] {message}")
                else:
                    self.console.console.print(message)

            elif event_type == "summary":
                # Print summary as a table or panel
                self.console.print_summary(data)

            elif event_type == "cancelled":
                reason = data.get("reason", "User interrupt")
                self.console.console.print(f"[yellow]⚠ Cancelled:[/yellow] {reason}")

    def close(self) -> None:
        """Close the sink."""
        pass


# Thread-local storage for current event sink
_thread_local = threading.local()


def set_event_sink(sink: EventSink | None) -> None:
    """Set the global event sink for the current thread.

    Args:
        sink: EventSink instance or None to disable event emission
    """
    _thread_local.sink = sink


def get_event_sink() -> EventSink | None:
    """Get the current thread's event sink.

    Returns:
        Current EventSink or None if not set
    """
    return getattr(_thread_local, "sink", None)


def emit_event(
    event_type: EventType,
    *,
    stage: str | None = None,
    data: dict[str, Any] | None = None,
    run_id: str | None = None,
) -> None:
    """Emit an event to the current thread's sink.

    Args:
        event_type: Type of event
        stage: Optional stage identifier
        data: Event-specific payload
        run_id: Optional run ID (auto-generated if not provided)
    """
    sink = get_event_sink()
    if sink is None:
        return

    event = Event(
        type=event_type,
        stage=stage,
        data=data or {},
        run_id=run_id or str(uuid.uuid4()),
    )
    sink.emit(event)


# Context manager for scoped event sink
class EventSinkContext:
    """Context manager for scoped event sink."""

    def __init__(self, sink: EventSink | None):
        """Initialize with sink.

        Args:
            sink: Event sink to set for this context
        """
        self.sink = sink
        self.previous_sink = None

    def __enter__(self):
        """Enter context and set sink."""
        self.previous_sink = get_event_sink()
        set_event_sink(self.sink)
        return self.sink

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context and restore previous sink."""
        if self.sink:
            self.sink.close()
        set_event_sink(self.previous_sink)
