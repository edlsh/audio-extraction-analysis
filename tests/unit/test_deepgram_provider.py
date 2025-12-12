"""Tests for Deepgram Nova 3 transcription provider."""

import io
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from src.providers.deepgram import DeepgramTranscriber

# Test constants - API key must be >= 20 chars to pass validation
TEST_API_KEY = "test_deepgram_api_key_12345"
TEST_AUDIO_PATH = "/tmp/test_audio.mp3"
TEST_MIMETYPE = "audio/mp3"
TEST_LANGUAGE = "en"


@pytest.mark.unit
@pytest.mark.fast
@pytest.mark.deepgram
@pytest.mark.mock
class TestDeepgramTranscriber:
    """Test Deepgram transcription provider functionality."""

    @pytest.fixture
    def deepgram_transcriber(self):
        """Create a DeepgramTranscriber instance for testing."""
        with patch.dict("os.environ", {"DEEPGRAM_API_KEY": TEST_API_KEY}):
            return DeepgramTranscriber(api_key=TEST_API_KEY)

    @pytest.fixture
    def mock_deepgram_response(self):
        """Create a standard mock Deepgram API response."""
        mock_response = Mock()
        mock_response.results.channels = [Mock()]
        mock_response.results.channels[0].alternatives = [Mock()]
        mock_response.results.channels[0].alternatives[0].transcript = "Test transcript"
        mock_response.metadata.duration = 10.0
        # Set optional attributes to None to prevent AttributeError
        mock_response.results.summary = None
        mock_response.results.topics = None
        mock_response.results.intents = None
        mock_response.results.sentiments = None
        mock_response.results.utterances = None
        return mock_response

    @pytest.fixture
    def mock_file_handle(self):
        """Create a mock file handle for testing."""
        mock_file = MagicMock(spec=io.BufferedReader)
        mock_file.__enter__ = Mock(return_value=mock_file)
        mock_file.__exit__ = Mock(return_value=False)
        return mock_file

    def test_validate_configuration_with_api_key(self, deepgram_transcriber):
        """Test configuration validation when API key is provided."""
        assert deepgram_transcriber.validate_configuration() is True

    def test_validate_configuration_without_api_key(self):
        """Test configuration validation when API key is missing."""
        with patch.dict("os.environ", {}, clear=True):
            # Patch get_config at the config module level since base.py imports from ..config
            with patch("src.config.get_config") as mock_config:
                mock_config.return_value.DEEPGRAM_API_KEY = None
                with pytest.raises(ValueError, match="DEEPGRAM_API_KEY not found"):
                    DeepgramTranscriber(api_key=None)

    def test_get_provider_name(self, deepgram_transcriber):
        """Test getting provider name."""
        assert deepgram_transcriber.get_provider_name() == "Deepgram Nova 3"

    def test_get_supported_features(self, deepgram_transcriber):
        """Test getting supported features."""
        features = deepgram_transcriber.get_supported_features()
        expected_features = {
            "speaker_diarization",
            "topic_detection",
            "intent_analysis",
            "sentiment_analysis",
            "timestamps",
            "summarization",
            "language_detection",
        }
        assert expected_features.issubset(
            features
        ), f"Missing features: {expected_features - set(features)}"

    @pytest.mark.asyncio
    async def test_transcription_reads_audio_bytes(
        self, deepgram_transcriber, mock_deepgram_response
    ):
        """Test that transcription reads audio bytes and sends to Deepgram."""
        mock_path = Mock(spec=Path)
        mock_path.read_bytes.return_value = b"fake audio data"
        mock_path.suffix = ".mp3"
        mock_path.name = "test_audio.mp3"
        mock_path.stat.return_value = Mock(st_size=1024)

        mock_client = Mock()
        mock_client.listen.v1.media.transcribe_file.return_value = mock_deepgram_response

        with (
            patch.object(deepgram_transcriber, "_create_client", return_value=mock_client),
            patch("src.providers.deepgram.validate_audio_file_or_raise", return_value=mock_path),
            patch.object(deepgram_transcriber, "_log_file_info"),
        ):
            result = await deepgram_transcriber._transcribe_impl(mock_path, TEST_LANGUAGE)

            assert result is not None
            assert result.transcript == "Test transcript"
            mock_path.read_bytes.assert_called_once()

    @pytest.mark.asyncio
    async def test_large_file_transcription(self, deepgram_transcriber):
        """Test that transcription correctly handles large audio files."""
        mock_path = Mock(spec=Path)
        mock_path.read_bytes.return_value = b"large audio data" * 1000
        mock_path.suffix = ".mp3"
        mock_path.name = "large_audio.mp3"
        mock_path.stat.return_value = Mock(st_size=16000)

        mock_client = Mock()
        mock_response = Mock()
        mock_response.results.channels = [Mock()]
        mock_response.results.channels[0].alternatives = [Mock()]
        mock_response.results.channels[0].alternatives[0].transcript = "Large file transcript"
        mock_response.metadata.duration = 120.0
        mock_response.results.summary = None
        mock_response.results.topics = None
        mock_response.results.intents = None
        mock_response.results.sentiments = None
        mock_response.results.utterances = None

        mock_client.listen.v1.media.transcribe_file.return_value = mock_response

        with (
            patch.object(deepgram_transcriber, "_create_client", return_value=mock_client),
            patch("src.providers.deepgram.validate_audio_file_or_raise", return_value=mock_path),
            patch.object(deepgram_transcriber, "_log_file_info"),
        ):
            result = await deepgram_transcriber._transcribe_impl(mock_path, TEST_LANGUAGE)

            assert result is not None
            assert result.transcript == "Large file transcript"
            mock_path.read_bytes.assert_called_once()
            call_args = mock_client.listen.v1.media.transcribe_file.call_args
            assert call_args[1]["request"] == b"large audio data" * 1000

    @pytest.mark.asyncio
    async def test_normal_file_transcription(self, deepgram_transcriber, mock_deepgram_response):
        """Test that normal-sized files work correctly."""
        mock_path = Mock(spec=Path)
        mock_path.read_bytes.return_value = b"normal audio data"
        mock_path.suffix = ".mp3"
        mock_path.name = "normal_audio.mp3"
        mock_path.stat.return_value = Mock(st_size=1024)

        mock_client = Mock()
        mock_client.listen.v1.media.transcribe_file.return_value = mock_deepgram_response

        with (
            patch.object(deepgram_transcriber, "_create_client", return_value=mock_client),
            patch("src.providers.deepgram.validate_audio_file_or_raise", return_value=mock_path),
            patch.object(deepgram_transcriber, "_log_file_info"),
        ):
            result = await deepgram_transcriber._transcribe_impl(mock_path, TEST_LANGUAGE)

            assert result is not None
            assert result.transcript == "Test transcript"


