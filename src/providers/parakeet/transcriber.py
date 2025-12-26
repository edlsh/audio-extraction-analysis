"""NVIDIA Parakeet STT transcription provider."""

from __future__ import annotations

import asyncio
import os
import time
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from src.config import get_config
from src.exceptions import ParakeetAudioError
from src.models.transcription import TranscriptionResult, TranscriptionUtterance
from src.utils.file_validation import validate_audio_file_or_raise
from src.utils.logger import get_logger

from ..base import BaseTranscriptionProvider, HealthCheckResult, ProviderMeta
from ..provider_utils import provider_error_handler
from .audio import AudioPreprocessor
from .cache import ParakeetModelCache
from .deps import NEMO_AVAILABLE, TORCH_AVAILABLE
from .gpu import GPUManager
from .metrics import ParakeetMetrics
from .models import PARAKEET_MODELS

if TYPE_CHECKING:
    from src.utils.retry import RetryConfig

logger = get_logger(__name__)


class ParakeetTranscriber(BaseTranscriptionProvider):
    """NVIDIA Parakeet STT transcription service with CTC/RNN-T model support."""

    META = ProviderMeta(
        name="NVIDIA Parakeet",
        provider_key="parakeet",
        supported_features=[
            "timestamps",
            "speaker_diarization",
            "language_detection",
            "punctuation_restoration",
            "local_processing",
            "offline_capable",
            "gpu_acceleration",
        ],
        sdk_imports=["nemo.collections.asr", "torch"],
        install_command='uv add "nemo-toolkit[asr]@1.20.0" --extra parakeet',
        is_local=True,
    )

    def __init__(
        self,
        api_key: str | None = None,
        retry_config: RetryConfig | None = None,
    ) -> None:
        """Initialize the Parakeet transcriber."""
        super().__init__(api_key, retry_config)
        self.gpu_manager = GPUManager()
        self.model_cache = ParakeetModelCache()
        self.audio_preprocessor = AudioPreprocessor()
        self.metrics = ParakeetMetrics()

        config = get_config()
        self.model_name = config.PARAKEET_MODEL
        self.batch_size = config.PARAKEET_BATCH_SIZE
        self.beam_size = config.PARAKEET_BEAM_SIZE
        self.use_fp16 = config.PARAKEET_USE_FP16
        self.chunk_length = config.PARAKEET_CHUNK_LENGTH
        self.model_cache_dir = str(config.PARAKEET_MODEL_CACHE_DIR)

    def _validate_dependencies(self) -> bool:
        """Check required dependencies are available."""
        if not NEMO_AVAILABLE:
            logger.error(f"NeMo toolkit not installed. Install with: {self.META.install_command}")
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

        from .deps import torch

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
        """Get provider name including model type."""
        model_type = PARAKEET_MODELS.get(self.model_name, {}).get("type", "unknown")
        return f"{self.META.name} ({model_type})"

    def get_supported_features(self) -> list[str]:
        """Get list of features supported by Parakeet."""
        return self.META.supported_features

    @provider_error_handler("parakeet", 'uv add "nemo-toolkit[asr]@1.20.0" --extra parakeet')
    async def _transcribe_impl(
        self, audio_file_path: Path, language: str = "en"
    ) -> TranscriptionResult | None:
        """Internal implementation of Parakeet transcription."""
        if not self._check_dependencies():
            raise ImportError("Parakeet dependencies (NeMo, PyTorch) not available")

        audio_file_path = validate_audio_file_or_raise(audio_file_path, provider_name="parakeet")

        preprocess_result = await asyncio.to_thread(self._validate_and_preprocess, audio_file_path)
        if preprocess_result is None:
            raise ParakeetAudioError("Audio preprocessing failed")

        processed_path, audio_duration, temp_file_created = preprocess_result

        try:
            return await self._execute_transcription(
                processed_path, audio_file_path, audio_duration
            )
        finally:
            if temp_file_created:
                self.audio_preprocessor.cleanup_temp_file(processed_path)

    def _check_dependencies(self) -> bool:
        """Check if required dependencies are available."""
        if not NEMO_AVAILABLE or not TORCH_AVAILABLE:
            logger.error("Required dependencies not available")
            return False
        return True

    def _validate_and_preprocess(self, audio_file_path: Path) -> tuple[Path, float, bool] | None:
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
        kwargs: dict[str, Any] = {
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
        model: Any,
        kwargs: dict[str, Any],
        device: str,
    ) -> list[str]:
        """Run transcription in thread pool to avoid blocking."""
        loop = asyncio.get_running_loop()

        def _transcribe() -> list[str]:
            try:
                if TORCH_AVAILABLE and device.startswith("cuda") and self.use_fp16:
                    from .deps import torch

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
        return [TranscriptionUtterance(speaker=1, start=0.0, end=audio_duration, text=transcript)]

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
            from .deps import torch

            available_memory = self.gpu_manager.get_available_memory()
            if available_memory is not None:
                metadata["gpu_memory_available_mb"] = available_memory / 1024**2

            metadata["gpu_memory_allocated_mb"] = torch.cuda.memory_allocated() / 1024**2
        except (ImportError, RuntimeError):
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
        """Parse Parakeet result into TranscriptionResult format."""
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

    async def health_check_async(self) -> HealthCheckResult:
        """Perform health check for Parakeet provider."""

        async def _check() -> dict[str, Any]:
            if not NEMO_AVAILABLE:
                return {
                    "healthy": False,
                    "status": "dependencies_missing",
                    "error": "NeMo toolkit not installed",
                }

            try:
                model = await self.model_cache.get_model_async(self.model_name)
                model_available = model is not None
            except Exception as e:
                logger.debug(f"Model loading test failed during health check: {e}")
                model_available = False

            return {
                "healthy": model_available,
                "status": "ready" if model_available else "model_not_loaded",
                "model_loaded": model_available,
                "model_name": self.model_name,
                "device": self.gpu_manager.device,
                "cuda_available": TORCH_AVAILABLE and self.gpu_manager.device.startswith("cuda"),
                "cache_stats": self.model_cache.get_cache_stats(),
            }

        return await self._run_health_check(_check)


__all__ = ["ParakeetTranscriber"]
