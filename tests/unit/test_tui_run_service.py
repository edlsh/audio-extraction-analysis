"""Tests for TUI run service (pipeline wrapper)."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from src.models.events import QueueEventSink
from src.ui.tui.services.run_service import run_pipeline


class TestRunService:
    """Tests for pipeline execution service."""

    @pytest.mark.asyncio
    async def test_run_pipeline_success(self):
        """Test successful pipeline execution."""
        queue = asyncio.Queue()
        sink = QueueEventSink(queue)

        with patch("src.pipeline.simple_pipeline.process_pipeline") as mock_pipeline:
            mock_pipeline.return_value = {"status": "success", "files_created": 3}

            result = await run_pipeline(
                input_path=Path("test.mp4"),
                output_dir=Path("output"),
                quality="speech",
                language="en",
                provider="auto",
                analysis_style="concise",
                event_sink=sink,
                run_id="test-123",
            )

            assert result["status"] == "success"
            assert result["files_created"] == 3

            # Verify pipeline was called with correct args
            mock_pipeline.assert_called_once()
            call_args = mock_pipeline.call_args
            assert call_args.kwargs["input_path"] == Path("test.mp4")
            assert call_args.kwargs["console_manager"] is None  # Disabled in TUI

    @pytest.mark.asyncio
    async def test_run_pipeline_sets_event_sink(self):
        """Test that event sink is properly set and unset."""
        queue = asyncio.Queue()
        sink = QueueEventSink(queue)

        with patch("src.pipeline.simple_pipeline.process_pipeline") as mock_pipeline:
            with patch("src.models.events.set_event_sink") as mock_set:
                mock_pipeline.return_value = {"status": "success"}

                await run_pipeline(
                    input_path=Path("test.mp4"),
                    output_dir=Path("output"),
                    quality="speech",
                    language="en",
                    provider="auto",
                    analysis_style="concise",
                    event_sink=sink,
                    run_id="test-123",
                )

                # Should be called twice: set and unset
                assert mock_set.call_count == 2
                mock_set.assert_any_call(sink)
                mock_set.assert_any_call(None)

    @pytest.mark.asyncio
    async def test_run_pipeline_cancellation_emits_event(self):
        """Test that cancellation emits cancelled event."""
        queue = asyncio.Queue()
        sink = QueueEventSink(queue)

        async def slow_pipeline(*args, **kwargs):
            await asyncio.sleep(10)  # Long-running task

        with patch(
            "src.pipeline.simple_pipeline.process_pipeline",
            side_effect=slow_pipeline,
        ):
            with patch("src.models.events.emit_event") as mock_emit:
                task = asyncio.create_task(
                    run_pipeline(
                        input_path=Path("test.mp4"),
                        output_dir=Path("output"),
                        quality="speech",
                        language="en",
                        provider="auto",
                        analysis_style="concise",
                        event_sink=sink,
                        run_id="test-123",
                    )
                )

                # Cancel after brief delay
                await asyncio.sleep(0.1)
                task.cancel()

                with pytest.raises(asyncio.CancelledError):
                    await task

                # Should have emitted cancelled event
                mock_emit.assert_called_once_with(
                    "cancelled", data={"reason": "User interrupted"}, run_id="test-123"
                )

    @pytest.mark.asyncio
    async def test_run_pipeline_error_emits_event(self):
        """Test that pipeline errors emit error event before raising."""
        queue = asyncio.Queue()
        sink = QueueEventSink(queue)

        with patch("src.pipeline.simple_pipeline.process_pipeline") as mock_pipeline:
            mock_pipeline.side_effect = ValueError("Test error")

            with patch("src.models.events.emit_event") as mock_emit:
                with pytest.raises(ValueError, match="Test error"):
                    await run_pipeline(
                        input_path=Path("test.mp4"),
                        output_dir=Path("output"),
                        quality="speech",
                        language="en",
                        provider="auto",
                        analysis_style="concise",
                        event_sink=sink,
                        run_id="test-123",
                    )

                # Should have emitted error event
                mock_emit.assert_called_once_with(
                    "error", data={"message": "Test error"}, run_id="test-123"
                )

    @pytest.mark.asyncio
    async def test_run_pipeline_quality_enum_conversion(self):
        """Test that quality string is converted to enum."""
        queue = asyncio.Queue()
        sink = QueueEventSink(queue)

        with patch("src.pipeline.simple_pipeline.process_pipeline") as mock_pipeline:
            mock_pipeline.return_value = {}

            await run_pipeline(
                input_path=Path("test.mp4"),
                output_dir=Path("output"),
                quality="high",  # String
                language="en",
                provider="auto",
                analysis_style="concise",
                event_sink=sink,
                run_id="test-123",
            )

            # Should be converted to AudioQuality.HIGH enum
            call_args = mock_pipeline.call_args
            from src.services.audio_extraction import AudioQuality

            assert call_args.kwargs["quality"] == AudioQuality.HIGH

    @pytest.mark.asyncio
    async def test_run_pipeline_event_sink_cleanup_on_error(self):
        """Test that event sink is unset even when pipeline fails."""
        queue = asyncio.Queue()
        sink = QueueEventSink(queue)

        with patch("src.pipeline.simple_pipeline.process_pipeline") as mock_pipeline:
            mock_pipeline.side_effect = RuntimeError("Pipeline failed")

            with patch("src.models.events.set_event_sink") as mock_set:
                with patch("src.models.events.emit_event"):
                    with pytest.raises(RuntimeError):
                        await run_pipeline(
                            input_path=Path("test.mp4"),
                            output_dir=Path("output"),
                            quality="speech",
                            language="en",
                            provider="auto",
                            analysis_style="concise",
                            event_sink=sink,
                            run_id="test-123",
                        )

                    # Should still unset event sink in finally block
                    assert mock_set.call_count == 2
                    mock_set.assert_any_call(None)

    @pytest.mark.asyncio
    async def test_run_pipeline_url_download_emits_stage_events(self):
        """URL ingestion path should emit url_download stage events exactly once."""
        queue = asyncio.Queue()
        sink = QueueEventSink(queue)

        class DummyConfig:
            url_ingest_enabled = True
            url_ingest_download_dir = Path("./data/url_downloads")
            url_ingest_prefer_audio_only = True
            url_ingest_keep_video_default = False

        with patch("src.pipeline.simple_pipeline.process_pipeline", new_callable=AsyncMock) as mock_pipeline:
            mock_pipeline.return_value = {"status": "success"}

            with patch("src.config.get_config", return_value=DummyConfig()):
                with patch("src.ui.tui.services.run_service.UrlIngestionService") as mock_ingestion_cls:
                    mock_ingestion_instance = mock_ingestion_cls.return_value
                    mock_ingestion_instance.ingest.return_value = type(
                        "Result",
                        (),
                        {"audio_path": Path("downloaded.wav"), "source_video_path": None},
                    )()

                    with patch("src.models.events.emit_event") as mock_emit:
                        await run_pipeline(
                            input_path=None,
                            output_dir=Path("output"),
                            quality="speech",
                            language="en",
                            provider="auto",
                            analysis_style="concise",
                            event_sink=sink,
                            run_id="test-123",
                            url="https://example.com/video",
                        )

                        url_download_starts = [
                            call
                            for call in mock_emit.call_args_list
                            if call.args[0] == "stage_start"
                            and call.kwargs.get("stage") == "url_download"
                        ]

                        assert len(url_download_starts) == 1
                        mock_emit.assert_any_call(
                            "stage_start",
                            stage="url_download",
                            data={"description": "Downloading media from URL", "total": 100},
                            run_id="test-123",
                        )
