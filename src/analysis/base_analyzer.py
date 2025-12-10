"""Base class for transcript analyzers containing shared heuristics."""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.utils.logger import get_logger

from ..utils.constants import AnalysisConstants
from ..utils.formatting import format_duration, format_timestamp

if TYPE_CHECKING:
    from ..models.transcription import TranscriptionResult, TranscriptionUtterance

logger = get_logger(__name__)


class BaseAnalyzer:
    """Base class providing common analysis logic."""

    def _format_duration(self, seconds: float) -> str:
        """Format duration in seconds to HH:MM:SS or MM:SS format."""
        return format_duration(seconds, style="compact")

    def _fallback_summary(self, transcript: str) -> str:
        """Generate a simple fallback summary when no AI-generated summary is available.

        Extracts either the first few sentences or the first few characters from
        the transcript to create a basic summary.

        Args:
            transcript: Raw transcript text

        Returns:
            Simple summary text.
        """
        if not transcript:
            return "No summary available."

        # Split by period and filter out empty strings
        sentences = [s.strip() for s in transcript.split(".") if s.strip()]

        if len(sentences) >= AnalysisConstants.SUMMARY_SENTENCE_COUNT:
            # We have enough sentences - use them as summary
            return ". ".join(sentences[: AnalysisConstants.SUMMARY_SENTENCE_COUNT]) + "."

        # Fewer than threshold sentences - truncate
        limit = AnalysisConstants.SUMMARY_CHAR_LIMIT
        return (transcript[:limit] + ("..." if len(transcript) > limit else "")).strip()

    def _find_action_sentences(self, transcript: str) -> list[str]:
        """Extract sentences containing action-oriented keywords.

        Uses a heuristic approach to identify actionable content by searching for
        sentences containing specific keywords defined in AnalysisConstants.

        Args:
            transcript: Raw transcript text

        Returns:
            List of sentences (strings) containing at least one action keyword.
        """
        if not transcript:
            return []

        sentences = [s.strip() for s in transcript.split(".") if s.strip()]

        # Check against keywords
        action_sentences = []
        for sentence in sentences:
            # Filter very short sentences to reduce noise
            if len(sentence) < 20:
                continue

            sentence_lower = sentence.lower()
            if any(k in sentence_lower for k in AnalysisConstants.ACTION_KEYWORDS):
                action_sentences.append(sentence)

        return action_sentences

    def _format_timestamp(self, seconds: float) -> str:
        """Format seconds as HH:MM:SS timestamp string.

        Args:
            seconds: Time in seconds

        Returns:
            Formatted string like "01:23:45" or "00:05:30"
        """
        return format_timestamp(seconds)

    def _get_sentiment_emoji(self, sentiment: str) -> str:
        """Get emoji representation for sentiment category.

        Args:
            sentiment: Sentiment category name (case-insensitive).

        Returns:
            Corresponding emoji: "😊" for positive, "😔" for negative,
            "😐" for neutral, or "🤔" for unknown/unrecognized sentiments.
        """
        sentiment_map = {"positive": "😊", "negative": "😔", "neutral": "😐"}
        return sentiment_map.get(sentiment.lower(), "🤔")
