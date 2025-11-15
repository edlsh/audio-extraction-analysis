"""Unit tests for event model and sinks."""

from __future__ import annotations

import asyncio
import io
import json
from pathlib import Path

import pytest

from src.models.events import (
    CompositeSink,
    Event,
    EventSinkContext,
    JsonLinesSink,
    QueueEventSink,
    emit_event,
    get_event_sink,
    set_event_sink,
)


class TestEvent:
    """Tests for Event dataclass."""

    def test_event_creation(self):
        """Test basic event creation."""
        event = Event(type="stage_start", stage="extract", data={"description": "test"})
        
        assert event.type == "stage_start"
        assert event.stage == "extract"
        assert event.data == {"description": "test"}
        assert event.ts is not None
        assert event.run_id is not None

    def test_event_to_dict(self):
        """Test event serialization to dict."""
        event = Event(
            type="stage_progress",
            stage="transcribe",
            data={"completed": 50, "total": 100},
            run_id="test-run-123",
        )
        
        event_dict = event.to_dict()
        
        assert event_dict["type"] == "stage_progress"
        assert event_dict["stage"] == "transcribe"
        assert event_dict["data"]["completed"] == 50
        assert event_dict["run_id"] == "test-run-123"

    def test_event_to_json(self):
        """Test event serialization to JSON."""
        event = Event(type="artifact", data={"kind": "audio", "path": "/tmp/test.mp3"})
        
        json_str = event.to_json()
        parsed = json.loads(json_str)
        
        assert parsed["type"] == "artifact"
        assert parsed["data"]["kind"] == "audio"


class TestJsonLinesSink:
    """Tests for JsonLinesSink."""

    def test_emit_to_stream(self):
        """Test emitting events to a stream."""
        stream = io.StringIO()
        sink = JsonLinesSink(file=stream)
        
        event1 = Event(type="stage_start", stage="extract", data={})
        event2 = Event(type="stage_end", stage="extract", data={})
        
        sink.emit(event1)
        sink.emit(event2)
        
        output = stream.getvalue()
        lines = output.strip().split("\n")
        
        assert len(lines) == 2
        assert json.loads(lines[0])["type"] == "stage_start"
        assert json.loads(lines[1])["type"] == "stage_end"

    def test_emit_to_file(self, tmp_path):
        """Test emitting events to a file."""
        output_file = tmp_path / "events.jsonl"
        sink = JsonLinesSink(path=str(output_file))
        
        event = Event(type="summary", data={"metrics": {"duration": 123.45}})
        sink.emit(event)
        sink.close()
        
        content = output_file.read_text()
        parsed = json.loads(content.strip())
        
        assert parsed["type"] == "summary"
        assert parsed["data"]["metrics"]["duration"] == 123.45


class TestQueueEventSink:
    """Tests for QueueEventSink."""

    @pytest.mark.asyncio
    async def test_emit_to_queue(self):
        """Test emitting events to an asyncio queue."""
        queue = asyncio.Queue()
        sink = QueueEventSink(queue)
        
        event = Event(type="log", data={"message": "test log"})
        sink.emit(event)
        
        # Wait a bit for the event to be queued
        await asyncio.sleep(0.01)
        
        received = await asyncio.wait_for(queue.get(), timeout=1.0)
        
        assert received.type == "log"
        assert received.data["message"] == "test log"


class TestCompositeSink:
    """Tests for CompositeSink."""

    def test_emit_to_multiple_sinks(self):
        """Test emitting events to multiple sinks."""
        stream1 = io.StringIO()
        stream2 = io.StringIO()
        
        sink1 = JsonLinesSink(file=stream1)
        sink2 = JsonLinesSink(file=stream2)
        composite = CompositeSink([sink1, sink2])
        
        event = Event(type="error", data={"message": "test error"})
        composite.emit(event)
        
        output1 = stream1.getvalue()
        output2 = stream2.getvalue()
        
        assert json.loads(output1.strip())["type"] == "error"
        assert json.loads(output2.strip())["type"] == "error"

    def test_resilient_to_sink_errors(self):
        """Test that composite sink continues on child sink errors."""
        class FailingSink:
            def emit(self, event):
                raise RuntimeError("Sink error")
            
            def close(self):
                pass
        
        stream = io.StringIO()
        good_sink = JsonLinesSink(file=stream)
        bad_sink = FailingSink()
        composite = CompositeSink([bad_sink, good_sink])
        
        event = Event(type="log", data={"message": "test"})
        composite.emit(event)  # Should not raise despite bad_sink failing
        
        output = stream.getvalue()
        assert json.loads(output.strip())["type"] == "log"


class TestEventSinkRegistry:
    """Tests for global event sink registry."""

    def test_set_and_get_event_sink(self):
        """Test setting and getting the current event sink."""
        stream = io.StringIO()
        sink = JsonLinesSink(file=stream)
        
        set_event_sink(sink)
        
        assert get_event_sink() is sink
        
        # Clean up
        set_event_sink(None)

    def test_emit_event_helper(self):
        """Test emit_event helper function."""
        stream = io.StringIO()
        sink = JsonLinesSink(file=stream)
        
        set_event_sink(sink)
        
        emit_event(
            "stage_progress",
            stage="analyze",
            data={"completed": 75, "total": 100},
            run_id="test-run",
        )
        
        output = stream.getvalue()
        parsed = json.loads(output.strip())
        
        assert parsed["type"] == "stage_progress"
        assert parsed["stage"] == "analyze"
        assert parsed["data"]["completed"] == 75
        assert parsed["run_id"] == "test-run"
        
        # Clean up
        set_event_sink(None)

    def test_emit_event_without_sink(self):
        """Test that emit_event gracefully handles missing sink."""
        set_event_sink(None)
        
        # Should not raise
        emit_event("log", data={"message": "test"})


class TestEventSinkContext:
    """Tests for EventSinkContext context manager."""

    def test_context_manager(self):
        """Test context manager sets and restores sink."""
        stream = io.StringIO()
        sink = JsonLinesSink(file=stream)
        
        # No sink initially
        assert get_event_sink() is None
        
        with EventSinkContext(sink):
            # Sink is set inside context
            assert get_event_sink() is sink
            
            emit_event("log", data={"message": "inside context"})
        
        # Sink is cleared after context
        assert get_event_sink() is None
        
        output = stream.getvalue()
        assert "inside context" in output

    def test_nested_contexts(self):
        """Test nested event sink contexts."""
        stream1 = io.StringIO()
        stream2 = io.StringIO()
        sink1 = JsonLinesSink(file=stream1)
        sink2 = JsonLinesSink(file=stream2)
        
        with EventSinkContext(sink1):
            emit_event("log", data={"message": "outer"})
            
            with EventSinkContext(sink2):
                emit_event("log", data={"message": "inner"})
            
            emit_event("log", data={"message": "outer again"})
        
        output1 = stream1.getvalue()
        output2 = stream2.getvalue()
        
        assert "outer" in output1
        assert "outer again" in output1
        assert "inner" not in output1
        
        assert "inner" in output2
        assert "outer" not in output2
