"""Tests for validation error handling in Deepgram _transcribe_impl.

These tests verify that validation errors (missing files, invalid formats, etc.) are
handled consistently via the provider_error_handler decorator and validate_audio_file_or_raise.
"""

from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from src.exceptions import AudioFileNotFoundError, ValidationError

# API key must be >= 20 chars to pass validation
TEST_API_KEY = "test_deepgram_api_key_12345"


class TestDeepgramValidationErrorMapping:
    """Test validation error handling in Deepgram _transcribe_impl."""

    @pytest.fixture
    def mock_config(self):
        """Mock the config to provide API key."""
        with patch("src.config.get_config") as mock:
            mock.return_value.DEEPGRAM_API_KEY = TEST_API_KEY
            mock.return_value.max_retries = 3
            mock.return_value.retry_delay = 1.0
            mock.return_value.max_retry_delay = 30.0
            mock.return_value.retry_exponential_base = 2.0
            mock.return_value.retry_jitter = 0.1
            mock.return_value.circuit_breaker_failure_threshold = 5
            mock.return_value.circuit_breaker_recovery_timeout = 30.0
            yield mock

    @pytest.mark.asyncio
    async def test_validation_error_raised_for_missing_file(self, mock_config):
        """ValidationError from validate_audio_file_or_raise should propagate."""
        from src.providers.deepgram import DeepgramTranscriber

        transcriber = DeepgramTranscriber(api_key=TEST_API_KEY)

        # Use a non-existent file path
        non_existent_path = Path("/nonexistent/audio.mp3")

        # Mock validate_audio_file_or_raise to raise ValidationError
        with patch(
            "src.providers.deepgram.validate_audio_file_or_raise",
            side_effect=ValidationError(
                f"Audio file validation failed: {non_existent_path}",
                context={"file_path": str(non_existent_path)},
            ),
        ):
            with pytest.raises((AudioFileNotFoundError, ValidationError)) as exc_info:
                await transcriber._transcribe_impl(non_existent_path, language="en")

            # Verify the error contains the file path context
            error = exc_info.value
            assert (
                (hasattr(error, "context") and "file_path" in error.context)
                or "not found" in str(error).lower()
                or "validation failed" in str(error).lower()
            )

    @pytest.mark.asyncio
    async def test_file_read_error_maps_to_audio_file_not_found(self, mock_config):
        """FileNotFoundError when reading file bytes should map to AudioFileNotFoundError."""
        from src.providers.deepgram import DeepgramTranscriber

        transcriber = DeepgramTranscriber(api_key=TEST_API_KEY)
        test_path = Mock(spec=Path)
        test_path.read_bytes.side_effect = FileNotFoundError(f"No such file: {test_path}")
        test_path.name = "missing_audio.mp3"
        test_path.stat.return_value = Mock(st_size=1024)

        # Mock validation to pass but file read to fail
        with (
            patch(
                "src.providers.deepgram.validate_audio_file_or_raise",
                return_value=test_path,
            ),
            patch.object(transcriber, "_create_client"),
            patch.object(transcriber, "_log_file_info"),
        ):
            with pytest.raises(AudioFileNotFoundError) as exc_info:
                await transcriber._transcribe_impl(test_path, language="en")

            error = exc_info.value
            assert (
                hasattr(error, "context") and "file_path" in error.context
            ) or "not found" in str(error).lower()
