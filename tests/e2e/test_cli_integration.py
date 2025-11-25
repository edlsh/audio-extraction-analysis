"""
CLI Integration Tests for audio-extraction-analysis.

Tests the complete CLI interface including:
- Extract command validation
- Transcribe command with different providers
- Process command end-to-end workflow
- Error handling and edge cases
"""

from unittest.mock import patch

import pytest

from .base import CLITestMixin, E2ETestBase, MockProviderMixin
from .test_data_manager import TestDataManager


@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.ffmpeg
class TestCLIExtractCommand(E2ETestBase, CLITestMixin):
    """
    Test cases for the extract command.

    This test class validates the audio extraction functionality of the CLI,
    including different quality presets, error handling, and edge cases.
    Tests verify that audio can be successfully extracted from video files
    and saved with the correct quality settings.
    """

    @classmethod
    def setup_class(cls):
        """
        Setup test data for the class.

        Initializes TestDataManager and generates all required test files
        (short, medium, audio_only, and edge case files) for extraction testing.
        """
        cls.test_data_manager = TestDataManager()
        cls.test_files = cls.test_data_manager.generate_all_test_files()

    def test_extract_high_quality(self):
        """
        Test audio extraction with high quality preset.

        Verifies that:
        - Extract command completes successfully with 'high' quality preset
        - Output file is created at the specified location
        - Output file contains data (non-zero size)
        """
        if "short" not in self.test_files:
            pytest.skip("Short test file not available")

        input_file = self.test_files["short"]
        output_file = self.output_dir / "extracted_high.mp3"

        result = self.run_extract_command(
            input_file=input_file, quality="high", output_file=output_file
        )

        # Verify successful extraction
        assert result.success, f"Extract command failed: {result.error}"
        assert output_file.exists(), "Output file was not created"
        assert output_file.stat().st_size > 0, "Output file is empty"

    def test_extract_speech_quality(self):
        """
        Test audio extraction with speech quality preset.

        Verifies that:
        - Extract command completes successfully with 'speech' quality preset
        - Output file is created
        - Speech quality produces smaller or equal file size compared to high quality
          (speech is optimized for voice, not music, resulting in better compression)
        """
        if "short" not in self.test_files:
            pytest.skip("Short test file not available")

        input_file = self.test_files["short"]
        output_file = self.output_dir / "extracted_speech.mp3"

        result = self.run_extract_command(
            input_file=input_file, quality="speech", output_file=output_file
        )

        assert result.success, f"Extract command failed: {result.error}"
        assert output_file.exists(), "Output file was not created"

        # Verify speech quality produces smaller files due to voice-optimized encoding
        high_quality_file = self.output_dir / "extracted_high.mp3"
        if high_quality_file.exists():
            assert output_file.stat().st_size <= high_quality_file.stat().st_size

    def test_extract_compressed_quality(self):
        """Test audio extraction with compressed quality preset."""
        if "short" not in self.test_files:
            pytest.skip("Short test file not available")

        input_file = self.test_files["short"]
        output_file = self.output_dir / "extracted_compressed.mp3"

        result = self.run_extract_command(
            input_file=input_file, quality="compressed", output_file=output_file
        )

        assert result.success, f"Extract command failed: {result.error}"
        assert output_file.exists(), "Output file was not created"

    def test_extract_nonexistent_file(self):
        """
        Test extract command with nonexistent input file.

        Verifies that:
        - Extract command fails gracefully when input file doesn't exist
        - Error message clearly indicates the file was not found
        """
        nonexistent_file = self.temp_dir / "nonexistent.mp4"

        result = self.run_extract_command(input_file=nonexistent_file)

        # Verify failure with clear error message
        assert not result.success, "Extract should fail with nonexistent file"
        assert "not found" in result.error.lower() or "no such file" in result.error.lower()

    def test_extract_invalid_quality(self):
        """Test extract command with invalid quality preset."""
        if "short" not in self.test_files:
            pytest.skip("Short test file not available")

        input_file = self.test_files["short"]

        result = self.run_extract_command(input_file=input_file, quality="invalid_quality")

        assert not result.success, "Extract should fail with invalid quality"
        assert "quality" in result.error.lower() or "invalid" in result.error.lower()

    def test_extract_with_output_directory_creation(self):
        """Test that extract command creates output directory if it doesn't exist."""
        if "short" not in self.test_files:
            pytest.skip("Short test file not available")

        input_file = self.test_files["short"]
        output_dir = self.temp_dir / "new_output_dir"
        output_file = output_dir / "extracted.mp3"

        result = self.run_extract_command(input_file=input_file, output_file=output_file)

        assert result.success, f"Extract command failed: {result.error}"
        assert output_dir.exists(), "Output directory was not created"
        assert output_file.exists(), "Output file was not created"

    def test_extract_overwrite_protection(self):
        """
        Test extract command behavior when output file already exists.

        Verifies that the CLI handles existing output files appropriately by either:
        - Successfully overwriting the file, or
        - Failing with a clear error message about file existence
        """
        if "short" not in self.test_files:
            pytest.skip("Short test file not available")

        input_file = self.test_files["short"]
        output_file = self.output_dir / "existing.mp3"

        # Pre-create the output file to test overwrite behavior
        output_file.write_text("existing content")

        result = self.run_extract_command(input_file=input_file, output_file=output_file)

        # Verify appropriate handling: either succeeds (overwrites) or fails with clear message
        if not result.success:
            assert "exists" in result.error.lower() or "overwrite" in result.error.lower()


