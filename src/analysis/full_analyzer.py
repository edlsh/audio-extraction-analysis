"""Full transcript analyzer generating 5 detailed markdown files.

Generates: executive summary, chapter overview, topics/intents,
full transcript, and key insights.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from src.utils.logger import get_logger

from .base_analyzer import BaseAnalyzer

if TYPE_CHECKING:
    from ..models.transcription import TranscriptionResult, TranscriptionUtterance

logger = get_logger(__name__)


class FullAnalyzer(BaseAnalyzer):
    """Generates 5 detailed markdown files from transcription results."""

    def analyze_and_save(
        self, result: TranscriptionResult, output_dir: Path, filename_base: str
    ) -> dict[str, Path]:
        """Generate 5 analysis markdown files and return their paths.

        Args:
            result: Rich transcription result containing transcript, speakers, chapters,
                topics, intents, sentiment data, and metadata
            output_dir: Directory where analysis files will be written. Created if needed.
            filename_base: Base name to include in metadata or for future identification.
                Currently used for potential file naming schemes but not in current output.

        Returns:
            Dictionary mapping logical file identifiers to their Path objects:
            - "executive_summary": Path to 01_executive_summary.md
            - "chapter_overview": Path to 02_chapter_overview.md
            - "topics_intents": Path to 03_key_topics_and_intents.md
            - "full_transcript": Path to 04_full_transcript_with_timestamps.md
            - "key_insights": Path to 05_key_insights_and_takeaways.md

        Example:
            >>> analyzer = FullAnalyzer()
            >>> paths = analyzer.analyze_and_save(
            ...     result=my_transcription,
            ...     output_dir=Path("./reports"),
            ...     filename_base="meeting_20240126"
            ... )
            >>> paths["executive_summary"].exists()
            True
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        paths = {
            "executive_summary": output_dir / "01_executive_summary.md",
            "chapter_overview": output_dir / "02_chapter_overview.md",
            "topics_intents": output_dir / "03_key_topics_and_intents.md",
            "full_transcript": output_dir / "04_full_transcript_with_timestamps.md",
            "key_insights": output_dir / "05_key_insights_and_takeaways.md",
        }

        paths["executive_summary"].write_text(
            self._render_executive_summary(result), encoding="utf-8"
        )
        paths["chapter_overview"].write_text(
            self._render_chapter_overview(result), encoding="utf-8"
        )
        paths["topics_intents"].write_text(
            self._render_topics_and_intents(result), encoding="utf-8"
        )
        paths["full_transcript"].write_text(self._render_full_transcript(result), encoding="utf-8")
        paths["key_insights"].write_text(self._render_key_insights(result), encoding="utf-8")

        logger.info("Full analysis generated: 5 markdown files")
        return paths

    # ---------------------- Renderers ----------------------
    def _render_executive_summary(self, result: TranscriptionResult) -> str:
        """Render the executive summary markdown file (01_executive_summary.md).

        Creates a high-level overview including session metadata, summary text,
        structural statistics, and navigation links to other analysis files.

        Args:
            result: TranscriptionResult containing all transcription data and metadata

        Returns:
            Formatted markdown string for the executive summary file
        """
        duration = self._format_timestamp(result.duration)
        speakers_count = len(result.speakers) if result.speakers else 0
        topic_count = len(result.topics or {})
        intents_count = len(result.intents or [])
        sentiment_overall = self._overall_sentiment(result)

        summary_text = result.summary or self._fallback_summary(result.transcript)

        return (
            f"# Executive Summary\n\n"
            f"## Session Information\n"
            f"- **Date Generated:** {result.generated_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"- **Duration:** {duration}\n"
            f"- **Total Speakers:** {speakers_count}\n"
            f"- **Provider:** {result.provider_name}\n"
            f"- **Audio File:** {Path(result.audio_file).name}\n\n"
            f"## Executive Summary\n"
            f"{summary_text}\n\n"
            f"## Session Structure\n"
            f"- Total Chapters: {len(result.chapters or [])}\n"
            f"- Key Topics Discussed: {topic_count}\n"
            f"- Detected Intents: {intents_count}\n"
            f"- Overall Sentiment: {sentiment_overall}\n\n"
            f"## Quick Links\n"
            f"- [Chapter Overview](02_chapter_overview.md)\n"
            f"- [Topics & Intents](03_key_topics_and_intents.md)\n"
            f"- [Full Transcript](04_full_transcript_with_timestamps.md)\n"
            f"- [Key Insights](05_key_insights_and_takeaways.md)\n"
        )

    def _calc_chapter_percentage(self, start_time: float, end_time: float, total: float) -> float:
        """Calculate chapter percentage of total duration."""
        if end_time < start_time:
            return 0.0
        return ((end_time - start_time) / max(total, 1e-6)) * 100

    def _get_chapter_title(self, topics: list[str] | None, idx: int) -> str:
        """Get chapter title from topics or default."""
        return ", ".join(topics) if topics else f"Chapter {idx}"

    def _render_chapter_details(self, chapters: list[Any], total_duration: float) -> list[str]:
        """Render detailed chapter sections."""
        lines: list[str] = []
        for idx, ch in enumerate(chapters, 1):
            start = self._format_timestamp(ch.start_time)
            end = self._format_timestamp(ch.end_time)
            pct = self._calc_chapter_percentage(ch.start_time, ch.end_time, total_duration)
            title = self._get_chapter_title(ch.topics, idx)

            lines.append(f"## Chapter {idx}: {title}")
            lines.append(f"**Time:** [{start}] - [{end}] ({pct:.1f}% of session)")
            lines.append("")
            lines.append("### Topics Covered:")
            if ch.topics:
                lines.extend(f"- {t}" for t in ch.topics)
            else:
                lines.append("- General discussion")
            lines.append("\n---\n")
        return lines

    def _render_chapter_summary_table(
        self, chapters: list[Any], total_duration: float
    ) -> list[str]:
        """Render chapter summary table."""
        lines = [
            "\n## Chapter Summary Table\n",
            "| # | Time Range | % | Title |",
            "|---|------------|---:|-------|",
        ]
        for idx, ch in enumerate(chapters, 1):
            start = self._format_timestamp(ch.start_time)
            end = self._format_timestamp(ch.end_time)
            pct = self._calc_chapter_percentage(ch.start_time, ch.end_time, total_duration)
            title = self._get_chapter_title(ch.topics, idx)
            lines.append(f"| {idx} | [{start}] - [{end}] | {pct:.1f}% | {title} |")
        return lines

    def _render_chapter_overview(self, result: TranscriptionResult) -> str:
        """Render the chapter-by-chapter overview (02_chapter_overview.md).

        Creates detailed chapter breakdowns with time ranges, duration percentages,
        and topic listings. Includes both detailed sections and a summary table.

        Args:
            result: TranscriptionResult containing chapter information

        Returns:
            Formatted markdown string with chapter analysis, or a simple message
            if no chapters were identified
        """
        if not result.chapters:
            return "# Chapter-by-Chapter Overview\n\n_No chapters identified._\n"

        lines: list[str] = ["# Chapter-by-Chapter Overview", ""]
        lines.extend(self._render_chapter_details(result.chapters, result.duration))
        lines.extend(self._render_chapter_summary_table(result.chapters, result.duration))
        return "\n".join(lines) + "\n"

    def _render_topics_and_intents(self, result: TranscriptionResult) -> str:
        """Render key topics and intents analysis (03_key_topics_and_intents.md).

        Creates three main sections:
        1. Topic frequency analysis (sorted by mention count)
        2. Detected intents (unique sorted list)
        3. Sentiment distribution with percentages

        Args:
            result: TranscriptionResult containing topics, intents, and sentiment data

        Returns:
            Formatted markdown string with topic, intent, and sentiment analysis
        """
        topics = result.topics or {}
        intents = result.intents or []
        sentiments = result.sentiment_distribution or {}

        lines: list[str] = ["# Key Topics and Detected Intents", ""]

        # Topic frequency table
        lines.append("## Topic Frequency Analysis")
        if topics:
            lines.append("| Topic | Mentions |")
            lines.append("|-------|----------:|")
            for topic, count in sorted(topics.items(), key=lambda x: x[1], reverse=True):
                lines.append(f"| {topic} | {count} |")
        else:
            lines.append("_No specific topics identified._")

        # Intents
        lines.append("\n## Detected Intents")
        if intents:
            lines.append("| Intent |")
            lines.append("|--------|")
            for intent in sorted(set(intents)):
                lines.append(f"| {intent} |")
        else:
            lines.append("_No intents detected._")

        # Sentiment
        lines.append("\n## Sentiment Analysis")
        if sentiments:
            total = sum(sentiments.values()) or 1
            for k, v in sentiments.items():
                lines.append(f"- {k.title()}: {v} segments ({(v / total) * 100:.1f}%)")
        else:
            lines.append("_No sentiment analysis available._")

        return "\n".join(lines) + "\n"

    def _render_utterances_with_sections(
        self, utterances: list[TranscriptionUtterance]
    ) -> list[str]:
        """Format utterances with timestamps, adding section headers every 10 minutes."""
        lines: list[str] = []
        last_section_min = -999
        for utt in utterances:
            current_min = int(utt.start // 600)
            if current_min > last_section_min:
                lines.append(f"\n## Section starting at [{self._format_timestamp(utt.start)}]\n")
                last_section_min = current_min
            lines.append(
                f"[{self._format_timestamp(utt.start)}] Speaker {utt.speaker + 1}: {utt.text}"
            )
        return lines

    def _render_speaker_statistics(
        self, utterances: list[TranscriptionUtterance], duration: float
    ) -> list[str]:
        """Calculate and format speaker talk time statistics."""
        lines: list[str] = ["\n---\n\n## Speaker Statistics"]
        totals: dict[int, float] = {}
        for utt in utterances:
            totals[utt.speaker] = totals.get(utt.speaker, 0.0) + max(0.0, utt.end - utt.start)
        for speaker_id, seconds in sorted(totals.items()):
            pct = (seconds / duration) * 100
            lines.append(
                f"- Speaker {speaker_id + 1}: {self._format_timestamp(seconds)} ({pct:.1f}%)"
            )
        return lines

    def _render_full_transcript(self, result: TranscriptionResult) -> str:
        """Render the full transcript with timestamps (04_full_transcript_with_timestamps.md).

        Generates a complete transcript with speaker attribution and timestamps.
        Organizes content into sections approximately every 10 minutes for readability.
        Includes speaker statistics showing talk time and percentage of total duration.

        Args:
            result: TranscriptionResult containing utterances or raw transcript

        Returns:
            Formatted markdown string with timestamped transcript and speaker statistics.
            Falls back to raw transcript if utterances are not available.
        """
        lines: list[str] = ["# Full Transcript with Speaker Timestamps", ""]

        if result.utterances:
            lines.extend(self._render_utterances_with_sections(result.utterances))
        else:
            lines.append(result.transcript)

        if result.utterances and result.duration > 0:
            lines.extend(self._render_speaker_statistics(result.utterances, result.duration))

        return "\n".join(lines) + "\n"

    def _render_key_insights(self, result: TranscriptionResult) -> str:
        """Render key insights and actionable takeaways (05_key_insights_and_takeaways.md).

        Extracts strategic insights by identifying sentences containing action-oriented
        keywords (e.g., "should", "must", "will", "recommend"). Each insight includes:
        - Evidence quote from the transcript
        - Approximate timestamp (if utterances available)
        - Placeholder sections for implications and action items

        Args:
            result: TranscriptionResult containing transcript and optionally utterances

        Returns:
            Formatted markdown string with up to 15 strategic insights, or a simple
            message if no action-oriented sentences are found.
        """
        lines: list[str] = ["# Key Insights and Actionable Takeaways", ""]

        # Simple heuristic: extract sentences containing action language
        candidates = self._find_action_sentences(result.transcript)
        if not candidates:
            lines.append("_No specific insights identified. Review transcript for highlights._")
            return "\n".join(lines) + "\n"

        lines.append("## Strategic Insights\n")
        for idx, sentence in enumerate(candidates[:15], 1):  # Limit to top 15 insights
            lines.append(f"### {idx}. Insight")
            lines.append(f'**Evidence:** "{sentence.strip()}"')
            # Attempt to find the timestamp where this sentence was spoken by matching
            # against utterances. This helps readers locate the insight in the full transcript.
            ts = self._approx_timestamp_for_sentence(sentence, result.utterances or [])
            if ts is not None:
                lines.append(f"**Timestamp:** [{self._format_timestamp(ts)}]")
            lines.append("**Implications:** Describe potential impact or meaning.")
            lines.append("**Action Items:** Define next steps or owners.")
            lines.append("")

        return "\n".join(lines) + "\n"

    # ---------------------- Helpers ----------------------
    def _overall_sentiment(self, result: TranscriptionResult) -> str:
        """Determine the dominant sentiment from sentiment distribution.

        Selects the sentiment category with the highest count from the
        result's sentiment_distribution dictionary.

        Args:
            result: TranscriptionResult with optional sentiment_distribution

        Returns:
            Title-cased sentiment label (e.g., "Positive", "Neutral") or "Unknown"
            if no sentiment data is available
        """
        dist = result.sentiment_distribution or {}
        if not dist:
            return "Unknown"
        return max(dist.items(), key=lambda x: x[1])[0].title()

    def _approx_timestamp_for_sentence(
        self, sentence: str, utterances: list[TranscriptionUtterance]
    ) -> float | None:
        """Find approximate timestamp for a given sentence.

        Attempts to locate the sentence within utterances by matching the first
        20 characters. This is a naive heuristic approach that may not always
        find exact matches.

        Args:
            sentence: Sentence text to locate in utterances
            utterances: List of TranscriptionUtterance objects with timestamps

        Returns:
            Start timestamp (float) of the utterance containing the sentence,
            or 0.0 as fallback if utterances exist but no match is found,
            or None if no utterances are available.
        """
        if not utterances:
            return None
        # Naive substring matching approach: Use first 20 chars of the sentence
        # as a search key. This is a heuristic and may not find exact matches,
        # especially if the sentence was paraphrased or extracted differently.
        key = sentence[:20].lower()
        for utt in utterances:
            # Search for the key substring in each utterance's text
            if key and key in (utt.text or "").lower():
                return utt.start  # Return timestamp of first matching utterance
        # Fallback: If no match found, return start of session (0.0) rather than None
        # to provide some temporal context even if inexact
        return 0.0
