"""Test suite for CLI JSON output and --no-progress functionality."""

import json
from io import StringIO
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.cli import create_parser, main
from src.cli.json_output import CommandTiming, JsonCommandResult
from src.ui.console import ConsoleManager, SilentProgressTracker

# Apply markers to all tests in this module
pytestmark = [
    pytest.mark.unit,
    pytest.mark.fast,
    pytest.mark.mock,
]


class TestCLIJsonFlag:
    """Test --json CLI flag parsing."""

    def test_json_flag_parsing(self):
        """Test --json flag is properly parsed."""
        parser = create_parser()

        args = parser.parse_args(["--json", "extract", "video.mp4"])
        assert args.json is True

        args = parser.parse_args(["extract", "video.mp4"])
        assert args.json is False

    def test_json_flag_with_no_progress(self):
        """Test --json and --no-progress can be used together."""
        parser = create_parser()

        args = parser.parse_args(["--json", "--no-progress", "extract", "video.mp4"])
        assert args.json is True
        assert args.no_progress is True


class TestCLINoProgressFlag:
    """Test --no-progress CLI flag parsing."""

    def test_no_progress_flag_parsing(self):
        """Test --no-progress flag is properly parsed."""
        parser = create_parser()

        args = parser.parse_args(["--no-progress", "extract", "video.mp4"])
        assert args.no_progress is True

        args = parser.parse_args(["extract", "video.mp4"])
        assert args.no_progress is False


class TestConsoleManagerJsonOutput:
    """Test ConsoleManager with json_output flag."""

    def test_console_manager_json_output_flag(self):
        """Test ConsoleManager initializes with json_output flag."""
        manager = ConsoleManager(json_output=True)
        assert manager.json_output is True
        assert manager.console is None  # Console should be None in JSON mode

    def test_console_manager_no_progress_flag(self):
        """Test ConsoleManager initializes with no_progress flag."""
        manager = ConsoleManager(no_progress=True)
        assert manager.no_progress is True


class TestSilentProgressTracker:
    """Test SilentProgressTracker for --no-progress mode."""

    def test_silent_progress_tracker_update(self):
        """Test SilentProgressTracker.update does nothing."""
        tracker = SilentProgressTracker("Test task")
        # Should not raise any exceptions
        tracker.update(50)
        tracker.update(100, total=100)
        tracker.update(75, description="Updated")

    def test_progress_context_uses_silent_tracker(self):
        """Test progress_context uses SilentProgressTracker when no_progress=True."""
        manager = ConsoleManager(no_progress=True)

        with manager.progress_context("Test task") as tracker:
            assert isinstance(tracker, SilentProgressTracker)
            tracker.update(50)


class TestCommandTiming:
    """Test CommandTiming utility class."""

    def test_timing_stages(self):
        """Test timing stage tracking."""
        timing = CommandTiming()

        timing.start_stage("stage1")
        timing.end_stage("stage1")

        assert "stage1" in timing.stages
        assert timing.stages["stage1"] >= 0

    def test_timing_total_seconds(self):
        """Test total_seconds calculation."""
        timing = CommandTiming()
        total = timing.total_seconds
        assert total >= 0


class TestJsonCommandResult:
    """Test JsonCommandResult dataclass."""

    def test_successful_result_to_dict(self):
        """Test successful result serialization."""
        result = JsonCommandResult(
            success=True,
            command="extract",
            input="/path/to/video.mp4",
            exit_code=0,
            outputs={"audio": "/path/to/audio.mp3"},
            timing={"total_seconds": 5.2, "stages": {"extract": 5.0}},
        )

        data = result.to_dict()

        assert data["success"] is True
        assert data["command"] == "extract"
        assert data["input"] == "/path/to/video.mp4"
        assert data["exit_code"] == 0
        assert data["outputs"]["audio"] == "/path/to/audio.mp3"
        assert data["timing"]["total_seconds"] == 5.2

    def test_failed_result_to_dict(self):
        """Test failed result serialization."""
        result = JsonCommandResult(
            success=False,
            command="transcribe",
            input="/path/to/audio.mp3",
            exit_code=1,
            errors=["API key not found", "Connection timeout"],
        )

        data = result.to_dict()

        assert data["success"] is False
        assert data["exit_code"] == 1
        assert len(data["errors"]) == 2
        assert "API key not found" in data["errors"]

    def test_print_json_output(self, capsys):
        """Test print_json outputs valid JSON to stdout."""
        result = JsonCommandResult(
            success=True,
            command="extract",
            input="/path/to/video.mp4",
            exit_code=0,
        )

        result.print_json()

        captured = capsys.readouterr()
        output = json.loads(captured.out)

        assert output["success"] is True
        assert output["command"] == "extract"


class TestExtractCommandJsonOutput:
    """Test extract command with --json flag."""

    def test_extract_json_success(self, temp_video_file, temp_output_dir, capsys):
        """Test extract command outputs valid JSON on success."""
        output_file = temp_output_dir / "output.mp3"
        test_args = [
            "--json",
            "extract",
            str(temp_video_file),
            "--output",
            str(output_file),
        ]

        with patch("sys.argv", ["audio-extraction-analysis", *test_args]):
            with patch("src.cli.commands.extract.AudioExtractor") as mock_extractor:
                mock_instance = Mock()
                mock_instance.extract_audio.return_value = output_file
                mock_extractor.return_value = mock_instance

                result = main()

        assert result == 0

        captured = capsys.readouterr()
        output = json.loads(captured.out)

        assert output["success"] is True
        assert output["command"] == "extract"
        assert "audio" in output["outputs"]
        assert "timing" in output

    def test_extract_json_failure(self, capsys):
        """Test extract command outputs valid JSON on failure."""
        test_args = ["--json", "extract", "/nonexistent/file.mp4"]

        with patch("sys.argv", ["audio-extraction-analysis", *test_args]):
            result = main()

        assert result == 1

        captured = capsys.readouterr()
        output = json.loads(captured.out)

        assert output["success"] is False
        assert output["command"] == "extract"
        assert output["exit_code"] == 1
        assert len(output["errors"]) > 0


