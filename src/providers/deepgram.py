"""Deepgram Nova 3 transcription provider implementation.

This module provides a full-featured transcription service using Deepgram's Nova 3 model,
supporting advanced capabilities including speaker diarization, topic detection, intent
analysis, sentiment analysis, and automatic summarization.
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime
from typing import TYPE_CHECKING, Any, BinaryIO

from src.utils.logger import get_logger

if TYPE_CHECKING:
    from pathlib import Path

    from ..utils.retry import RetryConfig

from ..config import get_config
from ..models.transcription import (
    TranscriptionChapter,
    TranscriptionResult,
    TranscriptionSpeaker,
    TranscriptionUtterance,
)
from ..utils.file_validation import validate_audio_file_or_raise
from .base import BaseTranscriptionProvider, CircuitBreakerConfig, ProviderMeta
from .deepgram_utils import build_prerecorded_options
from .deepgram_utils import detect_mimetype as _dg_detect_mimetype
from .provider_utils import check_sdk_available, get_default_configs, provider_error_handler

logger = get_logger(__name__)

# Threshold for streaming upload (100MB) - files larger than this use streaming
STREAMING_THRESHOLD_BYTES = 100 * 1024 * 1024


class DeepgramTranscriber(BaseTranscriptionProvider):
    """Deepgram Nova 3 transcription provider with comprehensive AI-powered features."""

    META = ProviderMeta(
        name="Deepgram Nova 3",
        provider_key="deepgram",
        supported_features=[
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
        ],
        api_key_env="DEEPGRAM_API_KEY",
        api_key_min_length=20,
        sdk_imports=["deepgram"],
        install_command="uv add deepgram-sdk",
    )

    def __init__(
        self,
        api_key: str | None = None,
        circuit_config: CircuitBreakerConfig | None = None,
        retry_config: RetryConfig | None = None,
    ) -> None:
        """Initialize the transcriber with API key and configurations."""
        retry_config, circuit_config = get_default_configs(retry_config, circuit_config)
        super().__init__(api_key, circuit_config, retry_config)
        self.api_key = self._resolve_api_key()
        if not self.api_key:
            raise ValueError(
                "DEEPGRAM_API_KEY not found. Set it as environment variable or pass to constructor."
            )

    # ---------------------- Internal helpers ----------------------
    def _create_client(self) -> Any:
        """Create and return a Deepgram client."""
        from deepgram import DeepgramClient

        return DeepgramClient(api_key=self.api_key)

    def _log_file_info(self, audio_file_path: Path) -> None:
        """Log audio file size information."""
        try:
            file_size_mb = audio_file_path.stat().st_size / (1024 * 1024)
            logger.info(f"File size: {file_size_mb:.2f} MB")
        except OSError as e:
            logger.debug("Could not determine file size for logging: %s", e)

    def _get_file_size(self, audio_file_path: Path) -> int:
        """Get file size in bytes."""
        try:
            return audio_file_path.stat().st_size
        except OSError as e:
            logger.debug("Could not determine file size: %s", e)
            return 0

    def _submit_transcription_job_streaming(
        self, client: Any, audio_file: BinaryIO, language: str
    ) -> Any:
        """Submit transcription using file handle for streaming upload (large files)."""
        return client.listen.v1.media.transcribe_file(
            request=audio_file,
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

    def _submit_transcription_job(self, client: Any, audio_bytes: bytes, language: str) -> Any:
        """Submit the prerecorded transcription request to Deepgram API (small files)."""
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
        if not results:
            return
        topics_obj = getattr(results, "topics", None)
        if not topics_obj:
            return
        topics_results = getattr(topics_obj, "results", topics_obj)
        if not topics_results:
            return
        topics_data = getattr(topics_results, "topics", topics_results)
        if not topics_data:
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
        if not results:
            return
        intents_obj = getattr(results, "intents", None)
        if not intents_obj:
            return
        intents_results = getattr(intents_obj, "results", intents_obj)
        if not intents_results:
            return
        intents_data = getattr(intents_results, "intents", intents_results)
        if not intents_data:
            return
        segments = getattr(intents_data, "segments", None)
        if not segments:
            return
        for segment in segments:
            for intent in getattr(segment, "intents", []):
                intent_name = getattr(intent, "intent", "")
                if intent_name:
                    result.intents.append(intent_name)

    def _extract_sentiments(self, response: Any, result: TranscriptionResult) -> None:
        """Extract sentiment distribution from response."""
        results = getattr(response, "results", None)
        if not results:
            return
        sentiments_obj = getattr(results, "sentiments", None)
        if not sentiments_obj:
            return
        for segment in getattr(sentiments_obj, "segments", []):
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
        if not results:
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
            speaker_times[speaker_id] = speaker_times.get(speaker_id, 0.0) + (end - start)
            result.utterances.append(
                TranscriptionUtterance(
                    speaker=speaker_id, start=start, end=end, text=transcript_text
                )
            )

        safe_total = duration if duration and duration > 0 else 1.0
        for speaker_id, total_time in speaker_times.items():
            percentage = (total_time / safe_total) * 100 if safe_total > 0 else 0.0
            result.speakers.append(
                TranscriptionSpeaker(id=speaker_id, total_time=total_time, percentage=percentage)
            )

    def _parse_response(
        self, response: Any, audio_file_path: Path, language: str
    ) -> TranscriptionResult:
        """Parse Deepgram API response into structured TranscriptionResult."""
        results = getattr(response, "results", None)
        metadata = getattr(response, "metadata", None)

        channels = getattr(results, "channels", []) if results else []
        transcript = ""
        if channels:
            alternatives = getattr(channels[0], "alternatives", [])
            if alternatives:
                transcript = getattr(alternatives[0], "transcript", "")

        duration = getattr(metadata, "duration", 0.0) if metadata else 0.0

        result = TranscriptionResult(
            transcript=transcript,
            duration=duration,
            generated_at=datetime.now(),
            audio_file=str(audio_file_path),
            provider_name=self.get_provider_name(),
            provider_features=self.get_supported_features(),
        )

        if results:
            summary_obj = getattr(results, "summary", None)
            if summary_obj:
                result.summary = getattr(summary_obj, "short", "")

        self._extract_topics(response, result, duration)
        self._extract_intents(response, result)
        self._extract_sentiments(response, result)
        self._extract_utterances(response, result, duration)

        return result

    # ---------------------- Public API ----------------------
    async def health_check_async(self) -> dict[str, Any]:
        """Perform health check for Deepgram service."""

        async def _check() -> dict[str, Any]:
            from deepgram import DeepgramClient

            if not self.api_key or len(self.api_key) < self.META.api_key_min_length:
                return {
                    "healthy": False,
                    "status": "invalid_api_key",
                    "error": "API key appears to be invalid or missing",
                }

            DeepgramClient(self.api_key)
            return {
                "healthy": True,
                "status": "operational",
                "api_accessible": True,
                "authentication": "key_format_valid",
            }

        return await self._run_health_check(_check)

    @provider_error_handler("deepgram", "uv add deepgram-sdk")
    async def _transcribe_impl(
        self, audio_file_path: Path, language: str = "en"
    ) -> TranscriptionResult | None:
        """Internal transcription implementation.

        Uses streaming upload for files larger than 100MB to avoid memory issues.
        """
        audio_file_path = validate_audio_file_or_raise(audio_file_path, provider_name="deepgram")

        logger.info(f"Starting Deepgram Nova 3 transcription: {audio_file_path}")
        self._log_file_info(audio_file_path)

        client = self._create_client()
        file_size = self._get_file_size(audio_file_path)

        if file_size > STREAMING_THRESHOLD_BYTES:
            # Large file: use streaming upload to avoid loading entire file into memory
            logger.info(
                f"Using streaming upload for large file ({file_size / (1024 * 1024):.1f} MB)"
            )
            with open(audio_file_path, "rb") as audio_file:
                response = self._submit_transcription_job_streaming(client, audio_file, language)
        else:
            # Small file: load into memory for simpler handling
            logger.info("Sending to Deepgram Nova 3...")
            audio_bytes = audio_file_path.read_bytes()
            response = self._submit_transcription_job(client, audio_bytes, language)

        logger.info("Transcription completed successfully")
        return self._parse_response(response, audio_file_path, language)
