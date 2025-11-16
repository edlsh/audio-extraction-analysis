"""Tests for NVIDIA Parakeet transcription provider."""

import asyncio
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

# Skip all tests if Parakeet dependencies are not available
torch = pytest.importorskip("torch", reason="PyTorch not installed (optional Parakeet dependency)")
pytest.importorskip("nemo", reason="NeMo not installed (optional Parakeet dependency)")

from src.models.transcription import TranscriptionResult
from src.providers.parakeet import (
    GPUManager,
    ParakeetAudioError,
    ParakeetGPUError,
    ParakeetModelCache,
    ParakeetModelError,
    ParakeetTranscriber,
)
from tests.conftest_helpers import skip_without_parakeet

# Apply markers to all tests in this module
pytestmark = [
    pytest.mark.unit,
    pytest.mark.fast,
    pytest.mark.parakeet,
    skip_without_parakeet(),
]


class TestGPUManager:
    """Test GPU resource management functionality."""

    def test_detect_best_device_cuda_available(self):
        """Test device detection when CUDA is available."""
        with patch("torch.cuda.is_available", return_value=True):
            with patch("torch.cuda.device_count", return_value=1):
                with patch("torch.randn", return_value=torch.randn(10, 10)):
                    with patch("torch.cuda.empty_cache"):
                        gpu_manager = GPUManager()
                        assert gpu_manager.device == "cuda"

    def test_detect_best_device_cuda_not_available(self):
        """Test device detection when CUDA is not available."""
        with patch("torch.cuda.is_available", return_value=False):
            gpu_manager = GPUManager()
            assert gpu_manager.device == "cpu"

    def test_detect_best_device_cuda_test_fails(self):
        """Test device detection when CUDA test fails."""
        with patch("torch.cuda.is_available", return_value=True):
            with patch("torch.cuda.device_count", return_value=1):
                with patch("torch.randn", side_effect=RuntimeError("CUDA test failed")):
                    gpu_manager = GPUManager()
                    assert gpu_manager.device == "cpu"

    def test_get_available_memory_cuda(self):
        """Test getting available GPU memory."""
        with patch("torch.cuda.is_available", return_value=True):
            with patch("torch.cuda.device_count", return_value=1):
                with patch("torch.randn", return_value=torch.randn(10, 10)):
                    with patch("torch.cuda.empty_cache"):
                        gpu_manager = GPUManager()

                        with patch("torch.cuda.get_device_properties") as mock_props:
                            mock_props.return_value.total_memory = 8 * 1024**3  # 8GB
                            with patch(
                                "torch.cuda.memory_allocated", return_value=2 * 1024**3
                            ):  # 2GB
                                with patch(
                                    "torch.cuda.memory_reserved", return_value=1 * 1024**3
                                ):  # 1GB
                                    available = gpu_manager.get_available_memory()
                                    # 8GB - 2GB - 500MB reserve = 5.5GB approximately
                                    assert available is not None
                                    assert available > 5 * 1024**3

    def test_get_available_memory_cpu(self):
        """Test getting available memory for CPU."""
        with patch("torch.cuda.is_available", return_value=False):
            gpu_manager = GPUManager()
            assert gpu_manager.get_available_memory() is None

    def test_can_allocate_model_cpu(self):
        """Test model allocation check for CPU."""
        with patch("torch.cuda.is_available", return_value=False):
            with patch("psutil.virtual_memory") as mock_mem:
                mock_mem.return_value.available = 8 * 1024**3  # 8GB
                gpu_manager = GPUManager()

                # Should allow 1GB model (needs 2GB total)
                assert gpu_manager.can_allocate_model(1 * 1024**3)

                # Should reject 5GB model (needs 10GB total)
                assert not gpu_manager.can_allocate_model(5 * 1024**3)

    def test_cleanup_gpu_memory(self):
        """Test GPU memory cleanup."""
        with patch("torch.cuda.is_available", return_value=True):
            with patch("torch.cuda.device_count", return_value=1):
                with patch("torch.randn", return_value=torch.randn(10, 10)):
                    with patch("torch.cuda.empty_cache") as mock_empty:
                        with patch("torch.cuda.synchronize") as mock_sync:
                            gpu_manager = GPUManager()
                            gpu_manager.cleanup_gpu_memory()

                            mock_empty.assert_called()
                            mock_sync.assert_called()


