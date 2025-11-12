"""Integration tests for pipeline progress tracking.

Migrated from AudioProcessingPipeline to simple_pipeline.process_pipeline().
"""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.pipeline.simple_pipeline import process_pipeline
from src.services.audio_extraction import AudioQuality
from src.ui.console import ConsoleManager


@pytest.mark.asyncio
async def test_pipeline_with_progress():
    """Test complete pipeline with progress tracking using JSON mode for stability."""
    console_manager = ConsoleManager(json_output=True)

    with patch(
        "src.services.audio_extraction_async.safe_validate_media_file",
        return_value=Path("test_input.mp4"),
    ), patch("src.pipeline.simple_pipeline.AsyncAudioExtractor") as mock_extractor_class, patch(
        "src.pipeline.simple_pipeline.TranscriptionService"
    ) as mock_transcriber, patch(
        "src.pipeline.simple_pipeline.FullAnalyzer"
    ) as mock_analyzer:
        # Setup mocks for async extraction
        mock_extractor = AsyncMock()
        mock_extractor_class.return_value = mock_extractor
        mock_extractor.extract_audio_async = AsyncMock(return_value=Path("/tmp/test_audio.wav"))

        mock_transcriber_instance = MagicMock()
        mock_transcriber.return_value = mock_transcriber_instance
        # Return a simple object to carry through to analyzer
        mock_transcriber_instance.transcribe_with_progress = AsyncMock(return_value=MagicMock())

        mock_analyzer_instance = MagicMock()
        mock_analyzer.return_value = mock_analyzer_instance
        mock_analyzer_instance.analyze_and_save.return_value = {"a": Path("analysis_file.md")}

        # Execute
        with tempfile.TemporaryDirectory() as temp_dir:
            results = await process_pipeline(
                input_path="test_input.mp4",
                output_dir=temp_dir,
                quality=AudioQuality.SPEECH,
                language="en",
                provider="auto",
                analysis_style="full",
                console_manager=console_manager,
            )

        assert "audio_path" in results
        assert "transcript" in results
        assert "analysis_files" in results
        assert "stage_results" in results

        # Verify stages
        assert results["stage_results"]["extraction"]["status"] == "complete"
        assert results["stage_results"]["transcription"]["status"] == "complete"
        assert results["stage_results"]["analysis"]["status"] == "complete"


@pytest.mark.asyncio
async def test_pipeline_extraction_failure():
    """Test pipeline handles audio extraction failures gracefully."""
    console_manager = ConsoleManager(json_output=True)

    with patch("src.pipeline.simple_pipeline.AsyncAudioExtractor") as mock_extractor_class:
        # Mock extractor to raise exception
        mock_extractor = AsyncMock()
        mock_extractor_class.return_value = mock_extractor
        mock_extractor.extract_audio_async.side_effect = RuntimeError("Extraction failed")

        with tempfile.TemporaryDirectory() as temp_dir:
            results = await process_pipeline(
                input_path="test_input.mp4",
                output_dir=temp_dir,
                quality=AudioQuality.SPEECH,
                language="en",
                provider="auto",
                analysis_style="full",
                console_manager=console_manager,
            )

        # Should fail gracefully
        assert results["success"] is False
        assert len(results["errors"]) > 0
        assert any("extraction" in err.lower() for err in results["errors"])
        assert "extraction" not in results.get("stage_results", {})


