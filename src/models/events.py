"""Event model for pipeline instrumentation and TUI integration."""

from __future__ import annotations

import asyncio
import contextvars
import json
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Literal, Protocol

from src.utils.logger import get_logger

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


# Context variable for current run ID - enables automatic correlation
# without explicit threading of run_id through every function call
_current_run_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "current_run_id", default=None
)


def set_current_run_id(run_id: str) -> contextvars.Token[str | None]:
    """Set the current run ID for event correlation.

    Call this at the start of a pipeline run to establish the run context.
    All subsequent emit_event() calls without explicit run_id will use this.

    Args:
        run_id: The run identifier (typically a UUID)

    Returns:
        Token that can be used to reset the context (for cleanup)

    Example:
        >>> token = set_current_run_id("abc-123")
        >>> try:
        ...     # All events emitted here will use "abc-123"
        ...     emit_event("stage_start", stage="extract")
        ... finally:
        ...     reset_current_run_id(token)
    """
    return _current_run_id.set(run_id)


def reset_current_run_id(token: contextvars.Token[str | None]) -> None:
    """Reset the current run ID to its previous value.

    Args:
        token: Token returned from set_current_run_id()
    """
    _current_run_id.reset(token)


def get_current_run_id() -> str | None:
    """Get the current run ID from context.

    Returns:
        Current run ID or None if not set
    """
    return _current_run_id.get()


def generate_run_id() -> str:
    """Generate a new unique run ID.

    Returns:
        A new UUID string for use as a run identifier
    """
    return str(uuid.uuid4())


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
    run_id: str = field(default_factory=lambda: get_current_run_id() or generate_run_id())
    stage: str | None = None
    data: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
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
                get_logger(__name__).warning("QueueEventSink: No event loop found, skipping event")
                return

        # Thread-safe enqueue
        self._loop.call_soon_threadsafe(self.queue.put_nowait, event)

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
    data: dict[str, object] | None = None,
    run_id: str | None = None,
) -> None:
    """Emit an event to the current thread's sink.

    Run ID resolution order:
    1. Explicit run_id parameter (if provided)
    2. Current run context (from set_current_run_id)
    3. Generate new UUID (fallback, but logs a warning)

    Args:
        event_type: Type of event
        stage: Optional stage identifier
        data: Event-specific payload
        run_id: Optional explicit run ID (uses context if not provided)
    """
    sink = get_event_sink()
    if sink is None:
        return

    # Resolve run_id with fallback chain
    resolved_run_id = run_id
    if resolved_run_id is None:
        resolved_run_id = get_current_run_id()
    if resolved_run_id is None:
        # Fallback: generate new ID but this indicates missing context setup
        resolved_run_id = generate_run_id()
        get_logger(__name__).debug(
            "emit_event called without run_id context; generated new ID: %s", resolved_run_id[:8]
        )

    event = Event(
        type=event_type,
        stage=stage,
        data=data or {},
        run_id=resolved_run_id,
    )
    sink.emit(event)


__all__ = [
    "Event",
    "EventSink",
    "EventType",
    "QueueEventSink",
    "emit_event",
    "generate_run_id",
    "get_current_run_id",
    "get_event_sink",
    "reset_current_run_id",
    "set_current_run_id",
    "set_event_sink",
]
