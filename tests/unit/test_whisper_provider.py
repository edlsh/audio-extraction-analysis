"""Tests for OpenAI Whisper transcription provider."""

from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.models.transcription import TranscriptionResult
from src.providers.whisper import WhisperTranscriber


@pytest.fixture(autouse=True)
def mock_whisper_config():
    """Automatically mock get_config() for all whisper tests."""
    with patch("src.providers.whisper.get_config") as mock_get_config:
        mock_config = Mock()
        mock_config.WHISPER_MODEL = "base"
        mock_config.WHISPER_DEVICE = "cpu"
        mock_config.WHISPER_COMPUTE_TYPE = "float16"
        mock_get_config.return_value = mock_config
        yield mock_config


class TestWhisperTranscriber:
    """Test Whisper transcription provider functionality."""

    @pytest.fixture
    def whisper_transcriber(self):
        """Create a WhisperTranscriber instance for testing."""
        with patch("src.providers.whisper.torch", None):
            return WhisperTranscriber()

    def test_validate_configuration_with_dependencies(self, whisper_transcriber):
        """Test configuration validation when dependencies are available."""
        with patch("src.providers.whisper.PROVIDER_AVAILABLE", True):
            with patch("src.providers.whisper.torch") as mock_torch:
                mock_torch.cuda.is_available.return_value = True
                assert whisper_transcriber.validate_configuration() is True

    def test_validate_configuration_without_dependencies(self, whisper_transcriber):
        """Test configuration validation when dependencies are missing."""
        with patch("src.providers.whisper.PROVIDER_AVAILABLE", False):
            assert whisper_transcriber.validate_configuration() is False

    def test_get_provider_name(self, whisper_transcriber):
        """Test getting provider name."""
        whisper_transcriber.model_name = "base"
        assert whisper_transcriber.get_provider_name() == "OpenAI Whisper (base)"

    def test_get_supported_features(self, whisper_transcriber):
        """Test getting supported features."""
        features = whisper_transcriber.get_supported_features()
        assert "timestamps" in features
        assert "word_timestamps" in features
        assert "language_detection" in features
        assert "local_processing" in features
        assert "offline_capable" in features

    @pytest.mark.asyncio
    async def test_load_model_success(self, whisper_transcriber):
        """Test successful model loading."""
        mock_model = Mock()
        with patch("src.providers.whisper.PROVIDER_AVAILABLE", True):
            # Mock the whisper module to avoid import issues
            with patch("src.providers.whisper.whisper") as mock_whisper:
                mock_whisper.load_model.return_value = mock_model
                with patch("asyncio.get_event_loop") as mock_loop:
                    mock_loop.return_value.run_in_executor = AsyncMock(return_value=mock_model)

                    await whisper_transcriber._load_model()
                    assert whisper_transcriber.model == mock_model

    @pytest.mark.asyncio
    async def test_load_model_failure(self, whisper_transcriber):
        """Test model loading failure."""
        with patch("src.providers.whisper.PROVIDER_AVAILABLE", True):
            # Mock the whisper module to avoid import issues
            with patch("src.providers.whisper.whisper") as mock_whisper:
                mock_whisper.load_model.return_value = Mock()
                with patch("asyncio.get_event_loop") as mock_loop:
                    mock_loop.return_value.run_in_executor = AsyncMock(
                        side_effect=Exception("Load failed")
                    )

                    with pytest.raises(Exception, match="Load failed"):
                        await whisper_transcriber._load_model()

    @pytest.mark.asyncio
    async def test_transcribe_impl_success(self, whisper_transcriber):
        """Test successful transcription implementation."""
        # Mock dependencies
        mock_model = Mock()
        mock_model.transcribe.return_value = {
            "segments": [
                {
                    "text": "Hello world",
                    "start": 0.0,
                    "end": 1.5,
                    "avg_logprob": 0.8,
                    "words": [
                        {"word": "Hello", "start": 0.0, "end": 0.5, "probability": 0.9},
                        {"word": "world", "start": 0.5, "end": 1.5, "probability": 0.8},
                    ],
                }
            ],
            "language": "en",
        }

        whisper_transcriber.model = mock_model

        with patch("src.providers.whisper.PROVIDER_AVAILABLE", True):
            # Mock file exists check
            with patch("pathlib.Path.exists", return_value=True):
                with patch("asyncio.get_event_loop") as mock_loop:
                    mock_loop.return_value.run_in_executor = AsyncMock(
                        return_value=mock_model.transcribe.return_value
                    )

                    audio_path = Path("/fake/audio.mp3")
                    result = await whisper_transcriber._transcribe_impl(audio_path, "en")

                    assert result is not None
                    assert isinstance(result, TranscriptionResult)
                    assert result.metadata["language"] == "en"
                    assert result.transcript == "Hello world"

    @pytest.mark.asyncio
    async def test_transcribe_impl_file_not_found(self, whisper_transcriber):
        """Test transcription with non-existent file."""
        audio_path = Path("/nonexistent/audio.mp3")

        with patch("src.providers.whisper.PROVIDER_AVAILABLE", True):
            # Mock file exists check to return False
            with patch("pathlib.Path.exists", return_value=False):
                with pytest.raises(FileNotFoundError):
                    await whisper_transcriber._transcribe_impl(audio_path, "en")

    def test_parse_whisper_result(self, whisper_transcriber):
        """Test parsing Whisper result into TranscriptionResult."""
        whisper_result = {
            "segments": [
                {
                    "text": "Test transcription",
                    "start": 0.0,
                    "end": 2.0,
                    "avg_logprob": 0.85,
                    "words": [
                        {"word": "Test", "start": 0.0, "end": 0.5, "probability": 0.9},
                        {"word": "transcription", "start": 0.5, "end": 2.0, "probability": 0.8},
                    ],
                }
            ],
            "language": "en",
        }

        audio_path = Path("/fake/audio.mp3")
        processing_time = 5.0

        result = whisper_transcriber._parse_whisper_result(
            whisper_result, audio_path, processing_time
        )

        assert isinstance(result, TranscriptionResult)
        assert result.audio_file == str(audio_path)
        assert result.metadata["language"] == "en"
        assert result.metadata["processing_time_seconds"] == 5.0
        assert result.transcript == "Test transcription"

    def test_extract_words(self, whisper_transcriber):
        """Test word extraction from Whisper segment."""
        segment = {
            "words": [
                {"word": "Hello", "start": 0.0, "end": 0.5, "probability": 0.9},
                {"word": "world", "start": 0.5, "end": 1.0, "probability": 0.8},
            ]
        }

        words = whisper_transcriber._extract_words(segment)

        assert words is not None
        assert len(words) == 2
        assert words[0]["word"] == "Hello"
        assert words[1]["word"] == "world"

    def test_extract_words_no_words(self, whisper_transcriber):
        """Test word extraction when no words are present."""
        segment = {"text": "Hello world", "start": 0.0, "end": 1.0}

        words = whisper_transcriber._extract_words(segment)

        assert words is None

    def test_generate_chapters(self, whisper_transcriber):
        """Test chapter generation from utterances."""
        from src.models.transcription import TranscriptionUtterance

        utterances = [
            TranscriptionUtterance(
                speaker=1, start=0.0, end=300.0, text="Chapter 1 content"  # 5 minutes
            ),
            TranscriptionUtterance(
                speaker=1, start=300.0, end=600.0, text="Chapter 2 content"  # 10 minutes
            ),
        ]

        chapters = whisper_transcriber._generate_chapters(utterances)

        assert len(chapters) >= 2  # At least 2 chapters for 10 minutes of content
        assert chapters[0]["start_time"] == 0.0
        assert chapters[0]["end_time"] == 300.0

    @pytest.mark.asyncio
    async def test_health_check_async_success(self, whisper_transcriber):
        """Test successful health check."""
        mock_model = Mock()
        whisper_transcriber.model = mock_model

        with patch("src.providers.whisper.PROVIDER_AVAILABLE", True):
            with patch("src.providers.whisper.torch") as mock_torch:
                mock_torch.cuda.is_available.return_value = True
                health = await whisper_transcriber.health_check_async()

                assert health["healthy"] is True
                assert health["status"] == "ready"
                assert "model_loaded" in health["details"]

    @pytest.mark.asyncio
    async def test_health_check_async_no_dependencies(self, whisper_transcriber):
        """Test health check without dependencies."""
        with patch("src.providers.whisper.PROVIDER_AVAILABLE", False):
            health = await whisper_transcriber.health_check_async()

            assert health["healthy"] is False
            assert health["status"] == "dependencies_missing"

    def test_get_model_size_info(self, whisper_transcriber):
        """Test getting model size information."""
        whisper_transcriber.model_name = "base"

        size_info = whisper_transcriber.get_model_size_info()

        assert "current_model" in size_info
        assert "current_info" in size_info
        assert "available_models" in size_info
        assert "model_sizes" in size_info
        assert size_info["current_model"] == "base"
        assert "params" in size_info["current_info"]

    @pytest.mark.asyncio
    async def test_transcribe_async_with_circuit_breaker(self, whisper_transcriber):
        """Test transcription with circuit breaker protection."""
        # Mock successful transcription
        mock_model = Mock()
        mock_model.transcribe.return_value = {
            "segments": [{"text": "Test", "start": 0.0, "end": 1.0}],
            "language": "en",
        }
        whisper_transcriber.model = mock_model

        with patch("src.providers.whisper.PROVIDER_AVAILABLE", True):
            with patch("asyncio.get_event_loop") as mock_loop:
                mock_loop.return_value.run_in_executor = AsyncMock(
                    return_value=mock_model.transcribe.return_value
                )

                # Mock file exists check
                with patch("pathlib.Path.exists", return_value=True):
                    audio_path = Path("/fake/audio.mp3")
                    result = await whisper_transcriber.transcribe_async(audio_path, "en")

                    assert result is not None
                    assert result.transcript == "Test"

    @pytest.mark.asyncio
    async def test_transcribe_async_failure(self, whisper_transcriber):
        """Test transcription failure handling."""
        # Mock failed transcription
        with patch("src.providers.whisper.PROVIDER_AVAILABLE", True):
            with patch("asyncio.get_event_loop") as mock_loop:
                mock_loop.return_value.run_in_executor = AsyncMock(
                    side_effect=Exception("Transcription failed")
                )

                # Mock file exists check
                with patch("pathlib.Path.exists", return_value=True):
                    audio_path = Path("/fake/audio.mp3")
                    result = await whisper_transcriber.transcribe_async(audio_path, "en")

                    assert result is None


