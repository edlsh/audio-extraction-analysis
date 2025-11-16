"""Test suite for CLI functionality."""

from unittest.mock import Mock, patch

import pytest

from src.cli import create_parser, main


class TestCLIParser:
    """Test CLI argument parsing."""

    def test_parser_creation(self):
        """Test that parser is created successfully."""
        parser = create_parser()
        assert parser is not None
        assert parser.prog == "audio-extraction-analysis"

    def test_version_argument(self):
        """Test --version argument."""
        parser = create_parser()

        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(["--version"])

        assert exc_info.value.code == 0

    def test_extract_command_parsing(self):
        """Test extract subcommand parsing."""
        parser = create_parser()

        args = parser.parse_args(["extract", "video.mp4"])
        assert args.command == "extract"
        assert args.input_file == "video.mp4"
        assert args.quality == "speech"  # default
        assert args.output is None  # default

    def test_extract_command_with_options(self):
        """Test extract subcommand with all options."""
        parser = create_parser()

        args = parser.parse_args(
            ["extract", "video.mp4", "--output", "audio.mp3", "--quality", "high"]
        )
        assert args.command == "extract"
        assert args.input_file == "video.mp4"
        assert args.output == "audio.mp3"
        assert args.quality == "high"

    def test_transcribe_command_parsing(self):
        """Test transcribe subcommand parsing."""
        parser = create_parser()

        args = parser.parse_args(["transcribe", "audio.mp3"])
        assert args.command == "transcribe"
        assert args.audio_file == "audio.mp3"
        assert args.language == "en"  # default
        assert args.output is None  # default

    def test_transcribe_command_with_options(self):
        """Test transcribe subcommand with all options."""
        parser = create_parser()

        args = parser.parse_args(
            [
                "transcribe",
                "audio.mp3",
                "--output",
                "transcript.txt",
                "--language",
                "es",
                "--provider",
                "deepgram",
            ]
        )
        assert args.command == "transcribe"
        assert args.audio_file == "audio.mp3"
        assert args.output == "transcript.txt"
        assert args.language == "es"
        assert args.provider == "deepgram"

    def test_transcribe_command_provider_default(self):
        """Test transcribe subcommand provider defaults to auto."""
        parser = create_parser()

        args = parser.parse_args(["transcribe", "audio.mp3"])
        assert args.provider == "auto"

    def test_transcribe_command_provider_choices(self):
        """Test transcribe subcommand provider argument accepts valid choices."""
        parser = create_parser()

        # Test valid choices
        for provider in ["deepgram", "elevenlabs", "auto"]:
            args = parser.parse_args(["transcribe", "audio.mp3", "--provider", provider])
            assert args.provider == provider

        # Test invalid choice
        with pytest.raises(SystemExit):
            parser.parse_args(["transcribe", "audio.mp3", "--provider", "invalid"])

    def test_process_command_parsing(self):
        """Test process subcommand parsing with local file."""
        parser = create_parser()

        args = parser.parse_args(["process", "video.mp4"])
        assert args.command == "process"
        assert args.video_file == "video.mp4"
        assert getattr(args, "url", None) is None
        assert args.quality == "speech"  # default
        assert args.language == "en"  # default
        assert args.output_dir is None  # default

    def test_process_command_parsing_with_url(self):
        """Test process subcommand parsing with URL only."""
        parser = create_parser()

        args = parser.parse_args(["process", "--url", "https://example.com/video"])
        assert args.command == "process"
        assert args.video_file is None
        assert args.url == "https://example.com/video"

    def test_process_command_with_options(self):
        """Test process subcommand with all options."""
        parser = create_parser()

        args = parser.parse_args(
            [
                "process",
                "video.mp4",
                "--output-dir",
                "./results",
                "--quality",
                "standard",
                "--language",
                "fr",
                "--provider",
                "elevenlabs",
            ]
        )
        assert args.command == "process"
        assert args.video_file == "video.mp4"
        assert args.output_dir == "./results"
        assert args.quality == "standard"
        assert args.language == "fr"
        assert args.provider == "elevenlabs"

    def test_process_command_provider_default(self):
        """Test process subcommand provider defaults to auto."""
        parser = create_parser()

        args = parser.parse_args(["process", "video.mp4"])
        assert args.provider == "auto"

        # Also works when using --url
        args = parser.parse_args(["process", "--url", "https://example.com/video"])
        assert args.provider == "auto"

    def test_verbose_flag(self):
        """Test --verbose flag parsing."""
        parser = create_parser()

        args = parser.parse_args(["--verbose", "extract", "video.mp4"])
        assert args.verbose is True

    def test_invalid_quality_choice(self):
        """Test invalid quality choice raises error."""
        parser = create_parser()

        with pytest.raises(SystemExit):
            parser.parse_args(["extract", "video.mp4", "--quality", "invalid"])


