"""Event model for pipeline instrumentation and TUI integration."""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Literal, Protocol

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
                logging.warning("QueueEventSink: No event loop found, skipping event")
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



