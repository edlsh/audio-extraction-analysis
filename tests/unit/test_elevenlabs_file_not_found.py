"""Tests for FileNotFoundError → AudioFileNotFoundError mapping in ElevenLabs _transcribe_impl.

These tests verify that when a FileNotFoundError is raised during transcription
(e.g., audio file doesn't exist), it maps to AudioFileNotFoundError via the
provider_error_handler decorator.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.exceptions import AudioFileNotFoundError


class TestElevenLabsFileNotFoundMapping:
    """Test FileNotFoundError handling in ElevenLabs _transcribe_impl."""

    @pytest.fixture
    def mock_elevenlabs_sdk(self):
        """Mock ElevenLabs SDK availability."""
        with patch.dict("sys.modules", {"elevenlabs": MagicMock(), "elevenlabs.client": MagicMock()}):
            yield

    @pytest.fixture
    def mock_config(self):
        """Mock the config to provide API key."""
        with patch("src.providers.elevenlabs.get_config") as mock:
            mock.return_value.ELEVENLABS_API_KEY = "test-api-key"
            mock.return_value.ELEVENLABS_TIMEOUT = 300.0
            mock.return_value.connect_timeout = 10.0
            mock.return_value.max_retries = 3
            mock.return_value.retry_delay = 1.0
            mock.return_value.max_retry_delay = 30.0
            mock.return_value.retry_exponential_base = 2.0
            mock.return_value.retry_jitter = 0.1
            mock.return_value.circuit_breaker_failure_threshold = 5
            mock.return_value.circuit_breaker_recovery_timeout = 30.0
            yield mock

    @pytest.mark.asyncio
    async def test_file_not_found_maps_to_audio_file_not_found_error(self, mock_config):
        """FileNotFoundError in _transcribe_impl should map to AudioFileNotFoundError."""
        # Patch the SDK check
        with patch("src.providers.elevenlabs.PROVIDER_AVAILABLE", True):
            with patch("src.providers.elevenlabs.ElevenLabsClient"):
                from src.providers.elevenlabs import ElevenLabsTranscriber

                transcriber = ElevenLabsTranscriber(api_key="test-api-key")

                # Use a non-existent file path
                non_existent_path = Path("/nonexistent/audio.mp3")

                # Mock safe_validate_audio_file to raise FileNotFoundError
                with patch(
                    "src.providers.elevenlabs.safe_validate_audio_file",
                    side_effect=FileNotFoundError(f"No such file: {non_existent_path}"),
                ):
                    with pytest.raises(AudioFileNotFoundError) as exc_info:
                        await transcriber._transcribe_impl(non_existent_path, language="en")

                    # Verify the error contains the file path context
                    assert "file_path" in exc_info.value.context or "not found" in str(
                        exc_info.value
                    ).lower()

    @pytest.mark.asyncio
    async def test_file_not_found_during_file_read_maps_correctly(self, mock_config):
        """FileNotFoundError when reading file should map to AudioFileNotFoundError."""
        with patch("src.providers.elevenlabs.PROVIDER_AVAILABLE", True):
            with patch("src.providers.elevenlabs.ElevenLabsClient"):
                from src.providers.elevenlabs import ElevenLabsTranscriber

                transcriber = ElevenLabsTranscriber(api_key="test-api-key")
                test_path = Path("/test/missing_audio.mp3")

                # Mock validation to pass but file operations to fail
                mock_stat = MagicMock()
                mock_stat.st_size = 1024 * 1024  # 1MB

                with (
                    patch(
                        "src.providers.elevenlabs.safe_validate_audio_file",
                        return_value=test_path,
                    ),
                    patch.object(
                        test_path.__class__,
                        "stat",
                        return_value=mock_stat,
                    ),
                    patch(
                        "builtins.open",
                        side_effect=FileNotFoundError(f"No such file: {test_path}"),
                    ),
                ):
                    with pytest.raises(AudioFileNotFoundError) as exc_info:
                        await transcriber._transcribe_impl(test_path, language="en")

                    # Error should contain path context
                    assert "file_path" in exc_info.value.context or str(test_path) in str(
                        exc_info.value
                    )