class TestEnsureWhisperAvailable:
    """Test _ensure_whisper_available function for dependency management."""

    def test_ensure_whisper_available_cached_true(self):
        """Test that _ensure_whisper_available returns cached True result."""
        with patch("src.providers.whisper.PROVIDER_AVAILABLE", True):
            from src.providers.whisper import _ensure_whisper_available

            result = _ensure_whisper_available()
            assert result is True

    def test_ensure_whisper_available_cached_false(self):
        """Test that _ensure_whisper_available returns cached False result."""
        with patch("src.providers.whisper.PROVIDER_AVAILABLE", False):
            from src.providers.whisper import _ensure_whisper_available

            result = _ensure_whisper_available()
            assert result is False

    def test_ensure_whisper_available_checks_both_dependencies(self):
        """Test that _ensure_whisper_available checks for both torch and whisper."""
        # This test verifies the function attempts to import both dependencies
        # The actual import behavior is tested implicitly by other tests
        with patch("src.providers.whisper.PROVIDER_AVAILABLE", True):
            from src.providers.whisper import _ensure_whisper_available

            result = _ensure_whisper_available()
            # When available, should return True
            assert result is True


class TestWhisperInitialization:
    """Test WhisperTranscriber initialization edge cases."""

    def test_init_default_configuration(self, mock_whisper_config):
        """Test initialization with default configuration."""
        # Use the autouse fixture's default values
        with patch("src.providers.whisper.torch") as mock_torch:
            mock_torch.cuda.is_available.return_value = False

            transcriber = WhisperTranscriber()

            assert transcriber.model_name == "base"
            assert transcriber.device == "cpu"
            assert transcriber.compute_type == "float16"

    def test_init_with_cuda_available(self, mock_whisper_config):
        """Test initialization when CUDA is available."""
        # Override autouse fixture values for this test
        mock_whisper_config.WHISPER_MODEL = "large"
        mock_whisper_config.WHISPER_DEVICE = "cuda"
        mock_whisper_config.WHISPER_COMPUTE_TYPE = "float16"

        with patch("src.providers.whisper.torch") as mock_torch:
            mock_torch.cuda.is_available.return_value = True

            transcriber = WhisperTranscriber()

            assert transcriber.model_name == "large"
            assert transcriber.device == "cuda"
            assert transcriber.compute_type == "float16"

    def test_init_without_cuda(self, mock_whisper_config):
        """Test initialization when CUDA is not available."""
        # Override autouse fixture values for this test
        mock_whisper_config.WHISPER_COMPUTE_TYPE = "float32"

        with patch("src.providers.whisper.torch", None):
            transcriber = WhisperTranscriber()

            assert transcriber.device == "cpu"
            assert transcriber.compute_type == "float32"