class TestCLIExtractCommand:
    """Test CLI extract command functionality."""

    def test_extract_command_success(self, temp_video_file, temp_output_dir):
        """Test successful extract command execution."""
        test_args = [
            "extract",
            str(temp_video_file),
            "--output",
            str(temp_output_dir / "output.mp3"),
            "--quality",
            "speech",
        ]

        with patch("sys.argv", ["audio-extraction-analysis", *test_args]):
            with patch("src.cli.AudioExtractor") as mock_extractor:
                mock_instance = Mock()
                mock_instance.extract_audio.return_value = temp_output_dir / "output.mp3"
                mock_extractor.return_value = mock_instance

                result = main()

        assert result == 0
        mock_instance.extract_audio.assert_called_once()

    def test_extract_command_input_not_found(self):
        """Test extract command with non-existent input file."""
        test_args = ["extract", "/non/existent/file.mp4"]

        with patch("sys.argv", ["audio-extraction-analysis", *test_args]):
            result = main()

        assert result == 1

    def test_extract_command_extraction_failure(self, temp_video_file):
        """Test extract command when extraction fails."""
        test_args = ["extract", str(temp_video_file)]

        with patch("sys.argv", ["audio-extraction-analysis", *test_args]):
            with patch("src.cli.AudioExtractor") as mock_extractor:
                mock_instance = Mock()
                mock_instance.extract_audio.return_value = None  # Failure
                mock_extractor.return_value = mock_instance

                result = main()

        assert result == 1


class TestCLITranscribeCommand:
    """Test CLI transcribe command functionality."""

    def test_transcribe_command_success(self, api_key_set, temp_audio_file, temp_output_dir):
        """Test successful transcribe command execution."""
        test_args = [
            "transcribe",
            str(temp_audio_file),
            "--output",
            str(temp_output_dir / "transcript.txt"),
            "--language",
            "en",
        ]

        with patch("sys.argv", ["audio-extraction-analysis", *test_args]):
            with patch("src.cli.TranscriptionService") as mock_service:
                from datetime import datetime

                from src.models.transcription import TranscriptionResult

                mock_result = TranscriptionResult(
                    transcript="Test transcript",
                    duration=60.0,
                    generated_at=datetime.now(),
                    audio_file=str(temp_audio_file),
                )

                mock_instance = Mock()
                mock_instance.transcribe.return_value = mock_result
                mock_instance.save_transcription_result.return_value = None
                mock_service.return_value = mock_instance

                result = main()

        assert result == 0
        mock_instance.transcribe.assert_called_once()
        mock_instance.save_transcription_result.assert_called_once()

    def test_transcribe_command_missing_api_key(self, temp_audio_file):
        """Test transcribe command without API key."""
        test_args = ["transcribe", str(temp_audio_file)]

        with patch("sys.argv", ["audio-extraction-analysis", *test_args]):
            with patch("src.cli.Config") as mock_config:
                mock_config.validate.side_effect = ValueError("API key not found")

                result = main()

        assert result == 1

    def test_transcribe_command_input_not_found(self, api_key_set):
        """Test transcribe command with non-existent audio file."""
        test_args = ["transcribe", "/non/existent/audio.mp3"]

        with patch("sys.argv", ["audio-extraction-analysis", *test_args]):
            result = main()

        assert result == 1

    def test_transcribe_command_failure(self, api_key_set, temp_audio_file):
        """Test transcribe command when transcription fails."""
        test_args = ["transcribe", str(temp_audio_file)]

        with patch("sys.argv", ["audio-extraction-analysis", *test_args]):
            with patch("src.cli.TranscriptionService") as mock_service:
                mock_instance = Mock()
                mock_instance.transcribe.return_value = None  # Failure
                mock_service.return_value = mock_instance

                result = main()

        assert result == 1


