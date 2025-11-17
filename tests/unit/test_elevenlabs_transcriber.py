"""Unit tests for ElevenLabsTranscriber.

Note: Integration-style tests (health checks, API mocking, full workflows)
are marked with @pytest.mark.integration and skipped in unit test runs.
These scenarios are covered by tests/integration/ and tests/e2e/.
"""

from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, mock_open, patch

import pytest

from src.models.transcription import TranscriptionResult, TranscriptionUtterance
from src.providers.elevenlabs import ElevenLabsTranscriber

# Apply markers for unit tests
pytestmark = [
    pytest.mark.unit,
    pytest.mark.fast,
    pytest.mark.elevenlabs,
    pytest.mark.mock,
]


@pytest.fixture(autouse=True)
def mock_provider_available(monkeypatch):
    """Mock PROVIDER_AVAILABLE as True for most tests."""
    monkeypatch.setattr("src.providers.elevenlabs.PROVIDER_AVAILABLE", True)


@pytest.fixture
def clear_elevenlabs_env(monkeypatch):
    """Ensure ELEVENLABS_API_KEY is absent by default; tests can set it explicitly when needed."""
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)


@pytest.fixture
def mock_elevenlabs_client():
    """Mock the ElevenLabs client to prevent external API calls during testing."""
    mock_client = Mock()

    # Mock speech_to_text as a client object with convert method
    mock_speech_to_text_client = Mock()

    # Mock a successful response
    mock_response = Mock()
    mock_response.text = "This is a test transcription from ElevenLabs."
    mock_response.segments = [
        Mock(start=0.0, end=15.0, text="This is a test transcription"),
        Mock(start=15.0, end=30.0, text="from ElevenLabs."),
    ]

    mock_speech_to_text_client.convert.return_value = mock_response
    mock_client.speech_to_text = mock_speech_to_text_client
    return mock_client, mock_response


@pytest.fixture
def temp_audio_file(tmp_path):
    """Create a temporary audio file for testing."""
    audio_file = tmp_path / "test_audio.mp3"
    # Create file with reasonable size (less than 50MB limit)
    audio_file.write_bytes(b"fake_audio_data" * 1000)  # ~15KB
    return audio_file


@pytest.fixture
def large_audio_file(tmp_path):
    """Create a large temporary audio file that exceeds ElevenLabs limit."""
    audio_file = tmp_path / "large_audio.mp3"
    # Create file larger than 50MB
    audio_file.write_bytes(b"fake_audio_data" * 4000000)  # ~60MB
    return audio_file


class TestElevenLabsTranscriberInit:
    """Test ElevenLabsTranscriber initialization."""

    def test_init_with_api_key(self):
        """Test initialization with explicit API key."""
        transcriber = ElevenLabsTranscriber(api_key="test_key")
        assert transcriber.api_key == "test_key"

    def test_init_with_env_api_key(self, monkeypatch):
        """Test initialization with API key from environment."""
        # Mock get_config to return a config with the API key set
        mock_config = Mock()
        mock_config.ELEVENLABS_API_KEY = "env_key"

        with patch("src.providers.elevenlabs.get_config", return_value=mock_config):
            transcriber = ElevenLabsTranscriber()
            assert transcriber.api_key == "env_key"

    def test_init_without_api_key_raises_error(self, clear_elevenlabs_env):
        """Test initialization without API key raises ValueError."""
        with pytest.raises(ValueError, match="ELEVENLABS_API_KEY not found"):
            ElevenLabsTranscriber()

    def test_validate_configuration_with_key(self):
        """Test configuration validation with valid API key."""
        transcriber = ElevenLabsTranscriber(api_key="test_key")
        assert transcriber.validate_configuration() is True

    def test_validate_configuration_without_key(self):
        """Test configuration validation without API key."""
        transcriber = ElevenLabsTranscriber(api_key="test_key")
        transcriber.api_key = None
        assert transcriber.validate_configuration() is False


