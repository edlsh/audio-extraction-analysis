"""Deepgram Nova 3 transcription provider implementation.

This module provides a full-featured transcription service using Deepgram's Nova 3 model,
supporting advanced capabilities including speaker diarization, topic detection, intent
analysis, sentiment analysis, and automatic summarization. The implementation uses streaming
uploads for memory efficiency and includes comprehensive error handling, retry logic, and
circuit breaker patterns for production reliability.
"""

from __future__ import annotations

import asyncio
import os
import time
from datetime import datetime
from typing import TYPE_CHECKING, Any, BinaryIO

from src.utils.logger import get_logger

if TYPE_CHECKING:
    from pathlib import Path

    from ..utils.retry import RetryConfig

try:
    from deepgram import DeepgramClient

    # SDK v5 uses dicts for options instead of PrerecordedOptions class
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

logger = get_logger(__name__)

# Check for Deepgram SDK availability
try:
    from deepgram import DeepgramClient

    PROVIDER_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Deepgram provider dependencies not installed: {e}")
    PROVIDER_AVAILABLE = False
    DeepgramClient = None


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

        Returns:
            DeepgramClient: Configured Deepgram SDK client instance ready for API calls
        """
        from deepgram import DeepgramClient

        # SDK v5 uses simpler client initialization
        return DeepgramClient(api_key=self.api_key)

    def _build_options(self, language: str) -> dict:
        """Build options dict for Nova-3 with all AI features enabled.

        Configures the Deepgram API request to enable speaker diarization, topic detection,
        intent analysis, sentiment analysis, summarization, and smart formatting.

        Args:
            language: ISO 639-1 language code (e.g., 'en', 'es', 'fr') for transcription

        Returns:
            dict: Fully configured options dict for the Deepgram API
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
        audio_bytes: bytes,
        language: str,
    ) -> Any:
        """Submit the prerecorded transcription request to Deepgram API.

        Args:
            client: Configured DeepgramClient instance
            audio_bytes: Audio file contents as bytes
            language: Language code for transcription

        Returns:
            Response: Deepgram API response containing transcription results

        Raises:
            ConnectionError: If the API request fails due to network issues
            TimeoutError: If the request exceeds the configured timeout
            ValueError: If the API rejects the request due to invalid parameters
        """
        # DG SDK v5: use listen.v1.media.transcribe_file() with keyword args
        return client.listen.v1.media.transcribe_file(
            request=audio_bytes,
            model="nova-3",
            smart_format=True,
            utterances=True,
            punctuate=True,
            paragraphs=True,
            diarize=True,
            summarize="v2",
            topics=True,
            intents=True,
            sentiment=True,
            language=language,
            detect_language=True,
            request_options={"timeout_in_seconds": 600},
        )

    def _extract_topics(self, response: Any, result: TranscriptionResult, duration: float) -> None:
        """Extract topics and chapters from response."""
        results = getattr(response, "results", None)
        if results is None:
            return
        topics_obj = getattr(results, "topics", None)
        if topics_obj is None:
            return
        # SDK v5: topics.results.topics.segments
        topics_results = getattr(topics_obj, "results", topics_obj)
        if topics_results is None:
            return
        topics_data = getattr(topics_results, "topics", topics_results)
        if topics_data is None:
            return
        segments = getattr(topics_data, "segments", None)
        if not segments:
            return
        for topic_segment in segments:
            seg_topics = getattr(topic_segment, "topics", [])
            chapter = TranscriptionChapter(
                start_time=getattr(topic_segment, "start_time", 0),
                end_time=getattr(topic_segment, "end_time", duration),
                topics=[getattr(t, "topic", "") for t in seg_topics],
                confidence_scores=[getattr(t, "confidence_score", 0.0) for t in seg_topics],
            )
            result.chapters.append(chapter)
            for topic in seg_topics:
                tname = getattr(topic, "topic", "")
                if tname:
                    result.topics[tname] = result.topics.get(tname, 0) + 1

    def _extract_intents(self, response: Any, result: TranscriptionResult) -> None:
        """Extract intents from response."""
        results = getattr(response, "results", None)
        if results is None:
            return
        intents_obj = getattr(results, "intents", None)
        if intents_obj is None:
            return
        # SDK v5: intents.results.intents.segments
        intents_results = getattr(intents_obj, "results", intents_obj)
        if intents_results is None:
            return
        intents_data = getattr(intents_results, "intents", intents_results)
        if intents_data is None:
            return
        segments = getattr(intents_data, "segments", None)
        if not segments:
            return
        for segment in segments:
            seg_intents = getattr(segment, "intents", [])
            for intent in seg_intents:
                intent_name = getattr(intent, "intent", "")
                if intent_name:
                    result.intents.append(intent_name)

    def _extract_sentiments(self, response: Any, result: TranscriptionResult) -> None:
        """Extract sentiment distribution from response."""
        results = getattr(response, "results", None)
        if results is None:
            return
        sentiments_obj = getattr(results, "sentiments", None)
        if sentiments_obj is None:
            return
        segments = getattr(sentiments_obj, "segments", None)
        if not segments:
            return
        for segment in segments:
            sentiment = getattr(segment, "sentiment", None)
            if sentiment:
                result.sentiment_distribution[sentiment] = (
                    result.sentiment_distribution.get(sentiment, 0) + 1
                )

    def _extract_utterances(
        self, response: Any, result: TranscriptionResult, duration: float
    ) -> None:
        """Extract speaker utterances and calculate speaker statistics."""
        results = getattr(response, "results", None)
        if results is None:
            return
        utterances = getattr(results, "utterances", None)
        if not utterances:
            return

        speaker_times: dict[int, float] = {}
        for utterance in utterances:
            speaker_id = getattr(utterance, "speaker", 0)
            start = getattr(utterance, "start", 0.0)
            end = getattr(utterance, "end", 0.0)
            transcript_text = getattr(utterance, "transcript", "")
            duration_segment = end - start
            speaker_times[speaker_id] = speaker_times.get(speaker_id, 0.0) + duration_segment
            result.utterances.append(
                TranscriptionUtterance(
                    speaker=speaker_id,
                    start=start,
                    end=end,
                    text=transcript_text,
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
        # SDK v5: access via attributes with safe fallbacks
        results = getattr(response, "results", None)
        metadata = getattr(response, "metadata", None)

        # Get transcript from channels
        channels = getattr(results, "channels", []) if results else []
        transcript = ""
        if channels:
            alternatives = getattr(channels[0], "alternatives", [])
            if alternatives:
                transcript = getattr(alternatives[0], "transcript", "")

        # Get duration from metadata
        duration = getattr(metadata, "duration", 0.0) if metadata else 0.0

        result = TranscriptionResult(
            transcript=transcript,
            duration=duration,
            generated_at=datetime.now(),
            audio_file=str(audio_file_path),
            provider_name=self.get_provider_name(),
            provider_features=self.get_supported_features(),
        )

        # Extract summary if available
        if results:
            summary_obj = getattr(results, "summary", None)
            if summary_obj:
                result.summary = getattr(summary_obj, "short", "")

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

        # Read audio file as bytes for SDK v5
        logger.info("Sending to Deepgram Nova 3...")
        audio_bytes = audio_file_path.read_bytes()
        response = self._submit_transcription_job(client, audio_bytes, language)
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