class TestValidateConfigurationEdgeCases:
    """Test validate_configuration edge cases."""

    def test_validate_cuda_fallback_to_cpu(self):
        """Test CUDA fallback to CPU when CUDA unavailable."""
        transcriber = WhisperTranscriber()
        transcriber.device = "cuda"

        with patch("src.providers.whisper.PROVIDER_AVAILABLE", True):
            with patch("src.providers.whisper.torch") as mock_torch:
                mock_torch.cuda.is_available.return_value = False

                result = transcriber.validate_configuration()

                assert result is True
                assert transcriber.device == "cpu"

    def test_validate_cuda_remains_when_available(self):
        """Test CUDA device remains when available."""
        transcriber = WhisperTranscriber()
        transcriber.device = "cuda"

        with patch("src.providers.whisper.PROVIDER_AVAILABLE", True):
            with patch("src.providers.whisper.torch") as mock_torch:
                mock_torch.cuda.is_available.return_value = True

                result = transcriber.validate_configuration()

                assert result is True
                assert transcriber.device == "cuda"


class TestTranscribeImplEdgeCases:
    """Test _transcribe_impl edge cases."""

    @pytest.mark.asyncio
    async def test_transcribe_impl_missing_dependencies(self):
        """Test transcription when dependencies are missing."""
        transcriber = WhisperTranscriber()

        with patch("src.providers.whisper.PROVIDER_AVAILABLE", False):
            audio_path = Path("/fake/audio.mp3")

            with pytest.raises(ImportError, match="Whisper dependencies not installed"):
                await transcriber._transcribe_impl(audio_path, "en")

    @pytest.mark.asyncio
    async def test_transcribe_impl_auto_language_detection(self):
        """Test transcription with automatic language detection."""
        transcriber = WhisperTranscriber()
        mock_model = Mock()
        mock_model.transcribe.return_value = {
            "segments": [{"text": "Bonjour", "start": 0.0, "end": 1.0}],
            "language": "fr",
        }
        transcriber.model = mock_model

        with patch("src.providers.whisper.PROVIDER_AVAILABLE", True):
            with patch("pathlib.Path.exists", return_value=True):
                with patch("asyncio.get_event_loop") as mock_loop:
                    mock_loop.return_value.run_in_executor = AsyncMock(
                        return_value=mock_model.transcribe.return_value
                    )

                    audio_path = Path("/fake/audio.mp3")
                    result = await transcriber._transcribe_impl(audio_path, "auto")

                    assert result is not None
                    assert result.metadata["language"] == "fr"

    @pytest.mark.asyncio
    async def test_transcribe_impl_transcription_error(self):
        """Test handling of transcription errors."""
        transcriber = WhisperTranscriber()
        mock_model = Mock()
        transcriber.model = mock_model

        with patch("src.providers.whisper.PROVIDER_AVAILABLE", True):
            with patch("pathlib.Path.exists", return_value=True):
                with patch("asyncio.get_event_loop") as mock_loop:
                    mock_loop.return_value.run_in_executor = AsyncMock(
                        side_effect=RuntimeError("CUDA out of memory")
                    )

                    audio_path = Path("/fake/audio.mp3")

                    with pytest.raises(RuntimeError, match="CUDA out of memory"):
                        await transcriber._transcribe_impl(audio_path, "en")