class TestElevenLabsTranscriberMethods:
    """Test ElevenLabsTranscriber methods."""

    def test_get_provider_name(self):
        """Test get_provider_name returns correct name."""
        transcriber = ElevenLabsTranscriber(api_key="test_key")
        assert transcriber.get_provider_name() == "ElevenLabs"

    def test_get_supported_features(self):
        """Test get_supported_features returns expected features."""
        transcriber = ElevenLabsTranscriber(api_key="test_key")
        features = transcriber.get_supported_features()

        expected_features = ["timestamps", "language_detection", "basic_transcription"]

        assert features == expected_features

    def test_supports_feature(self):
        """Test supports_feature method."""
        transcriber = ElevenLabsTranscriber(api_key="test_key")

        assert transcriber.supports_feature("timestamps") is True
        assert transcriber.supports_feature("basic_transcription") is True
        assert transcriber.supports_feature("speaker_diarization") is False
        assert transcriber.supports_feature("topic_detection") is False


class TestElevenLabsTranscriberTranscription:
    """Test ElevenLabsTranscriber transcription functionality."""

    def test_transcribe_async_success(self, temp_audio_file):
        """Test successful async transcription."""
        transcriber = ElevenLabsTranscriber(api_key="test_key")

        # Mock the transcribe_async method directly
        from datetime import datetime

        mock_result = TranscriptionResult(
            transcript="This is a test transcription from ElevenLabs.",
            duration=30.5,
            generated_at=datetime.now(),
            audio_file=str(temp_audio_file),
            provider_name="ElevenLabs",
            provider_features=["timestamps", "language_detection", "basic_transcription"],
        )

        # Add mock utterances
        mock_result.utterances = [
            TranscriptionUtterance(
                speaker=0, start=0.0, end=15.0, text="This is a test transcription"
            ),
            TranscriptionUtterance(speaker=0, start=15.0, end=30.0, text="from ElevenLabs."),
        ]

        with patch.object(transcriber, "transcribe_async", return_value=mock_result):
            result = transcriber.transcribe(temp_audio_file, "en")

        assert result is not None
        assert isinstance(result, TranscriptionResult)
        assert result.transcript == "This is a test transcription from ElevenLabs."
        assert result.provider_name == "ElevenLabs"
        assert result.provider_features == [
            "timestamps",
            "language_detection",
            "basic_transcription",
        ]
        assert result.duration == 30.5
        assert len(result.utterances) == 2

        # Check utterances
        assert result.utterances[0].start == 0.0
        assert result.utterances[0].end == 15.0
        assert result.utterances[0].text == "This is a test transcription"

    def test_transcribe_async_file_not_found(self):
        """Test transcription with non-existent file raises ValidationError."""
        from src.exceptions import ValidationError

        transcriber = ElevenLabsTranscriber(api_key="test_key")
        non_existent_file = Path("/non/existent/file.mp3")

        with pytest.raises(ValidationError, match="Audio file validation failed"):
            transcriber.transcribe(non_existent_file, "en")

    def test_transcribe_async_file_too_large(self, large_audio_file):
        """Test transcription with file exceeding size limit raises FileSizeError."""
        from src.exceptions import FileSizeError

        transcriber = ElevenLabsTranscriber(api_key="test_key")

        with patch(
            "src.providers.elevenlabs.safe_validate_audio_file", return_value=large_audio_file
        ):
            with pytest.raises(FileSizeError, match=r"exceeds.*MB limit"):
                transcriber.transcribe(large_audio_file, "en")

    @patch("src.providers.elevenlabs.ElevenLabsClient")
    def test_transcribe_async_elevenlabs_not_installed(
        self, mock_elevenlabs_class, temp_audio_file
    ):
        """Test transcription when ElevenLabs SDK is not installed raises ProviderNotAvailableError."""
        from src.exceptions import ProviderNotAvailableError

        mock_elevenlabs_class.side_effect = ImportError("No module named 'elevenlabs'")
        transcriber = ElevenLabsTranscriber(api_key="test_key")

        with patch(
            "src.providers.elevenlabs.safe_validate_audio_file", return_value=temp_audio_file
        ):
            with pytest.raises(ProviderNotAvailableError, match="ElevenLabs SDK not available"):
                transcriber.transcribe(temp_audio_file, "en")

    @patch("src.providers.elevenlabs.ElevenLabsClient")
    def test_transcribe_async_api_error(self, mock_elevenlabs_class, temp_audio_file):
        """Test transcription with API error raises ProviderAPIError."""
        from src.exceptions import ProviderAPIError

        mock_client = Mock()
        mock_speech_to_text_client = Mock()
        mock_speech_to_text_client.convert.side_effect = Exception("API Error")
        mock_client.speech_to_text = mock_speech_to_text_client
        mock_elevenlabs_class.return_value = mock_client

        transcriber = ElevenLabsTranscriber(api_key="test_key")

        with patch("builtins.open", mock_open(read_data=b"fake_audio_data")):
            with patch(
                "src.providers.elevenlabs.safe_validate_audio_file", return_value=temp_audio_file
            ):
                with patch("src.providers.elevenlabs.asyncio.wait_for") as mock_wait:
                    mock_wait.side_effect = Exception("API Error")
                    with pytest.raises(ProviderAPIError, match="Unexpected ElevenLabs error"):
                        transcriber.transcribe(temp_audio_file, "en")

    @patch("src.providers.elevenlabs.ElevenLabsClient")
    def test_transcribe_async_response_variations(self, mock_elevenlabs_class, temp_audio_file):
        """Test transcription with different response formats."""
        mock_client = Mock()

        # Test response with transcript attribute instead of text
        mock_response = Mock()
        mock_response.transcript = "Test with transcript attribute"
        # Make sure text attribute exists but is None to test the fallback
        mock_response.text = None
        # Set segments to a valid value (False/None) to avoid iteration issues
        mock_response.segments = []
        # Set hasattr properly by defining the attribute
        del mock_response.segments  # Remove the segments attribute to test fallback
        mock_speech_to_text_client = Mock()
        mock_speech_to_text_client.convert.return_value = mock_response
        mock_client.speech_to_text = mock_speech_to_text_client
        # Patch returns the mock client directly (ElevenLabsClient is the class)
        mock_elevenlabs_class.return_value = mock_client

        transcriber = ElevenLabsTranscriber(api_key="test_key")

        with patch("builtins.open", mock_open(read_data=b"fake_audio_data")):
            result = transcriber.transcribe(temp_audio_file, "en")

        assert result is not None
        assert result.transcript == "Test with transcript attribute"

    @patch("src.providers.elevenlabs.ElevenLabsClient")
    def test_transcribe_async_no_segments(self, mock_elevenlabs_class, temp_audio_file):
        """Test transcription with response that has no segments."""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.text = "Simple transcription without segments"
        mock_response.segments = None
        mock_speech_to_text_client = Mock()
        mock_speech_to_text_client.convert.return_value = mock_response
        mock_client.speech_to_text = mock_speech_to_text_client
        # Patch returns the mock client directly (ElevenLabsClient is the class)
        mock_elevenlabs_class.return_value = mock_client

        transcriber = ElevenLabsTranscriber(api_key="test_key")

        with patch("builtins.open", mock_open(read_data=b"fake_audio_data")):
            result = transcriber.transcribe(temp_audio_file, "en")

        assert result is not None
        assert result.transcript == "Simple transcription without segments"
        assert len(result.utterances) == 0