class TestCLIProcessCommand:
    """Test CLI process command functionality."""

    @pytest.mark.skip(reason="Integration test - requires full pipeline mocking")
    def test_process_command_success(self, api_key_set, temp_video_file, temp_output_dir):
        """Test successful process command execution."""
        test_args = [
            "process",
            str(temp_video_file),
            "--output-dir",
            str(temp_output_dir),
            "--quality",
            "speech",
            "--language",
            "en",
        ]

        with patch("sys.argv", ["audio-extraction-analysis", *test_args]):
            with patch("src.cli.AudioProcessingPipeline") as mock_pipeline:
                from datetime import datetime

                from src.models.transcription import TranscriptionResult

                mock_result = TranscriptionResult(
                    transcript="Pipeline test transcript",
                    duration=120.0,
                    generated_at=datetime.now(),
                    audio_file=str(temp_video_file),
                )

                mock_instance = Mock()
                mock_instance.process_video.return_value = mock_result
                mock_pipeline.return_value = mock_instance

                result = main()

        assert result == 0
        mock_instance.process_video.assert_called_once()

    def test_process_command_input_not_found(self, api_key_set):
        """Test process command with non-existent video file."""
        test_args = ["process", "/non/existent/video.mp4"]

        with patch("sys.argv", ["audio-extraction-analysis", *test_args]):
            result = main()

        assert result == 1

    def test_process_command_pipeline_failure(self, api_key_set, temp_video_file):
        """Test process command when pipeline fails."""
        test_args = ["process", str(temp_video_file)]

        with patch("sys.argv", ["audio-extraction-analysis", *test_args]):
            with patch("src.cli.AudioProcessingPipeline") as mock_pipeline:
                mock_instance = Mock()
                mock_instance.process_video.return_value = None  # Failure
                mock_pipeline.return_value = mock_instance

                result = main()

        assert result == 1


class TestCLILogging:
    """Test CLI logging functionality."""

    def test_verbose_logging_setup(self, temp_video_file):
        """Test that verbose flag sets up debug logging."""
        test_args = ["--verbose", "extract", str(temp_video_file)]

        with patch("sys.argv", ["audio-extraction-analysis", *test_args]):
            with patch("src.cli.setup_logging") as mock_setup:
                with patch("src.cli.AudioExtractor"):
                    main()

                mock_setup.assert_called_once_with(True)

    def test_normal_logging_setup(self, temp_video_file):
        """Test that normal execution sets up info logging."""
        test_args = ["extract", str(temp_video_file)]

        with patch("sys.argv", ["audio-extraction-analysis", *test_args]):
            with patch("src.cli.setup_logging") as mock_setup:
                with patch("src.cli.AudioExtractor"):
                    main()

                mock_setup.assert_called_once_with(False)


class TestCLIErrorHandling:
    """Test CLI error handling."""

    def test_unknown_command_error(self):
        """Test handling of unknown commands (should be caught by argparse)."""
        # This would be caught by argparse before reaching our code
        parser = create_parser()

        with pytest.raises(SystemExit):
            parser.parse_args(["unknown_command"])

    def test_general_exception_handling(self, api_key_set, temp_audio_file):
        """Test handling of unexpected exceptions."""
        test_args = ["transcribe", str(temp_audio_file)]

        with patch("sys.argv", ["audio-extraction-analysis", *test_args]):
            with patch("src.cli.TranscriptionService") as mock_service:
                mock_service.side_effect = Exception("Unexpected error")

                result = main()

        assert result == 1

    def test_keyboard_interrupt_handling(self, api_key_set, temp_audio_file):
        """Test handling of keyboard interrupt."""
        test_args = ["transcribe", str(temp_audio_file)]

        with patch("sys.argv", ["audio-extraction-analysis", *test_args]):
            with patch("src.cli.TranscriptionService") as mock_service:
                mock_service.side_effect = KeyboardInterrupt()

                result = main()

        assert result == 1


