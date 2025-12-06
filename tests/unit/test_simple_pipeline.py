from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from src.pipeline.simple_pipeline import AudioQuality, process_pipeline


class _DummyProgress:
    def __enter__(self) -> "_DummyProgress":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def update(self, *args: Any, **kwargs: Any) -> None:
        return None


class _DummyConsole:
    def setup_logging(self, logger) -> None:  # pragma: no cover - trivial
        return None

    def print_stage(self, *_, **__) -> None:
        return None

    def progress_context(self, *_, **__):
        return _DummyProgress()

    def print_summary(self, *_args, **__kwargs) -> None:
        return None


@pytest.mark.asyncio
async def test_process_pipeline_full_analysis(monkeypatch, tmp_path: Path) -> None:
    input_file = tmp_path / "input.mp4"
    input_file.write_bytes(b"video")
    output_dir = tmp_path / "out"

    class FakeExtractor:
        async def extract_audio_async(self, input_path, output_path, *_args, **_kwargs):
            # Audio now extracts directly to output_dir
            output_path.write_bytes(b"audio")
            return output_path

    class FakeTranscriptionService:
        def __init__(self) -> None:
            self.saved_paths: list[Path] = []

        async def transcribe_with_progress(self, *_args, **_kwargs):
            return SimpleNamespace(
                provider_name="mock",
                audio_file=str(output_dir / "input.mp3"),
                duration=1.0,
                transcript="hello",
            )

        def save_transcription_result(self, _result, dest: Path, provider_name: str | None = None):
            dest.write_text("transcript")
            self.saved_paths.append(dest)

    class FakeFullAnalyzer:
        def analyze_and_save(self, _transcript, out_dir: Path, stem: str):
            report = out_dir / f"{stem}_analysis.md"
            report.parent.mkdir(parents=True, exist_ok=True)
            report.write_text("analysis")
            return {"report": report}

    monkeypatch.setattr("src.pipeline.simple_pipeline.ConsoleManager", _DummyConsole)
    monkeypatch.setattr("src.pipeline.simple_pipeline.AsyncAudioExtractor", FakeExtractor)
    monkeypatch.setattr(
        "src.pipeline.simple_pipeline.TranscriptionService", FakeTranscriptionService
    )
    monkeypatch.setattr("src.pipeline.simple_pipeline.FullAnalyzer", FakeFullAnalyzer)

    results = await process_pipeline(
        input_path=input_file,
        output_dir=output_dir,
        quality=AudioQuality.SPEECH,
        analysis_style="full",
    )

    assert results["success"] is True
    assert "analysis" in Path(results["analysis_files"][0]).name
    transcript_path = output_dir / f"{input_file.stem}_transcript.txt"
    assert transcript_path.exists()
    assert (output_dir / f"{input_file.stem}.mp3").exists()


@pytest.mark.asyncio
async def test_process_pipeline_concise_analysis(monkeypatch, tmp_path: Path) -> None:
    input_file = tmp_path / "clip.mp4"
    input_file.write_bytes(b"video")
    output_dir = tmp_path / "concise"

    class FakeExtractor:
        async def extract_audio_async(self, input_path, output_path, *_args, **_kwargs):
            output_path.write_bytes(b"audio")
            return output_path

    class FakeTranscriptionService:
        async def transcribe_with_progress(self, *_args, **_kwargs):
            return SimpleNamespace(
                provider_name="mock",
                audio_file=str(output_dir / "clip.mp3"),
                duration=1.0,
                transcript="text",
            )

        def save_transcription_result(self, _result, dest: Path, provider_name: str | None = None):
            dest.write_text("transcript")

    class FakeConciseAnalyzer:
        def analyze_and_save(self, _transcript, out_dir: Path, stem: str):
            report = out_dir / f"{stem}_concise.md"
            report.write_text("concise")
            return report

    monkeypatch.setattr("src.pipeline.simple_pipeline.ConsoleManager", _DummyConsole)
    monkeypatch.setattr("src.pipeline.simple_pipeline.AsyncAudioExtractor", FakeExtractor)
    monkeypatch.setattr(
        "src.pipeline.simple_pipeline.TranscriptionService", FakeTranscriptionService
    )
    monkeypatch.setattr("src.pipeline.simple_pipeline.ConciseAnalyzer", FakeConciseAnalyzer)

    results = await process_pipeline(
        input_path=input_file,
        output_dir=output_dir,
        quality=AudioQuality.STANDARD,
        analysis_style="concise",
    )

    assert results["success"] is True
    assert results["analysis_files"]
    assert Path(results["analysis_files"][0]).name.endswith("_concise.md")