@pytest.mark.asyncio
async def test_pipeline_transcription_failure():
    """Test pipeline handles transcription failures gracefully."""
    console_manager = ConsoleManager(json_output=True)

    with patch(
        "src.services.audio_extraction_async.safe_validate_media_file",
        return_value=Path("test_input.mp4"),
    ), patch("src.pipeline.simple_pipeline.AsyncAudioExtractor") as mock_extractor_class, patch(
        "src.pipeline.simple_pipeline.TranscriptionService"
    ) as mock_transcriber_class:
        # Mock successful extraction
        mock_extractor = AsyncMock()
        mock_extractor_class.return_value = mock_extractor
        mock_extractor.extract_audio_async = AsyncMock(return_value=Path("/tmp/test.mp3"))

        # Mock transcription failure
        mock_transcriber = MagicMock()
        mock_transcriber_class.return_value = mock_transcriber
        mock_transcriber.transcribe_with_progress = AsyncMock(return_value=None)

        with tempfile.TemporaryDirectory() as temp_dir:
            results = await process_pipeline(
                input_path="test_input.mp4",
                output_dir=temp_dir,
                quality=AudioQuality.SPEECH,
                language="en",
                provider="auto",
                analysis_style="full",
                console_manager=console_manager,
            )

        # Should fail after extraction succeeds but transcription fails
        assert results["success"] is False
        assert "audio_extraction" in results.get("stages_completed", [])
        assert "transcription" not in results.get("stages_completed", [])
        assert len(results["errors"]) > 0
        assert any("transcription" in err.lower() for err in results["errors"])


@pytest.mark.asyncio
async def test_pipeline_analysis_failure_partial_success():
    """Test that analysis failure doesn't prevent overall success if transcript exists."""
    console_manager = ConsoleManager(json_output=True)

    with patch(
        "src.services.audio_extraction_async.safe_validate_media_file",
        return_value=Path("test_input.mp4"),
    ), patch("src.pipeline.simple_pipeline.AsyncAudioExtractor") as mock_extractor_class, patch(
        "src.pipeline.simple_pipeline.TranscriptionService"
    ) as mock_transcriber_class, patch(
        "src.pipeline.simple_pipeline.FullAnalyzer"
    ) as mock_analyzer:
        # Mock successful extraction and transcription
        mock_extractor = AsyncMock()
        mock_extractor_class.return_value = mock_extractor
        mock_extractor.extract_audio_async = AsyncMock(return_value=Path("/tmp/test.mp3"))

        mock_transcriber = MagicMock()
        mock_transcriber_class.return_value = mock_transcriber
        mock_transcriber.transcribe_with_progress = AsyncMock(return_value=MagicMock())

        # Mock analysis failure
        mock_analyzer_instance = MagicMock()
        mock_analyzer.return_value = mock_analyzer_instance
        mock_analyzer_instance.analyze_and_save.side_effect = RuntimeError("Analysis failed")

        with tempfile.TemporaryDirectory() as temp_dir:
            results = await process_pipeline(
                input_path="test_input.mp4",
                output_dir=temp_dir,
                quality=AudioQuality.SPEECH,
                language="en",
                provider="auto",
                analysis_style="full",
                console_manager=console_manager,
            )

        # Should succeed overall since transcript was created
        assert results["success"] is True
        assert "audio_extraction" in results["stages_completed"]
        assert "transcription" in results["stages_completed"]
        assert "analysis" not in results["stages_completed"]
        assert len(results["errors"]) > 0
        assert any("analysis" in err.lower() for err in results["errors"])


@pytest.mark.asyncio
async def test_pipeline_concise_analysis():
    """Test pipeline with concise analysis style."""
    console_manager = ConsoleManager(json_output=True)

    with patch(
        "src.services.audio_extraction_async.safe_validate_media_file",
        return_value=Path("test_input.mp4"),
    ), patch("src.pipeline.simple_pipeline.AsyncAudioExtractor") as mock_extractor_class, patch(
        "src.pipeline.simple_pipeline.TranscriptionService"
    ) as mock_transcriber_class, patch(
        "src.pipeline.simple_pipeline.ConciseAnalyzer"
    ) as mock_analyzer:
        # Setup mocks
        mock_extractor = AsyncMock()
        mock_extractor_class.return_value = mock_extractor
        mock_extractor.extract_audio_async = AsyncMock(return_value=Path("/tmp/test.mp3"))

        mock_transcriber = MagicMock()
        mock_transcriber_class.return_value = mock_transcriber
        mock_transcriber.transcribe_with_progress = AsyncMock(return_value=MagicMock())

        mock_analyzer_instance = MagicMock()
        mock_analyzer.return_value = mock_analyzer_instance
        mock_analyzer_instance.analyze_and_save.return_value = Path("concise_analysis.md")

        with tempfile.TemporaryDirectory() as temp_dir:
            results = await process_pipeline(
                input_path="test_input.mp4",
                output_dir=temp_dir,
                quality=AudioQuality.SPEECH,
                language="en",
                provider="auto",
                analysis_style="concise",
                console_manager=console_manager,
            )

        assert results["success"] is True
        assert "analysis" in results["stages_completed"]
        # Concise analysis returns a list with single path
        assert isinstance(results["analysis_files"], list)
        mock_analyzer_instance.analyze_and_save.assert_called_once()