class TestElevenLabsTranscriberDurationEstimation:
    """Test ElevenLabsTranscriber duration estimation."""

    @patch("subprocess.run")
    def test_estimate_audio_duration_with_ffprobe(self, mock_subprocess, temp_audio_file):
        """Test duration estimation using ffprobe."""
        mock_subprocess.return_value = Mock(returncode=0, stdout='{"format": {"duration": "45.6"}}')

        transcriber = ElevenLabsTranscriber(api_key="test_key")
        duration = transcriber._estimate_audio_duration(temp_audio_file)

        assert duration == 45.6

    @patch("subprocess.run")
    def test_estimate_audio_duration_ffprobe_fail(self, mock_subprocess, temp_audio_file):
        """Test duration estimation fallback when ffprobe fails."""
        mock_subprocess.return_value = Mock(returncode=1)

        transcriber = ElevenLabsTranscriber(api_key="test_key")
        duration = transcriber._estimate_audio_duration(temp_audio_file)

        # Should use file size estimation
        assert duration > 0
        assert isinstance(duration, float)

    @patch("subprocess.run")
    def test_estimate_audio_duration_ffprobe_exception(self, mock_subprocess, temp_audio_file):
        """Test duration estimation when ffprobe raises exception."""
        mock_subprocess.side_effect = Exception("ffprobe not found")

        transcriber = ElevenLabsTranscriber(api_key="test_key")
        duration = transcriber._estimate_audio_duration(temp_audio_file)

        # Should use file size estimation
        assert duration > 0
        assert isinstance(duration, float)


