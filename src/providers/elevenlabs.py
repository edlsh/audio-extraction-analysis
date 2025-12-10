"""ElevenLabs speech-to-text transcription service."""

from __future__ import annotations

import asyncio
import json
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from src.utils.logger import get_logger

from ..config import get_config
from ..models.transcription import TranscriptionResult, TranscriptionUtterance
from ..utils.constants import Limits
from ..utils.file_validation import validate_audio_file_or_raise

if TYPE_CHECKING:
    from ..utils.retry import RetryConfig
from .base import BaseTranscriptionProvider, CircuitBreakerConfig, ProviderMeta
from .provider_utils import check_sdk_available, get_default_configs, provider_error_handler

logger = get_logger(__name__)

# Check for ElevenLabs SDK availability
try:
    from elevenlabs import ElevenLabs
    from elevenlabs.client import ElevenLabs as ElevenLabsClient

    PROVIDER_AVAILABLE = True
except ImportError as e:
    logger.warning(f"ElevenLabs provider dependencies not installed: {e}")
    PROVIDER_AVAILABLE = False
    ElevenLabs = None
    ElevenLabsClient = None


class ElevenLabsTranscriber(BaseTranscriptionProvider):
    """ElevenLabs speech-to-text transcription service."""

    META = ProviderMeta(
        name="ElevenLabs",
        provider_key="elevenlabs",
        supported_features=["timestamps", "language_detection", "basic_transcription"],
        api_key_env="ELEVENLABS_API_KEY",
        api_key_min_length=10,
        sdk_imports=["elevenlabs"],
        install_command="uv add elevenlabs",
    )

    # File size limits - use centralized constants
    MAX_FILE_SIZE_MB = Limits.MAX_FILE_SIZE_MB
    CHUNK_SIZE = Limits.CHUNK_SIZE
    MAX_MEMORY_SIZE = Limits.MAX_MEMORY_BUFFER

    def __init__(
        self,
        api_key: str | None = None,
        circuit_config: CircuitBreakerConfig | None = None,
        retry_config: RetryConfig | None = None,
    ) -> None:
        """Initialize the ElevenLabs transcriber with API key and configurations."""
        retry_config, circuit_config = get_default_configs(retry_config, circuit_config)
        super().__init__(api_key, circuit_config, retry_config)
        
        self.api_key = self._resolve_api_key()
        
        if not PROVIDER_AVAILABLE:
            raise ImportError("ElevenLabs SDK not available. Install with: uv add elevenlabs")

        if not self.api_key:
            raise ValueError(
                "ELEVENLABS_API_KEY not found. Set it as environment variable or pass to constructor."
            )

    async def health_check_async(self) -> dict[str, Any]:
        """Perform health check for ElevenLabs service."""
        async def _check() -> dict[str, Any]:
            if not PROVIDER_AVAILABLE:
                return {"healthy": False, "status": "sdk_not_available", "error": "ElevenLabs SDK not installed"}

            client = ElevenLabsClient(api_key=self.api_key)
            config = get_config()
            response = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(None, lambda: client.user.get_user_info()),
                timeout=float(config.connect_timeout),
            )

            return {
                "healthy": True,
                "status": "operational",
                "api_accessible": True,
                "authentication": "valid",
                "user_id": getattr(response, "user_id", "unknown"),
            }

        return await self._run_health_check(_check)

    def _validate_file_size(self, audio_file_path: Path) -> float:
        """Validate file size against ElevenLabs limits."""
        from ..exceptions import FileSizeError

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
        return file_size_mb

    def _load_audio_data(self, audio_file_path: Path, file_size_mb: float) -> bytes:
        """Load audio data, using chunked reading for large files."""
        if file_size_mb * 1024 * 1024 > self.MAX_MEMORY_SIZE:
            logger.info(f"Using streaming approach for large file ({file_size_mb:.2f}MB)")
            return self._read_file_chunked(audio_file_path)
        with open(audio_file_path, "rb") as audio_file:
            return audio_file.read()

    def _extract_transcript(self, response: Any) -> str:
        """Extract transcript text from response."""
        if hasattr(response, "text") and response.text is not None:
            return response.text
        if hasattr(response, "transcript") and response.transcript is not None:
            return response.transcript
        return str(response)

    def _build_result(
        self, response: Any, transcript: str, audio_file_path: Path, duration: float
    ) -> TranscriptionResult:
        """Build TranscriptionResult from response."""
        result = TranscriptionResult(
            transcript=transcript,
            duration=duration,
            generated_at=datetime.now(),
            audio_file=str(audio_file_path),
            provider_name=self.get_provider_name(),
            provider_features=self.get_supported_features(),
        )

        if hasattr(response, "segments") and response.segments:
            if result.utterances is None:
                result.utterances = []
            for segment in response.segments:
                result.utterances.append(
                    TranscriptionUtterance(
                        speaker=0,
                        start=getattr(segment, "start", 0.0),
                        end=getattr(segment, "end", duration),
                        text=getattr(segment, "text", ""),
                    )
                )
        return result

    @provider_error_handler("elevenlabs", "uv add elevenlabs")
    async def _transcribe_impl(
        self, audio_file_path: Path, language: str = "en"
    ) -> TranscriptionResult | None:
        """Internal transcription implementation."""
        audio_file_path, file_size_mb = self._validate_audio_input(audio_file_path)

        if not PROVIDER_AVAILABLE:
            raise ImportError("ElevenLabs SDK not available")

        response = await self._call_elevenlabs_api(audio_file_path, file_size_mb, language)
        return self._process_response(response, audio_file_path)

    def _validate_audio_input(self, audio_file_path: Path) -> tuple[Path, float]:
        """Validate audio file and return validated path with file size."""
        validated_path = validate_audio_file_or_raise(
            audio_file_path,
            max_file_size=self.MAX_FILE_SIZE_MB * 1024 * 1024,
            provider_name="elevenlabs",
        )
        file_size_mb = self._validate_file_size(validated_path)
        return validated_path, file_size_mb

    async def _call_elevenlabs_api(
        self, audio_file_path: Path, file_size_mb: float, language: str
    ) -> Any:
        """Call ElevenLabs API and return response."""
        logger.info(f"Starting ElevenLabs transcription: {audio_file_path} ({file_size_mb:.2f}MB)")

        client = ElevenLabsClient(api_key=self.api_key)
        audio_data = self._load_audio_data(audio_file_path, file_size_mb)

        logger.info("Sending to ElevenLabs...")
        config = get_config()
        return await asyncio.wait_for(
            asyncio.get_event_loop().run_in_executor(
                None,
                lambda: client.speech_to_text.convert(
                    file=audio_data,
                    model_id="eleven_multilingual_sts_v2",
                    language_code=language if language else None,
                ),
            ),
            timeout=config.ELEVENLABS_TIMEOUT,
        )

    def _process_response(self, response: Any, audio_file_path: Path) -> TranscriptionResult:
        """Process API response into TranscriptionResult."""
        transcript = self._extract_transcript(response)
        duration = self._estimate_audio_duration(audio_file_path)
        result = self._build_result(response, transcript, audio_file_path, duration)
        logger.info(f"Transcription completed. Length: {len(transcript)} characters")
        return result

    def _check_file_size(self, file_path: Path) -> None:
        """Validate file size is within memory limits."""
        file_size = file_path.stat().st_size
        if file_size > self.MAX_MEMORY_SIZE:
            raise MemoryError(f"File size {file_size} exceeds memory limit {self.MAX_MEMORY_SIZE}")

    def _read_chunks(self, file_path: Path) -> list[bytes]:
        """Read file in chunks with memory safety checks."""
        chunks = []
        total_read = 0
        with open(file_path, "rb") as f:
            while chunk := f.read(self.CHUNK_SIZE):
                chunks.append(chunk)
                total_read += len(chunk)
                if total_read > self.MAX_MEMORY_SIZE:
                    raise MemoryError("File reading exceeded memory limit")
        return chunks

    def _join_chunks(self, chunks: list[bytes]) -> bytes:
        """Join chunks efficiently based on count."""
        if len(chunks) > 100:
            result = bytearray()
            for chunk in chunks:
                result.extend(chunk)
            return bytes(result)
        return b"".join(chunks)

    def _read_file_chunked(self, file_path: Path) -> bytes:
        """Read file in chunks to manage memory usage."""
        try:
            self._check_file_size(file_path)
            chunks = self._read_chunks(file_path)
            return self._join_chunks(chunks)
        except OSError as e:
            logger.error(f"Failed to read file {file_path}: {e}")
            raise OSError(f"Cannot read file: {file_path}") from e

    def _estimate_audio_duration(self, audio_file_path: Path) -> float:
        """Estimate audio duration from file using ffprobe."""
        try:
            cmd = [
                "ffprobe",
                "-v",
                "quiet",
                "-print_format",
                "json",
                "-show_entries",
                "format=duration",
                str(audio_file_path),
            ]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10.0,
                check=False,
            )

            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout)
                raw_duration = data.get("format", {}).get("duration")
                if raw_duration:
                    duration = float(raw_duration)
                    if duration > 0:
                        return duration
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.debug(f"Failed to parse ffprobe output: {e}")
        except FileNotFoundError:
            logger.debug("ffprobe not found in PATH - using fallback duration estimation")
        except subprocess.TimeoutExpired:
            logger.debug("ffprobe timed out - using fallback duration estimation")
        except Exception as e:
            logger.debug(f"ffprobe failed, using fallback estimation: {e}")

        # Fallback: rough estimation based on file size and typical bitrates
        try:
            file_size_bytes = audio_file_path.stat().st_size
            estimated_duration = (file_size_bytes * 8) / (128 * 1000)
            return max(1.0, estimated_duration)
        except OSError as e:
            logger.warning(f"Failed to get file size for duration estimation: {e}")
            return 1.0
