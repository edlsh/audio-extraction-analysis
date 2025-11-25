"""Markdown templates for transcript export.

These are simple string templates filled by the MarkdownFormatter.
Runtime options (timestamps/speakers/confidence) are applied by the
formatter; the templates contain placeholders that will be populated.
"""

from __future__ import annotations

TEMPLATES: dict[str, dict[str, object]] = {
    "default": {
        "header": (
            "# Transcript: {title}\n\n"
            "**Source**: {source}  \n"
            "**Duration**: {duration}  \n"
            "**Processed**: {processed_at}  \n"
            "**Provider**: {provider}\n\n"
            "---\n\n"
        ),
        # Uses {timestamp} only if timestamps enabled by the formatter
        "segment": "[{timestamp}] {speaker_prefix}{text}\n\n",
        # The formatter will blank this if speakers are disabled
        "speaker_prefix": "**{speaker}**: ",
        "timestamp_format": "HH:MM:SS",
    },
    "minimal": {
        "header": "# {title}\n\n",
        "segment": "{text}\n\n",
        "speaker_prefix": "",
        "timestamp_format": None,
    },
    "detailed": {
        "header": (
            "# Transcript Analysis Report\n\n"
            "## Source Information\n"
            "- **File**: {source}\n"
            "- **Duration**: {duration}\n"
            "- **Processing Date**: {processed_at}\n"
            "- **Transcription Provider**: {provider}\n"
            "- **Total Segments**: {segment_count}\n"
            "- **Average Confidence**: {avg_confidence}%\n\n"
            "## Transcript\n\n"
        ),
        "segment": "**[{timestamp}]** {speaker_prefix}{text} _{confidence}_\n\n",
        "speaker_prefix": "**{speaker}**: ",
        "timestamp_format": "HH:MM:SS",
    },
}