class TestElevenLabsTranscriberSaveResult:
    """Test ElevenLabsTranscriber save result functionality."""

    def test_save_result_to_file(self, tmp_path):
        """Test saving transcription result to file."""
        transcriber = ElevenLabsTranscriber(api_key="test_key")

        # Create a test result
        result = TranscriptionResult(
            transcript="Test transcription content",
            duration=60.0,
            generated_at=datetime(2024, 1, 1, 12, 0, 0),
            audio_file="test.mp3",
            provider_name="ElevenLabs",
            provider_features=["timestamps", "basic_transcription"],
        )

        # Add some utterances
        result.utterances = [
            TranscriptionUtterance(speaker=0, start=0.0, end=30.0, text="First part"),
            TranscriptionUtterance(speaker=0, start=30.0, end=60.0, text="Second part"),
        ]

        output_file = tmp_path / "transcript.txt"
        transcriber.save_result_to_file(result, output_file)

        # Verify file was created and contains expected content
        assert output_file.exists()
        content = output_file.read_text(encoding="utf-8")

        assert "ELEVENLABS TRANSCRIPTION" in content
        assert "Generated: 2024-01-01 12:00:00" in content
        assert "Audio File: test.mp3" in content
        assert "Duration: 60.00 seconds" in content
        assert "Provider: ElevenLabs" in content
        assert "Test transcription content" in content
        assert "[0.00s] First part" in content
        assert "[30.00s] Second part" in content

    def test_save_result_to_file_no_utterances(self, tmp_path):
        """Test saving transcription result with no utterances."""
        transcriber = ElevenLabsTranscriber(api_key="test_key")

        result = TranscriptionResult(
            transcript="Simple transcription",
            duration=30.0,
            generated_at=datetime.now(),
            audio_file="simple.mp3",
            provider_name="ElevenLabs",
        )

        output_file = tmp_path / "simple_transcript.txt"
        transcriber.save_result_to_file(result, output_file)

        assert output_file.exists()
        content = output_file.read_text(encoding="utf-8")

        assert "Simple transcription" in content
        assert "TRANSCRIPT WITH TIMESTAMPS:" not in content  # Should not appear without utterances

    def test_save_result_creates_parent_directory(self, tmp_path):
        """Test that saving result creates parent directories if they don't exist."""
        transcriber = ElevenLabsTranscriber(api_key="test_key")

        result = TranscriptionResult(
            transcript="Test",
            duration=10.0,
            generated_at=datetime.now(),
            audio_file="test.mp3",
            provider_name="ElevenLabs",
        )

        nested_output = tmp_path / "nested" / "dir" / "transcript.txt"
        transcriber.save_result_to_file(result, nested_output)

        assert nested_output.exists()
        assert "Test" in nested_output.read_text(encoding="utf-8")


