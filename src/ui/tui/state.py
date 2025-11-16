"""Application state management for the TUI."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, TypedDict

from ...models.events import Event

if TYPE_CHECKING:
    from pathlib import Path


class TruncationMarker(TypedDict):
    """TypedDict for log truncation marker."""

    truncated: bool
    count: int


@dataclass
class LogEntry:
    """Represents a log entry in the UI.

    Attributes:
        type: Entry type (log, warning, error)
        timestamp: Unix timestamp
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        message: Log message content
        logger: Logger name
    """

    type: str = "log"
    timestamp: float = 0.0
    level: str = "INFO"
    message: str = ""
    logger: str = ""


@dataclass
class AppState:
    """Application state for the TUI.

    Tracks configuration, run status, and results throughout the user's session.
    """

    # Configuration
    input_path: Path | None = None
    output_dir: Path | None = None
    quality: str = "speech"
    language: str = "en"
    provider: str = "auto"
    analysis_style: str = "concise"

    # Run state
    is_running: bool = False
    can_cancel: bool = False
    current_stage: str | None = None
    current_progress: float = 0.0
    current_message: str = ""

    # Stage tracking (for progress calculations)
    stage_totals: dict[str, int] = field(default_factory=dict)  # {stage: total_units}
    stage_completed: dict[str, int] = field(default_factory=dict)  # {stage: completed_units}
    stage_durations: dict[str, float] = field(default_factory=dict)  # {stage: duration_sec}

    # Results
    artifacts: list[dict[str, str]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    logs: list[LogEntry | TruncationMarker] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)

    # Run ID for event tracking
    run_id: str | None = None
    pending_run_config: dict[str, Any] | None = None

    def reset_run_state(self) -> None:
        """Reset state for a new run."""
        self.is_running = False
        self.can_cancel = False
        self.current_stage = None
        self.current_progress = 0.0
        self.current_message = ""
        self.stage_totals.clear()
        self.stage_completed.clear()
        self.stage_durations.clear()
        self.artifacts.clear()
        self.errors.clear()
        self.logs.clear()
        self.summary.clear()
        self.run_id = None
        self.pending_run_config = None


def _append_to_ring(items: list[Any], item: Any, max_size: int) -> list[Any]:
    """Append item to ring buffer with middle truncation.

    Maintains a ring buffer by keeping the first 25% and last 75% of entries
    when the buffer exceeds max_size, with a truncation marker in between.

    Args:
        items: Current list of items
        item: New item to append
        max_size: Maximum buffer size

    Returns:
        Updated list with ring buffer truncation applied

    Example:
        >>> logs = []
        >>> for i in range(3000):
        ...     logs = _append_to_ring(logs, {"msg": f"Log {i}"}, 2000)
        >>> len(logs)
        2000
        >>> any(x.get("truncated") for x in logs)
        True
    """
    result = [*items, item]

    if len(result) > max_size:
        # Keep first 25% and last 75% with truncation marker
        keep_head = max_size // 4
        keep_tail = max_size - keep_head - 1  # Reserve 1 slot for marker

        return [
            *result[:keep_head],
            {"truncated": True, "count": len(result) - max_size + 1},
            *result[-keep_tail:],
        ]

    return result


def apply_event(state: AppState, event: Event) -> AppState:
    """Pure reducer function: (state, event) -> new_state.

    Applies an event to the current state and returns a new state instance.
    NEVER mutates the input state.

    Args:
        state: Current application state
        event: Event object with type, stage, data fields

    Returns:
        New AppState with event applied

    Example:
        >>> state = AppState()
        >>> event = Event(type="stage_start", stage="extract", data={"description": "Extracting", "total": 100})
        >>> new_state = apply_event(state, event)
        >>> new_state.current_stage
        'extract'
        >>> state.current_stage  # Original unchanged
        None
    """
    event_type = event.type
    event_stage = event.stage
    event_data = event.data

    # Match on event type
    if event_type == "stage_start":
        # data: {"description": str, "total": int}
        return dataclasses.replace(
            state,
            current_stage=event_stage,
            current_message=event_data.get("description", ""),
            stage_totals={**state.stage_totals, event_stage: event_data.get("total", 100)},
            stage_completed={**state.stage_completed, event_stage: 0},
            is_running=True,
            can_cancel=True,
        )

    elif event_type == "stage_progress":
        # data: {"completed": int, "total": int, "message": str}
        completed = event_data.get("completed", 0)
        total = event_data.get("total", state.stage_totals.get(event_stage, 100))

        # Update totals if provided (handles dynamic total updates)
        new_totals = state.stage_totals
        if total != state.stage_totals.get(event_stage):
            new_totals = {**state.stage_totals, event_stage: total}

        return dataclasses.replace(
            state,
            stage_completed={**state.stage_completed, event_stage: completed},
            stage_totals=new_totals,
            current_message=event_data.get("message", state.current_message),
            current_progress=(completed / total * 100) if total > 0 else 0,
        )

    elif event_type == "stage_end":
        # data: {"duration": float, "status": str}
        return dataclasses.replace(
            state,
            stage_durations={**state.stage_durations, event_stage: event_data.get("duration", 0.0)},
            current_stage=None,
            current_progress=0.0,
        )

    elif event_type == "artifact":
        # data: {"kind": str, "path": str}
        return dataclasses.replace(
            state,
            artifacts=[*state.artifacts, event_data],
        )

    elif event_type == "log":
        # data: {"message": str, "level": str, "logger": str}
        log_entry = LogEntry(
            type="log",
            timestamp=event.ts,
            level=event_data.get("level", "INFO"),
            message=event_data.get("message", ""),
            logger=event_data.get("logger", ""),
        )
        return dataclasses.replace(
            state,
            logs=_append_to_ring(state.logs, log_entry, max_size=2000),
        )

    elif event_type == "warning":
        # data: {"message": str, "level": str, "logger": str}
        log_entry = LogEntry(
            type="warning",
            timestamp=event.ts,
            level="WARNING",
            message=event_data.get("message", ""),
            logger=event_data.get("logger", ""),
        )
        return dataclasses.replace(
            state,
            logs=_append_to_ring(state.logs, log_entry, max_size=2000),
        )

    elif event_type == "error":
        # data: {"message": str, "level": str, "logger": str}
        error_msg = event_data.get("message", "Unknown error")
        log_entry = LogEntry(
            type="error",
            timestamp=event.ts,
            level="ERROR",
            message=error_msg,
            logger=event_data.get("logger", ""),
        )
        return dataclasses.replace(
            state,
            errors=[*state.errors, error_msg],
            logs=_append_to_ring(state.logs, log_entry, max_size=2000),
        )

    elif event_type == "summary":
        # data: {"metrics": dict, "provider": str, "output_dir": str}
        return dataclasses.replace(
            state,
            summary=event_data,
            is_running=False,
            can_cancel=False,
        )

    elif event_type == "cancelled":
        # data: {"reason": str}
        reason = event_data.get("reason", "User interrupt")
        return dataclasses.replace(
            state,
            is_running=False,
            can_cancel=False,
            current_message=f"Cancelled: {reason}",
        )

    # Unknown event type; preserve state
    return state
