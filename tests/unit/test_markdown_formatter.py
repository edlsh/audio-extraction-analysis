from datetime import datetime
from pathlib import Path

import pytest

from src.formatters.markdown_formatter import MarkdownFormatter, TemplateNotFoundError
from src.models.transcription import (
    TranscriptionResult,
    TranscriptionUtterance,
)


def _sample_result() -> TranscriptionResult:
    return TranscriptionResult(
        transcript="Hello world. This is a test.",
        duration=125.0,
        generated_at=datetime.now(),
        audio_file="sample.mp3",
        provider_name="deepgram",
        utterances=[
            TranscriptionUtterance(speaker=0, start=0.0, end=5.0, text="Hello world."),
            TranscriptionUtterance(speaker=1, start=5.0, end=12.0, text="This is a test."),
        ],
    )


class TestMarkdownFormatter:
    def test_format_basic_transcript(self, tmp_path: Path):
        fmt = MarkdownFormatter()
        res = _sample_result()
        md = fmt.format_transcript(
            res,
            {
                "source": res.audio_file,
                "processed_at": "2024-01-01T00:00:00",
                "provider": res.provider_name,
                "total_duration": res.duration,
            },
            tmp_path / "out.md",
            include_timestamps=True,
            include_speakers=True,
            template="default",
        )

        assert "# Transcript:" in md
        assert "**Provider**: deepgram" in md
        assert "[00:00:00]" in md
        assert "**Speaker 0**:" in md
        assert "Hello world." in md

    def test_format_with_timestamps(self, tmp_path: Path):
        fmt = MarkdownFormatter()
        res = _sample_result()
        md = fmt.format_transcript(
            res,
            {
                "source": res.audio_file,
                "processed_at": "2024-01-01T00:00:00",
                "provider": res.provider_name,
                "total_duration": res.duration,
            },
            tmp_path / "out.md",
            include_timestamps=True,
            include_speakers=False,
            template="default",
        )
        assert "[00:00:00]" in md
        assert "[00:00:05]" in md

    def test_format_with_speakers(self, tmp_path: Path):
        fmt = MarkdownFormatter()
        res = _sample_result()
        md = fmt.format_transcript(
            res,
            {
                "source": res.audio_file,
                "processed_at": "2024-01-01T00:00:00",
                "provider": res.provider_name,
                "total_duration": res.duration,
            },
            tmp_path / "out.md",
            include_timestamps=False,
            include_speakers=True,
            template="default",
        )
        assert "**Speaker 0**:" in md
        assert "**Speaker 1**:" in md

    def test_template_selection(self, tmp_path: Path):
        fmt = MarkdownFormatter()
        res = _sample_result()
        md = fmt.format_transcript(
            res,
            {
                "source": res.audio_file,
                "processed_at": "2024-01-01T00:00:00",
                "provider": res.provider_name,
                "total_duration": res.duration,
            },
            tmp_path / "out.md",
            template="minimal",
            include_timestamps=False,
            include_speakers=False,
        )
        # Minimal header is just '# title' without Provider line
        assert md.startswith("# sample")
        assert "Provider" not in md.splitlines()[0:3]

    def test_file_output(self, tmp_path: Path):
        fmt = MarkdownFormatter()
        out = tmp_path / "transcript.md"
        content = "# Title\n\nHello"
        fmt.save_transcript(content, out)
        assert out.exists()
        assert out.read_text(encoding="utf-8").startswith("# Title")

    def test_error_handling(self, tmp_path: Path):
        fmt = MarkdownFormatter()
        res = _sample_result()
        with pytest.raises(TemplateNotFoundError):
            fmt.format_transcript(
                res,
                {
                    "source": res.audio_file,
                    "processed_at": "2024-01-01T00:00:00",
                    "provider": res.provider_name,
                    "total_duration": res.duration,
                },
                tmp_path / "out.md",
                template="does-not-exist",
            )

    def test_save_transcript_io_error(self, monkeypatch, tmp_path: Path):
        fmt = MarkdownFormatter()
        # Patch open to raise OSError
        import builtins

        from src.formatters.markdown_formatter import MarkdownFormattingError

        def boom(*args, **kwargs):
            raise OSError("disk full")

        monkeypatch.setattr(builtins, "open", boom)
        with pytest.raises(MarkdownFormattingError):
            fmt.save_transcript("x", tmp_path / "out.md")

    def test_sanitize_dirname(self):
        s = MarkdownFormatter.sanitize_dirname("../../weird name!#@$")
        assert (
            s == "____weird_name____" or s.replace("_", "") != ""
        )  # ensures sanitized and not empty
        assert "/" not in s and "\\" not in s

    def test_format_timestamp_zero_and_negative(self):
        fmt = MarkdownFormatter()
        assert fmt._format_timestamp(0) == "00:00:00"
        assert fmt._format_timestamp(-5) == "00:00:00"
