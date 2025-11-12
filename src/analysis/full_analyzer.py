"""Full transcript analyzer that generates 5 structured markdown files.

This module provides the FullAnalyzer class for comprehensive transcription analysis.
It takes a TranscriptionResult object and produces structured documentation across
five interconnected markdown files.

Output Files
------------
The analyzer produces the following files in the output directory:
1. 01_executive_summary.md - High-level session overview with metadata and quick links
2. 02_chapter_overview.md - Detailed chapter breakdown with time ranges and topics
3. 03_key_topics_and_intents.md - Topic frequency, intent detection, and sentiment analysis
4. 04_full_transcript_with_timestamps.md - Complete transcript with speaker attribution
5. 05_key_insights_and_takeaways.md - Strategic insights with actionable recommendations

Usage Example
-------------
    from pathlib import Path
    from analysis.full_analyzer import FullAnalyzer
    from models.transcription import TranscriptionResult

    # Assuming you have a TranscriptionResult object
    analyzer = FullAnalyzer()
    output_paths = analyzer.analyze_and_save(
        result=transcription_result,
        output_dir=Path("./analysis_output"),
        filename_base="meeting_2024"
    )

References
----------
The structure broadly follows docs/transcription_formatting_prompts.md
and examples in the examples/ and data/output/ folders.
"""

from __future__ import annotations

import logging
from pathlib import Path

from ..models.transcription import TranscriptionResult, TranscriptionUtterance

logger = logging.getLogger(__name__)


