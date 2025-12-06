"""Tests for FileNotFoundError → AudioFileNotFoundError mapping in Deepgram _transcribe_impl.

These tests verify that when a FileNotFoundError is raised during transcription
(e.g., audio file doesn't exist), it maps to AudioFileNotFoundError via the
provider_error_handler decorator.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.exceptions import AudioFileNotFoundError


class TestDeepgramFileNotFoundMapping:
    """Test FileNotFoundError handling in Deepgram _transcribe_impl."""

    @pytest.fixture
    def mock_deepgram_client(self):
        """Create a mock Deepgram client."""
        with patch("src.providers.deepgram.DeepgramClient") as mock:
            yield mock

    @pytest.fixture
    def mock_config(self):
        """Mock the config to provide API key."""
        with patch("src.providers.deepgram.get_config") as mock:
            mock.return_value.DEEPGRAM_API_KEY = "test-api-key"
            mock.return_value.max_retries = 3
            mock.return_value.retry_delay = 1.0
            mock.return_value.max_retry_delay = 30.0
            mock.return_value.retry_exponential_base = 2.0
            mock.return_value.retry_jitter = 0.1
            mock.return_value.circuit_breaker_failure_threshold = 5
            mock.return_value.circuit_breaker_recovery_timeout = 30.0
            yield mock

    @pytest.mark.asyncio
    async def test_file_not_found_maps_to_audio_file_not_found_error(
        self, mock_config, mock_deepgram_client
    ):
        """FileNotFoundError in _transcribe_impl should map to AudioFileNotFoundError."""
        from src.providers.deepgram import DeepgramTranscriber

        transcriber = DeepgramTranscriber(api_key="test-api-key")

        # Use a non-existent file path
        non_existent_path = Path("/nonexistent/audio.mp3")

        # Mock safe_validate_audio_file to raise FileNotFoundError
        with patch(
            "src.providers.deepgram.safe_validate_audio_file",
            side_effect=FileNotFoundError(f"No such file: {non_existent_path}"),
        ):
            with pytest.raises(AudioFileNotFoundError) as exc_info:
                await transcriber._transcribe_impl(non_existent_path, language="en")

            # Verify the error contains the file path context
            assert "file_path" in exc_info.value.context or "not found" in str(
                exc_info.value
            ).lower()

    @pytest.mark.asyncio
    async def test_file_not_found_during_file_open_maps_correctly(
        self, mock_config, mock_deepgram_client
    ):
        """FileNotFoundError when opening file should map to AudioFileNotFoundError."""
        from src.providers.deepgram import DeepgramTranscriber

        transcriber = DeepgramTranscriber(api_key="test-api-key")
        test_path = Path("/test/missing_audio.mp3")

        # Mock validation to pass but file open to fail
        with (
            patch(
                "src.providers.deepgram.safe_validate_audio_file",
                return_value=test_path,
            ),
            patch.object(
                transcriber,
                "_open_audio_file",
                side_effect=FileNotFoundError(f"No such file: {test_path}"),
            ),
            patch.object(transcriber, "_create_client"),
            patch.object(transcriber, "_build_options"),
            patch.object(transcriber, "_detect_mimetype", return_value="audio/mp3"),
            patch.object(transcriber, "_log_file_info"),
        ):
            with pytest.raises(AudioFileNotFoundError) as exc_info:
                await transcriber._transcribe_impl(test_path, language="en")

            assert "file_path" in exc_info.value.context or str(test_path) in str(
                exc_info.value.context
            )