class TestElevenLabsTranscriberHealthCheck:
    """Test ElevenLabsTranscriber health check functionality."""

    @pytest.mark.asyncio
    @patch("src.providers.elevenlabs.ElevenLabsClient")
    async def test_health_check_success(self, mock_elevenlabs_class):
        """Test successful health check with valid API credentials."""
        mock_client = Mock()
        mock_user_info = Mock()
        mock_user_info.user_id = "test_user_123"
        mock_client.user.get_user_info.return_value = mock_user_info
        mock_elevenlabs_class.return_value = mock_client

        transcriber = ElevenLabsTranscriber(api_key="test_key")
        result = await transcriber.health_check_async()

        assert result["healthy"] is True
        assert result["status"] == "operational"
        assert "response_time_ms" in result
        assert result["details"]["provider"] == "ElevenLabs"
        assert result["details"]["api_accessible"] is True
        assert result["details"]["authentication"] == "valid"
        assert result["details"]["user_id"] == "test_user_123"

    @pytest.mark.asyncio
    @patch("src.providers.elevenlabs.PROVIDER_AVAILABLE", False)
    async def test_health_check_sdk_not_available(self):
        """Test health check when SDK is not available."""
        with pytest.raises(ImportError, match="ElevenLabs SDK not available"):
            ElevenLabsTranscriber(api_key="test_key")

    @pytest.mark.asyncio
    @patch("src.providers.elevenlabs.ElevenLabsClient")
    async def test_health_check_api_error(self, mock_elevenlabs_class):
        """Test health check with API error."""
        mock_client = Mock()
        mock_client.user.get_user_info.side_effect = Exception("API connection failed")
        mock_elevenlabs_class.return_value = mock_client

        transcriber = ElevenLabsTranscriber(api_key="test_key")
        result = await transcriber.health_check_async()

        assert result["healthy"] is False
        assert result["status"] == "error"
        assert "response_time_ms" in result
        assert result["details"]["provider"] == "ElevenLabs"
        assert "API connection failed" in result["details"]["error"]
        assert result["details"]["error_type"] == "Exception"

    @pytest.mark.asyncio
    @patch("src.providers.elevenlabs.ElevenLabsClient")
    async def test_health_check_timeout(self, mock_elevenlabs_class):
        """Test health check with timeout."""

        mock_client = Mock()

        def slow_call():
            import time

            time.sleep(10)  # Simulate timeout
            return Mock()

        mock_client.user.get_user_info = slow_call
        mock_elevenlabs_class.return_value = mock_client

        transcriber = ElevenLabsTranscriber(api_key="test_key")

        # Use a short timeout for testing
        with patch("src.config.Config.HEALTH_CHECK_TIMEOUT", 0.1):
            result = await transcriber.health_check_async()

        assert result["healthy"] is False
        assert result["status"] == "error"
        assert "response_time_ms" in result


class TestElevenLabsTranscriberChunkedReading:
    """Test ElevenLabsTranscriber chunked file reading functionality."""

    def test_read_file_chunked_small_file(self, temp_audio_file):
        """Test chunked reading with small file."""
        transcriber = ElevenLabsTranscriber(api_key="test_key")

        content = transcriber._read_file_chunked(temp_audio_file)

        assert isinstance(content, bytes)
        assert len(content) > 0
        assert content == temp_audio_file.read_bytes()

    def test_read_file_chunked_large_chunks(self, tmp_path):
        """Test chunked reading with large number of chunks."""
        transcriber = ElevenLabsTranscriber(api_key="test_key")

        # Create file with >100 chunks (each chunk is 1MB, so need >100MB)
        # But constrained by MAX_MEMORY_SIZE, so create file just under limit
        large_file = tmp_path / "large_chunks.bin"
        # Create 45MB file (will create ~45 chunks of 1MB each)
        chunk_data = b"x" * (1024 * 1024)  # 1MB chunk
        with open(large_file, "wb") as f:
            for _ in range(45):
                f.write(chunk_data)

        content = transcriber._read_file_chunked(large_file)

        assert isinstance(content, bytes)
        assert len(content) == 45 * 1024 * 1024

    def test_read_file_chunked_exceeds_memory_limit(self, tmp_path):
        """Test chunked reading when file exceeds memory limit."""
        transcriber = ElevenLabsTranscriber(api_key="test_key")

        # Create file larger than MAX_MEMORY_SIZE (50MB)
        huge_file = tmp_path / "huge.bin"
        huge_file.write_bytes(b"x" * (60 * 1024 * 1024))  # 60MB

        with pytest.raises(MemoryError, match="exceeds memory limit"):
            transcriber._read_file_chunked(huge_file)

    def test_read_file_chunked_file_not_found(self):
        """Test chunked reading with non-existent file."""
        transcriber = ElevenLabsTranscriber(api_key="test_key")

        non_existent = Path("/non/existent/file.bin")

        with pytest.raises(OSError, match="Cannot read file"):
            transcriber._read_file_chunked(non_existent)

    def test_read_file_chunked_permission_error(self, tmp_path):
        """Test chunked reading with permission denied."""
        transcriber = ElevenLabsTranscriber(api_key="test_key")

        restricted_file = tmp_path / "restricted.bin"
        restricted_file.write_bytes(b"test data")

        # Mock permission error
        with patch("builtins.open", side_effect=PermissionError("Permission denied")):
            with pytest.raises(OSError, match="Cannot read file"):
                transcriber._read_file_chunked(restricted_file)


