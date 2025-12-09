"""Simplified linear audio processing pipeline.

This module replaces the complex orchestration system with a straightforward
linear execution: extract → transcribe → analyze.

The previous implementation had dual orchestration systems (pipeline/ + orchestration/)
totaling ~2,700 LOC for what is fundamentally a 3-step sequential process.
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import TYPE_CHECKING, Literal, NotRequired, Required, TypedDict

from src.utils.logger import get_logger

from ..analysis.concise_analyzer import ConciseAnalyzer
from ..analysis.full_analyzer import FullAnalyzer
from ..models import events as event_models
from ..services.audio_extraction import AudioQuality
from ..services.audio_extraction_async import AsyncAudioExtractor
from ..services.transcription import TranscriptionService
from ..ui.console import ConsoleManager

if TYPE_CHECKING:
    from ..models.transcription import TranscriptionResult

logger = get_logger(__name__)


# =============================================================================
# Type Definitions
# =============================================================================


class StageResult(TypedDict, total=False):
    """Result details for a single pipeline stage."""

    status: Required[Literal["complete", "error", "skipped"]]
    duration: float
    output: str
    files: list[str]
    error: NotRequired[str]


class PipelineResult(TypedDict, total=False):
    """Complete pipeline execution result."""

    success: Required[bool]
    audio_path: str
    transcript: TranscriptionResult
    analysis_files: list[str]
    stages_completed: list[str]
    files_created: list[str]
    errors: list[str]
    stage_results: dict[str, StageResult]


# =============================================================================
# Event helpers
# =============================================================================


def _emit_stage_start(stage: str, description: str, total: int, run_id: str | None) -> None:
    event_models.emit_event(
        "stage_start",
        stage=stage,
        data={"description": description, "total": total},
        run_id=run_id,
    )


def _emit_stage_progress(
    stage: str,
    completed: int,
    total: int,
    message: str,
    run_id: str | None,
) -> None:
    event_models.emit_event(
        "stage_progress",
        stage=stage,
        data={"completed": completed, "total": total, "message": message},
        run_id=run_id,
    )


def _emit_stage_end(stage: str, duration: float, status: str, run_id: str | None) -> None:
    event_models.emit_event(
        "stage_end",
        stage=stage,
        data={"duration": duration, "status": status},
        run_id=run_id,
    )


def _emit_log(message: str, level: str, logger_name: str, run_id: str | None) -> None:
    event_models.emit_event(
        "log",
        data={"message": message, "level": level, "logger": logger_name},
        run_id=run_id,
    )


def _emit_error(stage: str | None, message: str, run_id: str | None) -> None:
    event_models.emit_event("error", stage=stage, data={"message": message}, run_id=run_id)


# =============================================================================
# Internal Stage Functions
# =============================================================================


async def _extract_audio(
    input_path: Path,
    output_dir: Path,
    cm: ConsoleManager,
    quality: AudioQuality,
    run_id: str | None,
) -> tuple[Path, float]:
    """Extract audio from input file directly to output directory.

    Args:
        input_path: Path to input audio/video file
        output_dir: Directory to save extracted audio
        cm: Console manager for progress display

    Returns:
        Tuple of (audio_path, extraction_duration)

    Raises:
        RuntimeError: If extraction fails or returns no path
    """
    cm.print_stage("Audio Extraction", "starting")
    _emit_stage_start("extract", "Extracting audio", 100, run_id)
    start: float = time.time()

    # Extract directly to output directory (no temp copy needed)
    audio_path: Path = output_dir / f"{input_path.stem}.mp3"

    with cm.progress_context("Extracting audio...", total=100) as progress:
        extractor = AsyncAudioExtractor()

        def progress_callback(completed: int, total: int) -> None:
            progress.update(completed, total, "Extracting audio...")
            _emit_stage_progress("extract", completed, total or 100, "Extracting audio...", run_id)

        extracted_path: Path | None = await extractor.extract_audio_async(
            input_path, audio_path, quality, progress_callback=progress_callback
        )

    if extracted_path is None:
        raise RuntimeError("Audio extraction failed")

    duration: float = time.time() - start
    cm.print_stage("Audio Extraction", "complete")
    _emit_stage_end("extract", duration, "complete", run_id)
    logger.info(f"Audio extracted to: {extracted_path} ({duration:.2f}s)")
    _emit_log(f"Audio extracted to: {extracted_path}", "INFO", __name__, run_id)

    return Path(extracted_path), duration


async def _transcribe_audio(
    audio_path: Path,
    provider: str,
    language: str,
    cm: ConsoleManager,
    service: TranscriptionService,
    run_id: str | None,
) -> tuple[TranscriptionResult, float]:
    """Transcribe audio file using provided service instance.

    Args:
        audio_path: Path to audio file
        provider: Provider name or "auto"
        language: Language code for transcription
        cm: Console manager for progress display
        service: Transcription service instance

    Returns:
        Tuple of (transcript, transcription_duration)

    Raises:
        RuntimeError: If transcription fails or returns None
    """
    # Import at runtime to avoid circular import in TYPE_CHECKING block
    from ..models.transcription import TranscriptionResult as TranscriptionResultType

    cm.print_stage("Transcription", "starting")
    _emit_stage_start("transcribe", "Transcribing audio", 100, run_id)
    start: float = time.time()

    with cm.progress_context("Transcribing audio...", total=100) as progress:

        def progress_callback(completed: int, total: int) -> None:
            progress.update(completed, total, "Transcribing audio...")
            _emit_stage_progress(
                "transcribe", completed, total or 100, "Transcribing audio...", run_id
            )

        provider_name: str | None = None if provider == "auto" else provider
        transcript: TranscriptionResultType | None = await service.transcribe_with_progress(
            audio_path,
            provider_name=provider_name,
            language=language,
            progress_callback=progress_callback,
        )

    if transcript is None:
        raise RuntimeError("Transcription failed")

    duration: float = time.time() - start
    cm.print_stage("Transcription", "complete")
    _emit_stage_end("transcribe", duration, "complete", run_id)
    logger.info(f"Transcription completed ({duration:.2f}s)")
    _emit_log("Transcription completed", "INFO", __name__, run_id)

    return transcript, duration


async def _analyze_transcript(
    transcript: TranscriptionResult,
    output_dir: Path,
    input_stem: str,
    analysis_style: str,
    cm: ConsoleManager,
    run_id: str | None,
) -> tuple[list[str], float]:
    """Analyze transcript and save results.

    Args:
        transcript: Transcription result to analyze
        output_dir: Directory to save analysis files
        input_stem: Input file stem for naming output files
        analysis_style: Either "concise" or "full"
        cm: Console manager for progress display

    Returns:
        Tuple of (analysis_files, analysis_duration)
    """
    cm.print_stage("Analysis", "starting")
    _emit_stage_start("analyze", "Analyzing transcript", 100, run_id)
    start: float = time.time()
    analysis_files: list[str] = []

    with cm.progress_context("Analyzing content...", total=100) as progress:
        progress.update(20)
        _emit_stage_progress("analyze", 20, 100, "Preparing analysis...", run_id)

        if analysis_style == "concise":
            concise_analyzer = ConciseAnalyzer()
            progress.update(60)
            _emit_stage_progress("analyze", 60, 100, "Running concise analysis...", run_id)
            result_path: Path = await asyncio.to_thread(
                concise_analyzer.analyze_and_save, transcript, output_dir, input_stem
            )
            progress.update(100)
            _emit_stage_progress("analyze", 100, 100, "Finalizing analysis...", run_id)
            analysis_files = [str(result_path)]
        else:
            full_analyzer = FullAnalyzer()
            progress.update(60)
            _emit_stage_progress("analyze", 60, 100, "Running full analysis...", run_id)
            paths: dict[str, Path] = await asyncio.to_thread(
                full_analyzer.analyze_and_save, transcript, output_dir, input_stem
            )
            progress.update(100)
            _emit_stage_progress("analyze", 100, 100, "Finalizing analysis...", run_id)
            analysis_files = [str(p) for p in paths.values()]

    duration: float = time.time() - start
    cm.print_stage("Analysis", "complete")
    _emit_stage_end("analyze", duration, "complete", run_id)
    logger.info(f"Analysis completed ({duration:.2f}s)")
    _emit_log("Analysis completed", "INFO", __name__, run_id)

    return analysis_files, duration


def _cleanup_on_failure(files: list[str]) -> None:
    """Clean up partial files on pipeline failure.

    Args:
        files: List of file paths to clean up
    """
    for file_path in files:
        try:
            p = Path(file_path)
            if p.exists():
                p.unlink()
                logger.debug(f"Cleaned up partial file: {file_path}")
        except OSError as e:
            logger.warning(f"Failed to cleanup {file_path}: {e}")


# =============================================================================
# Main Pipeline Function
# =============================================================================


async def process_pipeline(
    input_path: str | Path,
    output_dir: str | Path,
    quality: AudioQuality = AudioQuality.SPEECH,
    language: str = "en",
    provider: str = "auto",
    analysis_style: str = "full",
    console_manager: ConsoleManager | None = None,
    run_id: str | None = None,
) -> PipelineResult:
    """Process audio/video file through extraction → transcription → analysis pipeline.

    This is a simplified linear pipeline that replaces the complex workflow orchestration
    system. All steps execute sequentially with proper error handling.

    Args:
        input_path: Path to input audio or video file
        output_dir: Directory to save results
        quality: Audio extraction quality preset
        language: Language code for transcription (e.g., 'en', 'es')
        provider: Transcription provider ('deepgram', 'elevenlabs', 'auto')
        analysis_style: Analysis style ('concise' or 'full')
        console_manager: Optional console manager for progress display
        run_id: Optional run identifier for TUI event emission

    Returns:
        Dictionary containing:
            - success: bool - Whether pipeline completed successfully
            - audio_path: str - Path to extracted audio file
            - transcript: TranscriptionResult - Transcription result object
            - analysis_files: list - Paths to generated analysis files
            - stages_completed: list - List of completed stage names
            - files_created: list - All files created during processing
            - errors: list - Any errors encountered
            - stage_results: dict - Detailed timing for each stage
    """
    total_start = time.time()
    input_path = Path(input_path)
    output_dir = Path(output_dir)

    # Create console manager if not provided
    cm = console_manager or ConsoleManager()
    cm.setup_logging(logger)

    # Create shared service instance (reused across stages)
    service = TranscriptionService()

    # Initialize result tracking
    results: PipelineResult = {
        "success": False,
        "stages_completed": [],
        "files_created": [],
        "errors": [],
        "stage_results": {},
    }

    try:
        output_dir.mkdir(parents=True, exist_ok=True)

        # Stage 1: Audio Extraction (directly to output_dir, no temp copy needed)
        try:
            audio_path, extraction_duration = await _extract_audio(
                input_path, output_dir, cm, quality, run_id
            )
            results["audio_path"] = str(audio_path)
            results["files_created"].append(str(audio_path))
            results["stages_completed"].append("audio_extraction")
            results["stage_results"]["extraction"] = {
                "status": "complete",
                "duration": extraction_duration,
                "output": str(audio_path),
            }
        except Exception as e:
            results["errors"].append(f"Audio extraction failed: {e!s}")
            logger.exception("Audio extraction failed")
            _emit_error("extract", str(e), run_id)
            raise

        # Stage 2: Transcription (reuse service instance)
        try:
            transcript, transcription_duration = await _transcribe_audio(
                audio_path, provider, language, cm, service, run_id
            )
            results["transcript"] = transcript
            results["stages_completed"].append("transcription")
            results["stage_results"]["transcription"] = {
                "status": "complete",
                "duration": transcription_duration,
            }

            # Save transcript file (reuse same service instance)
            transcript_path = output_dir / f"{input_path.stem}_transcript.txt"
            service.save_transcription_result(
                transcript, transcript_path, provider_name=transcript.provider_name
            )
            results["files_created"].append(str(transcript_path))
        except Exception as e:
            results["errors"].append(f"Transcription failed: {e!s}")
            logger.exception("Transcription failed")
            _emit_error("transcribe", str(e), run_id)
            results["success"] = False
            _cleanup_on_failure(results.get("files_created", []))
            return results

        # Stage 3: Analysis
        try:
            analysis_files, analysis_duration = await _analyze_transcript(
                transcript, output_dir, input_path.stem, analysis_style, cm, run_id
            )
            results["analysis_files"] = analysis_files
            results["files_created"].extend(analysis_files)
            results["stages_completed"].append("analysis")
            results["stage_results"]["analysis"] = {
                "status": "complete",
                "duration": analysis_duration,
                "files": analysis_files,
            }
            results["success"] = True
        except Exception as e:
            results["errors"].append(f"Analysis failed: {e!s}")
            logger.exception("Analysis failed")
            _emit_error("analyze", str(e), run_id)
            results["success"] = False
            _cleanup_on_failure(results.get("files_created", []))

        # Finalize
        total_duration = time.time() - total_start
        results["stage_results"]["total"] = {"status": "complete", "duration": total_duration}

        cm.print_summary(results["stage_results"])
        logger.info(f"Pipeline completed in {total_duration:.2f}s. Results: {output_dir}")

        return results

    except Exception as e:
        if not results["errors"]:
            results["errors"].append(f"Pipeline failed: {e!s}")
        logger.exception("Pipeline processing failed")
        cm.print_stage("Pipeline", "error")
        _emit_error(None, str(e), run_id)
        _cleanup_on_failure(results.get("files_created", []))
        return results
