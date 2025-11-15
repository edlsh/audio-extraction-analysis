"""Tests for Deepgram Nova 3 transcription provider."""

import io
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from src.providers.deepgram import DeepgramTranscriber

# Test constants
TEST_API_KEY = "test_api_key"
TEST_AUDIO_PATH = "/tmp/test_audio.mp3"
TEST_MIMETYPE = "audio/mp3"
TEST_LANGUAGE = "en"


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

    def test_open_audio_file_returns_file_handle(self, deepgram_transcriber, mock_file_handle):
        """Test that _open_audio_file returns a file handle, not bytes."""
        test_file = Path(TEST_AUDIO_PATH)

        with patch("builtins.open", return_value=mock_file_handle) as mock_open_func:
            result = deepgram_transcriber._open_audio_file(test_file)

            # Verify file was opened in binary read mode
            mock_open_func.assert_called_once_with(test_file, "rb")
            # Verify we got the file handle, not bytes
            assert result == mock_file_handle

    @pytest.mark.asyncio
    async def test_streaming_upload_uses_file_handle(
        self, deepgram_transcriber, mock_deepgram_response, mock_file_handle
    ):
        """Test that streaming upload passes file handle instead of bytes."""
        test_file = Path(TEST_AUDIO_PATH)

        # Mock Deepgram client
        mock_client = Mock()
        mock_client.listen.prerecorded.v.return_value.transcribe_file.return_value = (
            mock_deepgram_response
        )

        with patch.object(
            deepgram_transcriber, "_create_client", return_value=mock_client
        ), patch.object(
            deepgram_transcriber, "_open_audio_file", return_value=mock_file_handle
        ), patch.object(
            deepgram_transcriber, "_build_options", return_value=Mock()
        ), patch.object(
            deepgram_transcriber, "_detect_mimetype", return_value=TEST_MIMETYPE
        ), patch(
            "src.providers.deepgram.safe_validate_audio_file", return_value=test_file
        ):
            result = await deepgram_transcriber._transcribe_impl(test_file, TEST_LANGUAGE)

            # Verify file handle was passed (not bytes)
            assert result is not None
            assert result.transcript == "Test transcript"

            # Verify transcribe_file was called with file handle
            call_args = mock_client.listen.prerecorded.v.return_value.transcribe_file.call_args
            assert "source" in call_args[1]
            # The buffer should be the file handle, not bytes
            assert call_args[1]["source"]["buffer"] == mock_file_handle

    @pytest.mark.asyncio
    async def test_large_file_streaming_memory_efficiency(self, deepgram_transcriber):
        """Test that large files use file handle streaming, not full memory load."""
        test_file = Path("/tmp/large_audio.mp3")

        # Track if .read() was called on the file (which would load into memory)
        read_called = False

        class MockFile:
            """Mock file that tracks read() calls."""

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self, size=-1):
                nonlocal read_called
                read_called = True
                return b"audio data"

        mock_file = MockFile()

        # Mock Deepgram client
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

        mock_client.listen.prerecorded.v.return_value.transcribe_file.return_value = mock_response

        with patch.object(
            deepgram_transcriber, "_create_client", return_value=mock_client
        ), patch.object(
            deepgram_transcriber, "_open_audio_file", return_value=mock_file
        ), patch.object(
            deepgram_transcriber, "_build_options", return_value=Mock()
        ), patch.object(
            deepgram_transcriber, "_detect_mimetype", return_value=TEST_MIMETYPE
        ), patch(
            "src.providers.deepgram.safe_validate_audio_file", return_value=test_file
        ):
            result = await deepgram_transcriber._transcribe_impl(test_file, TEST_LANGUAGE)

            assert result is not None
            assert result.transcript == "Large file transcript"

            # Verify file handle was passed to SDK (not bytes read into memory)
            call_args = mock_client.listen.prerecorded.v.return_value.transcribe_file.call_args
            assert call_args[1]["source"]["buffer"] == mock_file
            # Our code should NOT call .read() - SDK handles streaming internally
            assert not read_called, "File .read() was called, indicating memory inefficiency"

    @pytest.mark.asyncio
    async def test_normal_file_no_regression(self, deepgram_transcriber, mock_file_handle):
        """Test that normal-sized files still work correctly."""
        test_file = Path("/tmp/normal_audio.mp3")

        # Mock Deepgram client with custom response
        mock_client = Mock()
        mock_response = Mock()
        mock_response.results.channels = [Mock()]
        mock_response.results.channels[0].alternatives = [Mock()]
        mock_response.results.channels[0].alternatives[0].transcript = "Normal file transcript"
        mock_response.metadata.duration = 30.0
        # Add optional attributes
        mock_response.results.summary = None
        mock_response.results.topics = None
        mock_response.results.intents = None
        mock_response.results.sentiments = None
        mock_response.results.utterances = None

        mock_client.listen.prerecorded.v.return_value.transcribe_file.return_value = mock_response

        with patch.object(
            deepgram_transcriber, "_create_client", return_value=mock_client
        ), patch.object(
            deepgram_transcriber, "_open_audio_file", return_value=mock_file_handle
        ), patch.object(
            deepgram_transcriber, "_build_options", return_value=Mock()
        ), patch.object(
            deepgram_transcriber, "_detect_mimetype", return_value=TEST_MIMETYPE
        ), patch(
            "src.providers.deepgram.safe_validate_audio_file", return_value=test_file
        ):
            result = await deepgram_transcriber._transcribe_impl(test_file, TEST_LANGUAGE)

            assert result is not None
            assert result.transcript == "Normal file transcript"
            assert result.duration == 30.0
            assert result.provider_name == "Deepgram Nova 3"

    @pytest.mark.skip(reason="Integration test - complex async error scenario")
    def test_file_handle_cleanup_on_error(self, deepgram_transcriber, mock_file_handle):
        """Test that file handles are properly closed even on errors."""
        test_file = Path("/tmp/error_audio.mp3")

        # Mock client to raise an error
        mock_client = Mock()
        mock_client.listen.prerecorded.v.return_value.transcribe_file.side_effect = Exception(
            "API Error"
        )

        with patch.object(
            deepgram_transcriber, "_create_client", return_value=mock_client
        ), patch.object(
            deepgram_transcriber, "_open_audio_file", return_value=mock_file_handle
        ), patch.object(
            deepgram_transcriber, "_build_options", return_value=Mock()
        ), patch.object(
            deepgram_transcriber, "_detect_mimetype", return_value=TEST_MIMETYPE
        ), patch(
            "src.providers.deepgram.safe_validate_audio_file", return_value=test_file
        ):
            with pytest.raises(ConnectionError):
                deepgram_transcriber.transcribe(test_file, TEST_LANGUAGE)

            # Verify __exit__ was called (file handle closed)
            mock_file_handle.__exit__.assert_called()
