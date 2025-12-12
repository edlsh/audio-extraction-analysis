"""Simplified linear audio processing pipeline.

This module replaces the complex orchestration system with a straightforward
linear execution: extract → transcribe → analyze.

Key improvements:
- Uses StageReporter for cleaner event emission
- Uses PipelineResult with typed errors for better error handling
- Uses ArtifactTier for smarter cleanup on partial failures
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, NotRequired, Required, TypedDict

from src.utils.logger import get_logger

from ..analysis.concise_analyzer import ConciseAnalyzer
from ..analysis.full_analyzer import FullAnalyzer
from ..models.events import EventSink
from ..services.audio_extraction import AudioQuality
from ..services.audio_extraction_async import AsyncAudioExtractor
from ..services.transcription import TranscriptionService
from ..ui.console import ConsoleManager
from .reporter import StageReporter, create_reporter
from .result import ArtifactTier, PipelineError, StageResult
from .result import PipelineResult as PipelineResultDataclass

if TYPE_CHECKING:
    from ..models.transcription import TranscriptionResult

logger = get_logger(__name__)


# =============================================================================
# Legacy Type Definitions (for backward compatibility)
# =============================================================================


class StageResultDict(TypedDict, total=False):
    """Result details for a single pipeline stage (legacy TypedDict)."""

    status: Required[Literal["complete", "error", "skipped"]]
    duration: float
    output: str
    files: list[str]
    error: NotRequired[str]


class PipelineResult(TypedDict, total=False):
    """Complete pipeline execution result (legacy TypedDict for backward compatibility)."""

    success: Required[bool]
    audio_path: str
    transcript: TranscriptionResult
    analysis_files: list[str]
    stages_completed: list[str]
    files_created: list[str]
    errors: list[str]
    stage_results: dict[str, StageResultDict]


# =============================================================================
# Internal Stage Functions (using StageReporter)
# =============================================================================


async def _extract_audio(
    input_path: Path,
    output_dir: Path,
    cm: ConsoleManager,
    quality: AudioQuality,
    reporter: StageReporter,
) -> tuple[Path, float]:
    """Extract audio from input file directly to output directory.

    Args:
        input_path: Path to input audio/video file
        output_dir: Directory to save extracted audio
        cm: Console manager for progress display
        quality: Audio quality preset
        reporter: Stage reporter for event emission

    Returns:
        Tuple of (audio_path, extraction_duration)

    Raises:
        AudioExtractionError: If extraction fails
    """
    from ..exceptions import AudioExtractionError

    cm.print_stage("Audio Extraction", "starting")

    with reporter.stage_context("extract", "Extracting audio", 100) as stage:
        start: float = time.time()
        audio_path: Path = output_dir / f"{input_path.stem}.mp3"

        with cm.progress_context("Extracting audio...", total=100) as progress:
            extractor = AsyncAudioExtractor()

            def progress_callback(completed: int, total: int) -> None:
                progress.update(completed, total, "Extracting audio...")
                stage.progress(completed, "Extracting audio...")

            extracted_path: Path | None = await extractor.extract_audio_async(
                input_path, audio_path, quality, progress_callback=progress_callback
            )

        if extracted_path is None:
            raise AudioExtractionError(
                "Audio extraction returned no path",
                context={"input_path": str(input_path), "output_path": str(audio_path)},
            )

        duration: float = time.time() - start
        cm.print_stage("Audio Extraction", "complete")
        reporter.log(f"Audio extracted to: {extracted_path}", "INFO", __name__)

        return Path(extracted_path), duration


async def _transcribe_audio(
    audio_path: Path,
    provider: str,
    language: str,
    cm: ConsoleManager,
    service: TranscriptionService,
    reporter: StageReporter,
) -> tuple[TranscriptionResult, float]:
    """Transcribe audio file using provided service instance.

    Args:
        audio_path: Path to audio file
        provider: Provider name or "auto"
        language: Language code for transcription
        cm: Console manager for progress display
        service: Transcription service instance
        reporter: Stage reporter for event emission

    Returns:
        Tuple of (transcript, transcription_duration)

    Raises:
        TranscriptionError: If transcription fails
    """
    from ..exceptions import TranscriptionError
    from ..models.transcription import TranscriptionResult as TranscriptionResultType

    cm.print_stage("Transcription", "starting")

    with reporter.stage_context("transcribe", "Transcribing audio", 100) as stage:
        start: float = time.time()

        with cm.progress_context("Transcribing audio...", total=100) as progress:

            def progress_callback(completed: int, total: int) -> None:
                progress.update(completed, total, "Transcribing audio...")
                stage.progress(completed, "Transcribing audio...")

            provider_name: str | None = None if provider == "auto" else provider
            transcript: TranscriptionResultType | None = await service.transcribe_with_progress(
                audio_path,
                provider_name=provider_name,
                language=language,
                progress_callback=progress_callback,
            )

        if transcript is None:
            raise TranscriptionError(
                "Transcription returned no result",
                context={"audio_path": str(audio_path), "provider": provider},
            )

        duration: float = time.time() - start
        cm.print_stage("Transcription", "complete")
        reporter.log("Transcription completed", "INFO", __name__)

        return transcript, duration


async def _analyze_transcript(
    transcript: TranscriptionResult,
    output_dir: Path,
    input_stem: str,
    analysis_style: str,
    cm: ConsoleManager,
    reporter: StageReporter,
) -> tuple[list[str], float]:
    """Analyze transcript and save results.

    Args:
        transcript: Transcription result to analyze
        output_dir: Directory to save analysis files
        input_stem: Input file stem for naming output files
        analysis_style: Either "concise" or "full"
        cm: Console manager for progress display
        reporter: Stage reporter for event emission

    Returns:
        Tuple of (analysis_files, analysis_duration)
    """
    cm.print_stage("Analysis", "starting")

    with reporter.stage_context("analyze", "Analyzing transcript", 100) as stage:
        start: float = time.time()
        analysis_files: list[str] = []

        with cm.progress_context("Analyzing content...", total=100) as progress:
            progress.update(20)
            stage.progress(20, "Preparing analysis...")

            if analysis_style == "concise":
                concise_analyzer = ConciseAnalyzer()
                progress.update(60)
                stage.progress(60, "Running concise analysis...")
                result_path: Path = await asyncio.to_thread(
                    concise_analyzer.analyze_and_save, transcript, output_dir, input_stem
                )
                progress.update(100)
                stage.progress(100, "Finalizing analysis...")
                analysis_files = [str(result_path)]
            else:
                full_analyzer = FullAnalyzer()
                progress.update(60)
                stage.progress(60, "Running full analysis...")
                paths: dict[str, Path] = await asyncio.to_thread(
                    full_analyzer.analyze_and_save, transcript, output_dir, input_stem
                )
                progress.update(100)
                stage.progress(100, "Finalizing analysis...")
                analysis_files = [str(p) for p in paths.values()]

        duration: float = time.time() - start
        cm.print_stage("Analysis", "complete")
        reporter.log("Analysis completed", "INFO", __name__)

        return analysis_files, duration


def _cleanup_artifacts(result: PipelineResultDataclass, failed_stage: str | None = None) -> None:
    """Clean up artifacts based on tier and failed stage.

    Args:
        result: Pipeline result with artifacts
        failed_stage: Stage that failed (for selective cleanup)
    """
    targets = result.get_cleanup_targets(failed_stage)
    for path in targets:
        try:
            if path.exists():
                path.unlink()
                logger.debug(f"Cleaned up artifact: {path}")
        except OSError as e:
            logger.warning(f"Failed to cleanup {path}: {e}")


def _result_to_dict(result: PipelineResultDataclass) -> PipelineResult:
    """Convert PipelineResultDataclass to legacy PipelineResult TypedDict.

    Maintains backward compatibility with existing consumers.
    """
    legacy: PipelineResult = {
        "success": result.success,
        "stages_completed": result.stages_completed,
        "files_created": result.files_created,
        "errors": result.error_messages,
        "stage_results": {},
    }

    if result.audio_path:
        legacy["audio_path"] = result.audio_path
    if result.transcript:
        legacy["transcript"] = result.transcript
    if result.analysis_files:
        legacy["analysis_files"] = result.analysis_files

    for name, stage_result in result.stage_results.items():
        legacy["stage_results"][name] = {
            "status": stage_result.status,
            "duration": stage_result.duration,
        }
        if stage_result.output:
            legacy["stage_results"][name]["output"] = stage_result.output
        if stage_result.files:
            legacy["stage_results"][name]["files"] = stage_result.files
        if stage_result.error:
            legacy["stage_results"][name]["error"] = stage_result.error.message

    return legacy


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
    event_sink: EventSink | None = None,
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
        event_sink: Optional event sink for direct event emission (bypasses thread-local)

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

    # Create stage reporter for event emission
    reporter = create_reporter(run_id=run_id, event_sink=event_sink)

    # Create shared service instance (reused across stages)
    service = TranscriptionService()

    # Initialize result tracking with new dataclass
    result = PipelineResultDataclass()

    try:
        output_dir.mkdir(parents=True, exist_ok=True)

        # Stage 1: Audio Extraction
        try:
            extract_start = time.time()
            audio_path, extraction_duration = await _extract_audio(
                input_path, output_dir, cm, quality, reporter
            )
            result.audio_path = str(audio_path)
            result.add_artifact(audio_path, "extract", ArtifactTier.INTERMEDIATE, "audio")
            result.stages_completed.append("audio_extraction")
            result.stage_results["extraction"] = StageResult(
                status="complete",
                duration=extraction_duration,
                output=str(audio_path),
            )
        except Exception as e:
            duration = time.time() - extract_start
            message = f"Audio extraction failed: {e!s}"
            result.add_error_message(message, "extract", error_type=type(e).__name__)
            result.stage_results["extraction"] = StageResult(
                status="error",
                duration=duration,
                error=PipelineError(
                    message=message,
                    error_type=type(e).__name__,
                    stage="extract",
                    original_exception=e,
                ),
            )
            logger.exception("Audio extraction failed")
            cm.print_stage("Audio Extraction", "error")
            result.success = False
            _cleanup_artifacts(result, "extract")
            return _result_to_dict(result)

        # Stage 2: Transcription
        try:
            transcribe_start = time.time()
            transcript, transcription_duration = await _transcribe_audio(
                audio_path, provider, language, cm, service, reporter
            )
            result.transcript = transcript
            result.stages_completed.append("transcription")
            result.stage_results["transcription"] = StageResult(
                status="complete",
                duration=transcription_duration,
            )

            # Save transcript file (valuable artifact - keep on partial failure)
            transcript_path = output_dir / f"{input_path.stem}_transcript.txt"
            service.save_transcription_result(
                transcript, transcript_path, provider_name=transcript.provider_name
            )
            result.add_artifact(transcript_path, "transcribe", ArtifactTier.VALUABLE, "transcript")
        except Exception as e:
            duration = time.time() - transcribe_start
            message = f"Transcription failed: {e!s}"
            result.add_error_message(message, "transcribe", error_type=type(e).__name__)
            result.stage_results["transcription"] = StageResult(
                status="error",
                duration=duration,
                error=PipelineError(
                    message=message,
                    error_type=type(e).__name__,
                    stage="transcribe",
                    original_exception=e,
                ),
            )
            logger.exception("Transcription failed")
            result.success = False
            _cleanup_artifacts(result, "transcribe")
            return _result_to_dict(result)

        # Stage 3: Analysis
        try:
            analyze_start = time.time()
            analysis_files, analysis_duration = await _analyze_transcript(
                transcript, output_dir, input_path.stem, analysis_style, cm, reporter
            )
            result.analysis_files = analysis_files
            for af in analysis_files:
                result.add_artifact(af, "analyze", ArtifactTier.VALUABLE, "analysis")
            result.stages_completed.append("analysis")
            result.stage_results["analysis"] = StageResult(
                status="complete",
                duration=analysis_duration,
                files=analysis_files,
            )
            result.success = True
        except Exception as e:
            duration = time.time() - analyze_start
            message = f"Analysis failed: {e!s}"
            result.add_error_message(message, "analyze", error_type=type(e).__name__)
            result.stage_results["analysis"] = StageResult(
                status="error",
                duration=duration,
                error=PipelineError(
                    message=message,
                    error_type=type(e).__name__,
                    stage="analyze",
                    original_exception=e,
                ),
            )
            logger.exception("Analysis failed")
            # Graceful degradation: success if we have transcript (extraction + transcription)
            result.success = len(result.stages_completed) >= 2
            _cleanup_artifacts(result, "analyze")

        # Finalize
        total_duration = time.time() - total_start
        result.stage_results["total"] = StageResult(status="complete", duration=total_duration)

        cm.print_summary(_result_to_dict(result)["stage_results"])
        logger.info(f"Pipeline completed in {total_duration:.2f}s. Results: {output_dir}")

        return _result_to_dict(result)

    except Exception as e:
        if not result.errors:
            result.add_error_message(f"Pipeline failed: {e!s}", None, error_type=type(e).__name__)
        logger.exception("Pipeline processing failed")
        cm.print_stage("Pipeline", "error")
        reporter.error(str(e), None)
        _cleanup_artifacts(result, None)
        return _result_to_dict(result)


# Also export the new dataclass version for advanced usage
async def process_pipeline_v2(
    input_path: str | Path,
    output_dir: str | Path,
    quality: AudioQuality = AudioQuality.SPEECH,
    language: str = "en",
    provider: str = "auto",
    analysis_style: str = "full",
    console_manager: ConsoleManager | None = None,
    run_id: str | None = None,
    event_sink: EventSink | None = None,
) -> PipelineResultDataclass:
    """Process pipeline returning new PipelineResult dataclass with typed errors.

    This is the new API that returns PipelineResultDataclass with:
    - Typed error objects (not just strings)
    - Artifact tiering for smart cleanup
    - Exit code suggestions

    See process_pipeline() for argument documentation.
    """
    # Run pipeline with legacy result
    legacy_result = await process_pipeline(
        input_path=input_path,
        output_dir=output_dir,
        quality=quality,
        language=language,
        provider=provider,
        analysis_style=analysis_style,
        console_manager=console_manager,
        run_id=run_id,
        event_sink=event_sink,
    )

    # Convert back to dataclass (this is a bit redundant but maintains backward compat)
    result = PipelineResultDataclass(
        success=legacy_result["success"],
        audio_path=legacy_result.get("audio_path", ""),
        transcript=legacy_result.get("transcript"),
        analysis_files=legacy_result.get("analysis_files", []),
        stages_completed=legacy_result.get("stages_completed", []),
    )

    # Add error messages as PipelineError objects
    for err_msg in legacy_result.get("errors", []):
        result.add_error_message(err_msg)

    return result
