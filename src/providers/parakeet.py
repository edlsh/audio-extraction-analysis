"""NVIDIA Parakeet STT transcription service."""

from __future__ import annotations

import asyncio
import gc
import logging
import os
import tempfile
import time
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import TYPE_CHECKING, Any

from ..models.transcription import TranscriptionResult, TranscriptionUtterance

if TYPE_CHECKING:
    from ..utils.retry import RetryConfig
from .base import BaseTranscriptionProvider, CircuitBreakerConfig

logger = logging.getLogger(__name__)

# =====================================================================
# Lazy dependency resolution
# =====================================================================

# PyTorch availability
try:
    import torch

    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    logger.warning("PyTorch not available. GPU features will be disabled.")

# NeMo availability
nemo_asr = None
NEMO_AVAILABLE = None


def _ensure_nemo() -> bool:
    """Ensure NeMo is available for model loading."""
    global NEMO_AVAILABLE, nemo_asr
    if NEMO_AVAILABLE is not None:
        return NEMO_AVAILABLE
    try:
        import nemo.collections.asr as _nemo_asr

        nemo_asr = _nemo_asr
        NEMO_AVAILABLE = True
    except Exception:
        NEMO_AVAILABLE = False
        logger.warning("NeMo toolkit not available. Parakeet features will be disabled.")
    return NEMO_AVAILABLE


# Audio processing libraries
try:
    import librosa
    import soundfile as sf

    AUDIO_LIBS_AVAILABLE = True
except ImportError:
    AUDIO_LIBS_AVAILABLE = False
    logger.warning("Audio processing libraries (librosa, soundfile) not available")


# =====================================================================
# Custom exceptions
# =====================================================================


class ParakeetError(Exception):
    """Base exception for Parakeet-specific errors."""

    pass


class ParakeetAudioError(Exception):
    """Raised when audio processing fails."""

    pass


class ParakeetGPUError(Exception):
    """Raised when GPU operations fail."""

    pass


class ParakeetModelError(Exception):
    """Raised when model loading fails."""

    pass


# =====================================================================
# Model definitions
# =====================================================================

PARAKEET_MODELS = {
    "stt_en_conformer_ctc_large": {
        "type": "ctc",
        "accuracy": "high",
        "speed": "fast",
        "memory": "4GB",
        "languages": ["en"],
    },
    "stt_en_conformer_transducer_large": {
        "type": "rnnt",
        "accuracy": "highest",
        "speed": "medium",
        "memory": "6GB",
        "languages": ["en"],
    },
    "stt_en_fastconformer_ctc_large": {
        "type": "ctc",
        "accuracy": "medium",
        "speed": "fastest",
        "memory": "2GB",
        "languages": ["en"],
    },
}


# =====================================================================
# GPU Management
# =====================================================================