class TestElevenLabsTranscriberMemoryManagement:
    """Test ElevenLabsTranscriber memory management edge cases."""

    @patch("src.providers.elevenlabs.ElevenLabsClient")
    @patch("src.providers.elevenlabs.safe_validate_audio_file")
    def test_transcribe_streaming_approach(self, mock_validate, mock_elevenlabs_class, tmp_path):
        """Test transcription uses streaming approach for large files."""
        # Note: MAX_FILE_SIZE_MB = MAX_MEMORY_SIZE = 50MB
        # Since chunked reading only triggers when file_size_mb * 1024 * 1024 > MAX_MEMORY_SIZE,
        # and files > MAX_FILE_SIZE_MB are rejected, chunked reading won't trigger for valid files.
        # This test verifies the chunked reading path by mocking the file size check.
        large_file = tmp_path / "streaming_test.mp3"
        # Create a small file (will be mocked to appear larger)
        large_file.write_bytes(b"x" * 1000)

        # Mock validation to pass (return the file path)
        mock_validate.return_value = large_file

        mock_client = Mock()
        mock_response = Mock()
        mock_response.text = "Streaming test transcription"
        mock_response.segments = []
        mock_speech_to_text_client = Mock()
        mock_speech_to_text_client.convert.return_value = mock_response
        mock_client.speech_to_text = mock_speech_to_text_client
        # Patch returns the mock client directly (ElevenLabsClient is the class)
        mock_elevenlabs_class.return_value = mock_client

        transcriber = ElevenLabsTranscriber(api_key="test_key")

        # Mock Path.stat() to return a size that's > MAX_MEMORY_SIZE but < MAX_FILE_SIZE_MB
        # This allows us to test the chunked reading path
        mock_stat_result = Mock()
        # Use 49MB to be under MAX_FILE_SIZE_MB but we'll mock it to trigger chunked reading
        # Actually, since MAX_FILE_SIZE_MB = MAX_MEMORY_SIZE, we need to mock MAX_FILE_SIZE_MB too
        mock_stat_result.st_size = 49 * 1024 * 1024  # 49MB (under both limits)

        # Mock MAX_FILE_SIZE_MB to be higher so the file passes the size check
        # but mock the actual file size to be > MAX_MEMORY_SIZE to trigger chunked reading
        with patch.object(transcriber, "MAX_FILE_SIZE_MB", 60):  # Increase limit to 60MB
            # Now mock stat to return 52MB (over MAX_MEMORY_SIZE but under mocked MAX_FILE_SIZE_MB)
            mock_stat_result.st_size = 52 * 1024 * 1024
            with patch("pathlib.Path.stat", return_value=mock_stat_result):
                with patch.object(
                    transcriber, "_read_file_chunked", return_value=b"mocked_data"
                ) as mock_read:
                    transcriber.transcribe(large_file, "en")

                # Verify streaming approach was used
                assert mock_read.called

    @patch("src.providers.elevenlabs.ElevenLabsClient")
    @patch("src.providers.elevenlabs.safe_validate_audio_file")
    def test_transcribe_validation_failure(
        self, mock_validate, mock_elevenlabs_class, temp_audio_file
    ):
        """Test transcription when file validation fails raises ValidationError."""
        from src.exceptions import ValidationError

        mock_validate.return_value = None  # Validation failed
        transcriber = ElevenLabsTranscriber(api_key="test_key")

        with pytest.raises(ValidationError, match="Audio file validation failed"):
            transcriber.transcribe(temp_audio_file, "en")

        mock_validate.assert_called_once()


