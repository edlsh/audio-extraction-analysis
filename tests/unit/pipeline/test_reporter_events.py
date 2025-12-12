"""Tests for structured pipeline event records.

Tests event creation, serialization, deserialization, and
StageReporter integration with typed events.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from src.pipeline.events import (
    PipelineEvent,
    StageEndEvent,
    StageProgressEvent,
    StageStartEvent,
    events_to_json_list,
)
from src.pipeline.reporter import StageReporter, create_reporter

if TYPE_CHECKING:
    pass


class TestStageStartEvent:
    """Tests for StageStartEvent dataclass."""

    def test_creation_with_defaults(self) -> None:
        """Test event creation with default timestamp."""
        event = StageStartEvent(stage="transcribe", description="Transcribing audio")

        assert event.stage == "transcribe"
        assert event.description == "Transcribing audio"
        assert event.total == 100
        assert isinstance(event.timestamp, datetime)
        assert event.timestamp.tzinfo == UTC

    def test_creation_with_custom_values(self) -> None:
        """Test event creation with custom values."""
        ts = datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC)
        event = StageStartEvent(
            stage="extract",
            description="Extracting audio",
            timestamp=ts,
            total=50,
        )

        assert event.stage == "extract"
        assert event.description == "Extracting audio"
        assert event.total == 50
        assert event.timestamp == ts

    def test_to_dict(self) -> None:
        """Test serialization to dictionary."""
        ts = datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC)
        event = StageStartEvent(
            stage="analyze",
            description="Analyzing transcript",
            timestamp=ts,
            total=200,
        )

        result = event.to_dict()

        assert result["stage"] == "analyze"
        assert result["description"] == "Analyzing transcript"
        assert result["total"] == 200
        assert result["timestamp"] == "2024-01-15T10:30:00+00:00"

    def test_from_dict(self) -> None:
        """Test deserialization from dictionary."""
        data = {
            "stage": "transcribe",
            "description": "Transcribing",
            "timestamp": "2024-01-15T10:30:00+00:00",
            "total": 75,
        }

        event = StageStartEvent.from_dict(data)

        assert event.stage == "transcribe"
        assert event.description == "Transcribing"
        assert event.total == 75
        assert event.timestamp.year == 2024

    def test_from_dict_with_missing_fields(self) -> None:
        """Test deserialization handles missing fields gracefully."""
        data: dict[str, object] = {}

        event = StageStartEvent.from_dict(data)

        assert event.stage == ""
        assert event.description == ""
        assert event.total == 100  # default

    def test_roundtrip_serialization(self) -> None:
        """Test that to_dict -> from_dict preserves data."""
        original = StageStartEvent(
            stage="test",
            description="Test stage",
            total=150,
        )

        serialized = original.to_dict()
        restored = StageStartEvent.from_dict(serialized)

        assert restored.stage == original.stage
        assert restored.description == original.description
        assert restored.total == original.total


class TestStageProgressEvent:
    """Tests for StageProgressEvent dataclass."""

    def test_creation_with_defaults(self) -> None:
        """Test event creation with defaults."""
        event = StageProgressEvent(
            stage="transcribe",
            completed=50,
            total=100,
        )

        assert event.stage == "transcribe"
        assert event.completed == 50
        assert event.total == 100
        assert event.message is None
        assert isinstance(event.timestamp, datetime)

    def test_creation_with_message(self) -> None:
        """Test event creation with message."""
        event = StageProgressEvent(
            stage="extract",
            completed=25,
            total=50,
            message="Processing chunk 1/2",
        )

        assert event.message == "Processing chunk 1/2"

    def test_to_dict(self) -> None:
        """Test serialization to dictionary."""
        ts = datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC)
        event = StageProgressEvent(
            stage="analyze",
            completed=75,
            total=100,
            message="Almost done",
            timestamp=ts,
        )

        result = event.to_dict()

        assert result["stage"] == "analyze"
        assert result["completed"] == 75
        assert result["total"] == 100
        assert result["message"] == "Almost done"
        assert result["timestamp"] == "2024-01-15T10:30:00+00:00"

    def test_from_dict(self) -> None:
        """Test deserialization from dictionary."""
        data = {
            "stage": "transcribe",
            "completed": 30,
            "total": 60,
            "message": "Working...",
            "timestamp": "2024-01-15T10:30:00+00:00",
        }

        event = StageProgressEvent.from_dict(data)

        assert event.stage == "transcribe"
        assert event.completed == 30
        assert event.total == 60
        assert event.message == "Working..."

    def test_roundtrip_serialization(self) -> None:
        """Test that to_dict -> from_dict preserves data."""
        original = StageProgressEvent(
            stage="test",
            completed=42,
            total=84,
            message="Half done",
        )

        serialized = original.to_dict()
        restored = StageProgressEvent.from_dict(serialized)

        assert restored.stage == original.stage
        assert restored.completed == original.completed
        assert restored.total == original.total
        assert restored.message == original.message


class TestStageEndEvent:
    """Tests for StageEndEvent dataclass."""

    def test_creation_complete_status(self) -> None:
        """Test event creation with complete status."""
        event = StageEndEvent(
            stage="transcribe",
            status="complete",
            duration_seconds=5.5,
        )

        assert event.stage == "transcribe"
        assert event.status == "complete"
        assert event.duration_seconds == 5.5
        assert event.output is None
        assert event.error is None

    def test_creation_error_status(self) -> None:
        """Test event creation with error status."""
        event = StageEndEvent(
            stage="extract",
            status="error",
            duration_seconds=1.2,
            error="FFmpeg failed",
        )

        assert event.status == "error"
        assert event.error == "FFmpeg failed"

    def test_creation_skipped_status(self) -> None:
        """Test event creation with skipped status."""
        event = StageEndEvent(
            stage="analyze",
            status="skipped",
            duration_seconds=0.0,
            output="Skipped due to cached result",
        )

        assert event.status == "skipped"
        assert event.output == "Skipped due to cached result"

    def test_to_dict(self) -> None:
        """Test serialization to dictionary."""
        ts = datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC)
        event = StageEndEvent(
            stage="transcribe",
            status="complete",
            duration_seconds=10.5,
            output="Success",
            timestamp=ts,
        )

        result = event.to_dict()

        assert result["stage"] == "transcribe"
        assert result["status"] == "complete"
        assert result["duration_seconds"] == 10.5
        assert result["output"] == "Success"
        assert result["error"] is None

    def test_from_dict(self) -> None:
        """Test deserialization from dictionary."""
        data = {
            "stage": "extract",
            "status": "error",
            "duration_seconds": 2.5,
            "error": "Failed",
            "timestamp": "2024-01-15T10:30:00+00:00",
        }

        event = StageEndEvent.from_dict(data)

        assert event.stage == "extract"
        assert event.status == "error"
        assert event.duration_seconds == 2.5
        assert event.error == "Failed"

    def test_from_dict_with_invalid_status(self) -> None:
        """Test deserialization handles invalid status."""
        data = {
            "stage": "test",
            "status": "unknown",
            "duration_seconds": 1.0,
        }

        event = StageEndEvent.from_dict(data)

        # Falls back to "complete"
        assert event.status == "complete"

    def test_roundtrip_serialization(self) -> None:
        """Test that to_dict -> from_dict preserves data."""
        original = StageEndEvent(
            stage="test",
            status="complete",
            duration_seconds=7.25,
            output="Done",
        )

        serialized = original.to_dict()
        restored = StageEndEvent.from_dict(serialized)

        assert restored.stage == original.stage
        assert restored.status == original.status
        assert restored.duration_seconds == original.duration_seconds
        assert restored.output == original.output


class TestPipelineEvent:
    """Tests for PipelineEvent wrapper."""

    def test_creation_with_start_event(self) -> None:
        """Test creation with StageStartEvent."""
        start_event = StageStartEvent(stage="test", description="Test")
        pipeline_event = PipelineEvent(
            event_type="stage_start",
            data=start_event,
            run_id="run-123",
        )

        assert pipeline_event.event_type == "stage_start"
        assert isinstance(pipeline_event.data, StageStartEvent)
        assert pipeline_event.run_id == "run-123"

    def test_creation_with_progress_event(self) -> None:
        """Test creation with StageProgressEvent."""
        progress_event = StageProgressEvent(
            stage="test",
            completed=50,
            total=100,
        )
        pipeline_event = PipelineEvent(
            event_type="stage_progress",
            data=progress_event,
        )

        assert pipeline_event.event_type == "stage_progress"
        assert isinstance(pipeline_event.data, StageProgressEvent)
        assert pipeline_event.run_id is None

    def test_to_dict(self) -> None:
        """Test serialization to dictionary."""
        start_event = StageStartEvent(stage="test", description="Test")
        pipeline_event = PipelineEvent(
            event_type="stage_start",
            data=start_event,
            run_id="run-456",
        )

        result = pipeline_event.to_dict()

        assert result["event_type"] == "stage_start"
        assert result["run_id"] == "run-456"
        assert isinstance(result["data"], dict)
        assert result["data"]["stage"] == "test"  # type: ignore[index]

    def test_from_dict_stage_start(self) -> None:
        """Test deserialization of stage_start event."""
        data = {
            "event_type": "stage_start",
            "data": {
                "stage": "transcribe",
                "description": "Transcribing",
                "total": 100,
                "timestamp": "2024-01-15T10:30:00+00:00",
            },
            "run_id": "run-789",
        }

        event = PipelineEvent.from_dict(data)

        assert event.event_type == "stage_start"
        assert isinstance(event.data, StageStartEvent)
        assert event.data.stage == "transcribe"
        assert event.run_id == "run-789"

    def test_from_dict_stage_progress(self) -> None:
        """Test deserialization of stage_progress event."""
        data = {
            "event_type": "stage_progress",
            "data": {
                "stage": "extract",
                "completed": 50,
                "total": 100,
                "message": "Processing",
                "timestamp": "2024-01-15T10:30:00+00:00",
            },
        }

        event = PipelineEvent.from_dict(data)

        assert event.event_type == "stage_progress"
        assert isinstance(event.data, StageProgressEvent)
        assert event.data.completed == 50

    def test_from_dict_stage_end(self) -> None:
        """Test deserialization of stage_end event."""
        data = {
            "event_type": "stage_end",
            "data": {
                "stage": "analyze",
                "status": "complete",
                "duration_seconds": 5.5,
                "timestamp": "2024-01-15T10:30:00+00:00",
            },
        }

        event = PipelineEvent.from_dict(data)

        assert event.event_type == "stage_end"
        assert isinstance(event.data, StageEndEvent)
        assert event.data.duration_seconds == 5.5

    def test_from_dict_unknown_type(self) -> None:
        """Test deserialization raises for unknown type."""
        data = {
            "event_type": "unknown",
            "data": {},
        }

        with pytest.raises(ValueError, match="Unknown event type"):
            PipelineEvent.from_dict(data)

    def test_roundtrip_serialization(self) -> None:
        """Test that to_dict -> from_dict preserves data."""
        start_event = StageStartEvent(stage="test", description="Test stage")
        original = PipelineEvent(
            event_type="stage_start",
            data=start_event,
            run_id="run-abc",
        )

        serialized = original.to_dict()
        restored = PipelineEvent.from_dict(serialized)

        assert restored.event_type == original.event_type
        assert restored.run_id == original.run_id
        assert isinstance(restored.data, StageStartEvent)
        assert restored.data.stage == start_event.stage


class TestEventsToJsonList:
    """Tests for events_to_json_list helper."""

    def test_empty_list(self) -> None:
        """Test with empty list."""
        result = events_to_json_list([])
        assert result == []

    def test_single_event(self) -> None:
        """Test with single event."""
        event = PipelineEvent(
            event_type="stage_start",
            data=StageStartEvent(stage="test", description="Test"),
        )

        result = events_to_json_list([event])

        assert len(result) == 1
        assert result[0]["event_type"] == "stage_start"

    def test_multiple_events(self) -> None:
        """Test with multiple events."""
        events = [
            PipelineEvent(
                event_type="stage_start",
                data=StageStartEvent(stage="s1", description="Start"),
            ),
            PipelineEvent(
                event_type="stage_progress",
                data=StageProgressEvent(stage="s1", completed=50, total=100),
            ),
            PipelineEvent(
                event_type="stage_end",
                data=StageEndEvent(stage="s1", status="complete", duration_seconds=1.0),
            ),
        ]

        result = events_to_json_list(events)

        assert len(result) == 3
        assert result[0]["event_type"] == "stage_start"
        assert result[1]["event_type"] == "stage_progress"
        assert result[2]["event_type"] == "stage_end"


class TestStageReporterEvents:
    """Tests for StageReporter typed event emission."""

    def test_reporter_emits_stage_start_event(self) -> None:
        """Test that starting a stage emits StageStartEvent."""
        reporter = create_reporter(run_id="test-run")

        ctx = reporter.stage("transcribe", "Transcribing audio")
        ctx.complete()

        events = reporter.get_events()

        # Should have start and end events
        assert len(events) >= 2

        start_event = events[0]
        assert start_event.event_type == "stage_start"
        assert isinstance(start_event.data, StageStartEvent)
        assert start_event.data.stage == "transcribe"
        assert start_event.data.description == "Transcribing audio"
        assert start_event.run_id == "test-run"

    def test_reporter_emits_stage_progress_event(self) -> None:
        """Test that progress updates emit StageProgressEvent."""
        reporter = create_reporter()

        ctx = reporter.stage("extract", total=200)
        ctx.progress(100, "Half done")
        ctx.complete()

        events = reporter.get_events()

        # Find progress event
        progress_events = [e for e in events if e.event_type == "stage_progress"]
        assert len(progress_events) == 1

        progress = progress_events[0]
        assert isinstance(progress.data, StageProgressEvent)
        assert progress.data.completed == 100
        assert progress.data.total == 200
        assert progress.data.message == "Half done"

    def test_reporter_emits_stage_end_event(self) -> None:
        """Test that completing a stage emits StageEndEvent."""
        reporter = create_reporter()

        ctx = reporter.stage("analyze")
        ctx.complete()

        events = reporter.get_events()

        # Find end event
        end_events = [e for e in events if e.event_type == "stage_end"]
        assert len(end_events) == 1

        end = end_events[0]
        assert isinstance(end.data, StageEndEvent)
        assert end.data.stage == "analyze"
        assert end.data.status == "complete"
        assert end.data.duration_seconds >= 0

    def test_reporter_emits_error_end_event(self) -> None:
        """Test that error() emits StageEndEvent with error status."""
        reporter = create_reporter()

        ctx = reporter.stage("transcribe")
        ctx.error("API timeout")

        events = reporter.get_events()

        # Find end events (error creates an end event too)
        end_events = [e for e in events if e.event_type == "stage_end"]
        # There may be 2 end events: one from error(), one from complete()
        # We care about the one with error status
        error_ends = [e for e in end_events if e.data.status == "error"]  # type: ignore[union-attr]
        assert len(error_ends) >= 1

        end = error_ends[0]
        assert isinstance(end.data, StageEndEvent)
        assert end.data.error == "API timeout"

    def test_reporter_get_events_as_dicts(self) -> None:
        """Test getting events as JSON-serializable dicts."""
        reporter = create_reporter()

        ctx = reporter.stage("test", "Test stage")
        ctx.progress(50, "Working")
        ctx.complete()

        dicts = reporter.get_events_as_dicts()

        assert isinstance(dicts, list)
        assert all(isinstance(d, dict) for d in dicts)
        assert len(dicts) >= 3  # start, progress, end

    def test_reporter_clear_events(self) -> None:
        """Test clearing event history."""
        reporter = create_reporter()

        ctx = reporter.stage("test")
        ctx.complete()

        assert len(reporter.get_events()) > 0

        reporter.clear_events()

        assert len(reporter.get_events()) == 0

    def test_reporter_callback_invoked(self) -> None:
        """Test that callbacks are invoked for each event."""
        reporter = create_reporter()
        received_events: list[PipelineEvent] = []

        def callback(event: PipelineEvent) -> None:
            received_events.append(event)

        reporter.add_callback(callback)

        ctx = reporter.stage("test", "Test stage")
        ctx.progress(50)
        ctx.complete()

        # Should have received start, progress, and end events
        assert len(received_events) >= 3
        event_types = [e.event_type for e in received_events]
        assert "stage_start" in event_types
        assert "stage_progress" in event_types
        assert "stage_end" in event_types

    def test_reporter_remove_callback(self) -> None:
        """Test that removed callbacks are not invoked."""
        reporter = create_reporter()
        received_events: list[PipelineEvent] = []

        def callback(event: PipelineEvent) -> None:
            received_events.append(event)

        reporter.add_callback(callback)

        ctx = reporter.stage("stage1")
        ctx.complete()

        initial_count = len(received_events)
        assert initial_count > 0

        reporter.remove_callback(callback)

        ctx2 = reporter.stage("stage2")
        ctx2.complete()

        # Should not have received more events after removal
        assert len(received_events) == initial_count

    def test_reporter_callback_error_handled(self) -> None:
        """Test that callback errors don't break event emission."""
        reporter = create_reporter()

        def bad_callback(event: PipelineEvent) -> None:
            raise ValueError("Callback error")

        reporter.add_callback(bad_callback)

        # Should not raise
        ctx = reporter.stage("test")
        ctx.complete()

        # Events should still be recorded
        assert len(reporter.get_events()) >= 2

    def test_stage_context_manager_emits_events(self) -> None:
        """Test that stage_context manager emits proper events."""
        reporter = create_reporter()

        with reporter.stage_context("test", "Test stage") as stage:
            stage.progress(50, "Working")

        events = reporter.get_events()

        assert len(events) >= 3
        event_types = [e.event_type for e in events]
        assert "stage_start" in event_types
        assert "stage_progress" in event_types
        assert "stage_end" in event_types

    def test_stage_context_manager_emits_error_on_exception(self) -> None:
        """Test that exceptions in context manager emit error events."""
        reporter = create_reporter()

        with pytest.raises(RuntimeError):
            with reporter.stage_context("test") as stage:
                stage.progress(25)
                raise RuntimeError("Test error")

        events = reporter.get_events()

        # Find end event with error status
        end_events = [
            e
            for e in events
            if e.event_type == "stage_end"
            and isinstance(e.data, StageEndEvent)
            and e.data.status == "error"
        ]
        assert len(end_events) >= 1

    def test_multiple_stages_emit_correct_events(self) -> None:
        """Test that multiple stages emit correct event sequences."""
        reporter = create_reporter()

        ctx1 = reporter.stage("extract")
        ctx1.progress(100)
        ctx1.complete()

        ctx2 = reporter.stage("transcribe")
        ctx2.progress(50)
        ctx2.progress(100)
        ctx2.complete()

        events = reporter.get_events()

        # Filter by stage
        extract_events = [e for e in events if e.data.stage == "extract"]
        transcribe_events = [e for e in events if e.data.stage == "transcribe"]

        assert len(extract_events) >= 3  # start, progress, end
        assert len(transcribe_events) >= 4  # start, progress, progress, end
