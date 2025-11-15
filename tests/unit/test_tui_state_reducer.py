"""Tests for TUI state reducer and ring buffer."""

from __future__ import annotations

import pytest

from src.models.events import Event
from src.ui.tui.state import AppState, _append_to_ring, apply_event


class TestAppendToRing:
    """Tests for ring buffer helper function."""

    def test_append_within_limit(self):
        """Test appending items within max_size limit."""
        items = []
        for i in range(100):
            items = _append_to_ring(items, {"msg": f"Item {i}"}, max_size=200)

        assert len(items) == 100
        assert items[0]["msg"] == "Item 0"
        assert items[-1]["msg"] == "Item 99"

    def test_append_exceeds_limit(self):
        """Test ring buffer truncation when exceeding max_size."""
        items = []
        for i in range(3000):
            items = _append_to_ring(items, {"msg": f"Item {i}"}, max_size=2000)

        assert len(items) == 2000
        # Should have truncation marker
        assert any(item.get("truncated") for item in items)

    def test_ring_buffer_keeps_head_and_tail(self):
        """Test that ring buffer preserves first 25% and last 75%."""
        items = []
        for i in range(2100):
            items = _append_to_ring(items, {"msg": f"Item {i}"}, max_size=2000)

        # Should keep first 500 (25% of 2000)
        assert items[0]["msg"] == "Item 0"
        assert items[499]["msg"] == "Item 499"

        # Find truncation marker
        truncation_idx = next(i for i, item in enumerate(items) if item.get("truncated"))
        assert truncation_idx == 500

        # Should keep last 1499 (75% of 2000 - 1 for marker)
        # Last item should be from original index 2099
        assert items[-1]["msg"] == "Item 2099"

    def test_ring_buffer_truncation_marker_has_count(self):
        """Test that truncation marker includes count of dropped items."""
        items = []
        for i in range(2500):
            items = _append_to_ring(items, {"msg": f"Item {i}"}, max_size=2000)

        truncation_marker = next(item for item in items if item.get("truncated"))
        assert "count" in truncation_marker
        assert truncation_marker["count"] > 0


class TestApplyEventStageStart:
    """Tests for stage_start event handling."""

    def test_stage_start_updates_state(self):
        """Test stage_start event updates current stage and totals."""
        state = AppState()
        event = Event(
            type="stage_start",
            stage="extract",
            data={"description": "Extracting audio", "total": 100},
        )

        new_state = apply_event(state, event)

        assert new_state.current_stage == "extract"
        assert new_state.current_message == "Extracting audio"
        assert new_state.stage_totals["extract"] == 100
        assert new_state.stage_completed["extract"] == 0
        assert new_state.is_running is True
        assert new_state.can_cancel is True

    def test_stage_start_immutable(self):
        """Test that apply_event doesn't mutate original state."""
        state = AppState()
        event = Event(
            type="stage_start", stage="extract", data={"description": "Test", "total": 100}
        )

        new_state = apply_event(state, event)

        # Original state unchanged
        assert state.current_stage is None
        assert state.is_running is False
        assert state.stage_totals == {}

        # New state updated
        assert new_state.current_stage == "extract"
        assert new_state.is_running is True


class TestApplyEventStageProgress:
    """Tests for stage_progress event handling."""

    def test_stage_progress_updates_completed(self):
        """Test stage_progress updates completed count."""
        state = AppState(stage_totals={"extract": 100})
        event = Event(
            type="stage_progress",
            stage="extract",
            data={"completed": 50, "total": 100},
        )

        new_state = apply_event(state, event)

        assert new_state.stage_completed["extract"] == 50
        assert new_state.current_progress == 50.0

    def test_stage_progress_coalescing(self):
        """Test rapid progress events update correctly."""
        state = AppState(stage_totals={"extract": 100}, stage_completed={"extract": 0})

        # Simulate rapid progress updates
        for i in range(10, 101, 10):
            event = Event(
                type="stage_progress",
                stage="extract",
                data={"completed": i, "total": 100},
            )
            state = apply_event(state, event)

        assert state.stage_completed["extract"] == 100
        assert state.current_progress == 100.0

    def test_stage_progress_dynamic_total(self):
        """Test progress handles dynamic total updates."""
        state = AppState(stage_totals={"transcribe": 100})
        event = Event(
            type="stage_progress",
            stage="transcribe",
            data={"completed": 50, "total": 200},  # Total changed
        )

        new_state = apply_event(state, event)

        assert new_state.stage_totals["transcribe"] == 200
        assert new_state.stage_completed["transcribe"] == 50
        assert new_state.current_progress == 25.0  # 50/200

    def test_stage_progress_with_message(self):
        """Test progress event with custom message."""
        state = AppState()
        event = Event(
            type="stage_progress",
            stage="extract",
            data={"completed": 30, "total": 100, "message": "Processing frame 3000"},
        )

        new_state = apply_event(state, event)

        assert new_state.current_message == "Processing frame 3000"