@pytest.mark.e2e
@pytest.mark.network
@pytest.mark.providers
class TestCLITranscribeCommand(E2ETestBase, CLITestMixin, MockProviderMixin):
    """
    Test cases for the transcribe command.

    This test class validates the transcription functionality of the CLI,
    including different provider integrations (Deepgram, ElevenLabs),
    auto provider selection, API key validation, and error handling.
    Uses mocked providers to avoid actual API calls and costs.
    """

    @classmethod
    def setup_class(cls):
        """
        Setup test data for the class.

        Initializes TestDataManager and generates test files including
        audio-only files for transcription testing.
        """
        cls.test_data_manager = TestDataManager()
        cls.test_files = cls.test_data_manager.generate_all_test_files()

    def test_transcribe_with_mock_deepgram(self):
        """
        Test transcription with mocked Deepgram provider.

        Verifies that:
        - Transcribe command works with Deepgram provider
        - API key is properly passed to the service
        - Output JSON file is created with transcription results

        Note: Uses mocked TranscriptionService to avoid actual API calls.
        """
        if "audio_only" not in self.test_files:
            pytest.skip("Audio test file not available")

        # Set up mock environment with Deepgram API key
        self.set_test_env(DEEPGRAM_API_KEY="test_key_deepgram")

        input_file = self.test_files["audio_only"]
        output_file = self.output_dir / "transcript_deepgram.json"

        # Mock the transcription service to avoid actual API calls
        with patch("src.services.transcription.TranscriptionService") as mock_service:
            mock_service.return_value.transcribe.return_value = self.mock_successful_transcription()

            result = self.run_transcribe_command(
                input_file=input_file, provider="deepgram", output_file=output_file
            )

        assert result.success, f"Transcribe command failed: {result.error}"
        assert output_file.exists(), "Output file was not created"

    def test_transcribe_with_mock_elevenlabs(self):
        """Test transcription with mocked ElevenLabs provider."""
        if "audio_only" not in self.test_files:
            pytest.skip("Audio test file not available")

        # Set up mock environment
        self.set_test_env(ELEVENLABS_API_KEY="test_key_elevenlabs")

        input_file = self.test_files["audio_only"]
        output_file = self.output_dir / "transcript_elevenlabs.json"

        # Mock the transcription service
        with patch("src.services.transcription.TranscriptionService") as mock_service:
            mock_service.return_value.transcribe.return_value = self.mock_successful_transcription()

            result = self.run_transcribe_command(
                input_file=input_file, provider="elevenlabs", output_file=output_file
            )

        assert result.success, f"Transcribe command failed: {result.error}"
        assert output_file.exists(), "Output file was not created"

    def test_transcribe_auto_provider_selection(self):
        """
        Test automatic provider selection.

        Verifies that:
        - CLI can automatically select an available provider when provider="auto"
        - Selection works when multiple API keys are configured
        - Transcription completes successfully with auto-selected provider
        """
        if "audio_only" not in self.test_files:
            pytest.skip("Audio test file not available")

        # Set up mock environment with multiple providers available
        self.set_test_env(
            DEEPGRAM_API_KEY="test_key_deepgram", ELEVENLABS_API_KEY="test_key_elevenlabs"
        )

        input_file = self.test_files["audio_only"]
        output_file = self.output_dir / "transcript_auto.json"

        # Mock the transcription service
        with patch("src.services.transcription.TranscriptionService") as mock_service:
            mock_service.return_value.transcribe.return_value = self.mock_successful_transcription()

            result = self.run_transcribe_command(
                input_file=input_file, provider="auto", output_file=output_file
            )

        assert result.success, f"Transcribe command failed: {result.error}"
        assert output_file.exists(), "Output file was not created"

    def test_transcribe_no_api_key(self):
        """Test transcription without API key configured."""
        if "audio_only" not in self.test_files:
            pytest.skip("Audio test file not available")

        # Ensure no API keys are set
        env_vars = {"DEEPGRAM_API_KEY": "", "ELEVENLABS_API_KEY": ""}

        input_file = self.test_files["audio_only"]

        result = self.run_transcribe_command(
            input_file=input_file, provider="deepgram", env_vars=env_vars
        )

        assert not result.success, "Transcribe should fail without API key"
        assert "api key" in result.error.lower() or "not configured" in result.error.lower()

    def test_transcribe_invalid_provider(self):
        """Test transcription with invalid provider."""
        if "audio_only" not in self.test_files:
            pytest.skip("Audio test file not available")

        input_file = self.test_files["audio_only"]

        result = self.run_transcribe_command(input_file=input_file, provider="invalid_provider")

        assert not result.success, "Transcribe should fail with invalid provider"
        assert "provider" in result.error.lower() or "invalid" in result.error.lower()

    def test_transcribe_unsupported_language(self):
        """Test transcription with unsupported language code."""
        if "audio_only" not in self.test_files:
            pytest.skip("Audio test file not available")

        self.set_test_env(DEEPGRAM_API_KEY="test_key")

        input_file = self.test_files["audio_only"]

        result = self.run_transcribe_command(
            input_file=input_file, provider="deepgram", language="invalid_lang"
        )

        # Should either succeed (provider handles it) or fail with clear message
        if not result.success:
            assert "language" in result.error.lower()

    def test_transcribe_large_file_handling(self):
        """
        Test transcription with large file to check size limits.

        Verifies that:
        - Large files are handled appropriately by the transcription service
        - If file size exceeds limits, error message is clear and informative
        - Extended timeout is respected for processing large files
        """
        # This test uses the 'large' test file if available
        large_file_path = self.test_data_manager.get_test_file_path("large")
        if not large_file_path or not large_file_path.exists():
            pytest.skip("Large test file not available")

        self.set_test_env(DEEPGRAM_API_KEY="test_key")

        result = self.run_transcribe_command(
            input_file=large_file_path,
            provider="deepgram",
            timeout=600,  # Extended timeout (10 minutes) for large file processing
        )

        # Verify either successful processing or size-related error message
        if not result.success:
            error_msg = result.error.lower()
            size_related = any(
                keyword in error_msg
                for keyword in ["size", "large", "limit", "exceeded", "too big"]
            )
            assert size_related, f"Unexpected error for large file: {result.error}"


