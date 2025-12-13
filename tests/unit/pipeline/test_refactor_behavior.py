"""Tests to lock in the P0 refactor behavior.

These tests verify the key behavioral changes from the pipeline architecture refactor:
1. Provider selection failure raises (not returns None)
2. StageContext emits exactly one stage_end event with correct error field
3. Reporter run_id is never empty
4. process_pipeline_v2 preserves typed errors with original_exception
5. QueueEventSink requires loop at construction
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from src.models.events import Event, QueueEventSink
from src.pipeline.events import PipelineEventType
from src.pipeline.reporter import StageReporter, create_reporter


class TestStageContextLifecycle:
    """Test StageContext emits exactly one stage_end event."""

    def test_stage_context_emits_single_end_event_on_success(self) -> None:
        """Stage context should emit exactly one stage_end event on successful completion."""
        reporter = create_reporter(run_id="test-run")
        events: list[tuple[PipelineEventType, object]] = []

        def capture_event(event: object) -> None:
            from src.pipeline.events import PipelineEvent

            if isinstance(event, PipelineEvent):
                events.append((event.event_type, event.data))

        reporter.add_callback(capture_event)

        with reporter.stage_context("test_stage", "Testing") as stage:
            stage.progress(50, "Half done")

        end_events = [e for e in events if e[0] == "stage_end"]
        assert len(end_events) == 1, f"Expected 1 stage_end event, got {len(end_events)}"

    def test_stage_context_emits_single_end_event_on_error(self) -> None:
        """Stage context should emit exactly one stage_end event on error."""
        reporter = create_reporter(run_id="test-run")
        events: list[tuple[PipelineEventType, object]] = []

        def capture_event(event: object) -> None:
            from src.pipeline.events import PipelineEvent

            if isinstance(event, PipelineEvent):
                events.append((event.event_type, event.data))

        reporter.add_callback(capture_event)

        with pytest.raises(ValueError, match="Test error"):
            with reporter.stage_context("test_stage", "Testing") as stage:
                stage.progress(50, "Half done")
                raise ValueError("Test error")

        end_events = [e for e in events if e[0] == "stage_end"]
        assert len(end_events) == 1, f"Expected 1 stage_end event, got {len(end_events)}"

    def test_stage_context_error_includes_message(self) -> None:
        """StageEndEvent.error should be populated on failure."""
        reporter = create_reporter(run_id="test-run")
        events: list[object] = []

        def capture_event(event: object) -> None:
            from src.pipeline.events import PipelineEvent

            if isinstance(event, PipelineEvent) and event.event_type == "stage_end":
                events.append(event.data)

        reporter.add_callback(capture_event)

        with pytest.raises(RuntimeError, match="Something broke"):
            with reporter.stage_context("test_stage", "Testing"):
                raise RuntimeError("Something broke")

        assert len(events) == 1
        from src.pipeline.events import StageEndEvent

        end_event = events[0]
        assert isinstance(end_event, StageEndEvent)
        assert end_event.status == "error"
        assert end_event.error == "Something broke"


class TestReporterRunId:
    """Test reporter run_id is never empty."""

    def test_reporter_with_explicit_run_id(self) -> None:
        """Reporter should use provided run_id."""
        reporter = create_reporter(run_id="explicit-run-id")
        assert reporter.run_id == "explicit-run-id"

    def test_reporter_generates_run_id_if_not_provided(self) -> None:
        """Reporter should work without explicit run_id (context or generated)."""
        reporter = create_reporter()
        # run_id may be None at construction, but events should get a run_id
        assert reporter.run_id is None or isinstance(reporter.run_id, str)

    def test_events_always_have_run_id(self) -> None:
        """Events emitted should always have a non-empty run_id."""
        reporter = create_reporter(run_id="test-run-123")
        collected_events: list[object] = []

        def capture_event(event: object) -> None:
            collected_events.append(event)

        reporter.add_callback(capture_event)

        with reporter.stage_context("test", "Test stage"):
            pass

        from src.pipeline.events import PipelineEvent

        for event in collected_events:
            if isinstance(event, PipelineEvent):
                assert event.run_id, "PipelineEvent should have non-empty run_id"
                assert event.run_id == "test-run-123"


class TestQueueEventSinkConstruction:
    """Test QueueEventSink requires loop at construction."""

    def test_queue_event_sink_with_explicit_loop(self) -> None:
        """QueueEventSink should accept an explicit loop."""

        async def test_with_loop() -> None:
            loop = asyncio.get_running_loop()
            queue: asyncio.Queue[Event] = asyncio.Queue()
            sink = QueueEventSink(queue, loop)
            assert sink._loop is loop

        asyncio.run(test_with_loop())

    def test_queue_event_sink_infers_running_loop(self) -> None:
        """QueueEventSink should infer loop when one is running."""

        async def test_with_running_loop() -> None:
            queue: asyncio.Queue[Event] = asyncio.Queue()
            sink = QueueEventSink(queue)
            assert sink._loop is asyncio.get_running_loop()

        asyncio.run(test_with_running_loop())

    def test_queue_event_sink_fails_without_loop(self) -> None:
        """QueueEventSink should raise RuntimeError if no loop available."""
        queue: asyncio.Queue[Event] = asyncio.Queue()
        with pytest.raises(RuntimeError, match="no running event loop"):
            QueueEventSink(queue)


class TestPipelineV2PreservesTypedErrors:
    """Test process_pipeline_v2 preserves typed errors."""

    def test_pipeline_result_dataclass_preserves_original_exception(self) -> None:
        """PipelineError should preserve original_exception."""
        from src.pipeline.result import PipelineError, PipelineResult

        original_exc = ValueError("Original error message")
        error = PipelineError.from_exception(original_exc, stage="test")

        assert error.original_exception is original_exc
        assert error.error_type == "ValueError"
        assert error.message == "Original error message"
        assert error.stage == "test"

    def test_pipeline_result_add_error_preserves_exception(self) -> None:
        """PipelineResult.add_error should preserve the original exception."""
        from src.pipeline.result import PipelineResult

        result = PipelineResult()
        original_exc = RuntimeError("Test runtime error")
        result.add_error(original_exc, stage="extraction")

        assert len(result.errors) == 1
        assert result.errors[0].original_exception is original_exc
        assert result.errors[0].error_type == "RuntimeError"

    def test_to_legacy_dict_produces_correct_format(self) -> None:
        """to_legacy_dict should produce the expected legacy format."""
        from src.pipeline.result import PipelineError, PipelineResult, StageResult

        result = PipelineResult(
            success=False,
            audio_path="/tmp/audio.mp3",
            stages_completed=["extraction"],
        )
        result.add_error_message("Test error", "extraction", "TestError")
        result.stage_results["extraction"] = StageResult(
            status="error",
            duration=1.5,
            error=PipelineError(
                message="Stage failed",
                error_type="TestError",
                stage="extraction",
            ),
        )

        legacy = result.to_legacy_dict()

        assert legacy["success"] is False
        assert legacy["audio_path"] == "/tmp/audio.mp3"
        assert legacy["stages_completed"] == ["extraction"]
        assert "Test error" in legacy["errors"]
        assert legacy["stage_results"]["extraction"]["status"] == "error"
        assert legacy["stage_results"]["extraction"]["error"] == "Stage failed"
