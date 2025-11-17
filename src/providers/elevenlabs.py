"""ElevenLabs speech-to-text transcription service."""

from __future__ import annotations

import asyncio
import json
import logging
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..config import get_config
from ..models.transcription import TranscriptionResult, TranscriptionUtterance
from ..utils.file_validation import safe_validate_audio_file

if TYPE_CHECKING:
    from ..utils.retry import RetryConfig
from .base import BaseTranscriptionProvider, CircuitBreakerConfig
from .provider_utils import ProviderInitializer

logger = logging.getLogger(__name__)

# Check for ElevenLabs SDK availability
try:
    from elevenlabs import ElevenLabs
    from elevenlabs.client import ElevenLabs as ElevenLabsClient

    PROVIDER_AVAILABLE = True
except ImportError as e:
    logger.warning(f"ElevenLabs provider dependencies not installed: {e}")
    PROVIDER_AVAILABLE = False
    # Create placeholder classes to prevent import errors
    ElevenLabs = None
    ElevenLabsClient = None


class ElevenLabsTranscriber(BaseTranscriptionProvider):
    """ElevenLabs speech-to-text transcription service."""

    # File size limits
    MAX_FILE_SIZE_MB = 50  # Maximum file size in MB for processing

    # Memory management constants
    CHUNK_SIZE = 1024 * 1024  # 1MB chunks for file reading
    MAX_MEMORY_SIZE = 50 * 1024 * 1024  # 50MB max in memory

    def __init__(
        self,
        api_key: str | None = None,
        circuit_config: CircuitBreakerConfig | None = None,
        retry_config: RetryConfig | None = None,
    ) -> None:
        """Initialize the ElevenLabs transcriber with API key and configurations.

        Args:
            api_key: Optional ElevenLabs API key. If None, uses get_config().ELEVENLABS_API_KEY
            circuit_config: Circuit breaker configuration
            retry_config: Retry configuration
        """
        # Use standardized provider initialization
        retry_config, circuit_config = ProviderInitializer.initialize_provider_configs(
            provider_name="ElevenLabs", retry_config=retry_config, circuit_config=circuit_config
        )

        super().__init__(api_key, circuit_config, retry_config)
        config = get_config()
        self.api_key = api_key or config.ELEVENLABS_API_KEY
        if not PROVIDER_AVAILABLE:
            raise ImportError("ElevenLabs SDK not available. Install with: uv add elevenlabs")

        if not self.api_key:
            raise ValueError(
                "ELEVENLABS_API_KEY not found. Set it as environment variable or pass to constructor."
            )

    def validate_configuration(self) -> bool:
        """Validate that ElevenLabs is properly configured.

        Returns:
            True if configuration is valid, False otherwise
        """
        return bool(self.api_key)

    def get_provider_name(self) -> str:
        """Get the name of this transcription provider.

        Returns:
            Human-readable name of the provider
        """
        return "ElevenLabs"

    def get_supported_features(self) -> list[str]:
        """Get list of features supported by ElevenLabs.

        Returns:
            List of feature names supported by this provider
        """
        return ["timestamps", "language_detection", "basic_transcription"]

    async def health_check_async(self) -> dict[str, Any]:
        """Perform health check for ElevenLabs service.

        Returns:
            Dictionary containing health status information
        """
        start_time = time.time()

        try:
            if not PROVIDER_AVAILABLE:
                return {
                    "healthy": False,
                    "status": "sdk_not_available",
                    "response_time_ms": (time.time() - start_time) * 1000,
                    "details": {"provider": "ElevenLabs", "error": "ElevenLabs SDK not installed"},
                }

            # Initialize client
            client = ElevenLabsClient(api_key=self.api_key)

            # Make a simple API call to check connectivity
            # Use the user endpoint which is lightweight
            config = get_config()
            response = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(None, lambda: client.user.get_user_info()),
                timeout=config.HEALTH_CHECK_TIMEOUT,
            )

            response_time = (time.time() - start_time) * 1000

            return {
                "healthy": True,
                "status": "operational",
                "response_time_ms": response_time,
                "details": {
                    "provider": "ElevenLabs",
                    "api_accessible": True,
                    "authentication": "valid",
                    "user_id": getattr(response, "user_id", "unknown"),
                },
            }

        except ImportError:
            return {
                "healthy": False,
                "status": "sdk_not_available",
                "response_time_ms": (time.time() - start_time) * 1000,
                "details": {"provider": "ElevenLabs", "error": "ElevenLabs SDK not installed"},
            }
        except Exception as e:
            return {
                "healthy": False,
                "status": "error",
                "response_time_ms": (time.time() - start_time) * 1000,
                "details": {
                    "provider": "ElevenLabs",
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
            }

    async def _transcribe_impl(
        self, audio_file_path: Path, language: str = "en"
    ) -> TranscriptionResult | None:
        """Internal transcription implementation without retry/circuit breaker logic.

        Args:
            audio_file_path: Path to audio file
            language: Language code for transcription

        Returns:
            TranscriptionResult with available features, or None if failed

        Raises:
            ProviderNotAvailableError: If ElevenLabs SDK not installed
            ValidationError: If audio file validation fails or file not found
            FileAccessError: If file permissions prevent access
            FileSizeError: If file exceeds size limits
            ProviderAPIError: If ElevenLabs API returns an error
            ProviderTimeoutError: If request times out
        """
        from ..exceptions import (
            FileAccessError,
            FileSizeError,
            ProviderAPIError,
            ProviderNotAvailableError,
            ValidationError,
        )

        # Validate audio file with ElevenLabs size limits
        validated_path = safe_validate_audio_file(
            audio_file_path,
            max_file_size=self.MAX_FILE_SIZE_MB * 1024 * 1024,
            provider_name="elevenlabs",
        )
        if validated_path is None:
            raise ValidationError(
                f"Audio file validation failed: {audio_file_path}",
                context={"file_path": str(audio_file_path), "provider": "elevenlabs"},
            )
        audio_file_path = validated_path

        # Check file size limit (ElevenLabs has 50MB limit)
        file_size_mb = audio_file_path.stat().st_size / (1024 * 1024)
        if file_size_mb > self.MAX_FILE_SIZE_MB:
            logger.error(
                f"File size {file_size_mb:.2f}MB exceeds ElevenLabs {self.MAX_FILE_SIZE_MB}MB limit"
            )
            raise FileSizeError(
                f"File size {file_size_mb:.2f}MB exceeds {self.MAX_FILE_SIZE_MB}MB limit",
                context={
                    "file_path": str(audio_file_path),
                    "file_size_mb": file_size_mb,
                    "limit_mb": self.MAX_FILE_SIZE_MB,
                },
            )

        try:
            # Check SDK availability
            if not PROVIDER_AVAILABLE:
                raise ImportError("ElevenLabs SDK not available")

            logger.info(f"Starting ElevenLabs transcription: {audio_file_path}")
            logger.info(f"File size: {file_size_mb:.2f} MB")

            # Initialize client
            client = ElevenLabsClient(api_key=self.api_key)

            # Memory-efficient audio data handling
            if file_size_mb * 1024 * 1024 > self.MAX_MEMORY_SIZE:
                # For large files, use streaming approach
                logger.info(f"Using streaming approach for large file ({file_size_mb:.2f}MB)")
                audio_data = self._read_file_chunked(audio_file_path)
            else:
                # For small files, read into memory
                with open(audio_file_path, "rb") as audio_file:
                    audio_data = audio_file.read()

            # Perform transcription
            logger.info("Sending to ElevenLabs...")
            config = get_config()
            response = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: client.speech_to_text.convert(
                        file=audio_data,
                        model_id="eleven_multilingual_sts_v2",  # Latest model
                        language_code=language if language else None,
                        # Add more parameters as they become available
                    ),
                ),
                timeout=config.ELEVENLABS_TIMEOUT,
            )

            logger.info("Transcription completed successfully")

            # Extract transcript text
            if hasattr(response, "text") and response.text is not None:
                transcript = response.text
            elif hasattr(response, "transcript") and response.transcript is not None:
                transcript = response.transcript
            else:
                transcript = str(response)

            # Get audio duration (estimate from file)
            duration = self._estimate_audio_duration(audio_file_path)

            # Create result object with basic transcription
            result = TranscriptionResult(
                transcript=transcript,
                duration=duration,
                generated_at=datetime.now(),
                audio_file=str(audio_file_path),
                provider_name=self.get_provider_name(),
                provider_features=self.get_supported_features(),
            )

            # Parse timestamps if available in response
            if hasattr(response, "segments") and response.segments:
                if hasattr(response, "segments") and response.segments:
                    if result.utterances is None:
                        result.utterances = []
                    for segment in response.segments:
                        utterance = TranscriptionUtterance(
                            speaker=0,  # ElevenLabs doesn't provide speaker ID
                            start=getattr(segment, "start", 0.0),
                            end=getattr(segment, "end", duration),
                            text=getattr(segment, "text", ""),
                        )
                        result.utterances.append(utterance)

            # Note: ElevenLabs doesn't provide advanced features like
            # speaker diarization, topics, intents, sentiment analysis
            # These would need to be handled by post-processing

            logger.info(f"Transcription completed. Length: {len(transcript)} characters")
            assert result is not None, "Result should be initialized"
            return result

        except ImportError as e:
            logger.error(f"ElevenLabs SDK not installed: {e}")
            raise ProviderNotAvailableError(
                "ElevenLabs SDK not available",
                context={"provider": "elevenlabs", "install_command": "uv add elevenlabs"},
            ) from e
        except FileNotFoundError as e:
            logger.error(f"Audio file not found: {e}")
            raise ValidationError(
                f"Audio file not found: {audio_file_path}",
                context={"file_path": str(audio_file_path)},
            ) from e
        except PermissionError as e:
            logger.error(f"Permission denied accessing file: {e}")
            raise FileAccessError(
                f"Permission denied: {audio_file_path}", context={"file_path": str(audio_file_path)}
            ) from e
        except MemoryError as e:
            logger.error(f"Insufficient memory to process file: {e}")
            raise ProviderAPIError(
                "Insufficient memory to process file",
                context={
                    "file_path": str(audio_file_path),
                    "file_size_mb": file_size_mb,
                    "error": str(e),
                },
            ) from e
        except (OSError, ConnectionError, TimeoutError):
            # Let provider-specific errors propagate directly
            logger.error("ElevenLabs API error")
            raise
        except Exception as e:
            logger.error(f"ElevenLabs transcription failed: {e}")
            raise ProviderAPIError(
                f"Unexpected ElevenLabs error: {e}",
                context={"error_type": type(e).__name__, "file_path": str(audio_file_path)},
            ) from e

    def _read_file_chunked(self, file_path: Path) -> bytes:
        """Read file in chunks to manage memory usage.

        Args:
            file_path: Path to file to read

        Returns:
            File contents as bytes

        Raises:
            MemoryError: If file is too large for available memory
            OSError: If file cannot be read
        """
        try:
            file_size = file_path.stat().st_size
            if file_size > self.MAX_MEMORY_SIZE:
                raise MemoryError(
                    f"File size {file_size} exceeds memory limit {self.MAX_MEMORY_SIZE}"
                )

            chunks = []
            total_read = 0

            with open(file_path, "rb") as f:
                while True:
                    chunk = f.read(self.CHUNK_SIZE)
                    if not chunk:
                        break

                    chunks.append(chunk)
                    total_read += len(chunk)

                    # Safety check to prevent memory exhaustion
                    if total_read > self.MAX_MEMORY_SIZE:
                        raise MemoryError("File reading exceeded memory limit")

            # Optimize memory usage for large numbers of chunks
            if len(chunks) > 100:  # Large number of chunks
                result = bytearray()
                for chunk in chunks:
                    result.extend(chunk)
                return bytes(result)
            else:
                return b"".join(chunks)

        except OSError as e:
            logger.error(f"Failed to read file {file_path}: {e}")
            raise OSError(f"Cannot read file: {file_path}") from e

    def _estimate_audio_duration(self, audio_file_path: Path) -> float:
        """Estimate audio duration from file.

        Args:
            audio_file_path: Path to audio file

        Returns:
            Estimated duration in seconds
        """
        try:
            # Try to use ffprobe for accurate duration
            result = subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "quiet",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "json",
                    str(audio_file_path),
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0:
                data = json.loads(result.stdout)
                return float(data["format"]["duration"])
        except (
            subprocess.CalledProcessError,
            subprocess.TimeoutExpired,
            FileNotFoundError,
            json.JSONDecodeError,
            KeyError,
            ValueError,
        ) as e:
            logger.debug(f"ffprobe failed, using fallback estimation: {e}")
        except Exception as e:
            logger.warning(f"Unexpected error in duration estimation: {e}")

        try:
            # Fallback: rough estimation based on file size and typical bitrates
            file_size_bytes = audio_file_path.stat().st_size
            # Assume average bitrate of 128 kbps for estimation
            estimated_duration = (file_size_bytes * 8) / (128 * 1000)
            return max(1.0, estimated_duration)  # Ensure minimum 1 second duration
        except OSError as e:
            logger.warning(f"Failed to get file size for duration estimation: {e}")
            return 1.0  # Default fallback

    def save_result_to_file(self, result: TranscriptionResult, output_path: Path) -> None:
        """Save transcription result to formatted text file.

        Args:
            result: TranscriptionResult to save
            output_path: Output file path
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write("ELEVENLABS TRANSCRIPTION\n")
            f.write("=" * 50 + "\n")
            f.write(f"Generated: {result.generated_at.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Audio File: {Path(result.audio_file).name}\n")
            f.write(f"Duration: {result.duration:.2f} seconds\n")
            f.write(f"Provider: {result.provider_name}\n")
            f.write("=" * 50 + "\n\n")

            # Note about features
            f.write("NOTE: ElevenLabs provides basic transcription.\n")
            f.write("For advanced features (speaker diarization, topics, sentiment),\n")
            f.write("consider using Deepgram Nova 3.\n\n")
            f.write("=" * 50 + "\n\n")

            # Utterances with timestamps if available
            if result.utterances:
                f.write("TRANSCRIPT WITH TIMESTAMPS:\n")
                f.write("-" * 30 + "\n")
                for utterance in result.utterances:
                    timestamp = f"[{utterance.start:.2f}s]"
                    f.write(f"{timestamp} {utterance.text}\n")
                f.write("\n" + "=" * 50 + "\n\n")

            # Full transcript
            f.write("FULL TRANSCRIPT:\n")
            f.write("-" * 30 + "\n\n")
            f.write(result.transcript)

            f.write("\n\n" + "=" * 50 + "\n")
            f.write("END OF TRANSCRIPTION\n")

        logger.info(f"Transcription saved to: {output_path}")