class TestParakeetModelCache:
    """Test model caching functionality."""

    def setup_method(self):
        """Reset cache before each test."""
        # Clear singleton instance
        ParakeetModelCache._instance = None

    @pytest.mark.asyncio
    async def test_singleton_behavior(self):
        """Test that cache behaves as singleton."""
        cache1 = ParakeetModelCache()
        cache2 = ParakeetModelCache()
        assert cache1 is cache2

    @pytest.mark.asyncio
    async def test_get_model_success(self):
        """Test successful model loading and caching."""
        mock_model = Mock()

        with patch("src.providers.parakeet.PROVIDER_AVAILABLE", True):
            with patch("src.providers.parakeet.nemo_asr") as mock_nemo:
                mock_nemo.models.ASRModel.from_pretrained = Mock(return_value=mock_model)

                cache = ParakeetModelCache()
                gpu_manager = Mock()
                gpu_manager.can_allocate_model.return_value = True

                model = await cache.get_model("test_model", gpu_manager)
                assert model == mock_model

                # Second call should return cached model
                model2 = await cache.get_model("test_model", gpu_manager)
                assert model2 == mock_model
                mock_nemo.models.ASRModel.from_pretrained.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_model_invalid_name(self):
        """Test model loading with invalid name."""
        cache = ParakeetModelCache()
        gpu_manager = Mock()

        with pytest.raises(ParakeetModelError, match="Invalid model name"):
            await cache.get_model("../etc/passwd", gpu_manager)

        with pytest.raises(ParakeetModelError, match="Invalid model name"):
            await cache.get_model("", gpu_manager)

    @pytest.mark.asyncio
    async def test_get_model_insufficient_memory(self):
        """Test model loading with insufficient memory."""
        cache = ParakeetModelCache()
        gpu_manager = Mock()
        gpu_manager.can_allocate_model.return_value = False
        gpu_manager.get_available_memory.return_value = 100 * 1024**2  # 100MB

        with pytest.raises(ParakeetGPUError, match="Insufficient memory"):
            await cache.get_model("test_model", gpu_manager)

    @pytest.mark.asyncio
    async def test_get_model_timeout(self):
        """Test model loading timeout."""
        with patch("src.providers.parakeet.PROVIDER_AVAILABLE", True):
            cache = ParakeetModelCache()
            cache._model_load_timeout = 0.1  # Very short timeout

            gpu_manager = Mock()
            gpu_manager.can_allocate_model.return_value = True

            # Mock slow model loading
            async def slow_load(*args):
                await asyncio.sleep(0.2)
                return Mock()

            with patch.object(cache, "_load_model_async", side_effect=slow_load):
                with pytest.raises(ParakeetModelError, match="timed out"):
                    await cache.get_model("test_model", gpu_manager)

    def test_estimate_model_size(self):
        """Test model size estimation."""
        cache = ParakeetModelCache()

        # Known model size
        size = cache._estimate_model_size("stt_en_conformer_ctc_large")
        assert size == 500 * 1024**2

        # Unknown model - should return default
        size = cache._estimate_model_size("unknown_model")
        assert size == 600 * 1024**2

    def test_is_valid_model_name(self):
        """Test model name validation."""
        cache = ParakeetModelCache()

        assert cache._is_valid_model_name("stt_en_conformer_ctc_large")
        assert cache._is_valid_model_name("model-name_v1.0")
        assert not cache._is_valid_model_name("../etc/passwd")
        assert not cache._is_valid_model_name("model with spaces")
        assert not cache._is_valid_model_name("")
        assert not cache._is_valid_model_name(None)
        assert not cache._is_valid_model_name("a" * 300)  # Too long