class TestApplyEventStageEnd:
    """Tests for stage_end event handling."""

    def test_stage_end_records_duration(self):
        """Test stage_end records duration and clears current stage."""
        state = AppState(current_stage="extract", current_progress=100.0)
        event = Event(
            type="stage_end",
            stage="extract",
            data={"duration": 5.23, "status": "complete"},
        )

        new_state = apply_event(state, event)

        assert new_state.stage_durations["extract"] == 5.23
        assert new_state.current_stage is None
        assert new_state.current_progress == 0.0


class TestApplyEventArtifact:
    """Tests for artifact event handling."""

    def test_artifact_appends_to_list(self):
        """Test artifact event adds to artifacts list."""
        state = AppState()
        event = Event(
            type="artifact",
            stage="extract",
            data={"kind": "audio", "path": "/path/to/audio.mp3"},
        )

        new_state = apply_event(state, event)

        assert len(new_state.artifacts) == 1
        assert new_state.artifacts[0]["kind"] == "audio"
        assert new_state.artifacts[0]["path"] == "/path/to/audio.mp3"

    def test_multiple_artifacts(self):
        """Test multiple artifact events accumulate."""
        state = AppState()

        for kind, path in [
            ("audio", "/audio.mp3"),
            ("transcript", "/transcript.txt"),
            ("markdown", "/analysis.md"),
        ]:
            event = Event(type="artifact", stage="test", data={"kind": kind, "path": path})
            state = apply_event(state, event)

        assert len(state.artifacts) == 3
        assert state.artifacts[0]["kind"] == "audio"
        assert state.artifacts[1]["kind"] == "transcript"
        assert state.artifacts[2]["kind"] == "markdown"


class TestApplyEventLogs:
    """Tests for log, warning, and error event handling."""

    def test_log_event_appends_to_logs(self):
        """Test log event creates log entry."""
        state = AppState()
        event = Event(
            type="log",
            ts="2025-11-15T18:00:00Z",
            data={"message": "Test log", "level": "INFO", "logger": "test.module"},
        )

        new_state = apply_event(state, event)

        assert len(new_state.logs) == 1
        assert new_state.logs[0]["type"] == "log"
        assert new_state.logs[0]["message"] == "Test log"
        assert new_state.logs[0]["level"] == "INFO"
        assert new_state.logs[0]["timestamp"] == "2025-11-15T18:00:00Z"

    def test_warning_event(self):
        """Test warning event creates warning log entry."""
        state = AppState()
        event = Event(
            type="warning",
            ts="2025-11-15T18:00:00Z",
            data={"message": "Test warning"},
        )

        new_state = apply_event(state, event)

        assert len(new_state.logs) == 1
        assert new_state.logs[0]["type"] == "warning"
        assert new_state.logs[0]["level"] == "WARNING"

    def test_error_event_adds_to_logs_and_errors(self):
        """Test error event adds to both logs and errors list."""
        state = AppState()
        event = Event(
            type="error",
            ts="2025-11-15T18:00:00Z",
            data={"message": "Test error"},
        )

        new_state = apply_event(state, event)

        assert len(new_state.logs) == 1
        assert new_state.logs[0]["type"] == "error"
        assert new_state.logs[0]["level"] == "ERROR"

        assert len(new_state.errors) == 1
        assert new_state.errors[0] == "Test error"

    def test_log_ring_buffer(self):
        """Test logs use ring buffer to prevent unbounded growth."""
        state = AppState()

        # Add 3000 log events
        for i in range(3000):
            event = Event(type="log", data={"message": f"Log {i}", "level": "INFO"})
            state = apply_event(state, event)

        # Should be capped at 2000
        assert len(state.logs) <= 2000
        # Should have truncation marker
        assert any(log.get("truncated") for log in state.logs)


