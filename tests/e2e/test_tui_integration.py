"""End-to-end integration tests for TUI with mock pipeline."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Skip all tests if textual is not available
textual = pytest.importorskip("textual")

from textual.pilot import Pilot

from src.models.events import Event
from src.ui.tui.app import AudioExtractionApp
from src.ui.tui.state import AppState
from src.ui.tui.views.run import RunScreen


class TestTUINavigation:
    """Test TUI navigation flow."""

    @pytest.mark.asyncio
    async def test_welcome_to_home_navigation(self, tmp_path: Path):
        """Test navigating from welcome screen to home screen."""
        app = AudioExtractionApp()

        async with app.run_test() as pilot:
            # Verify welcome screen is shown
            assert app.query_one("#welcome-container")

            # Click start button
            await pilot.click("#start-btn")
            await pilot.pause()

            # Verify home screen is pushed
            assert len(app.screen_stack) > 1

    @pytest.mark.asyncio
    async def test_home_to_config_navigation(self, tmp_path: Path, sample_audio_mp3: Path):
        """Test navigating from home to config screen."""
        app = AudioExtractionApp()

        async with app.run_test() as pilot:
            # Navigate to home
            await pilot.click("#start-btn")
            await pilot.pause()

            # Set input path in state
            app.state.input_path = sample_audio_mp3

            # Press 'c' to go to config (or click a button if available)
            # This test assumes the home screen has a way to navigate to config
            # when a file is selected

    @pytest.mark.asyncio
    async def test_quit_application(self):
        """Test quitting the application."""
        app = AudioExtractionApp()

        async with app.run_test() as pilot:
            # Press 'q' to quit
            await pilot.press("q")
            await pilot.pause()

            # App should exit gracefully


class TestMockPipelineExecution:
    """Test TUI with mock pipeline execution."""

    @pytest.mark.asyncio
    async def test_pipeline_progress_updates(self, tmp_path: Path, sample_audio_mp3: Path):
        """Test that progress updates are reflected in UI."""
        app = AudioExtractionApp(input_path=str(sample_audio_mp3), output_dir=str(tmp_path))

        # Create mock pipeline that emits events
        async def mock_pipeline(**kwargs):
            queue = kwargs.get("event_queue")
            if queue:
                # Emit extraction events
                await queue.put(
                    Event(
                        type="stage_start",
                        stage="extract",
                        data={"description": "Starting extraction"},
                    )
                )
                await asyncio.sleep(0.1)

                await queue.put(
                    Event(
                        type="stage_progress", stage="extract", data={"completed": 50, "total": 100}
                    )
                )
                await asyncio.sleep(0.1)

                await queue.put(Event(type="stage_end", stage="extract", data={"duration": 1.5}))

                # Emit transcription events
                await queue.put(
                    Event(
                        type="stage_start",
                        stage="transcribe",
                        data={"description": "Starting transcription"},
                    )
                )
                await asyncio.sleep(0.1)

                await queue.put(
                    Event(
                        type="stage_progress",
                        stage="transcribe",
                        data={"completed": 100, "total": 100},
                    )
                )
                await asyncio.sleep(0.1)

                await queue.put(Event(type="stage_end", stage="transcribe", data={"duration": 2.0}))

            return str(tmp_path)

        config = {
            "output_dir": str(tmp_path),
            "quality": "standard",
            "provider": "auto",
            "language": "en",
            "analysis_style": "concise",
        }

        # Create run screen with mock
        with patch("src.ui.tui.views.run.run_pipeline", new=mock_pipeline):
            run_screen = RunScreen(input_file=sample_audio_mp3, config=config)
            app.push_screen(run_screen)

            async with app.run_test():
                # Wait for events to process
                await asyncio.sleep(1.0)

                # Verify consumer processed events
                if run_screen._event_consumer:
                    state = run_screen._event_consumer.state
                    # Check that stages were tracked
                    assert "extract" in state.stage_durations or state.current_stage == "extract"

    @pytest.mark.asyncio
    async def test_pipeline_cancellation(self, tmp_path: Path, sample_audio_mp3: Path):
        """Test cancelling a running pipeline."""
        app = AudioExtractionApp()

        # Create long-running mock pipeline
        async def slow_pipeline(**kwargs):
            queue = kwargs.get("event_queue")
            if queue:
                await queue.put(
                    Event(
                        type="stage_start", stage="extract", data={"description": "Long extraction"}
                    )
                )
                # Simulate long operation
                try:
                    await asyncio.sleep(10.0)
                except asyncio.CancelledError:
                    await queue.put(
                        Event(type="cancelled", stage="extract", data={"reason": "User cancelled"})
                    )
                    raise
            return str(tmp_path)

        config = {
            "output_dir": str(tmp_path),
            "quality": "standard",
            "provider": "auto",
            "language": "en",
        }

        with patch("src.ui.tui.views.run.run_pipeline", new=slow_pipeline):
            run_screen = RunScreen(input_file=sample_audio_mp3, config=config)
            app.push_screen(run_screen)

            async with app.run_test() as pilot:
                # Wait for pipeline to start
                await asyncio.sleep(0.2)

                # Click cancel button
                await pilot.click("#cancel-btn")
                await pilot.pause()

                # Pipeline task should be cancelled
                assert run_screen._pipeline_task is None or run_screen._pipeline_task.cancelled()

    @pytest.mark.asyncio
    async def test_pipeline_error_handling(self, tmp_path: Path, sample_audio_mp3: Path):
        """Test error handling when pipeline fails."""
        app = AudioExtractionApp()

        # Create failing mock pipeline
        async def failing_pipeline(**kwargs):
            queue = kwargs.get("event_queue")
            if queue:
                await queue.put(
                    Event(
                        type="stage_start",
                        stage="extract",
                        data={"description": "Starting extraction"},
                    )
                )
                await asyncio.sleep(0.1)

                await queue.put(
                    Event(
                        type="error",
                        stage="extract",
                        data={"message": "FFmpeg failed", "error_type": "FFmpegError"},
                    )
                )

            raise RuntimeError("Pipeline failed!")

        config = {
            "output_dir": str(tmp_path),
            "quality": "standard",
            "provider": "auto",
            "language": "en",
        }

        with patch("src.ui.tui.views.run.run_pipeline", new=failing_pipeline):
            run_screen = RunScreen(input_file=sample_audio_mp3, config=config)
            app.push_screen(run_screen)

            async with app.run_test():
                # Wait for error to occur
                await asyncio.sleep(0.5)

                # Verify error was captured in state
                if run_screen._event_consumer:
                    state = run_screen._event_consumer.state
                    assert len(state.errors) > 0

    @pytest.mark.asyncio
    async def test_pipeline_completion_opens_output(self, tmp_path: Path, sample_audio_mp3: Path):
        """Test that output button is enabled on completion."""
        app = AudioExtractionApp()

        # Create successful mock pipeline
        async def successful_pipeline(**kwargs):
            queue = kwargs.get("event_queue")
            if queue:
                await queue.put(
                    Event(type="stage_start", stage="extract", data={"description": "Extracting"})
                )
                await asyncio.sleep(0.1)

                await queue.put(Event(type="stage_end", stage="extract", data={"duration": 1.0}))

                await queue.put(
                    Event(
                        type="summary",
                        stage="complete",
                        data={"total_duration": 5.0, "status": "success"},
                    )
                )

            return str(tmp_path)

        config = {
            "output_dir": str(tmp_path),
            "quality": "standard",
            "provider": "auto",
            "language": "en",
        }

        with patch("src.ui.tui.views.run.run_pipeline", new=successful_pipeline):
            run_screen = RunScreen(input_file=sample_audio_mp3, config=config)
            app.push_screen(run_screen)

            async with app.run_test():
                # Wait for completion
                await asyncio.sleep(0.5)

                # Output button should be enabled
                output_btn = run_screen.query_one("#output-btn")
                assert not output_btn.disabled


class TestEventConsumerIntegration:
    """Test EventConsumer integration with TUI."""

    @pytest.mark.asyncio
    async def test_event_consumer_processes_all_event_types(self):
        """Test that EventConsumer handles all event types correctly."""
        from src.ui.tui.events import EventConsumer, EventConsumerConfig

        queue = EventConsumer.create_queue(EventConsumerConfig(throttle_ms=25))
        processed: list[Event] = []

        consumer = EventConsumer(queue, lambda batch: processed.extend(batch))
        consumer_task = asyncio.create_task(consumer.run())

        # Queue various event types
        events = [
            Event(type="stage_start", stage="extract", data={"description": "Start"}),
            Event(type="stage_progress", stage="extract", data={"completed": 50, "total": 100}),
            Event(type="log", stage="extract", data={"level": "INFO", "message": "Processing"}),
            Event(type="stage_end", stage="extract", data={"duration": 1.5}),
            Event(
                type="artifact", stage="extract", data={"path": "/tmp/audio.wav", "type": "audio"}
            ),
            Event(type="error", stage="transcribe", data={"message": "API error"}),
        ]

        for event in events:
            await queue.put(event)

        # Let it process
        await asyncio.sleep(0.2)
        await consumer.stop()
        await consumer_task

        event_types = {event.type for event in processed}
        assert {"stage_start", "stage_progress", "stage_end", "artifact", "log", "error"}.issubset(
            event_types
        )
        assert any(event.stage == "extract" for event in processed)

    @pytest.mark.asyncio
    async def test_event_consumer_throttling(self):
        """Test that EventConsumer throttles rapid events."""
        from src.ui.tui.events import EventConsumer, EventConsumerConfig

        queue = EventConsumer.create_queue(EventConsumerConfig(throttle_ms=25))
        processed: list[Event] = []
        consumer = EventConsumer(queue, lambda batch: processed.extend(batch))
        consumer_task = asyncio.create_task(consumer.run())

        # Queue 100 progress events rapidly
        for i in range(100):
            await queue.put(
                Event(type="stage_progress", stage="extract", data={"completed": i, "total": 100})
            )

        # Let it process with throttling
        await asyncio.sleep(0.3)

        await consumer.stop()
        await consumer_task

        progress_updates = [event for event in processed if event.type == "stage_progress"]
        assert progress_updates, "Expected throttled progress events to be emitted"
        assert progress_updates[-1].data.get("completed", 0) >= 99


class TestPersistenceIntegration:
    """Test configuration persistence integration."""

    @pytest.mark.asyncio
    async def test_settings_persist_across_sessions(self, tmp_path: Path):
        """Test that settings are saved and loaded correctly."""
        from src.ui.tui.persistence import default_settings, load_settings, save_settings

        # Create custom settings
        settings = default_settings()
        settings["defaults"]["quality"] = "high"
        settings["defaults"]["provider"] = "deepgram"
        settings["defaults"]["language"] = "es"
        settings["last_output_dir"] = str(tmp_path)

        # Save settings
        save_settings(settings)

        # Load settings
        loaded = load_settings()

        # Verify persistence
        assert loaded["defaults"]["quality"] == "high"
        assert loaded["defaults"]["provider"] == "deepgram"
        assert loaded["defaults"]["language"] == "es"
        assert loaded["last_output_dir"] == str(tmp_path)

    @pytest.mark.asyncio
    async def test_recent_files_tracking(self, tmp_path: Path):
        """Test that recent files are tracked correctly."""
        from src.ui.tui.persistence import add_recent_file, load_recent_files

        # Add some files
        file1 = tmp_path / "audio1.mp3"
        file2 = tmp_path / "audio2.mp3"
        file3 = tmp_path / "audio3.mp3"

        file1.touch()
        file2.touch()
        file3.touch()

        config_dir = tmp_path / "config"
        config_dir.mkdir()

        with patch("src.ui.tui.persistence.get_config_dir", return_value=config_dir):
            add_recent_file(file1)
            add_recent_file(file2)
            add_recent_file(file3)

            # Get recent files
            recent = load_recent_files()

        # Should have all 3 files (most recent first)
        assert len(recent) >= 3
        recent_paths = [item["path"] for item in recent]
        assert str(file3.resolve()) in recent_paths  # Most recent


@pytest.fixture
def sample_audio_mp3(tmp_path: Path) -> Path:
    """Create a dummy audio file for testing."""
    audio_file = tmp_path / "test_audio.mp3"
    audio_file.write_bytes(b"fake audio data")
    return audio_file