class TestParakeetTranscriber:
    """Test Parakeet transcription provider functionality."""

    @pytest.fixture
    def parakeet_transcriber(self):
        """Create a ParakeetTranscriber instance for testing."""
        with patch("src.providers.parakeet.GPUManager"):
            with patch("src.providers.parakeet.ParakeetModelCache"):
                return ParakeetTranscriber()

    @pytest.fixture
    def mock_audio_file(self):
        """Create a temporary mock audio file."""
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            yield Path(f.name)
        # Cleanup
        try:
            os.unlink(f.name)
        except FileNotFoundError:
            pass

    def test_validate_configuration_with_dependencies(self, parakeet_transcriber):
        """Test configuration validation when dependencies are available."""
        with patch("src.providers.parakeet.PROVIDER_AVAILABLE", True):
            with patch("src.providers.parakeet.PARAKEET_MODELS", {"test_model": {}}):
                parakeet_transcriber.model_name = "test_model"
                parakeet_transcriber.gpu_manager.device = "cuda"
                parakeet_transcriber.gpu_manager.can_allocate_model = Mock(return_value=True)

                with patch("torch.cuda.is_available", return_value=True):
                    with patch("torch.randn", return_value=torch.randn(10, 10)):
                        with patch("torch.cuda.empty_cache"):
                            with patch("pathlib.Path.mkdir"):
                                with patch("pathlib.Path.exists", return_value=True):
                                    with patch("pathlib.Path.is_dir", return_value=True):
                                        with patch("os.access", return_value=True):
                                            assert (
                                                parakeet_transcriber.validate_configuration()
                                                is True
                                            )

    def test_validate_configuration_without_dependencies(self, parakeet_transcriber):
        """Test configuration validation when dependencies are missing."""
        with patch("src.providers.parakeet.PROVIDER_AVAILABLE", False):
            assert parakeet_transcriber.validate_configuration() is False

    def test_validate_configuration_unsupported_model(self, parakeet_transcriber):
        """Test configuration validation with unsupported model."""
        with patch("src.providers.parakeet.PROVIDER_AVAILABLE", True):
            parakeet_transcriber.model_name = "unsupported_model"
            assert parakeet_transcriber.validate_configuration() is False

    def test_validate_configuration_invalid_parameters(self, parakeet_transcriber):
        """Test configuration validation with invalid parameters."""
        with patch("src.providers.parakeet.PROVIDER_AVAILABLE", True):
            with patch("src.providers.parakeet.PARAKEET_MODELS", {"test_model": {}}):
                parakeet_transcriber.model_name = "test_model"

                # Test invalid batch size
                parakeet_transcriber.batch_size = 0
                assert parakeet_transcriber.validate_configuration() is False

                parakeet_transcriber.batch_size = 100
                assert parakeet_transcriber.validate_configuration() is False

                # Reset to valid value
                parakeet_transcriber.batch_size = 8

                # Test invalid beam size
                parakeet_transcriber.beam_size = 0
                assert parakeet_transcriber.validate_configuration() is False

    def test_validate_configuration_insufficient_memory(self, parakeet_transcriber):
        """Test configuration validation with insufficient memory."""
        with patch("src.providers.parakeet.PROVIDER_AVAILABLE", True):
            with patch("src.providers.parakeet.PARAKEET_MODELS", {"test_model": {}}):
                parakeet_transcriber.model_name = "test_model"
                parakeet_transcriber.gpu_manager.can_allocate_model = Mock(return_value=False)
                parakeet_transcriber.gpu_manager.get_available_memory = Mock(
                    return_value=100 * 1024**2
                )

                assert parakeet_transcriber.validate_configuration() is False

    def test_get_provider_name(self, parakeet_transcriber):
        """Test getting provider name."""
        parakeet_transcriber.model_name = "stt_en_conformer_ctc_large"
        assert parakeet_transcriber.get_provider_name() == "NVIDIA Parakeet (ctc)"

    def test_get_supported_features(self, parakeet_transcriber):
        """Test getting supported features."""
        features = parakeet_transcriber.get_supported_features()
        assert "timestamps" in features
        assert "speaker_diarization" in features
        assert "language_detection" in features
        assert "punctuation_restoration" in features
        assert "local_processing" in features
        assert "offline_capable" in features
        assert "gpu_acceleration" in features

    @pytest.mark.asyncio
    async def test_preprocess_audio_success(self, parakeet_transcriber, mock_audio_file):
        """Test successful audio preprocessing."""
        # Create a mock tensor that behaves like a real tensor
        mock_waveform = torch.randn(1, 16000)  # 1 channel, 1 second at 16kHz
        mock_sample_rate = 16000

        with patch(
            "src.providers.parakeet.torchaudio.load", return_value=(mock_waveform, mock_sample_rate)
        ):
            with patch("pathlib.Path.stat") as mock_stat:
                mock_stat.return_value.st_size = 1000000  # 1MB
                result_tensor, duration = await parakeet_transcriber._preprocess_audio(
                    mock_audio_file
                )
                assert isinstance(result_tensor, torch.Tensor)
                assert isinstance(duration, float)
                assert duration > 0
                # Check that it's a 1D tensor (squeezed)
                assert len(result_tensor.shape) == 1

    @pytest.mark.asyncio
    async def test_preprocess_audio_file_not_found(self, parakeet_transcriber):
        """Test audio preprocessing with non-existent file."""
        non_existent_path = Path("/nonexistent/audio.wav")
        with pytest.raises(ParakeetAudioError, match="Audio file not found"):
            await parakeet_transcriber._preprocess_audio(non_existent_path)

    @pytest.mark.asyncio
    async def test_preprocess_audio_unsafe_path(self, parakeet_transcriber):
        """Test audio preprocessing with unsafe file path."""
        unsafe_path = Path("../../../etc/passwd.wav")
        with pytest.raises(ParakeetAudioError, match="Unsafe file path"):
            await parakeet_transcriber._preprocess_audio(unsafe_path)

    @pytest.mark.asyncio
    async def test_preprocess_audio_file_too_large(self, parakeet_transcriber, mock_audio_file):
        """Test audio preprocessing with oversized file."""
        with patch("pathlib.Path.stat") as mock_stat:
            mock_stat.return_value.st_size = 600 * 1024 * 1024  # 600MB
            with pytest.raises(ParakeetAudioError, match="too large"):
                await parakeet_transcriber._preprocess_audio(mock_audio_file)

    @pytest.mark.asyncio
    async def test_preprocess_audio_silent_audio(self, parakeet_transcriber, mock_audio_file):
        """Test audio preprocessing with silent audio."""
        # Create silent waveform
        mock_waveform = torch.zeros(1, 16000)  # Silent audio
        mock_sample_rate = 16000

        with patch(
            "src.providers.parakeet.torchaudio.load", return_value=(mock_waveform, mock_sample_rate)
        ):
            with patch("pathlib.Path.stat") as mock_stat:
                mock_stat.return_value.st_size = 1000000  # 1MB
                result_tensor, duration = await parakeet_transcriber._preprocess_audio(
                    mock_audio_file
                )

                # Should handle silent audio gracefully
                assert isinstance(result_tensor, torch.Tensor)
                assert duration > 0
                # Silent audio should be replaced with minimal noise
                assert torch.max(torch.abs(result_tensor)) > 0

    @pytest.mark.asyncio
    async def test_transcribe_impl_success(self, parakeet_transcriber, mock_audio_file):
        """Test successful transcription implementation."""
        # Mock dependencies
        mock_model = Mock()
        mock_model.transcribe.return_value = ["Test transcription"]
        mock_model.to.return_value = mock_model

        with patch("src.providers.parakeet.PROVIDER_AVAILABLE", True):
            # Mock model cache
            mock_cache = Mock()
            mock_cache.get_model = AsyncMock(return_value=mock_model)

            with patch("src.providers.parakeet.ParakeetModelCache", return_value=mock_cache):
                # Mock GPU manager
                parakeet_transcriber.gpu_manager.device = "cuda"
                parakeet_transcriber.gpu_manager.get_available_memory = Mock(
                    return_value=1024**3
                )  # 1GB

                # Mock the preprocessing to return a proper tensor and duration
                mock_tensor = torch.randn(16000)  # 1 second of audio
                with patch.object(
                    parakeet_transcriber,
                    "_preprocess_audio",
                    AsyncMock(return_value=(mock_tensor, 1.0)),
                ):
                    with patch.object(
                        parakeet_transcriber,
                        "_run_transcription",
                        AsyncMock(return_value=["Test transcription"]),
                    ):
                        result = await parakeet_transcriber._transcribe_impl(mock_audio_file, "en")

                        assert result is not None
                        assert isinstance(result, TranscriptionResult)
                        assert result.transcript == "Test transcription"
                        assert result.duration == 1.0

    @pytest.mark.asyncio
    async def test_transcribe_impl_file_not_found(self, parakeet_transcriber):
        """Test transcription with non-existent file."""
        audio_path = Path("/nonexistent/audio.mp3")

        with patch("src.providers.parakeet.PROVIDER_AVAILABLE", True):
            with pytest.raises(FileNotFoundError):
                await parakeet_transcriber._transcribe_impl(audio_path, "en")

    def test_parse_parakeet_result(self, parakeet_transcriber):
        """Test parsing Parakeet result into TranscriptionResult."""
        parakeet_result = ["Test transcription result"]
        audio_path = Path("/fake/audio.mp3")
        processing_time = 5.0
        audio_duration = 10.0

        result = parakeet_transcriber._parse_parakeet_result(
            parakeet_result, audio_path, processing_time, audio_duration
        )

        assert isinstance(result, TranscriptionResult)
        assert result.audio_file == str(audio_path)
        assert result.metadata["processing_time_seconds"] == 5.0
        assert result.metadata["audio_duration_seconds"] == 10.0
        assert result.transcript == "Test transcription result"
        assert result.duration == 10.0
        assert len(result.utterances) == 1
        assert result.utterances[0].start == 0.0
        assert result.utterances[0].end == 10.0

    def test_parse_parakeet_result_empty(self, parakeet_transcriber):
        """Test parsing empty Parakeet result."""
        parakeet_result = []
        audio_path = Path("/fake/audio.mp3")
        processing_time = 5.0
        audio_duration = 10.0

        result = parakeet_transcriber._parse_parakeet_result(
            parakeet_result, audio_path, processing_time, audio_duration
        )

        assert isinstance(result, TranscriptionResult)
        assert result.transcript == ""
        assert len(result.utterances) == 0

    @pytest.mark.asyncio
    async def test_health_check_async_success(self, parakeet_transcriber):
        """Test successful health check."""
        with patch("src.providers.parakeet.PROVIDER_AVAILABLE", True):
            mock_cache = Mock()
            mock_cache.get_model = AsyncMock(return_value=Mock())

            with patch("src.providers.parakeet.ParakeetModelCache", return_value=mock_cache):
                with patch("torch.cuda.is_available", return_value=True):
                    health = await parakeet_transcriber.health_check_async()

                    assert health["healthy"] is True
                    assert health["status"] == "ready"
                    assert "model_loaded" in health["details"]

    @pytest.mark.asyncio
    async def test_health_check_async_no_dependencies(self, parakeet_transcriber):
        """Test health check without dependencies."""
        with patch("src.providers.parakeet.PROVIDER_AVAILABLE", False):
            health = await parakeet_transcriber.health_check_async()

            assert health["healthy"] is False
            assert health["status"] == "dependencies_missing"

    def test_is_safe_path_valid_paths(self, parakeet_transcriber):
        """Test safe path validation with valid paths."""
        # Mock resolve to return safe paths
        with patch("pathlib.Path.resolve") as mock_resolve:
            mock_resolve.return_value = Path("/tmp/audio.wav")
            assert parakeet_transcriber._is_safe_path(Path("/tmp/audio.wav"))

            mock_resolve.return_value = Path("/home/user/audio.mp3")
            assert parakeet_transcriber._is_safe_path(Path("audio.mp3"))

            mock_resolve.return_value = Path("/home/user/data/test.flac")
            assert parakeet_transcriber._is_safe_path(Path("./data/test.flac"))

    def test_is_safe_path_invalid_paths(self, parakeet_transcriber):
        """Test safe path validation with invalid paths."""
        assert not parakeet_transcriber._is_safe_path(Path("../../../etc/passwd"))
        assert not parakeet_transcriber._is_safe_path(Path("../passwd.wav"))  # Path traversal
        assert not parakeet_transcriber._is_safe_path(Path("audio.exe"))  # Wrong extension
        assert not parakeet_transcriber._is_safe_path(Path("script.sh"))  # Wrong extension

        # Test dangerous system paths - mock resolve to simulate actual system paths
        with patch("pathlib.Path.resolve") as mock_resolve:
            mock_resolve.return_value = Path("/etc/shadow.wav")
            assert not parakeet_transcriber._is_safe_path(Path("shadow.wav"))


