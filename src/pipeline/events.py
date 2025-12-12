"""Structured event records for pipeline execution.

These typed event dataclasses provide:
- Type-safe event representation
- JSON serialization/deserialization
- Programmatic consumption for metrics, TUI, and logging
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Literal


@dataclass
class StageStartEvent:
    """Event emitted when a pipeline stage begins.

    Attributes:
        stage: Stage identifier (e.g., "extract", "transcribe", "analyze")
        description: Human-readable description of the stage
        timestamp: When the stage started (UTC)
        total: Total units for progress tracking
    """

    stage: str
    description: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    total: int = 100

    def to_dict(self) -> dict[str, object]:
        """Convert to dictionary for JSON serialization."""
        return {
            "stage": self.stage,
            "description": self.description,
            "timestamp": self.timestamp.isoformat(),
            "total": self.total,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> StageStartEvent:
        """Create from dictionary.

        Args:
            data: Dictionary with stage, description, timestamp, total

        Returns:
            StageStartEvent instance
        """
        ts = data.get("timestamp")
        if isinstance(ts, str):
            timestamp = datetime.fromisoformat(ts)
        elif isinstance(ts, datetime):
            timestamp = ts
        else:
            timestamp = datetime.now(UTC)

        return cls(
            stage=str(data.get("stage", "")),
            description=str(data.get("description", "")),
            timestamp=timestamp,
            total=int(data.get("total", 100)),
        )


@dataclass
class StageProgressEvent:
    """Event emitted during stage progress updates.

    Attributes:
        stage: Stage identifier
        completed: Number of units completed
        total: Total units for progress tracking
        message: Optional progress message
        timestamp: When the progress was recorded (UTC)
    """

    stage: str
    completed: int
    total: int
    message: str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, object]:
        """Convert to dictionary for JSON serialization."""
        return {
            "stage": self.stage,
            "completed": self.completed,
            "total": self.total,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> StageProgressEvent:
        """Create from dictionary.

        Args:
            data: Dictionary with stage, completed, total, message, timestamp

        Returns:
            StageProgressEvent instance
        """
        ts = data.get("timestamp")
        if isinstance(ts, str):
            timestamp = datetime.fromisoformat(ts)
        elif isinstance(ts, datetime):
            timestamp = ts
        else:
            timestamp = datetime.now(UTC)

        return cls(
            stage=str(data.get("stage", "")),
            completed=int(data.get("completed", 0)),
            total=int(data.get("total", 100)),
            message=data.get("message") if data.get("message") else None,
            timestamp=timestamp,
        )


StageEndStatus = Literal["complete", "error", "skipped"]


@dataclass
class StageEndEvent:
    """Event emitted when a pipeline stage completes.

    Attributes:
        stage: Stage identifier
        status: Completion status (complete, error, skipped)
        duration_seconds: How long the stage took
        output: Optional output message
        error: Optional error message (if status is error)
        timestamp: When the stage ended (UTC)
    """

    stage: str
    status: StageEndStatus
    duration_seconds: float
    output: str | None = None
    error: str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, object]:
        """Convert to dictionary for JSON serialization."""
        return {
            "stage": self.stage,
            "status": self.status,
            "duration_seconds": self.duration_seconds,
            "output": self.output,
            "error": self.error,
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> StageEndEvent:
        """Create from dictionary.

        Args:
            data: Dictionary with stage, status, duration_seconds, output, error, timestamp

        Returns:
            StageEndEvent instance
        """
        ts = data.get("timestamp")
        if isinstance(ts, str):
            timestamp = datetime.fromisoformat(ts)
        elif isinstance(ts, datetime):
            timestamp = ts
        else:
            timestamp = datetime.now(UTC)

        status_raw = data.get("status", "complete")
        status: StageEndStatus = (
            status_raw if status_raw in ("complete", "error", "skipped") else "complete"
        )

        return cls(
            stage=str(data.get("stage", "")),
            status=status,
            duration_seconds=float(data.get("duration_seconds", 0.0)),
            output=data.get("output") if data.get("output") else None,
            error=data.get("error") if data.get("error") else None,
            timestamp=timestamp,
        )


PipelineEventType = Literal["stage_start", "stage_progress", "stage_end"]
PipelineEventData = StageStartEvent | StageProgressEvent | StageEndEvent


@dataclass
class PipelineEvent:
    """Union wrapper for all pipeline events.

    Provides a uniform interface for consuming pipeline events regardless of type.

    Attributes:
        event_type: Discriminator for the event type
        data: The typed event data
        run_id: Optional pipeline run identifier
    """

    event_type: PipelineEventType
    data: PipelineEventData
    run_id: str | None = None

    def to_dict(self) -> dict[str, object]:
        """Convert to dictionary for JSON serialization."""
        return {
            "event_type": self.event_type,
            "data": self.data.to_dict(),
            "run_id": self.run_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> PipelineEvent:
        """Create from dictionary.

        Args:
            data: Dictionary with event_type, data, run_id

        Returns:
            PipelineEvent instance

        Raises:
            ValueError: If event_type is unknown
        """
        event_type = str(data.get("event_type", ""))
        event_data = data.get("data", {})
        if not isinstance(event_data, dict):
            event_data = {}

        parsed_data: PipelineEventData
        if event_type == "stage_start":
            parsed_data = StageStartEvent.from_dict(event_data)
        elif event_type == "stage_progress":
            parsed_data = StageProgressEvent.from_dict(event_data)
        elif event_type == "stage_end":
            parsed_data = StageEndEvent.from_dict(event_data)
        else:
            raise ValueError(f"Unknown event type: {event_type}")

        run_id = data.get("run_id")
        return cls(
            event_type=event_type,  # type: ignore[arg-type]
            data=parsed_data,
            run_id=str(run_id) if run_id else None,
        )


def events_to_json_list(events: list[PipelineEvent]) -> list[dict[str, object]]:
    """Convert a list of pipeline events to JSON-serializable list.

    Args:
        events: List of PipelineEvent instances

    Returns:
        List of dictionaries ready for JSON serialization
    """
    return [event.to_dict() for event in events]


__all__ = [
    "PipelineEvent",
    "PipelineEventData",
    "PipelineEventType",
    "StageEndEvent",
    "StageEndStatus",
    "StageProgressEvent",
    "StageStartEvent",
    "events_to_json_list",
]
