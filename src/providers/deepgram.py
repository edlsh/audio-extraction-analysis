"""Deepgram Nova 3 transcription provider implementation.

This module provides a full-featured transcription service using Deepgram's Nova 3 model,
supporting advanced capabilities including speaker diarization, topic detection, intent
analysis, sentiment analysis, and automatic summarization. The implementation uses streaming
uploads for memory efficiency and includes comprehensive error handling, retry logic, and
circuit breaker patterns for production reliability.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from datetime import datetime
from typing import TYPE_CHECKING, Any, BinaryIO

if TYPE_CHECKING:
    from pathlib import Path

    from ..utils.retry import RetryConfig

try:
    from deepgram import DeepgramClient, PrerecordedOptions

    # For response type, we might need to be generic if we don't know the exact class structure
    # or use a Protocol. For now, we'll try to use specific types if available or Any if not sure.
except ImportError:
    pass

from ..config import get_config
from ..models.transcription import (
    TranscriptionChapter,
    TranscriptionResult,
    TranscriptionSpeaker,
    TranscriptionUtterance,
)
from ..utils.file_validation import safe_validate_audio_file
from .base import BaseTranscriptionProvider, CircuitBreakerConfig
from .deepgram_utils import build_prerecorded_options
from .deepgram_utils import detect_mimetype as _dg_detect_mimetype
from .provider_utils import get_default_configs, provider_error_handler

logger = logging.getLogger(__name__)

# Check for Deepgram SDK availability
try:
    from deepgram import DeepgramClient, PrerecordedOptions

    PROVIDER_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Deepgram provider dependencies not installed: {e}")
    PROVIDER_AVAILABLE = False
    DeepgramClient = None
    PrerecordedOptions = None


class DeepgramTranscriber(BaseTranscriptionProvider):
    """Deepgram Nova 3 transcription provider with comprehensive AI-powered features.

    This provider implements the Deepgram Nova 3 transcription engine with support for:
    - Speaker diarization (identifying and separating speakers)
    - Topic detection and chapter segmentation
    - Intent analysis (detecting user goals and actions)
    - Sentiment analysis (positive/negative/neutral detection)
    - Automatic summarization
    - Language detection and multi-language support
    - Smart formatting with punctuation and paragraphs

    The implementation uses streaming uploads to handle large audio files efficiently,
    includes retry logic with exponential backoff, and implements circuit breaker patterns
    for fault tolerance in production environments.
    """

    # ---------------------- Internal helpers (extracted) ----------------------
    def _create_client(self) -> DeepgramClient:
        """Create and return a Deepgram client configured for production use.

        The client is configured with:
        - 600 second (10 minute) timeout to handle large audio files
        - API key from instance configuration
        - Environment-based configuration options

        Returns:
            DeepgramClient: Configured Deepgram SDK client instance ready for API calls
        """
        # Import Deepgram SDK lazily to avoid import-time failures when optional
        from deepgram import ClientOptionsFromEnv, DeepgramClient

        # 10 minute timeout (large files can take time)
        config = ClientOptionsFromEnv(options={"timeout": 600})
        return DeepgramClient(self.api_key, config=config)

    def _build_options(self, language: str) -> PrerecordedOptions:
        """Build PrerecordedOptions for Nova-3 with all AI features enabled.

        Configures the Deepgram API request to enable speaker diarization, topic detection,
        intent analysis, sentiment analysis, summarization, and smart formatting.

        Args:
            language: ISO 639-1 language code (e.g., 'en', 'es', 'fr') for transcription

        Returns:
            PrerecordedOptions: Fully configured options object for the Deepgram API
        """
        return build_prerecorded_options(language)

    def _detect_mimetype(self, path: Path) -> str:
        """Detect audio file MIME type based on file extension.

        Uses a lookup table of common audio file extensions to determine the appropriate
        MIME type for the Deepgram API. Falls back to 'audio/mp3' for unrecognized
        extensions to maintain backward compatibility.

        Args:
            path: Path object pointing to the audio file

        Returns:
            str: MIME type string (e.g., 'audio/wav', 'audio/mp3', 'audio/flac')
        """
        return _dg_detect_mimetype(path)

    def _open_audio_file(self, audio_file_path: Path) -> Any:  # BinaryIO
        """Open audio file for streaming upload to Deepgram API.

        Opens the file in binary read mode and returns a file handle rather than loading
        the entire file into memory. This streaming approach enables processing of large
        audio files (GB+) with constant memory usage, preventing out-of-memory errors.

        Args:
            audio_file_path: Path to the audio file to open

        Returns:
            BinaryIO: File handle opened in binary read mode ('rb')

        Raises:
            FileNotFoundError: If the audio file doesn't exist at the specified path
            PermissionError: If the process lacks read permissions for the file
            OSError: For other I/O errors (disk failures, invalid paths, etc.)
        """
        return open(audio_file_path, "rb")

    def _submit_transcription_job(
        self,
        client: DeepgramClient,
        audio_source: Any,  # BinaryIO
        mimetype: str,
        options: PrerecordedOptions,
    ) -> Any:  # PrerecordedResponseProtocol or Any since response structure is complex
        """Submit the prerecorded transcription request to Deepgram API with streaming.

        Uses the Deepgram SDK's file streaming capabilities to upload audio data efficiently.
        The SDK handles chunked uploads internally when a file handle is provided, reducing
        memory overhead compared to loading the entire file.

        Args:
            client: Configured DeepgramClient instance
            audio_source: File handle (BinaryIO) opened in binary read mode
            mimetype: MIME type string for the audio file (e.g., 'audio/wav')
            options: PrerecordedOptions with enabled features and language settings

        Returns:
            PrerecordedResponse: Deepgram API response containing transcription results,
                metadata, and enabled feature outputs (speakers, topics, intents, etc.)

        Raises:
            ConnectionError: If the API request fails due to network issues
            TimeoutError: If the request exceeds the configured timeout
            ValueError: If the API rejects the request due to invalid parameters
        """
        # DG SDK: deepgram.listen.prerecorded.v("1").transcribe_file(...)
        # Pass file handle directly - SDK should handle streaming internally
        return client.listen.prerecorded.v("1").transcribe_file(
            source={"buffer": audio_source, "mimetype": mimetype}, options=options
        )

    def _extract_topics(self, response: Any, result: TranscriptionResult, duration: float) -> None:
        """Extract topics and chapters from response."""
        if not hasattr(response.results, "topics") or not response.results.topics:
            return
        for topic_segment in response.results.topics.segments:
            chapter = TranscriptionChapter(
                start_time=getattr(topic_segment, "start_time", 0),
                end_time=getattr(topic_segment, "end_time", duration),
                topics=[t.topic for t in topic_segment.topics],
                confidence_scores=[
                    getattr(t, "confidence_score", 0.0) for t in topic_segment.topics
                ],
            )
            result.chapters.append(chapter)
            for topic in topic_segment.topics:
                tname = topic.topic
                result.topics[tname] = result.topics.get(tname, 0) + 1

    def _extract_intents(self, response: Any, result: TranscriptionResult) -> None:
        """Extract intents from response."""
        if not hasattr(response.results, "intents") or not response.results.intents:
            return
        for segment in response.results.intents.segments:
            for intent in segment.intents:
                result.intents.append(intent.intent)

    def _extract_sentiments(self, response: Any, result: TranscriptionResult) -> None:
        """Extract sentiment distribution from response."""
        if not hasattr(response.results, "sentiments") or not response.results.sentiments:
            return
        for segment in response.results.sentiments.segments:
            if hasattr(segment, "sentiment"):
                s = segment.sentiment
                result.sentiment_distribution[s] = result.sentiment_distribution.get(s, 0) + 1

    def _extract_utterances(
        self, response: Any, result: TranscriptionResult, duration: float
    ) -> None:
        """Extract speaker utterances and calculate speaker statistics."""
        if not hasattr(response.results, "utterances") or not response.results.utterances:
            return

        speaker_times: dict[int, float] = {}
        for utterance in response.results.utterances:
            speaker_id = utterance.speaker
            duration_segment = utterance.end - utterance.start
            speaker_times[speaker_id] = speaker_times.get(speaker_id, 0.0) + duration_segment
            result.utterances.append(
                TranscriptionUtterance(
                    speaker=speaker_id,
                    start=utterance.start,
                    end=utterance.end,
                    text=utterance.transcript,
                )
            )

        safe_total = duration if duration and duration > 0 else 1.0
        for speaker_id, total_time in speaker_times.items():
            percentage = (total_time / safe_total) * 100 if safe_total > 0 else 0.0
            result.speakers.append(
                TranscriptionSpeaker(id=speaker_id, total_time=total_time, percentage=percentage)
            )

    def _parse_response(
        self,
        response: Any,
        audio_file_path: Path,
        language: str,
    ) -> TranscriptionResult:
        """Parse Deepgram API response into structured TranscriptionResult."""
        transcript = response.results.channels[0].alternatives[0].transcript
        duration = response.metadata.duration

        result = TranscriptionResult(
            transcript=transcript,
            duration=duration,
            generated_at=datetime.now(),
            audio_file=str(audio_file_path),
            provider_name=self.get_provider_name(),
            provider_features=self.get_supported_features(),
        )

        if hasattr(response.results, "summary") and response.results.summary:
            result.summary = response.results.summary.short

        self._extract_topics(response, result, duration)
        self._extract_intents(response, result)
        self._extract_sentiments(response, result)
        self._extract_utterances(response, result, duration)

        return result

    def _log_file_info(self, audio_file_path: Path) -> None:
        """Log audio file size information for debugging and monitoring.

        Args:
            audio_file_path: Path to the audio file to inspect
        """
        try:
            file_size_mb = audio_file_path.stat().st_size / (1024 * 1024)
            logger.info(f"File size: {file_size_mb:.2f} MB")
        except Exception:
            # Non-fatal
            logger.debug("Could not determine file size for logging.")

    def __init__(
        self,
        api_key: str | None = None,
        circuit_config: CircuitBreakerConfig | None = None,
        retry_config: RetryConfig | None = None,
    ) -> None:
        """Initialize the transcriber with API key and configurations.

        Args:
            api_key: Optional Deepgram API key. If None, uses get_config().DEEPGRAM_API_KEY
            circuit_config: Circuit breaker configuration
            retry_config: Retry configuration
        """
        retry_config, circuit_config = get_default_configs(retry_config, circuit_config)

        super().__init__(api_key, circuit_config, retry_config)
        self.api_key = api_key or get_config().DEEPGRAM_API_KEY
        if not self.api_key:
            raise ValueError(
                "DEEPGRAM_API_KEY not found. Set it as environment variable or pass to constructor."
            )

    def validate_configuration(self) -> bool:
        """Validate that Deepgram is properly configured.

        Returns:
            True if configuration is valid, False otherwise
        """
        return bool(self.api_key)

    def get_provider_name(self) -> str:
        """Get the name of this transcription provider.

        Returns:
            Human-readable name of the provider
        """
        return "Deepgram Nova 3"

    def get_supported_features(self) -> list[str]:
        """Get list of features supported by Deepgram Nova 3.

        Returns:
            List of feature names supported by this provider
        """
        return [
            "speaker_diarization",
            "topic_detection",
            "intent_analysis",
            "sentiment_analysis",
            "timestamps",
            "summarization",
            "language_detection",
            "punctuation",
            "paragraphs",
            "smart_format",
        ]

    async def health_check_async(self) -> dict[str, Any]:
        """Perform health check for Deepgram service availability and configuration.

        Validates the Deepgram provider by checking:
        - API key format and presence
        - SDK availability and import success
        - Client instantiation capability

        Note: This is a lightweight check that validates configuration and SDK availability
        but does not make actual API calls to Deepgram servers.

        Returns:
            Dict[str, Any]: Health status dictionary with keys:
                - healthy (bool): Overall health status
                - status (str): Status code (operational/invalid_api_key/sdk_not_available/error)
                - response_time_ms (float): Check duration in milliseconds
                - details (dict): Provider-specific diagnostic information
        """
        start_time = time.time()

        try:
            # Import Deepgram SDK
            from deepgram import DeepgramClient

            # Validate API key format - Deepgram keys are typically 32-64 hex characters
            if not self.api_key or len(self.api_key) < 20:
                return self._build_health_response(
                    healthy=False,
                    status="invalid_api_key",
                    response_time_ms=(time.time() - start_time) * 1000,
                    error="API key appears to be invalid or missing",
                )

            # Try to create a client instance
            try:
                DeepgramClient(self.api_key)
                response_time = (time.time() - start_time) * 1000

                return self._build_health_response(
                    healthy=True,
                    status="operational",
                    response_time_ms=response_time,
                    api_accessible=True,
                    authentication="key_format_valid",
                    note="Health check validates SDK and key format only",
                )
            except Exception as client_error:
                return self._build_health_response(
                    healthy=False,
                    status="client_creation_failed",
                    response_time_ms=(time.time() - start_time) * 1000,
                    error=f"Failed to create client: {client_error!s}",
                )

        except ImportError:
            return self._build_health_response(
                healthy=False,
                status="sdk_not_available",
                response_time_ms=(time.time() - start_time) * 1000,
                error="Deepgram SDK not installed",
            )
        except Exception as e:
            return self._build_health_response(
                healthy=False,
                status="error",
                response_time_ms=(time.time() - start_time) * 1000,
                error=str(e),
                error_type=type(e).__name__,
            )

    @provider_error_handler("deepgram", "uv add deepgram-sdk")
    async def _transcribe_impl(
        self, audio_file_path: Path, language: str = "en"
    ) -> TranscriptionResult | None:
        """Internal transcription implementation without retry/circuit breaker logic.

        Args:
            audio_file_path: Path to audio file
            language: Language code for transcription

        Returns:
            TranscriptionResult with all features, or None if failed

        Raises:
            ProviderNotAvailableError: If Deepgram SDK not installed
            ValidationError: If audio file validation fails or file not found
            FileAccessError: If file permissions prevent access
            ProviderAPIError: If Deepgram API returns an error
            ProviderTimeoutError: If request times out
        """
        from ..exceptions import ValidationError

        # Validate audio file
        validated_path = safe_validate_audio_file(audio_file_path, provider_name="deepgram")
        if validated_path is None:
            raise ValidationError(
                f"Audio file validation failed: {audio_file_path}",
                context={"file_path": str(audio_file_path), "provider": "deepgram"},
            )
        audio_file_path = validated_path

        logger.info(f"Starting Deepgram Nova 3 transcription: {audio_file_path}")
        self._log_file_info(audio_file_path)

        # Build request
        client = self._create_client()
        options = self._build_options(language)
        mimetype = self._detect_mimetype(audio_file_path)

        # Submit transcription job using file handle for efficient streaming upload
        # This prevents loading entire file into memory for large audio files
        logger.info("Sending to Deepgram Nova 3 with streaming upload...")
        with self._open_audio_file(audio_file_path) as audio_source:
            response = self._submit_transcription_job(client, audio_source, mimetype, options)
        logger.info("Transcription completed successfully")

        # Parse and return
        return self._parse_response(response, audio_file_path, language)

    def transcribe(
        self,
        audio_file_path: Path,
        language: str = "en",
        *,
        timeout: float | None = None,
    ) -> TranscriptionResult | None:
        """Synchronous transcription method for blocking I/O contexts.

        This method provides a synchronous interface to the async transcription implementation.
        It handles event loop management internally and is safe to call from non-async code.
        Prefer using `transcribe_async()` directly if you're already in an async context.

        Args:
            audio_file_path: Path to the audio file to transcribe
            language: ISO 639-1 language code (default: 'en')
            timeout: Optional timeout (seconds) applied to the async implementation

        Returns:
            TranscriptionResult: Complete transcription result with all features

        Raises:
            ProviderAPIError: If transcription fails
            AudioFileNotFoundError: If audio file not found
            ProviderNotAvailableError: If Deepgram SDK not installed

        Note:
            This method creates its own event loop. If called from an existing async context,
            it will attempt to create a new loop to avoid conflicts.
        """
        from .provider_utils import map_provider_error

        loop: asyncio.AbstractEventLoop | None = None
        try:
            return asyncio.run(self.transcribe_async(audio_file_path, language, timeout=timeout))
        except RuntimeError as re:
            # Check if this is the "running event loop" edge case
            if (
                "running event loop" not in str(re).lower()
                and "cannot be called" not in str(re).lower()
            ):
                # Not an event loop conflict - map and re-raise the error
                raise map_provider_error(
                    re, "deepgram", audio_file_path, install_command="uv add deepgram-sdk"
                ) from re
            # Handle edge case: if called from async context with running event loop,
            # create a new isolated loop to avoid conflicts
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                return loop.run_until_complete(
                    self.transcribe_async(audio_file_path, language, timeout=timeout)
                )
            except Exception as inner:
                raise map_provider_error(
                    inner, "deepgram", audio_file_path, install_command="uv add deepgram-sdk"
                ) from inner
            finally:
                if loop is not None:
                    try:
                        loop.close()
                    except RuntimeError:
                        pass  # Loop already closed or running
        except Exception as exc:
            # Catch any provider exceptions (ProviderAPIError, ValidationError,
            # AudioFileNotFoundError, etc.) from the initial asyncio.run() and map them
            raise map_provider_error(
                exc, "deepgram", audio_file_path, install_command="uv add deepgram-sdk"
            ) from exc