@pytest.mark.unit
@pytest.mark.fast
@pytest.mark.deepgram
@pytest.mark.mock
class TestDeepgramTranscriberErrorPaths:
    """Test Deepgram transcription provider error handling paths."""

    @pytest.fixture
    def deepgram_transcriber(self):
        """Create a DeepgramTranscriber instance for testing."""
        with patch.dict("os.environ", {"DEEPGRAM_API_KEY": TEST_API_KEY}):
            return DeepgramTranscriber(api_key=TEST_API_KEY)

    @pytest.mark.asyncio
    async def test_import_error_raises_provider_not_available(self, deepgram_transcriber):
        """ImportError during transcription should raise ProviderNotAvailableError."""
        from src.exceptions import ProviderNotAvailableError

        test_file = Path("/tmp/test.mp3")

        with (
            patch(
                "src.providers.deepgram.validate_audio_file_or_raise",
                return_value=test_file,
            ),
            patch.object(
                deepgram_transcriber,
                "_create_client",
                side_effect=ImportError("No module named 'deepgram'"),
            ),
        ):
            with pytest.raises(ProviderNotAvailableError) as exc_info:
                await deepgram_transcriber._transcribe_impl(test_file)

            assert "deepgram" in exc_info.value.message.lower()
            assert exc_info.value.context.get("install_command") == "uv add deepgram-sdk"

    @pytest.mark.asyncio
    async def test_permission_error_raises_file_access_error(self, deepgram_transcriber):
        """PermissionError should raise FileAccessError."""
        from src.exceptions import FileAccessError

        # Create a mock Path that raises PermissionError on read_bytes()
        mock_path = Mock(spec=Path)
        mock_path.read_bytes.side_effect = PermissionError("Permission denied")
        mock_path.suffix = ".mp3"
        mock_path.name = "protected_audio.mp3"
        mock_path.stat.return_value = Mock(st_size=1024)

        with (
            patch(
                "src.providers.deepgram.validate_audio_file_or_raise",
                return_value=mock_path,
            ),
            patch.object(deepgram_transcriber, "_create_client", return_value=Mock()),
            patch.object(deepgram_transcriber, "_log_file_info"),
        ):
            with pytest.raises(FileAccessError) as exc_info:
                await deepgram_transcriber._transcribe_impl(mock_path)

            assert "permission" in exc_info.value.message.lower()

    @pytest.mark.asyncio
    async def test_os_error_raises_provider_api_error(self, deepgram_transcriber):
        """OSError should raise ProviderAPIError."""
        from src.exceptions import ProviderAPIError

        # Create a mock Path that raises OSError on read_bytes()
        mock_path = Mock(spec=Path)
        mock_path.read_bytes.side_effect = OSError("Disk full")
        mock_path.suffix = ".mp3"
        mock_path.name = "test_audio.mp3"
        mock_path.stat.return_value = Mock(st_size=1024)

        with (
            patch(
                "src.providers.deepgram.validate_audio_file_or_raise",
                return_value=mock_path,
            ),
            patch.object(deepgram_transcriber, "_create_client", return_value=Mock()),
            patch.object(deepgram_transcriber, "_log_file_info"),
        ):
            with pytest.raises(ProviderAPIError) as exc_info:
                await deepgram_transcriber._transcribe_impl(mock_path)

            assert "system error" in exc_info.value.message.lower()

    @pytest.mark.asyncio
    async def test_connection_error_passes_through(self, deepgram_transcriber):
        """ConnectionError should pass through for retry logic."""
        # Create a mock Path that returns bytes
        mock_path = Mock(spec=Path)
        mock_path.read_bytes.return_value = b"audio data"
        mock_path.suffix = ".mp3"
        mock_path.name = "test_audio.mp3"
        mock_path.stat.return_value = Mock(st_size=1024)

        # Mock client that raises ConnectionError on transcribe
        mock_client = Mock()
        mock_client.listen.v1.media.transcribe_file.side_effect = ConnectionError(
            "Connection refused"
        )

        with (
            patch(
                "src.providers.deepgram.validate_audio_file_or_raise",
                return_value=mock_path,
            ),
            patch.object(deepgram_transcriber, "_create_client", return_value=mock_client),
            patch.object(deepgram_transcriber, "_log_file_info"),
        ):
            with pytest.raises(ConnectionError):
                await deepgram_transcriber._transcribe_impl(mock_path)

    @pytest.mark.asyncio
    async def test_validation_error_on_invalid_file(self, deepgram_transcriber):
        """ValidationError should be raised for invalid audio file."""
        from src.exceptions import ValidationError

        test_file = Path("/tmp/invalid.mp3")

        with patch(
            "src.providers.deepgram.validate_audio_file_or_raise",
            side_effect=ValidationError(
                f"Audio file validation failed: {test_file}",
                context={"file_path": str(test_file), "provider": "deepgram"},
            ),
        ):
            with pytest.raises(ValidationError) as exc_info:
                await deepgram_transcriber._transcribe_impl(test_file)

            assert "validation failed" in exc_info.value.message.lower()