class GPUManager:
    """Manages GPU resources for Parakeet models."""

    def __init__(self) -> None:
        """Initialize GPU manager with device detection."""
        self._device = None
        self._device_id = None
        if TORCH_AVAILABLE:
            self._device = self._detect_best_device()
            if self._device.startswith("cuda"):
                self._device_id = int(self._device.split(":")[-1]) if ":" in self._device else 0

    @property
    def device(self) -> str:
        """Get the current device string (e.g., 'cuda:0', 'cpu')."""
        if not self._device:
            return "cpu"
        return self._device

    @property
    def device_id(self) -> int | None:
        """Get the CUDA device ID if using GPU."""
        return self._device_id

    def _detect_best_device(self) -> str:
        """Detect the best available device for model execution.

        Returns:
            Device string (e.g., 'cuda:0', 'mps', 'cpu')
        """
        if not TORCH_AVAILABLE:
            return "cpu"

        try:
            cuda_device = self._detect_cuda_device()
            if cuda_device:
                return cuda_device

            if self._is_mps_available():
                logger.info("Using Apple Metal Performance Shaders (MPS)")
                return "mps"
        except Exception as e:
            logger.warning(f"Error detecting GPU device: {e}")

        return "cpu"

    def _detect_cuda_device(self) -> str | None:
        """Detect best CUDA device. Returns device string or None."""
        if not torch.cuda.is_available():
            return None

        device_count = torch.cuda.device_count()
        if device_count == 0:
            return None

        best_device = 0
        max_free_memory = 0

        for i in range(device_count):
            free_memory = torch.cuda.mem_get_info(i)[0]
            if free_memory > max_free_memory:
                max_free_memory = free_memory
                best_device = i

        logger.info(
            f"Selected CUDA device {best_device} with {max_free_memory / 1e9:.2f}GB free memory"
        )
        return f"cuda:{best_device}"

    @staticmethod
    def _is_mps_available() -> bool:
        """Check if Apple MPS is available."""
        return hasattr(torch.backends, "mps") and torch.backends.mps.is_available()

    def get_available_memory(self) -> int | None:
        """Get available memory on current device in bytes.

        Returns:
            Available memory in bytes, or None if cannot be determined
        """
        if not TORCH_AVAILABLE:
            return None

        try:
            if self._device and self._device.startswith("cuda"):
                if self._device_id is not None:
                    free, _total = torch.cuda.mem_get_info(self._device_id)
                    return free
            elif self._device == "mps":
                # MPS doesn't provide direct memory query
                # Return a conservative estimate
                return 4 * 1024 * 1024 * 1024  # 4GB
        except Exception as e:
            logger.warning(f"Could not get available memory: {e}")

        return None

    def can_allocate_model(self, estimated_model_size: int) -> bool:
        """Check if there's enough memory to allocate a model.

        Args:
            estimated_model_size: Estimated model size in bytes

        Returns:
            True if model can likely be allocated
        """
        available = self.get_available_memory()
        if available is None:
            # If we can't determine memory, optimistically return True
            # The actual allocation will fail if insufficient
            return True

        # Leave 500MB buffer for operations
        buffer = 500 * 1024 * 1024
        return available > (estimated_model_size + buffer)

    def cleanup_gpu_memory(self) -> None:
        """Force GPU memory cleanup."""
        if not TORCH_AVAILABLE:
            return

        try:
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                logger.debug("GPU memory cache cleared")
        except Exception as e:
            logger.warning(f"Error cleaning up GPU memory: {e}")


# =====================================================================
# Audio Preprocessing
# =====================================================================


class AudioPreprocessor:
    """Handles audio preprocessing for Parakeet models."""

    # Parakeet models typically expect 16kHz audio
    TARGET_SAMPLE_RATE = 16000

    @classmethod
    def preprocess_audio(cls, audio_path: Path) -> tuple[Path | None, float | None]:
        """Preprocess audio file for Parakeet transcription.

        Converts audio to 16kHz mono WAV format if needed.

        Args:
            audio_path: Path to input audio file

        Returns:
            Tuple of (processed_audio_path, duration_seconds)
            Returns (None, None) if preprocessing fails
        """
        if not AUDIO_LIBS_AVAILABLE:
            logger.error("Audio processing libraries not available")
            return None, None

        try:
            # Load audio
            audio_data, sample_rate = librosa.load(
                str(audio_path),
                sr=None,  # Preserve original sample rate initially
                mono=True,  # Convert to mono
            )

            # Calculate duration
            duration = len(audio_data) / sample_rate

            # Resample if needed
            if sample_rate != cls.TARGET_SAMPLE_RATE:
                logger.info(f"Resampling audio from {sample_rate}Hz to {cls.TARGET_SAMPLE_RATE}Hz")
                audio_data = librosa.resample(
                    audio_data, orig_sr=sample_rate, target_sr=cls.TARGET_SAMPLE_RATE
                )
                sample_rate = cls.TARGET_SAMPLE_RATE

            # Check if we need to save preprocessed audio
            needs_preprocessing = (
                audio_path.suffix.lower() != ".wav" or sample_rate != cls.TARGET_SAMPLE_RATE
            )

            if needs_preprocessing:
                # Create temporary WAV file
                with tempfile.NamedTemporaryFile(
                    suffix=".wav", delete=False, dir=audio_path.parent
                ) as tmp_file:
                    output_path = Path(tmp_file.name)

                # Save preprocessed audio
                sf.write(
                    str(output_path),
                    audio_data,
                    cls.TARGET_SAMPLE_RATE,
                    subtype="PCM_16",  # 16-bit PCM
                )

                logger.info(f"Preprocessed audio saved to {output_path}")
                return output_path, duration
            else:
                # Audio is already in correct format
                return audio_path, duration

        except Exception as e:
            logger.error(f"Audio preprocessing failed: {e}")
            raise ParakeetAudioError(f"Failed to preprocess audio: {e}")

    @classmethod
    def validate_audio_file(cls, audio_path: Path) -> bool:
        """Validate that audio file can be processed.

        Args:
            audio_path: Path to audio file

        Returns:
            True if file is valid and can be processed
        """
        if not audio_path.exists():
            logger.error(f"Audio file not found: {audio_path}")
            return False

        if not audio_path.is_file():
            logger.error(f"Path is not a file: {audio_path}")
            return False

        # Check file size (max 2GB)
        max_size = 2 * 1024 * 1024 * 1024
        if audio_path.stat().st_size > max_size:
            logger.error(f"Audio file too large: {audio_path.stat().st_size} bytes")
            return False

        # Check if we can read the file
        if not AUDIO_LIBS_AVAILABLE:
            logger.warning("Cannot validate audio format without librosa/soundfile")
            # Optimistically return True - actual processing will fail if invalid
            return True

        try:
            # Try to get audio info
            info = sf.info(str(audio_path))
            logger.debug(
                f"Audio file info: duration={info.duration}s, "
                f"samplerate={info.samplerate}Hz, channels={info.channels}"
            )
            return True
        except Exception as e:
            logger.error(f"Invalid audio file {audio_path}: {e}")
            return False

    @classmethod
    def cleanup_temp_file(cls, temp_path: Path | None) -> None:
        """Clean up temporary audio file.

        Args:
            temp_path: Path to temporary file to delete
        """
        if temp_path and temp_path.exists():
            try:
                temp_path.unlink()
                logger.debug(f"Cleaned up temporary file: {temp_path}")
            except Exception as e:
                logger.warning(f"Failed to clean up temp file {temp_path}: {e}")


