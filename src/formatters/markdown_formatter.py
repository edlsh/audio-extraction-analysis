"""Markdown formatting for transcription results."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from ..config import Config
from ..models.transcription import (
    TranscriptionResult,
    TranscriptionUtterance,
)
from ..utils.paths import sanitize_dirname as util_sanitize_dirname
from .templates import TEMPLATES


class MarkdownFormattingError(Exception):
    """Raised when markdown formatting fails."""


class TemplateNotFoundError(Exception):
    """Raised when specified template doesn't exist."""


class MarkdownFormatter:
    """Formats transcription results as markdown documents."""

    def __init__(self, config: Config | None = None):
        self.config = config or Config

    def format_transcript(
        self,
        result: TranscriptionResult,
        source_info: dict[str, Any],
        output_path: Path,
        include_timestamps: bool = True,
        include_speakers: bool = True,
        include_confidence: bool = False,
        template: str = "default",
    ) -> str:
        """Generate markdown transcript with metadata and formatting options.
            template: Template name to use from TEMPLATES dict (default: "default").

        Returns:
            Formatted markdown string containing header and transcript segments.

        Raises:
            TemplateNotFoundError: If the specified template does not exist.
            MarkdownFormattingError: If formatting fails for any other reason.
        """
        try:
            tpl = TEMPLATES.get(template)
            if tpl is None:
                raise TemplateNotFoundError(f"Template '{template}' not found")

            header = self._format_header(result, source_info, tpl)
            segments_md = self._format_segments(
                result.utterances or [],
                include_timestamps=include_timestamps,
                include_speakers=include_speakers,
                include_confidence=include_confidence,
                template=tpl,
            )

            # Fallback mechanism: If no utterances are available or segments_md is empty,
            # render the full transcript text as a single segment
            if not segments_md.strip():
                # Apply minimal template formatting to the complete transcript
                text_block = result.transcript.strip() if result.transcript else ""
                if text_block:
                    seg_tpl = str(tpl.get("segment", "{text}\n\n"))
                    segments_md = seg_tpl.format(
                        timestamp=(
                            "00:00:00" if include_timestamps and tpl.get("timestamp_format") else ""
                        ),
                        speaker_prefix=(
                            ""
                            if not include_speakers
                            else (str(tpl.get("speaker_prefix", ""))).format(speaker="")
                        ),
                        text=text_block,
                        confidence="" if not include_confidence else "",
                    )

            return header + segments_md
        except TemplateNotFoundError:
            raise
        except Exception as e:
            raise MarkdownFormattingError(f"Failed to format transcript: {e}") from e

    def _format_header(
        self, result: TranscriptionResult, source_info: dict[str, Any], tpl: dict[str, Any]
    ) -> str:
        """Generate markdown header with metadata.

        Creates a formatted header section containing transcription metadata such as
        title, source, duration, processing timestamp, provider, segment count, and
        average confidence score.

        Args:
            result: The transcription result with metadata and utterances.
            source_info: Dictionary containing source-level metadata.
            tpl: Template dictionary containing header format string.

        Returns:
            Formatted markdown header string with metadata fields populated.
        """
        header_tpl = str(tpl.get("header", "# Transcript\n\n"))

        title = Path(source_info.get("source", result.audio_file or "transcript")).stem
        duration_seconds = float(
            source_info.get("total_duration", getattr(result, "duration", 0.0) or 0.0)
        )
        duration = self._format_timestamp(duration_seconds)
        processed_at = source_info.get("processed_at") or datetime.now().isoformat()
        provider = source_info.get("provider") or result.provider_name
        segment_count = len(result.utterances or [])
        avg_confidence = source_info.get("avg_confidence", "N/A")

        return header_tpl.format(
            title=title,
            source=source_info.get("source", result.audio_file),
            duration=duration,
            processed_at=processed_at,
            provider=provider,
            segment_count=segment_count,
            avg_confidence=avg_confidence,
        )

    def _format_segments(
        self,
        segments: list[TranscriptionUtterance],
        include_timestamps: bool,
        include_speakers: bool,
        include_confidence: bool,
        template: dict[str, Any],
    ) -> str:
        """Format transcript segments with optional metadata.

        Processes a list of transcription utterances and formats each segment
        according to the template, optionally including timestamps, speaker
        labels, and confidence scores.

        Args:
            segments: List of transcription utterances to format.
            include_timestamps: Whether to include timestamp for each segment.
            include_speakers: Whether to include speaker identification labels.
            include_confidence: Whether to include confidence scores (currently N/A
                               as per-utterance confidence is not available).
            template: Template dictionary containing segment format strings.

        Returns:
            Concatenated string of all formatted segments. Returns empty string
            if no segments are provided.
        """
        if not segments:
            return ""

        seg_tpl = str(template.get("segment", "{text}\n\n"))
        sp_prefix_tpl = str(template.get("speaker_prefix", ""))
        use_ts = include_timestamps and bool(template.get("timestamp_format"))

        parts: list[str] = []
        for seg in segments:
            timestamp = self._format_timestamp(seg.start) if use_ts else ""
            speaker_prefix = (
                sp_prefix_tpl.format(speaker=f"Speaker {seg.speaker}") if include_speakers else ""
            )
            text = getattr(seg, "text", None) or getattr(seg, "transcript", "")
            confidence_str = ""
            if include_confidence:
                # TranscriptionUtterance model doesn't include per-utterance confidence scores
                # Display N/A to indicate the field is not available
                confidence_str = "confidence: N/A"

            parts.append(
                seg_tpl.format(
                    timestamp=timestamp,
                    speaker_prefix=speaker_prefix,
                    text=text,
                    confidence=confidence_str,
                )
            )

        return "".join(parts)

    def _format_timestamp(self, seconds: float) -> str:
        """Convert seconds to HH:MM:SS format.

        Converts a floating-point seconds value to a formatted timestamp string
        in HH:MM:SS format. Handles negative values by clamping to zero.

        Args:
            seconds: Duration in seconds to convert. Negative values are clamped to 0.

        Returns:
            Formatted timestamp string in HH:MM:SS format (e.g., "01:23:45").
        """
        seconds = max(0.0, float(seconds or 0.0))
        td = timedelta(seconds=int(seconds))
        # Ensure HH:MM:SS
        total_seconds = int(td.total_seconds())
        h = total_seconds // 3600
        m = (total_seconds % 3600) // 60
        s = total_seconds % 60
        return f"{h:02d}:{m:02d}:{s:02d}"

    def save_transcript(self, content: str, output_path: Path) -> None:
        """Save formatted transcript to file.

        Writes the markdown-formatted transcript content to the specified file path.
        Creates parent directories if they don't exist. Uses the encoding specified
        in the config (defaults to UTF-8).

        Args:
            content: The formatted markdown content to write.
            output_path: Path object specifying where to save the file.

        Raises:
            MarkdownFormattingError: If the file cannot be written due to OS errors
                                    or permission issues.
        """
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            encoding = getattr(self.config, "markdown_output_encoding", "utf-8")
            with open(output_path, "w", encoding=encoding) as f:
                f.write(content)
        except (OSError, PermissionError) as e:
            raise MarkdownFormattingError(
                f"Failed to write transcript to {output_path}: {e}"
            ) from e

    @staticmethod
    def sanitize_dirname(name: str) -> str:
        """Sanitize a string for use as a directory name.

        Delegates to the shared utility sanitizer to ensure consistent
        sanitization behavior across the application.

        Args:
            name: The string to sanitize for directory name usage.

        Returns:
            Sanitized string safe for use as a directory name.
        """
        return util_sanitize_dirname(name)
