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
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..config import get_config
from ..models.transcription import TranscriptionResult, TranscriptionUtterance

if TYPE_CHECKING:
    from ..utils.retry import RetryConfig
from .base import BaseTranscriptionProvider, CircuitBreakerConfig

logger = logging.getLogger(__name__)

# Lazy dependency resolution to avoid import-time failures in environments
# where Whisper/torch are not installed or incompatible. These globals are
# populated on-demand during the first call to _ensure_whisper_available().
# This pattern allows the module to be imported without requiring heavy
# dependencies, deferring the import until actually needed.
PROVIDER_AVAILABLE = None  # Tri-state: None (unknown), True (available), False (missing)
whisper = None  # openai-whisper module, loaded on demand
torch = None  # PyTorch module, loaded on demand
get_writer = None  # Whisper output writer utility, optional


def _ensure_whisper_available() -> bool:
    """Ensure Whisper dependencies are available and loaded.

    This function performs lazy initialization of Whisper and PyTorch dependencies.
    It caches the result to avoid repeated import attempts. The function is safe
    to call multiple times as it returns immediately after the first successful check.

    Returns:
        True if all required Whisper dependencies are available, False otherwise.

    Note:
        This function modifies module-level globals (whisper, torch, get_writer)
        and should be called before any Whisper operations. Failure to load
        dependencies is logged as a warning, not an error, to support graceful
        degradation in multi-provider environments.
    """
    global PROVIDER_AVAILABLE, whisper, torch, get_writer
    if PROVIDER_AVAILABLE is not None:
        return PROVIDER_AVAILABLE
    try:
        import torch as _torch
        import whisper as _whisper

        try:
            # get_writer is optional and may not be available in all Whisper versions
            from whisper.utils import get_writer as get_writer_
        except Exception:
            get_writer_ = None
        torch = _torch
        whisper = _whisper
        get_writer = get_writer_
        PROVIDER_AVAILABLE = True
    except Exception as e:
        logger.warning(f"Whisper provider dependencies not installed: {e}")
        PROVIDER_AVAILABLE = False
    return PROVIDER_AVAILABLE


