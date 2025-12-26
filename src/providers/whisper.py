"""OpenAI Whisper transcription service with local processing support.

This module provides a transcription provider implementation using OpenAI's Whisper
model for local audio-to-text conversion. It supports multiple model sizes, automatic
language detection, and GPU acceleration while maintaining compatibility with the
BaseTranscriptionProvider interface.

The implementation uses lazy dependency loading to allow the module to be imported
in environments where Whisper/PyTorch are not installed, enabling graceful
degradation in multi-provider setups.

Dependencies:
    - openai-whisper: The core Whisper model (install: uv add openai-whisper)
    - torch: PyTorch for model execution (install: uv add torch)
    - ffmpeg: Audio format conversion (system package)

Configuration:
    Set via Config object:
        - WHISPER_MODEL: Model size (tiny/base/small/medium/large/large-v2/large-v3)
        - WHISPER_DEVICE: Compute device (cuda/cpu)
        - WHISPER_COMPUTE_TYPE: Precision (float16/float32)

Example:
    >>> from pathlib import Path
    >>> transcriber = WhisperTranscriber()
    >>> if transcriber.validate_configuration():
    ...     result = await transcriber.transcribe_async(Path("audio.mp3"))
    ...     print(f"Transcript: {result.transcript}")
    ...     print(f"Duration: {result.duration}s")
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from src.utils.logger import get_logger

from ..config import get_config
from ..exceptions import TranscriptionError
from ..models.transcription import TranscriptionResult, TranscriptionUtterance
from ..utils.constants import UIConstants
from ..utils.file_validation import validate_audio_file_or_raise

if TYPE_CHECKING:
    from ..utils.retry import RetryConfig

from .base import BaseTranscriptionProvider, HealthCheckResult, ProviderMeta
from .provider_utils import provider_error_handler

logger = get_logger(__name__)

# Lazy dependency resolution
PROVIDER_AVAILABLE = None
whisper = None
torch = None
get_writer = None


def _ensure_whisper_available() -> bool:
    """Check and lazily load Whisper dependencies. Returns True if available."""
    global PROVIDER_AVAILABLE, whisper, torch, get_writer
    if PROVIDER_AVAILABLE is not None:
        return PROVIDER_AVAILABLE
    try:
        import torch as _torch
        import whisper as _whisper

        try:
            from whisper.utils import get_writer as get_writer_
        except ImportError:
            get_writer_ = None
        torch = _torch
        whisper = _whisper
        get_writer = get_writer_
        PROVIDER_AVAILABLE = True
    except ImportError as e:
        logger.warning(f"Whisper dependencies not installed: {e}")
        PROVIDER_AVAILABLE = False
    return PROVIDER_AVAILABLE


class WhisperTranscriber(BaseTranscriptionProvider):
    """Local Whisper transcription. No speaker diarization. Supports GPU acceleration."""

    META = ProviderMeta(
        name="OpenAI Whisper",
        provider_key="whisper",
        supported_features=[
            "timestamps",
            "word_timestamps",
            "language_detection",
            "vad_filter",
            "local_processing",
            "offline_capable",
        ],
        sdk_imports=["whisper", "torch"],
        install_command="uv add openai-whisper torch",
        is_local=True,
    )

    def __init__(self, api_key: str | None = None, retry_config: RetryConfig | None = None) -> None:
        """Initialize the Whisper transcriber."""
        super().__init__(api_key, retry_config)
        self.model = None
        config = get_config()
        self.model_name = config.WHISPER_MODEL or "base"
        self.device = (
            config.WHISPER_DEVICE or "cuda" if torch and torch.cuda.is_available() else "cpu"
        )
        self.compute_type = config.WHISPER_COMPUTE_TYPE or "float16"

    async def transcribe_async(
        self, audio_file_path: Path, language: str = "en", *, timeout: float | None = None
    ) -> TranscriptionResult | None:
        """Run transcription and return None on failure for graceful degradation."""
        try:
            return await super().transcribe_async(audio_file_path, language, timeout=timeout)
        except TimeoutError as exc:
            logger.error("Whisper transcription timed out: %s", exc)
            raise
        except (ImportError, OSError, RuntimeError) as exc:
            logger.error("Whisper transcription failed: %s", exc)
            raise TranscriptionError(f"Whisper transcription failed: {exc}") from exc
        except Exception as exc:
            logger.error("Whisper transcription failed with unexpected error: %s", exc)
            raise TranscriptionError(f"Whisper transcription failed: {exc}") from exc

    def validate_configuration(self) -> bool:
        """Validate Whisper dependencies are available."""
        if not _ensure_whisper_available():
            logger.error(
                f"Whisper dependencies not installed. Install with: {self.META.install_command}"
            )
            return False

        if self.device == "cuda" and torch and not torch.cuda.is_available():
            logger.warning("CUDA requested but not available, falling back to CPU")
            self.device = "cpu"

        return True

    def get_provider_name(self) -> str:
        """Get provider name including model variant."""
        return f"{self.META.name} ({self.model_name})"

    async def _load_model(self) -> None:
        """Load the Whisper model asynchronously."""
        if self.model is None:
            logger.info(f"Loading Whisper model: {self.model_name} on {self.device}")
            try:
                loop = asyncio.get_running_loop()
                self.model = await loop.run_in_executor(
                    None, whisper.load_model, self.model_name, self.device
                )
                logger.info(f"Whisper model loaded successfully: {self.model_name}")
            except Exception as e:
                logger.error(f"Failed to load Whisper model: {e}")
                raise

    @provider_error_handler("whisper", "uv add openai-whisper torch")
    async def _transcribe_impl(
        self, audio_file_path: Path, language: str = "en"
    ) -> TranscriptionResult | None:
        """Internal implementation of Whisper transcription."""
        if not _ensure_whisper_available():
            raise ImportError("Whisper dependencies not installed")

        audio_file_path = validate_audio_file_or_raise(audio_file_path, provider_name="whisper")

        await self._load_model()

        options = {
            "language": language if language != "auto" else None,
            "task": "transcribe",
            "fp16": self.compute_type == "float16",
            "verbose": False,
        }

        logger.info(f"Transcribing with Whisper: {audio_file_path.name}")
        start_time = time.time()

        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None, self.model.transcribe, str(audio_file_path), **options
        )

        processing_time = time.time() - start_time
        logger.info(f"Whisper transcription completed in {processing_time:.2f}s")

        return self._parse_whisper_result(result, audio_file_path, processing_time)

    def _parse_whisper_result(
        self, whisper_result: dict[str, object], audio_file_path: Path, processing_time: float
    ) -> TranscriptionResult:
        """Parse Whisper result into TranscriptionResult format."""
        utterances = []

        for segment in whisper_result.get("segments", []):
            utterance = TranscriptionUtterance(
                speaker=1,
                start=segment["start"],
                end=segment["end"],
                text=segment["text"].strip(),
            )
            utterances.append(utterance)

        total_duration = max(utterance.end for utterance in utterances) if utterances else 0

        metadata = {
            "whisper_model": self.model_name,
            "device": self.device,
            "compute_type": self.compute_type,
            "has_words": any(
                segment.get("words") for segment in whisper_result.get("segments", [])
            ),
            "chapters": self._generate_chapters(utterances),
            "language": whisper_result.get("language", "en"),
            "processing_time_seconds": processing_time,
        }

        result = self._build_transcription_result(
            transcript=" ".join(
                segment["text"].strip() for segment in whisper_result.get("segments", [])
            ),
            audio_file=audio_file_path,
            duration=total_duration,
            metadata=metadata,
        )

        return result

    def _generate_chapters(
        self, utterances: list[TranscriptionUtterance]
    ) -> list[dict[str, object]]:
        """Generate simple chapters based on time intervals."""
        if not utterances:
            return []

        interval = UIConstants.CHAPTER_INTERVAL_SECONDS
        chapters = []
        total_duration = max(utt.end for utt in utterances)

        for i in range(0, int(total_duration) + interval, interval):
            if i <= total_duration:
                chapters.append({"start_time": i, "end_time": min(i + interval, total_duration)})

        return chapters

    async def health_check_async(self) -> HealthCheckResult:
        """Perform health check for Whisper provider."""

        async def _check() -> dict[str, Any]:
            if not _ensure_whisper_available():
                return {
                    "healthy": False,
                    "status": "dependencies_missing",
                    "error": "Whisper dependencies not installed",
                }

            if self.model is None:
                await self._load_model()

            return {
                "healthy": self.model is not None,
                "status": "ready" if self.model else "model_not_loaded",
                "model_loaded": self.model is not None,
                "model_name": self.model_name,
                "device": self.device,
                "compute_type": self.compute_type,
                "cuda_available": torch.cuda.is_available() if torch else False,
            }

        return await self._run_health_check(_check)