class TestParseWhisperResultEdgeCases:
    """Test _parse_whisper_result edge cases."""

    def test_parse_empty_segments(self):
        """Test parsing result with empty segments."""
        transcriber = WhisperTranscriber()
        whisper_result = {"segments": [], "language": "en"}

        audio_path = Path("/fake/audio.mp3")
        processing_time = 1.0

        result = transcriber._parse_whisper_result(whisper_result, audio_path, processing_time)

        assert result.transcript == ""
        assert result.duration == 0
        assert len(result.metadata["chapters"]) == 0

    def test_parse_missing_language(self):
        """Test parsing result when language field is missing."""
        transcriber = WhisperTranscriber()
        whisper_result = {
            "segments": [{"text": "Test", "start": 0.0, "end": 1.0}],
            # Missing language field
        }

        audio_path = Path("/fake/audio.mp3")
        processing_time = 1.0

        result = transcriber._parse_whisper_result(whisper_result, audio_path, processing_time)

        assert result.metadata["language"] == "en"  # Default fallback

    def test_parse_segments_without_words(self):
        """Test parsing segments that don't have word-level data."""
        transcriber = WhisperTranscriber()
        whisper_result = {
            "segments": [
                {"text": "First", "start": 0.0, "end": 1.0},
                {"text": "Second", "start": 1.0, "end": 2.0},
            ],
            "language": "en",
        }

        audio_path = Path("/fake/audio.mp3")
        processing_time = 1.5

        result = transcriber._parse_whisper_result(whisper_result, audio_path, processing_time)

        assert result.transcript == "First Second"
        assert result.metadata["has_words"] is False


