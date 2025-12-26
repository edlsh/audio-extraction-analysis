"""Single-file transcript analyzer generating comprehensive markdown reports."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from src.utils.logger import get_logger

from ..utils.constants import AnalysisConstants
from .base_analyzer import BaseAnalyzer

if TYPE_CHECKING:
    from ..models.transcription import TranscriptionResult

logger = get_logger(__name__)


class ConciseAnalyzer(BaseAnalyzer):
    """Generates single comprehensive analysis file from transcription results."""

    def analyze_and_save(
        self, result: TranscriptionResult, output_dir: Path, filename_base: str
    ) -> Path:
        """Generate and save comprehensive analysis markdown file.

        Args:
            result: Transcription result with topics, speakers, sentiment
            output_dir: Output directory (created if needed)
            filename_base: Base filename (output: {base}_analysis.md)

        Returns:
            Path to generated analysis file
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        analysis_path = output_dir / f"{filename_base}_analysis.md"

        # Generate and write the analysis content
        analysis_path.write_text(self._generate_analysis(result), encoding="utf-8")

        logger.info(f"Concise analysis saved to: {analysis_path}")
        return analysis_path

    def _generate_analysis(self, result: TranscriptionResult) -> str:
        """Generate complete analysis markdown content.

        Args:
            result: TranscriptionResult with optional
                   fields like topics, speakers, sentiment, chapters, and utterances.

        Returns:
            str: Complete markdown-formatted analysis content with all non-empty
                sections joined by double newlines.
        """
        sections = [
            self._generate_header(result),
            self._generate_overview(result),
            self._generate_key_topics(result),
            self._generate_speaker_insights(result),
            self._generate_sentiment_analysis(result),
            self._generate_highlights_and_quotes(result),
            self._generate_action_items_and_intents(result),
            self._generate_timeline(result),
            self._generate_metadata(result),
        ]

        return "\n\n".join(filter(None, sections))

    def _generate_header(self, result: TranscriptionResult) -> str:
        """Generate the document header with key metadata.

        Returns:
            str: Markdown-formatted header section with generation time, provider,
                duration, and audio filename.
        """
        duration_formatted = self._format_duration(result.duration)

        return f"""# Audio Analysis Report

**Generated:** {result.generated_at.strftime("%Y-%m-%d %H:%M:%S")}  
**Provider:** {result.provider_name}  
**Duration:** {duration_formatted}  
**File:** {Path(result.audio_file).name}

---"""

    def _generate_overview(self, result: TranscriptionResult) -> str:
        """Generate overview section with content statistics and summary.

        If a summary is available in the result, it's used directly. Otherwise,
        a fallback summary is generated from the first 3 sentences or first 300
        characters of the transcript.

        Returns:
            str: Markdown-formatted overview with character/word counts and summary.
        """
        word_count = len(result.transcript.split())

        overview = f"""## 📋 Overview

**Content Length:** {len(result.transcript):,} characters / {word_count:,} words"""

        if result.summary:
            overview += f"\n\n**Summary:** {result.summary}"
        else:
            overview += f"\n\n**Key Content:** {self._fallback_summary(result.transcript)}"

        return overview

    def _generate_key_topics(self, result: TranscriptionResult) -> str:
        """Generate key topics section ranked by frequency.

        Topics are sorted by mention count in descending order, with the top 10
        most frequent topics displayed. Topic names are title-cased for readability.

        Returns:
            str: Markdown-formatted section with numbered topic list, or a message
                if no topics are available.
        """
        if not result.topics:
            return "## 🎯 Key Topics\n\n*No specific topics identified*"

        content = "## 🎯 Key Topics\n\n"

        # Sort topics by frequency
        sorted_topics = sorted(result.topics.items(), key=lambda x: x[1], reverse=True)

        for i, (topic, count) in enumerate(sorted_topics[:10], 1):
            content += f"{i}. **{topic.title()}** ({count} mentions)\n"

        return content

    def _generate_speaker_insights(self, result: TranscriptionResult) -> str:
        """Generate speaker insights section with time distribution.

        For each detected speaker, calculates and displays their total speaking time
        and percentage of total audio duration. Speakers are identified by numeric ID.

        Returns:
            str: Markdown-formatted section with speaker statistics, or a message
                if speaker diarization data is unavailable.
        """
        if not result.speakers:
            return "## 👥 Speaker Analysis\n\n*No speaker diarization data available*"

        content = "## 👥 Speaker Analysis\n\n"

        for speaker in result.speakers:
            percentage = (speaker.total_time / result.duration * 100) if result.duration > 0 else 0
            speaker_name = f"Speaker {speaker.id}"
            duration = self._format_duration(speaker.total_time)
            content += f"**{speaker_name}:** {duration} ({percentage:.1f}%)\n"

        return content

    def _generate_sentiment_analysis(self, result: TranscriptionResult) -> str:
        """Generate sentiment analysis section with distribution breakdown.

        Displays the distribution of sentiment across transcript segments, showing
        count and percentage for each sentiment category (positive, negative, neutral).
        Each sentiment is accompanied by a corresponding emoji for visual clarity.

        Returns:
            str: Markdown-formatted section with sentiment distribution and emojis,
                or a message if sentiment analysis data is unavailable.
        """
        if not result.sentiment_distribution:
            return "## 😊 Sentiment Analysis\n\n*No sentiment analysis data available*"

        content = "## 😊 Sentiment Analysis\n\n"

        total_segments = sum(result.sentiment_distribution.values())
        for sentiment, count in result.sentiment_distribution.items():
            percentage = (count / total_segments * 100) if total_segments > 0 else 0
            emoji = self._get_sentiment_emoji(sentiment)
            content += f"{emoji} **{sentiment.title()}:** {count} segments ({percentage:.1f}%)\n"

        return content

    def _generate_highlights_and_quotes(self, result: TranscriptionResult) -> str:
        """Generate highlights and notable quotes section.

        Uses a heuristic approach to identify meaningful content:
        - Extracts sentences with 15+ words (substantial content)
        - Filters sentences under 200 characters (avoids run-ons)
        - Selects top 5 longest sentences as likely highlights

        This simple length-based heuristic tends to surface sentences with more
        detailed or important information.

        Returns:
            str: Markdown-formatted section with top 5 extracted quotes, or a
                message if no suitable highlights are found.
        """
        content = "## 💡 Key Highlights & Quotes\n\n"

        # Extract meaningful sentences (longer sentences often contain more substance)
        sentences = [s.strip() for s in result.transcript.split(".") if s.strip()]
        meaningful_sentences = [
            s
            for s in sentences
            if len(s.split()) >= AnalysisConstants.MIN_SENTENCE_WORDS
            and len(s) <= AnalysisConstants.MAX_SENTENCE_CHARS
        ]

        # Take top sentences by length (simple heuristic)
        top_sentences = sorted(meaningful_sentences, key=len, reverse=True)[
            : AnalysisConstants.TOP_HIGHLIGHTS_COUNT
        ]

        if top_sentences:
            for i, sentence in enumerate(top_sentences, 1):
                content += f'{i}. *"{sentence.strip()}."\n\n'
        else:
            content += "*No specific highlights identified*\n"

        return content

    def _generate_action_items_and_intents(self, result: TranscriptionResult) -> str:
        """Generate action items and intents section.

        If intent data is available from the provider, it displays unique identified
        intents. Otherwise, uses a keyword-based heuristic to detect potential action
        items by searching for action-oriented language.

        Limits fallback detection to 5 potential action items to avoid noise.

        Returns:
            str: Markdown-formatted section with intents or potential action items,
                or a message if none are detected.
        """
        content = "## ✅ Intents & Action Items\n\n"

        if result.intents:
            content += "**Identified Intents:**\n"
            for intent in set(result.intents):  # Remove duplicates
                content += f"- {intent.title()}\n"
        else:
            action_sentences = self._find_action_sentences(result.transcript)

            if action_sentences:
                content += "**Potential Action Items:**\n"
                for sentence in action_sentences[:5]:  # Limit to 5
                    content += f"- {sentence.strip()}\n"
            else:
                content += "*No specific action items or intents identified*"

        return content

    def _generate_timeline(self, result: TranscriptionResult) -> str:
        """Generate timeline section from chapters or utterances.

        Prioritizes chapter data (topic segments) if available, otherwise falls back
        to displaying the first 10 utterances as key moments. Chapter topics are
        displayed with timestamps, while utterances show preview text (truncated to
        100 characters).

        Returns:
            str: Markdown-formatted timeline with timestamps and content previews,
                or a message if no timeline data is available.
        """
        if not result.chapters and not result.utterances:
            return "## ⏰ Timeline\n\n*No timeline data available*"

        content = "## ⏰ Timeline\n\n"

        if result.chapters:
            content += "**Topic Segments:**\n"
            for chapter in result.chapters:
                start_time = self._format_duration(chapter.start_time)
                topics = ", ".join(chapter.topics) if chapter.topics else "General Discussion"
                content += f"- **{start_time}:** {topics}\n"
        elif result.utterances:
            content += "**Key Moments:**\n"
            # Show first few utterances as examples
            for utterance in result.utterances[:10]:
                start_time = self._format_duration(utterance.start)
                preview = (
                    utterance.text[:100] + "..." if len(utterance.text) > 100 else utterance.text
                )
                content += f"- **{start_time}:** {preview}\n"

        return content

    def _generate_metadata(self, result: TranscriptionResult) -> str:
        """Generate technical metadata section.

        Includes provider features, audio file path, processing timestamp, and
        optional counts for speakers, chapters, and utterances if available.

        Returns:
            str: Markdown-formatted section with technical details and statistics.
        """
        content = "## 📊 Technical Metadata\n\n"
        content += f"**Provider Features:** {', '.join(result.provider_features or [])}\n"
        content += f"**Audio File:** `{result.audio_file}`\n"
        content += f"**Processing Time:** {result.generated_at.strftime('%Y-%m-%d %H:%M:%S')}\n"

        if result.speakers:
            content += f"**Speakers Detected:** {len(result.speakers)}\n"

        if result.chapters:
            content += f"**Topic Segments:** {len(result.chapters)}\n"

        if result.utterances:
            content += f"**Total Utterances:** {len(result.utterances)}\n"

        return content