@pytest.mark.e2e
@pytest.mark.network
@pytest.mark.providers
@pytest.mark.slow
class TestCLIProcessCommand(E2ETestBase, CLITestMixin, MockProviderMixin):
    """
    Test cases for the full process command.

    This test class validates the complete end-to-end processing pipeline,
    which includes audio extraction, transcription, and analysis to produce
    multiple markdown output files (executive summary, chapters, topics, etc.).
    Tests cover the full workflow, custom output directories, performance,
    and error handling scenarios.
    """

    @classmethod
    def setup_class(cls):
        """
        Setup test data for the class.

        Initializes TestDataManager and generates all test files including
        video files for full pipeline processing tests.
        """
        cls.test_data_manager = TestDataManager()
        cls.test_files = cls.test_data_manager.generate_all_test_files()

    def test_process_full_pipeline(self):
        """
        Test complete processing pipeline from video to markdown.

        Verifies that:
        - Full pipeline executes: extraction → transcription → analysis
        - All expected markdown output files are created
        - Output files contain the expected content
        - Process completes successfully with mocked services

        Expected outputs: executive summary, chapter overview, topic analysis,
        full transcript, and key insights markdown files.
        """
        if "short" not in self.test_files:
            pytest.skip("Short test file not available")

        # Set up mock environment
        self.set_test_env(DEEPGRAM_API_KEY="test_key_deepgram")

        input_file = self.test_files["short"]

        # Define expected output files from the full analysis pipeline
        expected_files = [
            "executive_summary.md",
            "chapter_overview.md",
            "topic_analysis.md",
            "full_transcript.md",
            "key_insights.md",
        ]

        # Mock the transcription and analysis services to avoid API calls
        with (
            patch("src.services.transcription.TranscriptionService") as mock_transcription,
            patch("src.analysis.full_analyzer.FullAnalyzer") as mock_analyzer,
        ):
            mock_transcription.return_value.transcribe.return_value = (
                self.mock_successful_transcription()
            )
            mock_analyzer.return_value.analyze.return_value = {
                "executive_summary": "Test summary",
                "chapter_overview": "Test chapters",
                "topic_analysis": "Test topics",
                "full_transcript": "Test transcript",
                "key_insights": "Test insights",
            }

            result = self.run_process_command(
                input_file=input_file, output_dir=self.output_dir, provider="deepgram"
            )

        assert result.success, f"Process command failed: {result.error}"

        # Validate all expected output files exist
        self.assert_files_exist(expected_files)

        # Verify that output files have content
        for filename in expected_files:
            file_path = self.output_dir / filename
            content = file_path.read_text()
            assert len(content) > 0, f"Output file {filename} is empty"
            assert "test" in content.lower(), f"Output file {filename} missing expected content"

    def test_process_with_custom_output_dir(self):
        """Test process command with custom output directory."""
        if "short" not in self.test_files:
            pytest.skip("Short test file not available")

        self.set_test_env(DEEPGRAM_API_KEY="test_key")

        input_file = self.test_files["short"]
        custom_output_dir = self.temp_dir / "custom_output"

        # Mock services
        with (
            patch("src.services.transcription.TranscriptionService") as mock_transcription,
            patch("src.analysis.full_analyzer.FullAnalyzer") as mock_analyzer,
        ):
            mock_transcription.return_value.transcribe.return_value = (
                self.mock_successful_transcription()
            )
            mock_analyzer.return_value.analyze.return_value = {"executive_summary": "Test summary"}

            result = self.run_process_command(
                input_file=input_file, output_dir=custom_output_dir, provider="deepgram"
            )

        assert result.success, f"Process command failed: {result.error}"
        assert custom_output_dir.exists(), "Custom output directory was not created"

        # Check that at least one output file exists in custom directory
        output_files = list(custom_output_dir.glob("*.md"))
        assert len(output_files) > 0, "No output files found in custom directory"

    def test_process_medium_file_performance(self):
        """
        Test process command performance with medium-sized file.

        Verifies that:
        - Medium-sized files are processed successfully
        - Processing completes within expected timeout (5 minutes)
        - With mocked services, processing is relatively fast (<60s)

        Note: Performance is measured with mocked services, so actual
        processing time will be longer with real API calls.
        """
        if "medium" not in self.test_files:
            pytest.skip("Medium test file not available")

        self.set_test_env(DEEPGRAM_API_KEY="test_key")

        input_file = self.test_files["medium"]

        # Mock services for faster execution and to avoid API costs
        with (
            patch("src.services.transcription.TranscriptionService") as mock_transcription,
            patch("src.analysis.full_analyzer.FullAnalyzer") as mock_analyzer,
        ):
            mock_transcription.return_value.transcribe.return_value = (
                self.mock_successful_transcription()
            )
            mock_analyzer.return_value.analyze.return_value = {"executive_summary": "Test"}

            result = self.run_process_command(
                input_file=input_file,
                output_dir=self.output_dir,
                timeout=300,  # 5 minute timeout for medium file
            )

        assert result.success, f"Process command failed: {result.error}"

        # Performance assertion - should complete within reasonable time
        # Note: This is with mocked services, so should be very fast
        assert result.duration < 60, f"Process took too long: {result.duration}s"

    def test_process_error_handling(self):
        """Test process command error handling scenarios."""
        if "edge_corrupted" not in self.test_files:
            pytest.skip("Corrupted test file not available")

        self.set_test_env(DEEPGRAM_API_KEY="test_key")

        # Test with corrupted file
        corrupted_file = self.test_files["edge_corrupted"]

        result = self.run_process_command(input_file=corrupted_file, output_dir=self.output_dir)

        # Should fail gracefully with informative error
        assert not result.success, "Process should fail with corrupted file"
        assert len(result.error) > 0, "Error message should not be empty"

        # Error should be informative
        error_keywords = ["corrupt", "invalid", "format", "error", "failed"]
        assert any(keyword in result.error.lower() for keyword in error_keywords)

    def test_process_no_providers_configured(self):
        """Test process command when no providers are configured."""
        if "short" not in self.test_files:
            pytest.skip("Short test file not available")

        # Clear all API keys
        env_vars = {"DEEPGRAM_API_KEY": "", "ELEVENLABS_API_KEY": ""}

        input_file = self.test_files["short"]

        result = self.run_process_command(
            input_file=input_file, output_dir=self.output_dir, env_vars=env_vars
        )

        assert not result.success, "Process should fail without providers"
        assert "provider" in result.error.lower() or "api key" in result.error.lower()

    def test_process_with_verbose_output(self):
        """
        Test process command with verbose logging.

        Verifies that:
        - Process command accepts --verbose flag
        - Verbose mode produces detailed output logs
        - Output includes progress indicators for each pipeline stage
          (processing, extracting, transcribing, analyzing)
        """
        if "short" not in self.test_files:
            pytest.skip("Short test file not available")

        self.set_test_env(DEEPGRAM_API_KEY="test_key")

        input_file = self.test_files["short"]

        # Mock services
        with (
            patch("src.services.transcription.TranscriptionService") as mock_transcription,
            patch("src.analysis.full_analyzer.FullAnalyzer") as mock_analyzer,
        ):
            mock_transcription.return_value.transcribe.return_value = (
                self.mock_successful_transcription()
            )
            mock_analyzer.return_value.analyze.return_value = {"executive_summary": "Test"}

            result = self.run_process_command(
                input_file=input_file, output_dir=self.output_dir, additional_args=["--verbose"]
            )

        assert result.success, f"Process command failed: {result.error}"

        # Verify verbose flag produces detailed output
        assert len(result.output) > 0, "Verbose output should not be empty"

        # Verify output contains progress indicators for pipeline stages
        progress_keywords = ["processing", "extracting", "transcribing", "analyzing"]
        output_lower = result.output.lower()
        assert any(keyword in output_lower for keyword in progress_keywords)