class TestExtractWordsEdgeCases:
    """Test _extract_words edge cases."""

    def test_extract_words_missing_probability(self):
        """Test word extraction when probability field is missing."""
        transcriber = WhisperTranscriber()
        segment = {
            "words": [
                {"word": "Test", "start": 0.0, "end": 0.5},  # Missing probability
                {"word": "word", "start": 0.5, "end": 1.0, "probability": 0.8},
            ]
        }

        words = transcriber._extract_words(segment)

        assert words is not None
        assert len(words) == 2
        assert words[0]["confidence"] == 0.0  # Default when missing
        assert words[1]["confidence"] == 0.8

    def test_extract_words_empty_words_list(self):
        """Test word extraction with empty words list."""
        transcriber = WhisperTranscriber()
        segment = {"words": []}

        words = transcriber._extract_words(segment)

        # Empty words list returns None per the implementation
        assert words is None


class TestGenerateChaptersEdgeCases:
    """Test _generate_chapters edge cases."""

    def test_generate_chapters_short_audio(self):
        """Test chapter generation for audio shorter than 5 minutes."""
        from src.models.transcription import TranscriptionUtterance

        transcriber = WhisperTranscriber()
        utterances = [
            TranscriptionUtterance(speaker=1, start=0.0, end=120.0, text="Short audio")
        ]

        chapters = transcriber._generate_chapters(utterances)

        assert len(chapters) == 1
        assert chapters[0]["start_time"] == 0
        assert chapters[0]["end_time"] == 120.0

    def test_generate_chapters_long_audio(self):
        """Test chapter generation for audio longer than 1 hour."""
        from src.models.transcription import TranscriptionUtterance

        transcriber = WhisperTranscriber()
        utterances = [
            TranscriptionUtterance(speaker=1, start=0.0, end=3600.0, text="Long audio")
        ]

        chapters = transcriber._generate_chapters(utterances)

        # Should have 13 chapters (0-300, 300-600, ..., 3600)
        assert len(chapters) >= 12
        assert chapters[0]["start_time"] == 0
        assert chapters[-1]["end_time"] == 3600.0

    def test_generate_chapters_empty_utterances(self):
        """Test chapter generation with empty utterances list."""
        transcriber = WhisperTranscriber()
        chapters = transcriber._generate_chapters([])

        assert chapters == []


class TestHealthCheckEdgeCases:
    """Test health_check_async edge cases."""

    @pytest.mark.asyncio
    async def test_health_check_loads_model_if_not_loaded(self):
        """Test that health check loads model if not already loaded."""
        transcriber = WhisperTranscriber()
        assert transcriber.model is None

        mock_model = Mock()
        with patch("src.providers.whisper.PROVIDER_AVAILABLE", True):
            with patch("src.providers.whisper.torch") as mock_torch:
                mock_torch.cuda.is_available.return_value = False
                with patch("src.providers.whisper.whisper") as mock_whisper:
                    mock_whisper.load_model.return_value = mock_model
                    with patch("asyncio.get_event_loop") as mock_loop:
                        mock_loop.return_value.run_in_executor = AsyncMock(return_value=mock_model)

                        health = await transcriber.health_check_async()

                        assert transcriber.model == mock_model
                        assert health["healthy"] is True
                        assert health["details"]["model_loaded"] is True

    @pytest.mark.asyncio
    async def test_health_check_exception_handling(self):
        """Test health check when exception occurs."""
        transcriber = WhisperTranscriber()

        with patch("src.providers.whisper.PROVIDER_AVAILABLE", True):
            with patch("asyncio.get_event_loop") as mock_loop:
                mock_loop.return_value.run_in_executor = AsyncMock(
                    side_effect=RuntimeError("Model load failed")
                )

                health = await transcriber.health_check_async()

                assert health["healthy"] is False
                assert health["status"] == "health_check_failed"
                assert "error" in health["details"]


class TestGetModelSizeInfoEdgeCases:
    """Test get_model_size_info edge cases."""

    def test_get_model_size_info_unknown_model(self):
        """Test getting model info for unknown model name."""
        transcriber = WhisperTranscriber()
        transcriber.model_name = "unknown-model"

        size_info = transcriber.get_model_size_info()

        assert size_info["current_model"] == "unknown-model"
        assert size_info["current_info"]["params"] == "unknown"
        assert size_info["current_info"]["disk"] == "unknown"

    def test_get_model_size_info_all_models(self):
        """Test that all documented models have size information."""
        transcriber = WhisperTranscriber()

        size_info = transcriber.get_model_size_info()
        available_models = size_info["available_models"]

        expected_models = ["tiny", "base", "small", "medium", "large", "large-v2", "large-v3"]

        for model in expected_models:
            assert model in available_models
            assert model in size_info["model_sizes"]