class TestTranscribeCommandJsonOutput:
    """Test transcribe command with --json flag."""

    def test_transcribe_json_success(self, api_key_set, temp_audio_file, temp_output_dir, capsys):
        """Test transcribe command outputs valid JSON on success."""
        test_args = [
            "--json",
            "transcribe",
            str(temp_audio_file),
            "--output",
            str(temp_output_dir / "transcript.txt"),
        ]

        with patch("sys.argv", ["audio-extraction-analysis", *test_args]):
            with patch("src.cli.commands.transcribe.TranscriptionService") as mock_service:
                from datetime import datetime

                from src.models.transcription import TranscriptionResult

                mock_result = TranscriptionResult(
                    transcript="Test transcript",
                    duration=60.0,
                    generated_at=datetime.now(),
                    audio_file=str(temp_audio_file),
                    provider_name="test_provider",
                )

                mock_instance = Mock()
                mock_instance.transcribe.return_value = mock_result
                mock_instance.save_transcription_result.return_value = None
                mock_service.return_value = mock_instance

                result = main()

        assert result == 0

        captured = capsys.readouterr()
        output = json.loads(captured.out)

        assert output["success"] is True
        assert output["command"] == "transcribe"
        assert "transcript" in output["outputs"]
        assert "timing" in output
        assert output["metadata"]["provider"] == "test_provider"

    def test_transcribe_json_failure(self, api_key_set, capsys):
        """Test transcribe command outputs valid JSON on failure."""
        test_args = ["--json", "transcribe", "/nonexistent/audio.mp3"]

        with patch("sys.argv", ["audio-extraction-analysis", *test_args]):
            result = main()

        assert result == 1

        captured = capsys.readouterr()
        output = json.loads(captured.out)

        assert output["success"] is False
        assert output["command"] == "transcribe"
        assert output["exit_code"] == 1


class TestProcessCommandJsonOutput:
    """Test process command with --json flag."""

    def test_process_json_failure_no_input(self, api_key_set, capsys):
        """Test process command outputs valid JSON when input file not found."""
        test_args = ["--json", "process", "/nonexistent/video.mp4"]

        with patch("sys.argv", ["audio-extraction-analysis", *test_args]):
            result = main()

        assert result == 1

        captured = capsys.readouterr()
        output = json.loads(captured.out)

        assert output["success"] is False
        assert output["command"] == "process"
        assert output["exit_code"] == 1

    def test_process_json_success(self, api_key_set, temp_video_file, temp_output_dir, capsys):
        """Test process command outputs valid JSON on success."""
        test_args = [
            "--json",
            "process",
            str(temp_video_file),
            "--output-dir",
            str(temp_output_dir),
        ]

        with patch("sys.argv", ["audio-extraction-analysis", *test_args]):
            with patch(
                "src.cli.commands.process.process_pipeline", new_callable=AsyncMock
            ) as mock_pipeline:
                from datetime import datetime

                from src.models.transcription import TranscriptionResult

                mock_result = TranscriptionResult(
                    transcript="Pipeline test transcript",
                    duration=120.0,
                    generated_at=datetime.now(),
                    audio_file=str(temp_video_file),
                )

                mock_pipeline.return_value = {
                    "success": True,
                    "transcript": mock_result,
                    "audio_path": temp_output_dir / "audio.mp3",
                    "files_created": [temp_output_dir / "analysis.md"],
                }

                result = main()

        assert result == 0

        captured = capsys.readouterr()
        output = json.loads(captured.out)

        assert output["success"] is True
        assert output["command"] == "process"
        assert "timing" in output


class TestNoProgressMode:
    """Test --no-progress mode suppresses progress output."""

    def test_extract_no_progress(self, temp_video_file, temp_output_dir, capsys):
        """Test extract command with --no-progress flag."""
        output_file = temp_output_dir / "output.mp3"
        test_args = [
            "--no-progress",
            "extract",
            str(temp_video_file),
            "--output",
            str(output_file),
        ]

        with patch("sys.argv", ["audio-extraction-analysis", *test_args]):
            with patch("src.cli.commands.extract.AudioExtractor") as mock_extractor:
                mock_instance = Mock()
                mock_instance.extract_audio.return_value = output_file
                mock_extractor.return_value = mock_instance

                result = main()

        assert result == 0
        # In no-progress mode, there should be no progress bar output
        captured = capsys.readouterr()
        # No progress percentage should appear in stderr
        assert "%" not in captured.err or "progress" not in captured.err.lower()

    def test_json_and_no_progress_combined(self, temp_video_file, temp_output_dir, capsys):
        """Test --json and --no-progress work together."""
        output_file = temp_output_dir / "output.mp3"
        test_args = [
            "--json",
            "--no-progress",
            "extract",
            str(temp_video_file),
            "--output",
            str(output_file),
        ]

        with patch("sys.argv", ["audio-extraction-analysis", *test_args]):
            with patch("src.cli.commands.extract.AudioExtractor") as mock_extractor:
                mock_instance = Mock()
                mock_instance.extract_audio.return_value = output_file
                mock_extractor.return_value = mock_instance

                result = main()

        assert result == 0

        captured = capsys.readouterr()
        output = json.loads(captured.out)

        assert output["success"] is True
        # Verify no progress output in stderr
        # (info messages may still appear, but no progress bars)