class FullAnalyzer:
    """Generates 5 detailed analysis files from a TranscriptionResult.

    The FullAnalyzer processes rich transcription data and creates a comprehensive
    documentation suite including executive summaries, chapter breakdowns, topic analysis,
    timestamped transcripts, and actionable insights.

    Features
    --------
    - Executive summary with session metadata and structure overview
    - Chapter-by-chapter analysis with time ranges and percentage breakdowns
    - Topic frequency analysis and intent detection
    - Full speaker-attributed transcript with timestamps
    - Strategic insights extraction using action-word heuristics
    - Cross-linked markdown files for easy navigation

    Attributes
    ----------
    None - This class is stateless and can be reused for multiple analyses.

    Methods
    -------
    analyze_and_save(result, output_dir, filename_base)
        Generate all 5 analysis markdown files from a TranscriptionResult.

    Examples
    --------
    >>> analyzer = FullAnalyzer()
    >>> paths = analyzer.analyze_and_save(
    ...     result=transcription_result,
    ...     output_dir=Path("./output"),
    ...     filename_base="session_001"
    ... )
    >>> print(paths["executive_summary"])
    Path('./output/01_executive_summary.md')
    """

    def __init__(self) -> None:
        """Initialize the FullAnalyzer.

        The analyzer is stateless and ready to process transcription results
        immediately after initialization.
        """
        pass

    def analyze_and_save(
        self, result: TranscriptionResult, output_dir: Path, filename_base: str
    ) -> dict[str, Path]:
        """Generate all 5 analysis files and return their paths.

        This method orchestrates the creation of all five markdown files by calling
        the respective rendering methods. The output directory is created if it doesn't
        exist. All files are written with UTF-8 encoding.

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
        duration = self._format_hms(result.duration)
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
        # Use a minimum value to avoid division by zero in percentage calculations
        total_duration = max(result.duration, 1e-6)

        for idx, ch in enumerate(result.chapters, 1):
            start = self._format_hms(ch.start_time)
            end = self._format_hms(ch.end_time)
            # Calculate what percentage of the total session this chapter represents
            pct = (
                ((ch.end_time - ch.start_time) / total_duration) * 100
                if ch.end_time >= ch.start_time
                else 0.0  # Guard against invalid time ranges
            )
            title = ", ".join(ch.topics) if ch.topics else f"Chapter {idx}"

            lines.append(f"## Chapter {idx}: {title}")
            lines.append(f"**Time:** [{start}] - [{end}] ({pct:.1f}% of session)")
            lines.append("")
            lines.append("### Topics Covered:")
            if ch.topics:
                for t in ch.topics:
                    lines.append(f"- {t}")
            else:
                lines.append("- General discussion")
            lines.append("\n---\n")

        # Optional summary table
        lines.append("\n## Chapter Summary Table\n")
        lines.append("| # | Time Range | % | Title |")
        lines.append("|---|------------|---:|-------|")
        for idx, ch in enumerate(result.chapters, 1):
            start = self._format_hms(ch.start_time)
            end = self._format_hms(ch.end_time)
            pct = (
                ((ch.end_time - ch.start_time) / total_duration) * 100
                if ch.end_time >= ch.start_time
                else 0.0
            )
            title = ", ".join(ch.topics) if ch.topics else f"Chapter {idx}"
            lines.append(f"| {idx} | [{start}] - [{end}] | {pct:.1f}% | {title} |")

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

        # If utterances exist, format with timestamps; else fall back to raw transcript
        if result.utterances:
            # Create section headers approximately every 10 minutes (600 seconds)
            # to improve readability of long transcripts. We track which 10-minute
            # bucket we're in and add a header when transitioning to a new bucket.
            last_section_min = -999  # Start with impossible value to trigger first section
            for utt in result.utterances:
                # Calculate which 10-minute bucket this utterance falls into (0, 1, 2, ...)
                current_min = int(utt.start // 600)
                if current_min > last_section_min:
                    # Transitioning to new 10-minute section - add section header
                    lines.append(f"\n## Section starting at [{self._format_hms(utt.start)}]\n")
                    last_section_min = current_min
                lines.append(
                    f"[{self._format_hms(utt.start)}] Speaker {utt.speaker + 1}: {utt.text}"
                )
        else:
            lines.append(result.transcript)

        # Calculate speaker statistics by summing the duration of each speaker's utterances.
        # This provides insights into talk time distribution across participants.
        if result.utterances and result.duration > 0:
            lines.append("\n---\n\n## Speaker Statistics")
            totals: dict[int, float] = {}  # Maps speaker ID to total talk time in seconds
            for utt in result.utterances:
                # Accumulate duration for each speaker (utterance end - start time)
                totals[utt.speaker] = totals.get(utt.speaker, 0.0) + max(0.0, utt.end - utt.start)
            for speaker_id, seconds in sorted(totals.items()):
                pct = (seconds / result.duration) * 100
                lines.append(
                    f"- Speaker {speaker_id + 1}: {self._format_hms(seconds)} ({pct:.1f}%)"
                )

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
                lines.append(f"**Timestamp:** [{self._format_hms(ts)}]")
            lines.append("**Implications:** Describe potential impact or meaning.")
            lines.append("**Action Items:** Define next steps or owners.")
            lines.append("")

        return "\n".join(lines) + "\n"

    # ---------------------- Helpers ----------------------
    def _format_hms(self, seconds: float) -> str:
        """Format seconds as HH:MM:SS timestamp string.

        Args:
            seconds: Time in seconds (negative values are clamped to 0)

        Returns:
            Zero-padded timestamp string in HH:MM:SS format (e.g., "01:23:45")
        """
        seconds = max(0.0, float(seconds))
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        return f"{h:02d}:{m:02d}:{s:02d}"

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

    def _fallback_summary(self, transcript: str) -> str:
        """Generate a simple fallback summary when no AI-generated summary is available.

        Extracts either the first 3 sentences or the first 300 characters from
        the transcript to create a basic summary.

        Args:
            transcript: Raw transcript text

        Returns:
            Simple summary text: first 3 sentences (if available), or first 300 chars,
            or "No summary available." for empty transcripts
        """
        # Fallback strategy: Extract first 3 complete sentences if available,
        # otherwise use first 300 characters. This provides a basic summary
        # when AI-generated summaries are not present in the TranscriptionResult.
        if not transcript:
            return "No summary available."
        # Split by period and filter out empty strings
        parts = [s.strip() for s in transcript.split(".") if s.strip()]
        if len(parts) >= 3:
            # We have at least 3 sentences - use them as summary
            return ". ".join(parts[:3]) + "."
        # Fewer than 3 sentences - truncate to 300 chars
        return (transcript[:300] + ("..." if len(transcript) > 300 else "")).strip()

    def _find_action_sentences(self, transcript: str) -> list[str]:
        """Extract sentences containing action-oriented keywords.

        Uses a heuristic approach to identify actionable content by searching for
        sentences containing specific keywords like "should", "must", "will", etc.

        Action keywords:
            should, need to, must, will, plan to, going to, have to, recommend, priority

        Args:
            transcript: Raw transcript text

        Returns:
            List of sentences (strings) containing at least one action keyword.
            Returns empty list if transcript is empty.
        """
        if not transcript:
            return []
        action_keywords = [
            "should",
            "need to",
            "must",
            "will",
            "plan to",
            "going to",
            "have to",
            "recommend",
            "priority",
        ]
        sentences = [s.strip() for s in transcript.split(".") if s.strip()]
        return [s for s in sentences if any(k in s.lower() for k in action_keywords)]

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