@pytest.mark.asyncio
async def test_pipeline_progress_callbacks():
    """Test that progress callbacks are invoked during pipeline execution."""
    console_manager = ConsoleManager(json_output=True)

    extraction_progress_called = []
    transcription_progress_called = []

    with patch(
        "src.services.audio_extraction_async.safe_validate_media_file",
        return_value=Path("test_input.mp4"),
    ), patch("src.pipeline.simple_pipeline.AsyncAudioExtractor") as mock_extractor_class, patch(
        "src.pipeline.simple_pipeline.TranscriptionService"
    ) as mock_transcriber_class, patch(
        "src.pipeline.simple_pipeline.FullAnalyzer"
    ) as mock_analyzer:
        # Mock extraction with progress callback
        mock_extractor = AsyncMock()
        mock_extractor_class.return_value = mock_extractor

        async def mock_extract_with_callback(*args, **kwargs):
            callback = kwargs.get("progress_callback")
            if callback:
                extraction_progress_called.append(True)
                callback(50, 100)
                callback(100, 100)
            return Path("/tmp/test.mp3")

        mock_extractor.extract_audio_async.side_effect = mock_extract_with_callback

        # Mock transcription with progress callback
        mock_transcriber = MagicMock()
        mock_transcriber_class.return_value = mock_transcriber

        async def mock_transcribe_with_callback(*args, **kwargs):
            callback = kwargs.get("progress_callback")
            if callback:
                transcription_progress_called.append(True)
                callback(50, 100)
                callback(100, 100)
            return MagicMock()

        mock_transcriber.transcribe_with_progress = AsyncMock(
            side_effect=mock_transcribe_with_callback
        )

        mock_analyzer_instance = MagicMock()
        mock_analyzer.return_value = mock_analyzer_instance
        mock_analyzer_instance.analyze_and_save.return_value = {"a": Path("test.md")}

        with tempfile.TemporaryDirectory() as temp_dir:
            results = await process_pipeline(
                input_path="test_input.mp4",
                output_dir=temp_dir,
                quality=AudioQuality.SPEECH,
                language="en",
                provider="auto",
                analysis_style="full",
                console_manager=console_manager,
            )

        assert results["success"] is True
        # Verify progress callbacks were invoked
        assert len(extraction_progress_called) > 0
        assert len(transcription_progress_called) > 0


@pytest.mark.asyncio
async def test_pipeline_without_console_manager():
    """Test pipeline creates default ConsoleManager when none provided."""

    with patch(
        "src.services.audio_extraction_async.safe_validate_media_file",
        return_value=Path("test_input.mp4"),
    ), patch("src.pipeline.simple_pipeline.AsyncAudioExtractor") as mock_extractor_class, patch(
        "src.pipeline.simple_pipeline.TranscriptionService"
    ) as mock_transcriber_class, patch(
        "src.pipeline.simple_pipeline.FullAnalyzer"
    ) as mock_analyzer:
        # Setup mocks
        mock_extractor = AsyncMock()
        mock_extractor_class.return_value = mock_extractor
        mock_extractor.extract_audio_async = AsyncMock(return_value=Path("/tmp/test.mp3"))

        mock_transcriber = MagicMock()
        mock_transcriber_class.return_value = mock_transcriber
        mock_transcriber.transcribe_with_progress = AsyncMock(return_value=MagicMock())

        mock_analyzer_instance = MagicMock()
        mock_analyzer.return_value = mock_analyzer_instance
        mock_analyzer_instance.analyze_and_save.return_value = {"a": Path("test.md")}

        with tempfile.TemporaryDirectory() as temp_dir:
            results = await process_pipeline(
                input_path="test_input.mp4",
                output_dir=temp_dir,
                quality=AudioQuality.SPEECH,
                language="en",
                provider="auto",
                analysis_style="full",
                console_manager=None,
            )

        # Should succeed with default console manager
        assert results["success"] is True
        assert "stage_results" in results