# =====================================================================
# Model Caching
# =====================================================================


class ParakeetModelCache:
    """Singleton cache for Parakeet ASR models.

    Implements LRU caching with GPU memory management.
    """

    _instance = None
    _lock = Lock()

    def __new__(cls) -> ParakeetModelCache:
        """Ensure singleton pattern."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def _initialize(self) -> None:
        """Initialize the cache (called once)."""
        if self._initialized:
            return

        self._models = {}  # model_name -> (model, last_used_time)
        self._model_sizes = {}  # model_name -> size_in_bytes
        self._max_cache_size = 3  # Maximum number of models to cache
        self._cache_lock = Lock()
        self._loading_locks = {}  # Per-model loading locks
        self._gpu_manager = GPUManager()
        self._initialized = True

        logger.info(f"ParakeetModelCache initialized with device: {self._gpu_manager.device}")

    def __init__(self) -> None:
        """Initialize cache if not already done."""
        if not hasattr(self, "_initialized") or not self._initialized:
            self._initialize()

    def get_model(self, model_name: str, force_reload: bool = False) -> Any | None:
        """Get a model from cache or load it.

        Args:
            model_name: Name of the Parakeet model
            force_reload: Force reload even if cached

        Returns:
            Loaded model or None if loading fails
        """
        if not _ensure_nemo():
            logger.error("NeMo toolkit not available")
            return None

        loading_lock = self._get_or_create_loading_lock(model_name)

        with loading_lock:
            cached = self._get_cached_model(model_name, force_reload)
            if cached is not None:
                return cached

            return self._load_and_cache_model(model_name)

    def _get_or_create_loading_lock(self, model_name: str) -> Lock:
        """Get or create a loading lock for a specific model."""
        with self._cache_lock:
            if model_name not in self._loading_locks:
                self._loading_locks[model_name] = Lock()
            return self._loading_locks[model_name]

    def _get_cached_model(self, model_name: str, force_reload: bool) -> Any | None:
        """Check cache for model. Returns model if found, None otherwise."""
        with self._cache_lock:
            if not force_reload and model_name in self._models:
                model, _ = self._models[model_name]
                self._models[model_name] = (model, time.time())
                logger.debug(f"Model {model_name} retrieved from cache")
                return model
        return None

    def _load_and_cache_model(self, model_name: str) -> Any | None:
        """Load model and add to cache."""
        try:
            logger.info(f"Loading model {model_name}...")
            model = self._load_model_sync(model_name)

            if model is not None:
                model_size = self._estimate_model_size(model_name)
                self._ensure_gpu_space(model_name, model_size)
                self._add_to_cache(model_name, model, model_size)

            return model

        except Exception as e:
            logger.error(f"Failed to load model {model_name}: {e}")
            raise ParakeetModelError(f"Failed to load model {model_name}: {e}")

    def _ensure_gpu_space(self, model_name: str, model_size: int) -> None:
        """Ensure GPU has space for model, evicting if necessary."""
        if not self._gpu_manager.can_allocate_model(model_size):
            logger.warning(f"Insufficient GPU memory for model {model_name}")
            self._evict_models_for_space(model_size, self._gpu_manager)

    def _add_to_cache(self, model_name: str, model: Any, model_size: int) -> None:
        """Add model to cache, enforcing size limits."""
        with self._cache_lock:
            self._enforce_cache_limit()
            self._models[model_name] = (model, time.time())
            self._model_sizes[model_name] = model_size
            logger.info(f"Model {model_name} added to cache")

    def _enforce_cache_limit(self) -> None:
        """Remove LRU model if cache is at capacity. Must hold _cache_lock."""
        if len(self._models) >= self._max_cache_size:
            lru_model = min(self._models.items(), key=lambda x: x[1][1])
            del self._models[lru_model[0]]
            if lru_model[0] in self._model_sizes:
                del self._model_sizes[lru_model[0]]
            logger.info(f"Evicted model {lru_model[0]} from cache (LRU)")

    async def get_model_async(self, model_name: str, force_reload: bool = False) -> Any | None:
        """Async wrapper for get_model.

        Args:
            model_name: Name of the Parakeet model
            force_reload: Force reload even if cached

        Returns:
            Loaded model or None if loading fails
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.get_model, model_name, force_reload)

    def _load_model_sync(self, model_name: str) -> Any:
        """Synchronously load a Parakeet model.

        Args:
            model_name: Name of the model to load

        Returns:
            Loaded model
        """
        if not self._is_valid_model_name(model_name):
            raise ValueError(f"Invalid model name: {model_name}")

        try:
            if not _ensure_nemo():
                raise RuntimeError("NeMo not available")
            model = nemo_asr.models.ASRModel.from_pretrained(model_name)
            if TORCH_AVAILABLE and self._gpu_manager.device != "cpu":
                model = model.to(self._gpu_manager.device)
            model.eval()
            return model
        except Exception as e:
            logger.error(f"Error loading model {model_name}: {e}")
            raise

    def _is_valid_model_name(self, model_name: str) -> bool:
        """Validate model name format.

        Args:
            model_name: Model name to validate

        Returns:
            True if valid
        """
        # Add validation logic for Parakeet model names
        # This is a basic check - expand as needed
        return bool(model_name and isinstance(model_name, str))

    def _estimate_model_size(self, model_name: str) -> int:
        """Estimate model size in bytes.

        Args:
            model_name: Name of the model

        Returns:
            Estimated size in bytes
        """
        # Rough estimates for common Parakeet models
        size_map = {
            "stt_en_fastconformer_transducer_large": 600 * 1024 * 1024,  # 600MB
            "stt_en_conformer_transducer_large": 500 * 1024 * 1024,  # 500MB
            "stt_en_conformer_transducer_medium": 300 * 1024 * 1024,  # 300MB
            "stt_en_conformer_transducer_small": 150 * 1024 * 1024,  # 150MB
        }

        # Default to 400MB for unknown models
        return size_map.get(model_name, 400 * 1024 * 1024)

    def _evict_models_for_space(self, required_size: int, gpu_manager: GPUManager) -> None:
        """Evict models to free up space.

        Args:
            required_size: Required size in bytes
            gpu_manager: GPU manager instance
        """
        with self._cache_lock:
            if not self._models:
                return

            # Sort models by last used time (oldest first)
            sorted_models = sorted(self._models.items(), key=lambda x: x[1][1])

            freed_space = 0
            models_to_evict = []

            for model_name, (_model, _last_used) in sorted_models:
                if freed_space >= required_size:
                    break

                model_size = self._model_sizes.get(model_name, 0)
                models_to_evict.append(model_name)
                freed_space += model_size

            # Evict models
            for model_name in models_to_evict:
                del self._models[model_name]
                if model_name in self._model_sizes:
                    del self._model_sizes[model_name]
                logger.info(f"Evicted model {model_name} to free GPU memory")

            # Clean up GPU memory
            if models_to_evict:
                gpu_manager.cleanup_gpu_memory()

    def get_cache_stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dictionary with cache stats
        """
        with self._cache_lock:
            total_size = sum(self._model_sizes.values())
            return {
                "cached_models": len(self._models),
                "model_names": list(self._models.keys()),
                "total_size_mb": total_size / (1024 * 1024),
                "max_cache_size": self._max_cache_size,
                "device": self._gpu_manager.device if hasattr(self, "_gpu_manager") else "unknown",
            }


# =====================================================================
# Metrics Tracking
# =====================================================================


class ParakeetMetrics:
    """Tracks metrics for Parakeet transcriptions."""

    def __init__(self) -> None:
        self.total_duration = 0.0
        self.total_processing_time = 0.0

    def log_transcription(self, duration: float, audio_length: float) -> None:
        """Log a transcription event.

        Args:
            duration: Processing time in seconds
            audio_length: Audio length in seconds
        """
        self.total_duration += audio_length
        self.total_processing_time += duration

    def get_rtf(self) -> float:
        """Get real-time factor (processing time / audio time).

        Returns:
            RTF value, or 0.0 if no data
        """
        if self.total_duration > 0:
            return self.total_processing_time / self.total_duration
        return 0.0


# =====================================================================
# Main Transcriber
# =====================================================================


class ParakeetTranscriber(BaseTranscriptionProvider):
    """NVIDIA Parakeet STT transcription service with CTC/RNN-T model support."""

    def __init__(
        self,
        api_key: str | None = None,
        circuit_config: CircuitBreakerConfig | None = None,
        retry_config: RetryConfig | None = None,
    ) -> None:
        """Initialize the Parakeet transcriber.

        Args:
            api_key: Optional API key (not used for local Parakeet)
            circuit_config: Circuit breaker configuration
            retry_config: Retry configuration
        """
        super().__init__(api_key, circuit_config, retry_config)
        self.gpu_manager = GPUManager()
        self.model_cache = ParakeetModelCache()
        self.audio_preprocessor = AudioPreprocessor()
        self.metrics = ParakeetMetrics()

        # Configuration from environment
        self.model_name = os.getenv("PARAKEET_MODEL", "stt_en_conformer_ctc_large")
        self.batch_size = int(os.getenv("PARAKEET_BATCH_SIZE", "8"))
        self.beam_size = int(os.getenv("PARAKEET_BEAM_SIZE", "10"))
        self.use_fp16 = os.getenv("PARAKEET_USE_FP16", "true").lower() == "true"
        self.chunk_length = int(os.getenv("PARAKEET_CHUNK_LENGTH", "30"))
        self.model_cache_dir = os.getenv("PARAKEET_MODEL_CACHE_DIR", "~/.cache/parakeet")

    def _validate_dependencies(self) -> bool:
        """Check required dependencies are available."""
        if not NEMO_AVAILABLE:
            logger.error(
                'NeMo toolkit not installed. Install with: uv add "nemo-toolkit[asr]@1.20.0" --extra parakeet'
            )
            return False
        if not TORCH_AVAILABLE:
            logger.error("PyTorch not installed")
            return False
        return True

    def _validate_model_name(self) -> bool:
        """Validate model name format and availability."""
        if not self.model_name or not isinstance(self.model_name, str):
            logger.error("Invalid model name format")
            return False
        if len(self.model_name) > 200:
            logger.error(f"Model name too long: {len(self.model_name)}")
            return False
        if self.model_name not in PARAKEET_MODELS:
            logger.error(f"Unsupported Parakeet model: {self.model_name}")
            return False
        return True

    def _validate_parameters(self) -> bool:
        """Validate configuration parameters."""
        if self.batch_size <= 0 or self.batch_size > 32:
            logger.error(f"Invalid batch size: {self.batch_size}")
            return False
        if self.beam_size <= 0 or self.beam_size > 50:
            logger.error(f"Invalid beam size: {self.beam_size}")
            return False
        if self.chunk_length <= 0 or self.chunk_length > 300:
            logger.error(f"Invalid chunk length: {self.chunk_length}")
            return False
        return True

    def _validate_gpu(self) -> bool:
        """Validate GPU availability and functionality."""
        device = self.gpu_manager.device
        if not device.startswith("cuda"):
            return True

        import torch

        if not torch.cuda.is_available():
            logger.error("CUDA not available but required by GPU manager")
            return False

        try:
            torch.cuda.empty_cache()
            test_tensor = torch.randn(10, 10, device="cuda")
            del test_tensor
            torch.cuda.empty_cache()
        except Exception as e:
            logger.error(f"GPU test failed: {e}")
            return False
        return True

    def _validate_cache_dir(self) -> bool:
        """Validate model cache directory."""
        try:
            cache_dir = Path(self.model_cache_dir).expanduser()
            if not cache_dir.exists():
                cache_dir.mkdir(parents=True, exist_ok=True)
            if not cache_dir.is_dir() or not os.access(cache_dir, os.W_OK):
                logger.error(f"Model cache directory not writable: {cache_dir}")
                return False
        except Exception as e:
            logger.error(f"Model cache directory validation failed: {e}")
            return False
        return True

    def _validate_memory(self) -> bool:
        """Check memory requirements for the model."""
        estimated_size = self.model_cache._estimate_model_size(self.model_name)
        if not self.gpu_manager.can_allocate_model(estimated_size):
            available = self.gpu_manager.get_available_memory()
            logger.error(
                f"Insufficient memory for model {self.model_name}. "
                f"Required: {estimated_size / 1024**2:.1f}MB, "
                f"Available: {available / 1024**2 if available else 'Unknown'}MB"
            )
            return False
        return True

    def validate_configuration(self) -> bool:
        """Validate that Parakeet is properly configured."""
        try:
            if not self._validate_dependencies():
                return False
            if not self._validate_model_name():
                return False
            if not self._validate_parameters():
                return False
            if not self._validate_gpu():
                return False
            if not self._validate_cache_dir():
                return False
            if not self._validate_memory():
                return False

            logger.info(
                f"Parakeet configuration validated: {self.model_name} on {self.gpu_manager.device}"
            )
            return True
        except Exception as e:
            logger.error(f"Configuration validation failed: {e}")
            return False

    def get_provider_name(self) -> str:
        """Get the name of this transcription provider.

        Returns:
            Human-readable name of the provider
        """
        model_type = PARAKEET_MODELS.get(self.model_name, {}).get("type", "unknown")
        return f"NVIDIA Parakeet ({model_type})"

    def get_supported_features(self) -> list[str]:
        """Get list of features supported by Parakeet.

        Returns:
            List of supported feature names
        """
        return [
            "timestamps",
            "speaker_diarization",
            "language_detection",
            "punctuation_restoration",
            "local_processing",
            "offline_capable",
            "gpu_acceleration",
        ]

    async def _transcribe_impl(
        self, audio_file_path: Path, language: str = "en"
    ) -> TranscriptionResult | None:
        """Internal implementation of Parakeet transcription.

        Args:
            audio_file_path: Path to the audio file to transcribe
            language: Language code for transcription

        Returns:
            TranscriptionResult object or None if failed
        """
        try:
            if not self._check_dependencies():
                return None

            preprocess_result = self._validate_and_preprocess(audio_file_path)
            if preprocess_result is None:
                return None

            processed_path, audio_duration, temp_file_created = preprocess_result

            try:
                return await self._execute_transcription(
                    processed_path, audio_file_path, audio_duration
                )
            finally:
                if temp_file_created:
                    self.audio_preprocessor.cleanup_temp_file(processed_path)

        except Exception as e:
            logger.error(f"Parakeet transcription failed: {e}")
            return None

    def _check_dependencies(self) -> bool:
        """Check if required dependencies are available."""
        if not NEMO_AVAILABLE or not TORCH_AVAILABLE:
            logger.error("Required dependencies not available")
            return False
        return True

    def _validate_and_preprocess(
        self, audio_file_path: Path
    ) -> tuple[Path, float, bool] | None:
        """Validate and preprocess audio file. Returns (path, duration, is_temp)."""
        if not self.audio_preprocessor.validate_audio_file(audio_file_path):
            logger.error(f"Invalid audio file: {audio_file_path}")
            return None

        processed_path, audio_duration = self.audio_preprocessor.preprocess_audio(audio_file_path)
        if processed_path is None:
            logger.error("Audio preprocessing failed")
            return None

        temp_file_created = processed_path != audio_file_path
        return processed_path, audio_duration, temp_file_created

    async def _execute_transcription(
        self, processed_path: Path, audio_file_path: Path, audio_duration: float
    ) -> TranscriptionResult | None:
        """Execute transcription with loaded model."""
        model = await self.model_cache.get_model_async(self.model_name)
        if model is None:
            logger.error("Failed to load model")
            return None

        transcription_kwargs = self._build_transcription_kwargs(processed_path)

        start_time = time.time()
        transcription = await self._run_transcription(
            model, transcription_kwargs, self.gpu_manager.device
        )
        processing_time = time.time() - start_time

        self.metrics.log_transcription(processing_time, audio_duration)

        return self._parse_parakeet_result(
            transcription, audio_file_path, processing_time, audio_duration
        )

    def _build_transcription_kwargs(self, processed_path: Path) -> dict[str, Any]:
        """Build kwargs dict for model.transcribe()."""
        kwargs = {
            "paths2audio_files": [str(processed_path)],
            "batch_size": self.batch_size,
            "return_hypotheses": False,
            "verbose": False,
        }
        if PARAKEET_MODELS.get(self.model_name, {}).get("type") == "rnnt":
            kwargs["beam_size"] = self.beam_size
        return kwargs

    async def _run_transcription(
        self,
        model: Any,  # NeMo ASRModelProtocol
        kwargs: dict[str, Any],
        device: str,
    ) -> list[str]:
        """Run transcription in thread pool to avoid blocking.

        Args:
            model: Loaded Parakeet model
            kwargs: Transcription arguments
            device: Device to run on

        Returns:
            List of transcription results
        """
        loop = asyncio.get_event_loop()

        def _transcribe() -> list[str]:
            try:
                if TORCH_AVAILABLE and device.startswith("cuda") and self.use_fp16:
                    import torch

                    with torch.cuda.amp.autocast():
                        return model.transcribe(**kwargs)
                else:
                    return model.transcribe(**kwargs)
            except Exception as e:
                logger.error(f"Model transcribe call failed: {e}")
                raise

        return await loop.run_in_executor(None, _transcribe)

    def _join_transcripts(self, parakeet_result: list[str]) -> str:
        """Join and clean transcript text from Parakeet result."""
        if not parakeet_result:
            return ""
        return " ".join(str(result) for result in parakeet_result if result).strip()

    def _create_utterances(
        self, transcript: str, audio_duration: float
    ) -> list[TranscriptionUtterance]:
        """Create utterances list from transcript."""
        if not transcript:
            return []
        return [
            TranscriptionUtterance(speaker=1, start=0.0, end=audio_duration, text=transcript)
        ]

    def _build_metadata(
        self,
        transcript: str,
        processing_time: float,
        audio_duration: float,
    ) -> dict[str, Any]:
        """Build base metadata dictionary for transcription result."""
        word_count = len(transcript.split()) if transcript else 0
        words_per_minute = (word_count / (audio_duration / 60)) if audio_duration > 0 else 0

        return {
            "parakeet_model": self.model_name,
            "model_type": PARAKEET_MODELS.get(self.model_name, {}).get("type", "unknown"),
            "device": self.gpu_manager.device,
            "use_fp16": self.use_fp16,
            "batch_size": self.batch_size,
            "beam_size": self.beam_size,
            "chunk_length": self.chunk_length,
            "processing_time_seconds": processing_time,
            "audio_duration_seconds": audio_duration,
            "rtf": self.metrics.get_rtf(),
            "words_per_minute": words_per_minute,
            "transcription_confidence": 1.0,
            "language": PARAKEET_MODELS.get(self.model_name, {}).get("languages", ["en"])[0],
            "sample_rate": 16000,
            "channels": 1,
        }

    def _add_gpu_metadata(self, metadata: dict[str, Any]) -> None:
        """Add GPU memory information to metadata if available."""
        if not (self.gpu_manager.device.startswith("cuda") and TORCH_AVAILABLE):
            return

        try:
            import torch

            available_memory = self.gpu_manager.get_available_memory()
            if available_memory is not None:
                metadata["gpu_memory_available_mb"] = available_memory / 1024**2

            metadata["gpu_memory_allocated_mb"] = torch.cuda.memory_allocated() / 1024**2
        except Exception:
            pass

    def _create_error_result(
        self,
        error: Exception,
        audio_file_path: Path,
        processing_time: float,
        audio_duration: float,
    ) -> TranscriptionResult:
        """Create minimal result on parsing failure."""
        return TranscriptionResult(
            transcript="",
            duration=audio_duration,
            generated_at=datetime.now(),
            audio_file=str(audio_file_path),
            provider_name=self.get_provider_name(),
            utterances=[],
            metadata={
                "error": f"Result parsing failed: {error}",
                "processing_time_seconds": processing_time,
                "audio_duration_seconds": audio_duration,
            },
        )

    def _parse_parakeet_result(
        self,
        parakeet_result: list[str],
        audio_file_path: Path,
        processing_time: float,
        audio_duration: float,
    ) -> TranscriptionResult:
        """Parse Parakeet result into TranscriptionResult format.

        Args:
            parakeet_result: Raw Parakeet transcription result
            audio_file_path: Path to the source audio file
            processing_time: Time taken for transcription
            audio_duration: Actual duration of the audio in seconds

        Returns:
            Formatted TranscriptionResult
        """
        try:
            transcript = self._join_transcripts(parakeet_result)
            utterances = self._create_utterances(transcript, audio_duration)
            metadata = self._build_metadata(transcript, processing_time, audio_duration)
            self._add_gpu_metadata(metadata)

            return TranscriptionResult(
                transcript=transcript,
                duration=audio_duration,
                generated_at=datetime.now(),
                audio_file=str(audio_file_path),
                provider_name=self.get_provider_name(),
                utterances=utterances,
                metadata=metadata,
            )

        except Exception as e:
            logger.error(f"Failed to parse Parakeet result: {e}")
            return self._create_error_result(e, audio_file_path, processing_time, audio_duration)

    async def health_check_async(self) -> dict[str, Any]:
        """Perform health check for Parakeet provider.

        Returns:
            Dictionary containing health check results
        """
        start_time = time.time()

        try:
            if not NEMO_AVAILABLE:
                return {
                    "healthy": False,
                    "status": "dependencies_missing",
                    "response_time_ms": 0,
                    "details": {"provider": "parakeet", "error": "NeMo toolkit not installed"},
                }

            # Test model loading
            try:
                model = await self.model_cache.get_model_async(self.model_name)
                model_available = model is not None
            except Exception as e:
                logger.debug(f"Model loading test failed during health check: {e}")
                model_available = False

            health_status = {
                "healthy": model_available,
                "status": "ready" if model_available else "model_not_loaded",
                "response_time_ms": (time.time() - start_time) * 1000,
                "details": {
                    "provider": "parakeet",
                    "model_loaded": model_available,
                    "model_name": self.model_name,
                    "device": self.gpu_manager.device,
                    "cuda_available": TORCH_AVAILABLE
                    and self.gpu_manager.device.startswith("cuda"),
                    "cache_stats": self.model_cache.get_cache_stats(),
                },
            }

            return health_status

        except Exception as e:
            return {
                "healthy": False,
                "status": "health_check_failed",
                "response_time_ms": (time.time() - start_time) * 1000,
                "details": {
                    "provider": "parakeet",
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
            }


# Maintain backward compatibility by exposing all classes at module level
__all__ = [
    "PARAKEET_MODELS",
    "AudioPreprocessor",
    "GPUManager",
    "ParakeetAudioError",
    "ParakeetError",
    "ParakeetGPUError",
    "ParakeetMetrics",
    "ParakeetModelCache",
    "ParakeetModelError",
    "ParakeetTranscriber",
]