class TestCLIProviderSelection:
    """Test CLI provider selection functionality."""

    def test_transcribe_command_with_deepgram_provider(
        self, temp_audio_file, temp_output_dir, monkeypatch
    ):
        """Test transcribe command with explicit Deepgram provider."""
        monkeypatch.setenv("DEEPGRAM_API_KEY", "test_deepgram_key")

        test_args = [
            "transcribe",
            str(temp_audio_file),
            "--provider",
            "deepgram",
            "--output",
            str(temp_output_dir / "transcript.txt"),
        ]

        with patch("sys.argv", ["audio-extraction-analysis", *test_args]):
            with patch("src.cli.TranscriptionService") as mock_service:
                from datetime import datetime

                from src.models.transcription import TranscriptionResult

                mock_result = TranscriptionResult(
                    transcript="Deepgram test transcript",
                    duration=60.0,
                    generated_at=datetime.now(),
                    audio_file=str(temp_audio_file),
                    provider_name="deepgram",
                )

                mock_instance = Mock()
                mock_instance.transcribe.return_value = mock_result
                mock_instance.save_transcription_result.return_value = None
                mock_service.return_value = mock_instance

                result = main()

        assert result == 0
        mock_instance.transcribe.assert_called_once()

    def test_transcribe_command_with_elevenlabs_provider(
        self, temp_audio_file, temp_output_dir, monkeypatch
    ):
        """Test transcribe command with explicit ElevenLabs provider."""
        test_args = [
            "transcribe",
            str(temp_audio_file),
            "--provider",
            "elevenlabs",
            "--output",
            str(temp_output_dir / "transcript.txt"),
        ]

        with patch("sys.argv", ["audio-extraction-analysis", *test_args]):
            with patch("src.cli.Config") as mock_config:
                # Mock Config methods
                mock_config.get_available_providers.return_value = ["elevenlabs"]
                mock_config.is_configured.return_value = True

                with patch("src.cli.TranscriptionService") as mock_service:
                    from datetime import datetime

                    from src.models.transcription import TranscriptionResult

                    mock_result = TranscriptionResult(
                        transcript="ElevenLabs test transcript",
                        duration=45.0,
                        generated_at=datetime.now(),
                        audio_file=str(temp_audio_file),
                        provider_name="elevenlabs",
                    )

                    mock_instance = Mock()
                    mock_instance.transcribe.return_value = mock_result
                    mock_instance.save_transcription_result.return_value = None
                    mock_service.return_value = mock_instance

                    result = main()

        assert result == 0
        mock_instance.transcribe.assert_called_once()

    def test_transcribe_command_with_auto_provider_selection(
        self, temp_audio_file, temp_output_dir, monkeypatch
    ):
        """Test transcribe command with auto provider selection."""
        monkeypatch.setenv("DEEPGRAM_API_KEY", "test_deepgram_key")

        test_args = [
            "transcribe",
            str(temp_audio_file),
            "--provider",
            "auto",
            "--output",
            str(temp_output_dir / "transcript.txt"),
        ]

        with patch("sys.argv", ["audio-extraction-analysis", *test_args]):
            with patch("src.cli.TranscriptionService") as mock_service:
                from datetime import datetime

                from src.models.transcription import TranscriptionResult

                mock_result = TranscriptionResult(
                    transcript="Auto-selected provider transcript",
                    duration=75.0,
                    generated_at=datetime.now(),
                    audio_file=str(temp_audio_file),
                    provider_name="deepgram",
                )

                mock_instance = Mock()
                mock_instance.transcribe.return_value = mock_result
                mock_instance.save_transcription_result.return_value = None
                mock_service.return_value = mock_instance

                result = main()

        assert result == 0
        mock_instance.transcribe.assert_called_once()

    def test_transcribe_command_provider_creation_failure(self, temp_audio_file, monkeypatch):
        """Test transcribe command when provider creation fails."""
        monkeypatch.setenv("DEEPGRAM_API_KEY", "test_key")

        test_args = ["transcribe", str(temp_audio_file), "--provider", "deepgram"]

        with patch("sys.argv", ["audio-extraction-analysis", *test_args]):
            with patch("src.cli.TranscriptionService") as mock_service:
                mock_service.side_effect = ValueError("Provider creation failed")

                result = main()

        assert result == 1

    @pytest.mark.skip(reason="Integration test - requires full pipeline mocking")
    def test_process_command_with_provider_selection(
        self, temp_video_file, temp_output_dir, monkeypatch
    ):
        """Test process command with provider selection."""
        test_args = [
            "process",
            str(temp_video_file),
            "--output-dir",
            str(temp_output_dir),
            "--provider",
            "elevenlabs",
        ]

        with patch("sys.argv", ["audio-extraction-analysis", *test_args]):
            with patch("src.cli.Config") as mock_config:
                # Mock Config methods
                mock_config.get_available_providers.return_value = ["elevenlabs"]
                mock_config.is_configured.return_value = True

                with patch("src.cli.AudioProcessingPipeline") as mock_pipeline:
                    from datetime import datetime

                    from src.models.transcription import TranscriptionResult

                    mock_result = TranscriptionResult(
                        transcript="Process command transcript",
                        duration=90.0,
                        generated_at=datetime.now(),
                        audio_file=str(temp_video_file),
                        provider_name="ElevenLabs",
                    )

                    mock_instance = Mock()
                    mock_instance.process_video.return_value = mock_result
                    mock_pipeline.return_value = mock_instance

                    result = main()

        assert result == 0
        # Verify pipeline was called with provider parameter
        mock_instance.process_video.assert_called_once()
        call_args = mock_instance.process_video.call_args
        assert "provider" in call_args.kwargs
        assert call_args.kwargs["provider"] == "elevenlabs"