@pytest.mark.asyncio
async def test_pipeline_stage_results_tracking():
    """Test that stage results properly track duration and status."""
    console_manager = ConsoleManager(json_output=True)

    with patch(
        "src.services.audio_extraction_async.safe_validate_media_file",
        return_value=Path("test_input.mp4"),
    ), patch("src.pipeline.simple_pipeline.AsyncAudioExtractor") as mock_extractor_class, patch(
        "src.pipeline.simple_pipeline.TranscriptionService"
    ) as mock_transcriber_class, patch(
        "src.pipeline.simple_pipeline.FullAnalyzer"
    ) as mock_analyzer:
        # Setup mocks
        mock_extractor = AsyncMock()
        mock_extractor_class.return_value = mock_extractor
        mock_extractor.extract_audio_async = AsyncMock(return_value=Path("/tmp/test.mp3"))

        mock_transcriber = MagicMock()
        mock_transcriber_class.return_value = mock_transcriber
        mock_transcriber.transcribe_with_progress = AsyncMock(return_value=MagicMock())

        mock_analyzer_instance = MagicMock()
        mock_analyzer.return_value = mock_analyzer_instance
        mock_analyzer_instance.analyze_and_save.return_value = {"a": Path("test.md")}

        with tempfile.TemporaryDirectory() as temp_dir:
            results = await process_pipeline(
                input_path="test_input.mp4",
                output_dir=temp_dir,
                quality=AudioQuality.SPEECH,
                language="en",
                provider="auto",
                analysis_style="full",
                console_manager=console_manager,
            )

        # Verify stage results structure
        assert "stage_results" in results
        stage_results = results["stage_results"]

        # Check extraction stage
        assert "extraction" in stage_results
        assert stage_results["extraction"]["status"] == "complete"
        assert "duration" in stage_results["extraction"]
        assert stage_results["extraction"]["duration"] > 0
        assert "output" in stage_results["extraction"]

        # Check transcription stage
        assert "transcription" in stage_results
        assert stage_results["transcription"]["status"] == "complete"
        assert "duration" in stage_results["transcription"]
        assert stage_results["transcription"]["duration"] > 0

        # Check analysis stage
        assert "analysis" in stage_results
        assert stage_results["analysis"]["status"] == "complete"
        assert "duration" in stage_results["analysis"]
        assert stage_results["analysis"]["duration"] > 0

        # Check total duration
        assert "total" in stage_results
        assert stage_results["total"]["status"] == "complete"
        assert stage_results["total"]["duration"] > 0


@pytest.mark.asyncio
async def test_pipeline_debug_dump_on_error():
    """Test that debug information is available on error when debug flag is enabled."""
    import os

    # Enable debug mode
    original_debug = os.getenv("AUDIO_PIPELINE_DEBUG")
    os.environ["AUDIO_PIPELINE_DEBUG"] = "true"

    try:
        console_manager = ConsoleManager(json_output=True)

        with patch("src.pipeline.simple_pipeline.AsyncAudioExtractor") as mock_extractor_class:
            # Mock extraction to fail
            mock_extractor = AsyncMock()
            mock_extractor_class.return_value = mock_extractor
            mock_extractor.extract_audio_async.side_effect = RuntimeError("Test error")

            with tempfile.TemporaryDirectory() as temp_dir:
                results = await process_pipeline(
                    input_path="test_input.mp4",
                    output_dir=temp_dir,
                    quality=AudioQuality.SPEECH,
                    language="en",
                    provider="auto",
                    analysis_style="full",
                    console_manager=console_manager,
                )

                # Verify error information is available
                assert results["success"] is False
                assert len(results["errors"]) > 0
                assert "stage_results" in results

    finally:
        # Restore original debug setting
        if original_debug is not None:
            os.environ["AUDIO_PIPELINE_DEBUG"] = original_debug
        else:
            os.environ.pop("AUDIO_PIPELINE_DEBUG", None)