class TestParakeetTranscriberEdgeCases:
    """Test edge cases and error conditions."""

    @pytest.fixture
    def transcriber(self):
        with patch("src.providers.parakeet.GPUManager"):
            with patch("src.providers.parakeet.ParakeetModelCache"):
                return ParakeetTranscriber()

    @pytest.mark.asyncio
    async def test_preprocess_audio_corrupted_file(self, transcriber):
        """Test handling of corrupted audio files."""
        with tempfile.NamedTemporaryFile(suffix=".wav") as f:
            audio_path = Path(f.name)

            with patch("pathlib.Path.stat") as mock_stat:
                mock_stat.return_value.st_size = 1000
                with patch(
                    "src.providers.parakeet.torchaudio.load",
                    side_effect=RuntimeError("Corrupted file"),
                ):
                    with patch("importlib.import_module", side_effect=ImportError("No librosa")):
                        with pytest.raises(ParakeetAudioError, match="Failed to load audio file"):
                            await transcriber._preprocess_audio(audio_path)

    def test_configuration_validation_edge_cases(self, transcriber):
        """Test configuration validation edge cases."""
        with patch("src.providers.parakeet.PROVIDER_AVAILABLE", True):
            with patch("src.providers.parakeet.PARAKEET_MODELS", {"test_model": {}}):
                # Test with None model name
                transcriber.model_name = None
                assert transcriber.validate_configuration() is False

                # Test with empty string model name
                transcriber.model_name = ""
                assert transcriber.validate_configuration() is False

                # Test with extremely long model name
                transcriber.model_name = "a" * 300
                assert transcriber.validate_configuration() is False