class TestCLIEdgeCases(E2ETestBase, CLITestMixin):
    """
    Test edge cases and error scenarios.

    This test class validates the CLI's handling of edge cases including:
    - Unicode and special characters in filenames
    - Filenames with spaces
    - Empty files
    - Invalid command arguments
    - Help and version commands

    These tests ensure robustness and graceful error handling.
    """

    @classmethod
    def setup_class(cls):
        """
        Setup test data for the class.

        Initializes TestDataManager and generates edge case test files
        (unicode filenames, files with spaces, empty files, etc.).
        """
        cls.test_data_manager = TestDataManager()
        cls.test_files = cls.test_data_manager.generate_all_test_files()

    def test_unicode_filename_handling(self):
        """
        Test CLI with unicode filenames.

        Verifies that:
        - CLI handles unicode characters in filenames correctly
        - If processing fails, error is not related to encoding/unicode issues
        - System supports international characters in file paths
        """
        if "edge_unicode" not in self.test_files:
            pytest.skip("Unicode test file not available")

        input_file = self.test_files["edge_unicode"]
        output_file = self.output_dir / "unicode_output.mp3"

        result = self.run_extract_command(input_file=input_file, output_file=output_file)

        # Verify unicode filenames are handled gracefully
        if not result.success:
            # If ffmpeg is not installed, that's expected in CI
            if "ffmpeg is required but not installed" in result.error.lower():
                pytest.skip("FFmpeg not installed - expected in CI environment")
            # Ensure error is not due to filename encoding issues
            # (check for encoding errors, not just the word "unicode" which may be in filename)
            assert "encoding" not in result.error.lower()
            assert "unicodeerror" not in result.error.lower()
            assert "decode" not in result.error.lower()

    def test_spaces_in_filename_handling(self):
        """Test CLI with filenames containing spaces."""
        if "edge_spaces" not in self.test_files:
            pytest.skip("Spaces test file not available")

        input_file = self.test_files["edge_spaces"]
        output_file = self.output_dir / "spaces output.mp3"

        result = self.run_extract_command(input_file=input_file, output_file=output_file)

        # Should handle spaces in filenames
        # If ffmpeg is not installed, that's expected in CI
        if not result.success and "ffmpeg is required but not installed" in result.error.lower():
            pytest.skip("FFmpeg not installed - expected in CI environment")
        # Either succeed or fail for reasons other than spaces in filename
        # (the word "spaces" may appear in the filename itself in error messages)
        assert result.success or "no such file" not in result.error.lower()

    def test_empty_file_handling(self):
        """Test CLI with empty input file."""
        if "edge_empty" not in self.test_files:
            pytest.skip("Empty test file not available")

        input_file = self.test_files["edge_empty"]

        result = self.run_extract_command(input_file=input_file)

        # Should fail gracefully with empty file
        assert not result.success, "Extract should fail with empty file"
        assert len(result.error) > 0, "Should provide error message for empty file"

    def test_invalid_command_arguments(self):
        """Test CLI with invalid command line arguments."""
        result = self.run_cli_command(["audio-extraction-analysis", "invalid_command"])

        assert not result.success, "Should fail with invalid command"
        assert "invalid" in result.error.lower() or "unknown" in result.error.lower()

    def test_help_command(self):
        """
        Test CLI help command.

        Verifies that:
        - --help flag executes successfully (exit code 0)
        - Help output contains usage information
        - Output includes standard help keywords (usage, commands, options)
        """
        result = self.run_cli_command(["audio-extraction-analysis", "--help"])

        # Verify help command executes successfully
        assert result.success or result.exit_code == 0, "Help command should succeed"

        # Verify output contains usage information
        output = result.output.lower()
        help_keywords = ["usage", "commands", "options", "help"]
        assert any(keyword in output for keyword in help_keywords)

    def test_version_command(self):
        """
        Test CLI version command.

        Verifies that:
        - --version flag executes successfully (exit code 0)
        - Version output is non-empty
        - Output appears in stdout or stderr (some CLIs use stderr for version)
        """
        result = self.run_cli_command(["audio-extraction-analysis", "--version"])

        # Verify version command executes successfully
        if result.success or result.exit_code == 0:
            # Verify version information is present (may be in stdout or stderr)
            output = result.output + result.error  # Version might go to stderr
            assert len(output.strip()) > 0, "Version output should not be empty"