@pytest.mark.asyncio
async def test_pipeline_cleanup_partial_files():
    """Test that partial files are cleaned up on failure."""
    console_manager = ConsoleManager(json_output=True)

    with patch(
        "src.services.audio_extraction_async.safe_validate_media_file",
        return_value=Path("test_input.mp4"),
    ), patch("src.pipeline.simple_pipeline.AsyncAudioExtractor") as mock_extractor_class, patch(
        "src.pipeline.simple_pipeline.TranscriptionService"
    ) as mock_transcriber_class:
        # Mock successful extraction
        mock_extractor = AsyncMock()
        mock_extractor_class.return_value = mock_extractor
        test_audio_path = Path("/tmp/test_audio.mp3")
        mock_extractor.extract_audio_async = AsyncMock(return_value=test_audio_path)

        # Mock transcription to fail after extraction
        mock_transcriber = MagicMock()
        mock_transcriber_class.return_value = mock_transcriber
        mock_transcriber.transcribe_with_progress = AsyncMock(
            side_effect=RuntimeError("Transcription failed")
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            results = await process_pipeline(
                input_path="test_input.mp4",
                output_dir=temp_dir,
                quality=AudioQuality.SPEECH,
                language="en",
                provider="auto",
                analysis_style="full",
                console_manager=console_manager,
            )

        # Verify cleanup was attempted
        assert results["success"] is False
        # Pipeline should have tracked created files
        assert "files_created" in results


@pytest.mark.asyncio
async def test_pipeline_files_created_tracking():
    """Test that all created files are tracked in results."""
    console_manager = ConsoleManager(json_output=True)

    with patch(
        "src.services.audio_extraction_async.safe_validate_media_file",
        return_value=Path("test_input.mp4"),
    ), patch("src.pipeline.simple_pipeline.AsyncAudioExtractor") as mock_extractor_class, patch(
        "src.pipeline.simple_pipeline.TranscriptionService"
    ) as mock_transcriber_class, patch(
        "src.pipeline.simple_pipeline.FullAnalyzer"
    ) as mock_analyzer:
        # Setup mocks
        mock_extractor = AsyncMock()
        mock_extractor_class.return_value = mock_extractor
        test_audio_path = "/tmp/test_audio.mp3"
        mock_extractor.extract_audio_async = AsyncMock(return_value=Path(test_audio_path))

        mock_transcriber = MagicMock()
        mock_transcriber_class.return_value = mock_transcriber
        mock_transcriber.transcribe_with_progress = AsyncMock(return_value=MagicMock())

        mock_analyzer_instance = MagicMock()
        mock_analyzer.return_value = mock_analyzer_instance
        analysis_files = ["/tmp/summary.md", "/tmp/topics.md", "/tmp/sentiment.md"]
        mock_analyzer_instance.analyze_and_save.return_value = {
            "summary": Path(analysis_files[0]),
            "topics": Path(analysis_files[1]),
            "sentiment": Path(analysis_files[2]),
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            results = await process_pipeline(
                input_path="test_input.mp4",
                output_dir=temp_dir,
                quality=AudioQuality.SPEECH,
                language="en",
                provider="auto",
                analysis_style="full",
                console_manager=console_manager,
            )

        # Verify all files are tracked
        assert "files_created" in results
        files_created = results["files_created"]

        # Audio file should be tracked
        assert test_audio_path in files_created

        # All analysis files should be tracked
        for analysis_file in analysis_files:
            assert analysis_file in files_created