class WhisperTranscriber(BaseTranscriptionProvider):
    """OpenAI Whisper transcription service with local processing.

    This provider implements transcription using OpenAI's Whisper model, which
    runs locally on the machine (CPU or GPU). It supports multiple model sizes,
    automatic language detection, and produces high-quality transcriptions without
    requiring API calls or internet connectivity (after initial model download).

    Key features:
        - Local processing (no API required after model download)
        - Multiple model sizes (tiny to large-v3)
        - Automatic language detection
        - Word-level timestamps (when enabled)
        - GPU acceleration support (CUDA)
        - Offline capability (after initial setup)

    Limitations:
        - No speaker diarization (all utterances assigned to speaker 1)
        - Requires significant computational resources for larger models
        - Initial model download required (75MB to 2.9GB depending on model)
        - Processing time scales with audio length and model size

    Example:
        >>> transcriber = WhisperTranscriber()
        >>> if transcriber.validate_configuration():
        ...     result = await transcriber.transcribe_async(audio_path)
        ...     print(result.transcript)
    """

    def __init__(
        self,
        api_key: str | None = None,
        circuit_config: CircuitBreakerConfig | None = None,
        retry_config: RetryConfig | None = None,
    ) -> None:
        """Initialize the Whisper transcriber.

        Args:
            api_key: Optional API key. Not used for local Whisper processing but
                included for interface compatibility with BaseTranscriptionProvider
                and other cloud-based providers.
            circuit_config: Circuit breaker configuration for resilience patterns.
                Controls failure thresholds and recovery behavior.
            retry_config: Retry configuration for transient failures. Defines
                retry attempts, backoff strategy, and timeout values.

        Note:
            Model loading is deferred until the first transcription request to
            minimize initialization time and memory usage.
        """
        super().__init__(api_key, circuit_config, retry_config)
        self.model = None
        config = get_config()
        self.model_name = config.WHISPER_MODEL or "base"
        self.device = (
            config.WHISPER_DEVICE or "cuda" if torch and torch.cuda.is_available() else "cpu"
        )
        self.compute_type = config.WHISPER_COMPUTE_TYPE or "float16"

    def validate_configuration(self) -> bool:
        """Validate that Whisper is properly configured and dependencies are available.

        This method checks for required dependencies and performs device availability
        verification. It automatically falls back to CPU if CUDA is requested but
        unavailable, ensuring graceful degradation.

        Returns:
            True if configuration is valid and dependencies are available,
            False if required dependencies are missing.

        Note:
            When CUDA is requested but unavailable, the device is automatically
            changed to "cpu" and validation still returns True. Only missing
            dependencies cause validation to fail.
        """
        if not _ensure_whisper_available():
            logger.error(
                "Whisper dependencies not installed. Install with: uv add openai-whisper torch"
            )
            return False

        # Check if CUDA device is available, fall back to CPU if not
        if self.device == "cuda" and torch and not torch.cuda.is_available():
            logger.warning("CUDA requested but not available, falling back to CPU")
            self.device = "cpu"

        return True

    def get_provider_name(self) -> str:
        """Get the name of this transcription provider.

        Returns:
            Human-readable name of the provider
        """
        return f"OpenAI Whisper ({self.model_name})"

    def get_supported_features(self) -> list[str]:
        """Get list of features supported by Whisper.

        Returns:
            List of supported feature names
        """
        return [
            "timestamps",
            "word_timestamps",
            "language_detection",
            "vad_filter",  # Voice Activity Detection
            "local_processing",
            "offline_capable",
        ]

    async def _load_model(self) -> None:
        """Load the Whisper model asynchronously.

        This method loads the model on first use (lazy loading). The model file
        is downloaded from OpenAI's servers if not already cached locally. Model
        loading is performed in a thread pool executor to prevent blocking the
        event loop, as it can take several seconds for larger models.

        Raises:
            Exception: If model loading fails (e.g., network error, insufficient
                memory, invalid model name).

        Note:
            Subsequent calls are no-ops if the model is already loaded. Model
            files are cached in ~/.cache/whisper by default.
        """
        if self.model is None:
            logger.info(f"Loading Whisper model: {self.model_name} on {self.device}")
            try:
                # Run model loading in thread pool to avoid blocking the event loop
                loop = asyncio.get_event_loop()
                self.model = await loop.run_in_executor(
                    None, whisper.load_model, self.model_name, self.device
                )
                logger.info(f"Whisper model loaded successfully: {self.model_name}")
            except Exception as e:
                logger.error(f"Failed to load Whisper model: {e}")
                raise

    async def _transcribe_impl(
        self, audio_file_path: Path, language: str = "en"
    ) -> TranscriptionResult | None:
        """Internal implementation of Whisper transcription.

        This method performs the core transcription logic, including model loading,
        transcription execution, and result parsing. The actual transcription runs
        in a thread pool executor to avoid blocking the async event loop.

        Args:
            audio_file_path: Path to the audio file to transcribe. Must exist and
                be in a format supported by ffmpeg (mp3, wav, m4a, etc.).
            language: ISO 639-1 language code (e.g., 'en', 'es', 'fr'). Use 'auto'
                to enable automatic language detection. Defaults to 'en'.

        Returns:
            TranscriptionResult object containing the transcript, utterances,
            timestamps, and metadata.

        Raises:
            ImportError: If Whisper dependencies are not installed.
            FileNotFoundError: If the audio file does not exist.
            Exception: For transcription failures (e.g., corrupted audio, OOM).

        Note:
            When language is set to 'auto', Whisper will automatically detect
            the language from the audio content, which may add a small processing
            overhead but ensures accuracy for multilingual content.
        """
        if not _ensure_whisper_available():
            raise ImportError("Whisper dependencies not installed")

        if not audio_file_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_file_path}")

        await self._load_model()

        # Prepare transcription options for Whisper
        options = {
            "language": language if language != "auto" else None,  # None triggers auto-detection
            "task": "transcribe",  # Alternative is "translate" (to English)
            "fp16": self.compute_type == "float16",  # Use half-precision for speed/memory
            "verbose": False,  # Suppress detailed logging from Whisper internals
        }

        logger.info(f"Transcribing with Whisper: {audio_file_path.name}")
        start_time = time.time()

        try:
            # Run transcription in thread pool
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, self.model.transcribe, str(audio_file_path), **options
            )

            processing_time = time.time() - start_time
            logger.info(f"Whisper transcription completed in {processing_time:.2f}s")

            return self._parse_whisper_result(result, audio_file_path, processing_time)

        except Exception as e:
            logger.error(f"Whisper transcription failed: {e}")
            raise

    def _parse_whisper_result(
        self, whisper_result: dict[str, object], audio_file_path: Path, processing_time: float
    ) -> TranscriptionResult:
        """Parse Whisper result into TranscriptionResult format.

        Converts the raw dictionary output from Whisper into a structured
        TranscriptionResult object. This includes extracting segments, calculating
        duration, and building metadata.

        Args:
            whisper_result: Raw Whisper transcription result dictionary containing
                'segments', 'language', and optionally 'words' data.
            audio_file_path: Path to the source audio file that was transcribed.
            processing_time: Time taken for transcription in seconds, used for
                performance metrics.

        Returns:
            Formatted TranscriptionResult with utterances, metadata, and timing
            information.

        Note:
            All utterances are assigned speaker ID of 1 because Whisper does not
            perform speaker diarization. For multi-speaker content, consider using
            a separate diarization provider or a different transcription service
            that supports speaker identification.
        """
        utterances = []

        for segment in whisper_result.get("segments", []):
            utterance = TranscriptionUtterance(
                speaker=1,  # Whisper lacks speaker diarization; all segments assigned to speaker 1
                start=segment["start"],
                end=segment["end"],
                text=segment["text"].strip(),
            )
            utterances.append(utterance)

        # Calculate total duration from audio file or segments
        total_duration = max(utterance.end for utterance in utterances) if utterances else 0

        # Create metadata dict
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

        result = TranscriptionResult(
            transcript=" ".join(
                segment["text"].strip() for segment in whisper_result.get("segments", [])
            ),
            duration=total_duration,
            generated_at=datetime.now(),
            audio_file=str(audio_file_path),
            provider_name=self.get_provider_name(),
            metadata=metadata,
        )

        return result

    def _extract_words(self, segment: dict[str, object]) -> list[dict[str, object]] | None:
        """Extract word-level timestamps from Whisper segment.

        This method processes word-level timing information when available in
        Whisper results. Word-level timestamps are provided when the model is
        configured with word_timestamps=True option.

        Args:
            segment: Whisper segment dictionary potentially containing 'words' key
                with word-level timing and probability information.

        Returns:
            List of word dictionaries with 'word', 'start', 'end', and 'confidence'
            keys, or None if word information is not available in the segment.

        Note:
            This method is currently not used in the main transcription pipeline
            but is available for future enhancement to support word-level timing
            export or more granular analysis.
        """
        if not segment.get("words"):
            return None

        words = []
        for word_info in segment["words"]:
            words.append(
                {
                    "word": word_info["word"],
                    "start": word_info["start"],
                    "end": word_info["end"],
                    "confidence": word_info.get("probability", 0.0),
                }
            )

        return words

    def _generate_chapters(
        self, utterances: list[TranscriptionUtterance]
    ) -> list[dict[str, object]]:
        """Generate simple chapters based on time intervals.

        Creates chapter markers at fixed 5-minute (300-second) intervals to help
        with navigation in long audio content. This is a basic implementation that
        does not consider content or topic boundaries.

        Args:
            utterances: List of transcription utterances from which to derive the
                total duration for chapter generation.

        Returns:
            List of chapter dictionaries with 'start_time' and 'end_time' keys
            in seconds. Returns empty list if no utterances provided.

        Note:
            The 5-minute interval is chosen as a reasonable default for podcast
            and lecture content. For more sophisticated chaptering based on topic
            changes or speaker transitions, consider implementing content-aware
            segmentation.
        """
        if not utterances:
            return []

        # Generate chapters at 5-minute (300-second) intervals
        chapters = []
        total_duration = max(utt.end for utt in utterances)

        for i in range(0, int(total_duration) + 300, 300):  # Every 5 minutes (300 seconds)
            if i <= total_duration:
                chapters.append({"start_time": i, "end_time": min(i + 300, total_duration)})

        return chapters

    async def health_check_async(self) -> dict[str, Any]:
        """Perform health check for Whisper provider.

        Verifies that dependencies are available and optionally loads the model
        to confirm full operational readiness. The health check includes dependency
        verification, device availability, and model loading status.

        Returns:
            Dictionary containing health check results with keys:
                - healthy (bool): Overall health status
                - status (str): Status description ('ready', 'dependencies_missing', etc.)
                - response_time_ms (float): Time taken for health check in milliseconds
                - details (dict): Provider-specific details including model info,
                  device configuration, and CUDA availability

        Note:
            This method has a side effect: if the model is not already loaded,
            it will be loaded during the health check. This ensures readiness
            but may take several seconds on first call. Subsequent calls will
            be fast as the model remains in memory.
        """
        start_time = time.time()

        try:
            if not PROVIDER_AVAILABLE:
                return {
                    "healthy": False,
                    "status": "dependencies_missing",
                    "response_time_ms": 0,
                    "details": {
                        "provider": "whisper",
                        "error": "Whisper dependencies not installed",
                    },
                }

            # Test model loading if not already loaded
            if self.model is None:
                await self._load_model()

            health_status = {
                "healthy": self.model is not None,
                "status": "ready" if self.model else "model_not_loaded",
                "response_time_ms": (time.time() - start_time) * 1000,
                "details": {
                    "provider": "whisper",
                    "model_loaded": self.model is not None,
                    "model_name": self.model_name,
                    "device": self.device,
                    "compute_type": self.compute_type,
                    "cuda_available": torch.cuda.is_available() if torch else False,
                },
            }

            return health_status

        except Exception as e:
            return {
                "healthy": False,
                "status": "health_check_failed",
                "response_time_ms": (time.time() - start_time) * 1000,
                "details": {"provider": "whisper", "error": str(e), "error_type": type(e).__name__},
            }

    def get_model_size_info(self) -> dict[str, Any]:
        """Get information about Whisper model sizes and resource requirements.

        Provides detailed information about available Whisper models including
        parameter counts, disk space requirements, and memory (RAM/VRAM) needs.
        This information helps users select appropriate models based on their
        hardware constraints.

        Returns:
            Dictionary containing:
                - current_model (str): Name of the currently configured model
                - current_info (dict): Resource requirements for current model
                - available_models (list): All available model names
                - model_sizes (dict): Complete mapping of models to their requirements

        Note:
            Memory requirements (RAM/VRAM) are approximate and may vary based on:
            - Batch size and audio length
            - Operating system and PyTorch version
            - GPU architecture and driver version
            - Compute type (float16 vs float32)

            Disk sizes represent the model file size only and do not include
            PyTorch/CUDA dependencies. Plan for 20-30% overhead beyond the stated
            values for safe operation.
        """
        model_sizes = {
            "tiny": {"params": "39M", "disk": "75MB", "ram": "~1GB", "vram": "~1GB"},
            "base": {"params": "74M", "disk": "142MB", "ram": "~1GB", "vram": "~1GB"},
            "small": {"params": "244M", "disk": "461MB", "ram": "~2GB", "vram": "~2GB"},
            "medium": {"params": "769M", "disk": "1.5GB", "ram": "~5GB", "vram": "~5GB"},
            "large": {"params": "1.5B", "disk": "2.9GB", "ram": "~10GB", "vram": "~10GB"},
            "large-v2": {"params": "1.5B", "disk": "2.9GB", "ram": "~10GB", "vram": "~10GB"},
            "large-v3": {"params": "1.5B", "disk": "2.9GB", "ram": "~10GB", "vram": "~10GB"},
        }

        return {
            "current_model": self.model_name,
            "current_info": model_sizes.get(
                self.model_name, {"params": "unknown", "disk": "unknown"}
            ),
            "available_models": list(model_sizes.keys()),
            "model_sizes": model_sizes,
        }