@pytest.mark.asyncio
async def test_process_pipeline_transcription_failure(monkeypatch, tmp_path: Path) -> None:
    input_file = tmp_path / "broken.mp4"
    input_file.write_bytes(b"video")
    output_dir = tmp_path / "broken_out"

    class FakeExtractor:
        async def extract_audio_async(self, input_path, output_path, *_args, **_kwargs):
            output_path.write_bytes(b"audio")
            return output_path

    class FailingTranscriptionService:
        async def transcribe_with_progress(self, *_args, **_kwargs):
            return None

        def save_transcription_result(self, *_args, **_kwargs):
            raise AssertionError("Should not be called")

    monkeypatch.setattr("src.pipeline.simple_pipeline.ConsoleManager", _DummyConsole)
    monkeypatch.setattr("src.pipeline.simple_pipeline.AsyncAudioExtractor", FakeExtractor)
    monkeypatch.setattr(
        "src.pipeline.simple_pipeline.TranscriptionService", FailingTranscriptionService
    )

    results = await process_pipeline(
        input_path=input_file,
        output_dir=output_dir,
        quality=AudioQuality.HIGH,
        analysis_style="full",
    )

    assert results["success"] is False
    assert any("Transcription failed" in err for err in results["errors"])
    assert "transcription" not in results["stages_completed"]


@pytest.mark.asyncio
async def test_process_pipeline_analysis_failure_cleanup(monkeypatch, tmp_path: Path) -> None:
    """Test that partial files are cleaned up when analysis fails."""
    input_file = tmp_path / "test.mp4"
    input_file.write_bytes(b"video")
    output_dir = tmp_path / "analysis_fail_out"

    class FakeExtractor:
        async def extract_audio_async(self, input_path, output_path, *_args, **_kwargs):
            output_path.write_bytes(b"audio")
            return output_path

    class FakeTranscriptionService:
        async def transcribe_with_progress(self, *_args, **_kwargs):
            return SimpleNamespace(
                provider_name="mock",
                audio_file=str(output_dir / "test.mp3"),
                duration=1.0,
                transcript="test transcript",
            )

        def save_transcription_result(self, _result, dest: Path, provider_name: str | None = None):
            dest.write_text("transcript")

    class FailingAnalyzer:
        def analyze_and_save(self, _transcript, out_dir: Path, stem: str):
            raise RuntimeError("Analysis failed intentionally")

    monkeypatch.setattr("src.pipeline.simple_pipeline.ConsoleManager", _DummyConsole)
    monkeypatch.setattr("src.pipeline.simple_pipeline.AsyncAudioExtractor", FakeExtractor)
    monkeypatch.setattr(
        "src.pipeline.simple_pipeline.TranscriptionService", FakeTranscriptionService
    )
    monkeypatch.setattr("src.pipeline.simple_pipeline.FullAnalyzer", FailingAnalyzer)

    results = await process_pipeline(
        input_path=input_file,
        output_dir=output_dir,
        quality=AudioQuality.SPEECH,
        analysis_style="full",
    )

    assert results["success"] is False
    assert any("Analysis failed" in err for err in results["errors"])
    assert "analysis" not in results["stages_completed"]
    # Verify partial files were cleaned up
    audio_file = output_dir / "test.mp3"
    transcript_file = output_dir / "test_transcript.txt"
    assert not audio_file.exists(), "Audio file should be cleaned up after analysis failure"
    assert not transcript_file.exists(), "Transcript should be cleaned up after analysis failure"


@pytest.mark.asyncio
async def test_process_pipeline_extraction_returns_none_raises_error(
    monkeypatch, tmp_path: Path
) -> None:
    """Test that extract_audio_async returning None raises RuntimeError."""
    input_file = tmp_path / "test.mp4"
    input_file.write_bytes(b"video")
    output_dir = tmp_path / "extraction_none_out"

    class NoneReturningExtractor:
        async def extract_audio_async(self, input_path, output_path, *_args, **_kwargs):
            return None  # Simulate extraction failure

    monkeypatch.setattr("src.pipeline.simple_pipeline.ConsoleManager", _DummyConsole)
    monkeypatch.setattr("src.pipeline.simple_pipeline.AsyncAudioExtractor", NoneReturningExtractor)

    results = await process_pipeline(
        input_path=input_file,
        output_dir=output_dir,
        quality=AudioQuality.SPEECH,
        analysis_style="full",
    )

    assert results["success"] is False
    assert any("Audio extraction failed" in err for err in results["errors"])
    assert "audio_extraction" not in results["stages_completed"]