class TestElevenLabsTranscriberEdgeCases:
    """Test ElevenLabsTranscriber edge cases in transcription."""

    @patch("src.providers.elevenlabs.ElevenLabsClient")
    def test_transcribe_language_none(self, mock_elevenlabs_class, temp_audio_file):
        """Test transcription with language=None."""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.text = "Language auto-detected"
        mock_response.segments = []
        mock_speech_to_text_client = Mock()
        mock_speech_to_text_client.convert.return_value = mock_response
        mock_client.speech_to_text = mock_speech_to_text_client
        # Patch returns the mock client directly (ElevenLabsClient is the class)
        mock_elevenlabs_class.return_value = mock_client

        transcriber = ElevenLabsTranscriber(api_key="test_key")

        with patch("builtins.open", mock_open(read_data=b"test_audio")):
            result = transcriber.transcribe(temp_audio_file, None)

        assert result is not None
        # Verify language_code was passed as None
        call_args = mock_speech_to_text_client.convert.call_args
        assert call_args[1]["language_code"] is None

    @patch("src.providers.elevenlabs.ElevenLabsClient")
    def test_transcribe_permission_error(self, mock_elevenlabs_class, temp_audio_file):
        """Test transcription with permission error raises FileAccessError."""
        from src.exceptions import FileAccessError

        mock_client = Mock()
        mock_speech_to_text_client = Mock()
        mock_speech_to_text_client.convert.side_effect = PermissionError("Permission denied")
        mock_client.speech_to_text = mock_speech_to_text_client
        mock_elevenlabs_class.return_value = mock_client

        transcriber = ElevenLabsTranscriber(api_key="test_key")

        with patch("builtins.open", mock_open(read_data=b"test_audio")):
            with patch(
                "src.providers.elevenlabs.safe_validate_audio_file", return_value=temp_audio_file
            ):
                with patch("src.providers.elevenlabs.asyncio.wait_for") as mock_wait:
                    mock_wait.side_effect = PermissionError("Permission denied")
                    with pytest.raises(FileAccessError, match="Permission denied"):
                        transcriber.transcribe(temp_audio_file, "en")

    @patch("src.providers.elevenlabs.ElevenLabsClient")
    def test_transcribe_memory_error(self, mock_elevenlabs_class, temp_audio_file):
        """Test transcription with memory error raises ProviderAPIError."""
        from src.exceptions import ProviderAPIError

        mock_client = Mock()
        mock_speech_to_text_client = Mock()
        mock_speech_to_text_client.convert.side_effect = MemoryError("Out of memory")
        mock_client.speech_to_text = mock_speech_to_text_client
        mock_elevenlabs_class.return_value = mock_client

        transcriber = ElevenLabsTranscriber(api_key="test_key")

        with patch("builtins.open", mock_open(read_data=b"test_audio")):
            with patch(
                "src.providers.elevenlabs.safe_validate_audio_file", return_value=temp_audio_file
            ):
                with patch("src.providers.elevenlabs.asyncio.wait_for") as mock_wait:
                    mock_wait.side_effect = MemoryError("Out of memory")
                    with pytest.raises(ProviderAPIError, match="Insufficient memory"):
                        transcriber.transcribe(temp_audio_file, "en")

    @patch("src.providers.elevenlabs.ElevenLabsClient")
    @patch("src.providers.elevenlabs.asyncio.run")
    def test_transcribe_os_error(self, mock_asyncio_run, mock_elevenlabs_class, temp_audio_file):
        """Test transcription with OS error raises the error through retry mechanism."""
        from src.utils.retry_legacy import RetryExhaustedError
        
        mock_client = Mock()
        mock_speech_to_text_client = Mock()
        mock_speech_to_text_client.convert.side_effect = OSError("Disk I/O error")
        mock_client.speech_to_text = mock_speech_to_text_client
        mock_elevenlabs_class.return_value = mock_client

        # Mock asyncio.run to raise RetryExhaustedError as would happen after retries fail
        mock_asyncio_run.side_effect = RetryExhaustedError(
            attempts=3,
            last_exception=OSError("Disk I/O error"),
            total_delay=3.02
        )

        transcriber = ElevenLabsTranscriber(api_key="test_key")

        with patch("builtins.open", mock_open(read_data=b"test_audio")):
            with patch(
                "src.providers.elevenlabs.safe_validate_audio_file", return_value=temp_audio_file
            ):
                with pytest.raises(RetryExhaustedError, match="Disk I/O error"):
                    transcriber.transcribe(temp_audio_file, "en")

    @patch("src.providers.elevenlabs.ElevenLabsClient")
    def test_transcribe_value_error(self, mock_elevenlabs_class, temp_audio_file):
        """Test transcription with value error raises ProviderAPIError."""
        from src.exceptions import ProviderAPIError

        mock_client = Mock()
        mock_speech_to_text_client = Mock()
        mock_speech_to_text_client.convert.side_effect = ValueError("Invalid audio format")
        mock_client.speech_to_text = mock_speech_to_text_client
        mock_elevenlabs_class.return_value = mock_client

        transcriber = ElevenLabsTranscriber(api_key="test_key")

        with patch("builtins.open", mock_open(read_data=b"test_audio")):
            with patch(
                "src.providers.elevenlabs.safe_validate_audio_file", return_value=temp_audio_file
            ):
                with patch("src.providers.elevenlabs.asyncio.wait_for") as mock_wait:
                    mock_wait.side_effect = ValueError("Invalid audio format")
                    with pytest.raises(ProviderAPIError, match="Unexpected ElevenLabs error"):
                        transcriber.transcribe(temp_audio_file, "en")

    @pytest.mark.asyncio
    @patch("src.providers.elevenlabs.ElevenLabsClient")
    async def test_transcribe_async_timeout(self, mock_elevenlabs_class, temp_audio_file):
        """Test async transcription with timeout raises TimeoutError."""
        import asyncio

        mock_client = Mock()

        def slow_transcribe(*args, **kwargs):
            import time

            time.sleep(10)  # Simulate slow transcription
            return Mock()

        mock_speech_to_text_client = Mock()
        mock_speech_to_text_client.convert = slow_transcribe
        mock_client.speech_to_text = mock_speech_to_text_client
        mock_elevenlabs_class.return_value = mock_client

        transcriber = ElevenLabsTranscriber(api_key="test_key")

        # Use short timeout for testing - patch get_config() to return a config with short timeout
        mock_config = Mock()
        mock_config.ELEVENLABS_TIMEOUT = 0.1
        with patch("src.providers.elevenlabs.get_config", return_value=mock_config):
            with patch("builtins.open", mock_open(read_data=b"test_audio")):
                with patch(
                    "src.providers.elevenlabs.safe_validate_audio_file",
                    return_value=temp_audio_file,
                ):
                    with pytest.raises(asyncio.TimeoutError):
                        await transcriber._transcribe_impl(temp_audio_file, "en")