class TestApplyEventSummary:
    """Tests for summary event handling."""

    def test_summary_event(self):
        """Test summary event updates state and marks run complete."""
        state = AppState(is_running=True, can_cancel=True)
        event = Event(
            type="summary",
            data={
                "metrics": {"total_duration": 17.68, "files_created": 5},
                "provider": "deepgram",
                "output_dir": "/path/to/output",
            },
        )

        new_state = apply_event(state, event)

        assert new_state.summary == event.data
        assert new_state.is_running is False
        assert new_state.can_cancel is False


class TestApplyEventCancelled:
    """Tests for cancelled event handling."""

    def test_cancelled_event(self):
        """Test cancelled event stops run and sets message."""
        state = AppState(is_running=True, can_cancel=True)
        event = Event(type="cancelled", data={"reason": "User interrupted"})

        new_state = apply_event(state, event)

        assert new_state.is_running is False
        assert new_state.can_cancel is False
        assert "Cancelled: User interrupted" in new_state.current_message

    def test_cancelled_default_reason(self):
        """Test cancelled event uses default reason if not provided."""
        state = AppState(is_running=True)
        event = Event(type="cancelled", data={})

        new_state = apply_event(state, event)

        assert "User interrupt" in new_state.current_message


class TestApplyEventUnknown:
    """Tests for unknown event type handling."""

    def test_unknown_event_preserves_state(self):
        """Test unknown event type leaves state unchanged."""
        state = AppState(current_stage="extract", current_progress=50.0)
        event = Event(type="unknown_type", data={"foo": "bar"})  # type: ignore

        new_state = apply_event(state, event)

        # State should be identical (dataclasses.replace returns new instance)
        assert new_state == state
        assert new_state.current_stage == "extract"
        assert new_state.current_progress == 50.0


class TestApplyEventIntegration:
    """Integration tests for event sequences."""

    def test_full_pipeline_event_sequence(self):
        """Test realistic sequence of events through full pipeline."""
        state = AppState()

        # Stage 1: Extract
        state = apply_event(
            state,
            Event(
                type="stage_start",
                stage="extract",
                data={"description": "Extracting", "total": 100},
            ),
        )
        assert state.current_stage == "extract"

        for i in range(0, 101, 25):
            state = apply_event(
                state,
                Event(
                    type="stage_progress",
                    stage="extract",
                    data={"completed": i, "total": 100},
                ),
            )

        state = apply_event(
            state,
            Event(type="stage_end", stage="extract", data={"duration": 3.5}),
        )
        assert state.stage_durations["extract"] == 3.5

        state = apply_event(
            state,
            Event(type="artifact", data={"kind": "audio", "path": "/audio.mp3"}),
        )

        # Stage 2: Transcribe
        state = apply_event(
            state,
            Event(
                type="stage_start",
                stage="transcribe",
                data={"description": "Transcribing", "total": 100},
            ),
        )

        state = apply_event(
            state,
            Event(
                type="stage_progress",
                stage="transcribe",
                data={"completed": 100, "total": 100},
            ),
        )

        state = apply_event(
            state,
            Event(type="stage_end", stage="transcribe", data={"duration": 10.2}),
        )

        state = apply_event(
            state,
            Event(type="artifact", data={"kind": "transcript", "path": "/transcript.txt"}),
        )

        # Summary
        state = apply_event(
            state,
            Event(
                type="summary",
                data={
                    "metrics": {"total_duration": 13.7},
                    "output_dir": "/output",
                },
            ),
        )

        # Final state checks
        assert state.is_running is False
        assert len(state.stage_durations) == 2
        assert len(state.artifacts) == 2
        assert state.summary["metrics"]["total_duration"] == 13.7
