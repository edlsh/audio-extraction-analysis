"""Unit tests for RunScreen."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Skip all tests if textual is not available
textual = pytest.importorskip("textual")

from src.ui.tui.views.run import RunScreen


class TestRunScreen:
    """Tests for RunScreen."""

    @pytest.fixture
    def mock_input_file(self, tmp_path: Path) -> Path:
        """Create a mock input file."""
        input_file = tmp_path / "test_audio.mp3"
        input_file.write_bytes(b"fake audio data")
        return input_file

    @pytest.fixture
    def mock_config(self, tmp_path: Path) -> dict:
        """Create a mock configuration."""
        return {
            "output_dir": str(tmp_path / "output"),
            "quality": "standard",
            "provider": "auto",
            "language": "en",
            "analysis_style": "concise",
            "export_markdown": True,
            "export_html": False,
        }

    def test_run_screen_initialization(self, mock_input_file: Path, mock_config: dict):
        """Test RunScreen initializes correctly."""
        screen = RunScreen(input_file=mock_input_file, config=mock_config)

        assert screen.input_file == mock_input_file
        assert screen.config == mock_config
        assert screen._event_consumer is None
        assert screen._pipeline_task is None
        assert screen._running is False

    @pytest.mark.asyncio
    async def test_run_screen_compose(self, mock_input_file: Path, mock_config: dict):
        """Test RunScreen composes widgets correctly."""
        screen = RunScreen(input_file=mock_input_file, config=mock_config)

        # Compose should yield widgets
        widgets = list(screen.compose())

        # Should have Header, containers, buttons, Footer
        assert len(widgets) > 0

    @pytest.mark.asyncio
    async def test_cancel_action_with_running_pipeline(
        self, mock_input_file: Path, mock_config: dict
    ):
        """Test cancel action when pipeline is running."""
        screen = RunScreen(input_file=mock_input_file, config=mock_config)

        # Create a mock pipeline task
        screen._pipeline_task = asyncio.create_task(asyncio.sleep(10))
        screen._running = True

        # Cancel
        await screen.action_cancel()

        # Pipeline should be cancelled
        assert screen._pipeline_task.cancelled() or not screen._running

    @pytest.mark.asyncio
    async def test_cancel_action_with_no_pipeline(self, mock_input_file: Path, mock_config: dict):
        """Test cancel action when no pipeline is running."""
        screen = RunScreen(input_file=mock_input_file, config=mock_config)

        # Should not raise error
        await screen.action_cancel()

    @pytest.mark.asyncio
    async def test_open_output_action_with_valid_dir(
        self, mock_input_file: Path, mock_config: dict, tmp_path: Path
    ):
        """Test open output action with valid directory."""
        screen = RunScreen(input_file=mock_input_file, config=mock_config)

        # Set output dir
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        screen._output_dir = output_dir

        # Mock os_open
        with patch("src.ui.tui.views.run.os_open") as mock_open:
            mock_open.return_value = asyncio.coroutine(lambda: None)()

            await screen.action_open_output()

    @pytest.mark.asyncio
    async def test_open_output_action_with_missing_dir(
        self, mock_input_file: Path, mock_config: dict
    ):
        """Test open output action with missing directory."""
        screen = RunScreen(input_file=mock_input_file, config=mock_config)

        # No output dir set
        screen._output_dir = None

        # Should handle gracefully
        await screen.action_open_output()

    @pytest.mark.asyncio
    async def test_pipeline_execution_success(
        self, mock_input_file: Path, mock_config: dict, tmp_path: Path
    ):
        """Test successful pipeline execution."""
        from src.models.events import Event

        # Mock run_pipeline
        async def mock_run_pipeline(**kwargs):
            queue = kwargs.get("event_queue")
            if queue:
                await queue.put(
                    Event(type="stage_start", stage="extract", data={"description": "Extracting"})
                )
                await asyncio.sleep(0.1)
                await queue.put(Event(type="stage_end", stage="extract", data={"duration": 1.0}))
            return str(tmp_path / "output")

        with patch("src.ui.tui.views.run.run_pipeline", new=mock_run_pipeline):
            screen = RunScreen(input_file=mock_input_file, config=mock_config)

            # Initialize event consumer
            from src.ui.tui.events import EventConsumer

            screen._event_consumer = EventConsumer()

            # Run pipeline
            await screen._run_pipeline_with_events()

            # Should complete successfully
            assert screen._output_dir is not None

    @pytest.mark.asyncio
    async def test_pipeline_execution_error(self, mock_input_file: Path, mock_config: dict):
        """Test pipeline execution with error."""
        from src.models.events import Event

        # Mock failing run_pipeline
        async def mock_failing_pipeline(**kwargs):
            queue = kwargs.get("event_queue")
            if queue:
                await queue.put(
                    Event(type="error", stage="extract", data={"message": "FFmpeg failed"})
                )
            raise RuntimeError("Pipeline failed")

        with patch("src.ui.tui.views.run.run_pipeline", new=mock_failing_pipeline):
            screen = RunScreen(input_file=mock_input_file, config=mock_config)

            # Initialize event consumer
            from src.ui.tui.events import EventConsumer

            screen._event_consumer = EventConsumer()

            # Run pipeline (should handle error gracefully)
            try:
                await screen._run_pipeline_with_events()
            except RuntimeError:
                pass  # Expected

            # Should not be running
            assert not screen._running

    @pytest.mark.asyncio
    async def test_pipeline_cancellation(self, mock_input_file: Path, mock_config: dict):
        """Test pipeline cancellation."""
        from src.models.events import Event

        # Mock long-running pipeline
        async def mock_long_pipeline(**kwargs):
            queue = kwargs.get("event_queue")
            if queue:
                await queue.put(
                    Event(
                        type="stage_start", stage="extract", data={"description": "Long operation"}
                    )
                )
                try:
                    await asyncio.sleep(10.0)
                except asyncio.CancelledError:
                    await queue.put(
                        Event(
                            type="cancelled", stage="extract", data={"reason": "Cancelled by user"}
                        )
                    )
                    raise
            return ""

        with patch("src.ui.tui.views.run.run_pipeline", new=mock_long_pipeline):
            screen = RunScreen(input_file=mock_input_file, config=mock_config)

            # Initialize event consumer
            from src.ui.tui.events import EventConsumer

            screen._event_consumer = EventConsumer()

            # Start pipeline
            screen._pipeline_task = asyncio.create_task(screen._run_pipeline_with_events())
            screen._running = True

            # Wait a bit
            await asyncio.sleep(0.1)

            # Cancel
            screen._pipeline_task.cancel()

            # Wait for cancellation
            try:
                await screen._pipeline_task
            except asyncio.CancelledError:
                pass

            # Task should be cancelled
            assert screen._pipeline_task.cancelled()

    @pytest.mark.asyncio
    async def test_back_action_blocks_when_running(self, mock_input_file: Path, mock_config: dict):
        """Test back action is blocked when pipeline is running."""
        screen = RunScreen(input_file=mock_input_file, config=mock_config)

        # Set running
        screen._running = True

        # Back action should not pop screen
        screen.action_back()

        # (Can't easily verify screen stack without full app context)

    @pytest.mark.asyncio
    async def test_back_action_allowed_when_not_running(
        self, mock_input_file: Path, mock_config: dict
    ):
        """Test back action is allowed when pipeline is not running."""
        screen = RunScreen(input_file=mock_input_file, config=mock_config)

        # Not running
        screen._running = False

        # Back action should work
        screen.action_back()


class TestRunScreenIntegration:
    """Integration tests for RunScreen with EventConsumer."""

    @pytest.mark.asyncio
    async def test_event_consumer_integration(self, tmp_path: Path):
        """Test RunScreen integrates correctly with EventConsumer."""
        from src.models.events import Event
        from src.ui.tui.events import EventConsumer

        input_file = tmp_path / "test.mp3"
        input_file.write_bytes(b"fake")

        config = {
            "output_dir": str(tmp_path),
            "quality": "standard",
            "provider": "auto",
            "language": "en",
        }

        # Mock pipeline that emits events
        async def mock_pipeline(**kwargs):
            queue = kwargs.get("event_queue")
            if queue:
                await queue.put(
                    Event(type="stage_start", stage="extract", data={"description": "Starting"})
                )
                await queue.put(
                    Event(
                        type="stage_progress",
                        stage="extract",
                        data={"completed": 100, "total": 100},
                    )
                )
                await queue.put(
                    Event(
                        type="log",
                        stage="extract",
                        data={"level": "INFO", "message": "Extracting audio"},
                    )
                )
                await queue.put(Event(type="stage_end", stage="extract", data={"duration": 2.0}))
            return str(tmp_path)

        with patch("src.ui.tui.views.run.run_pipeline", new=mock_pipeline):
            screen = RunScreen(input_file=input_file, config=config)
            screen._event_consumer = EventConsumer()

            # Run pipeline
            await screen._run_pipeline_with_events()

            # Let consumer process
            await asyncio.sleep(0.2)

            # Verify events were processed
            state = screen._event_consumer.state
            assert len(state.logs) > 0
            assert "extract" in state.stage_durations or state.current_stage == "extract"