class TestElevenLabsTranscriberIntegration:
    """Integration tests for ElevenLabsTranscriber."""

    @patch("src.providers.elevenlabs.ElevenLabsClient")
    def test_full_transcription_workflow(self, mock_elevenlabs_class, temp_audio_file, tmp_path):
        """Test complete transcription workflow from audio file to saved result."""
        # Setup mock
        mock_client = Mock()
        mock_response = Mock()
        mock_response.text = "Complete integration test transcription"
        mock_response.segments = [
            Mock(start=0.0, end=20.0, text="Complete integration test"),
            Mock(start=20.0, end=40.0, text="transcription"),
        ]
        mock_speech_to_text_client = Mock()
        mock_speech_to_text_client.convert.return_value = mock_response
        mock_client.speech_to_text = mock_speech_to_text_client
        # Patch returns the mock client directly (ElevenLabsClient is the class)
        mock_elevenlabs_class.return_value = mock_client

        transcriber = ElevenLabsTranscriber(api_key="integration_test_key")

        # Perform transcription
        with patch("builtins.open", mock_open(read_data=b"integration_test_audio")):
            result = transcriber.transcribe(temp_audio_file, "en")

        # Verify result
        assert result is not None
        assert result.provider_name == "ElevenLabs"
        assert "integration test" in result.transcript.lower()

        # Save and verify file
        output_file = tmp_path / "integration_result.txt"
        transcriber.save_result_to_file(result, output_file)

        assert output_file.exists()
        content = output_file.read_text()
        assert "ELEVENLABS TRANSCRIPTION" in content
        assert "Complete integration test transcription" in content
