"""Simplified linear audio processing pipeline.

This module replaces the complex orchestration system with a straightforward
linear execution: extract → transcribe → analyze.

The previous implementation had dual orchestration systems (pipeline/ + orchestration/)
totaling ~2,700 LOC for what is fundamentally a 3-step sequential process.
"""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..analysis.concise_analyzer import ConciseAnalyzer
from ..analysis.full_analyzer import FullAnalyzer
from ..services.audio_extraction import AudioQuality
from ..services.audio_extraction_async import AsyncAudioExtractor
from ..services.transcription import TranscriptionService
from ..ui.console import ConsoleManager

if TYPE_CHECKING:
    from ..models.transcription import TranscriptionResult

logger = logging.getLogger(__name__)


async def _extract_audio(
    input_path: Path,
    output_dir: Path,
    cm: ConsoleManager,
) -> tuple[Path, float]:
    """Extract audio from input file directly to output directory.

    Returns:
        Tuple of (audio_path, extraction_duration)

    Raises:
        RuntimeError: If extraction fails
    """
    cm.print_stage("Audio Extraction", "starting")
    start = time.time()

    # Extract directly to output directory (no temp copy needed)
    audio_path = output_dir / f"{input_path.stem}.mp3"

    with cm.progress_context("Extracting audio...", total=100) as progress:
        extractor = AsyncAudioExtractor()

        def progress_callback(completed: int, total: int) -> None:
            progress.update(completed, total, "Extracting audio...")

        progress.update(10)
        extracted_path = await extractor.extract_audio_async(
            input_path, audio_path, AudioQuality.SPEECH, progress_callback=progress_callback
        )
        progress.update(100)

    if not extracted_path:
        raise RuntimeError("Audio extraction failed")

    duration = time.time() - start
    cm.print_stage("Audio Extraction", "complete")
    logger.info(f"Audio extracted to: {extracted_path} ({duration:.2f}s)")

    return Path(extracted_path), duration


async def _transcribe_audio(
    audio_path: Path,
    provider: str,
    language: str,
    cm: ConsoleManager,
    service: TranscriptionService,
) -> tuple[TranscriptionResult, float]:
    """Transcribe audio file using provided service instance.

    Returns:
        Tuple of (transcript, transcription_duration)

    Raises:
        RuntimeError: If transcription fails
    """
    cm.print_stage("Transcription", "starting")
    start = time.time()

    with cm.progress_context("Transcribing audio...", total=100) as progress:

        def progress_callback(completed: int, total: int) -> None:
            progress.update(completed, total, "Transcribing audio...")

        progress.update(10)

        provider_name = None if provider == "auto" else provider
        transcript = await service.transcribe_with_progress(
            audio_path,
            provider_name=provider_name,
            language=language,
            progress_callback=progress_callback,
        )
        progress.update(100)

    if not transcript:
        raise RuntimeError("Transcription failed")

    duration = time.time() - start
    cm.print_stage("Transcription", "complete")
    logger.info(f"Transcription completed ({duration:.2f}s)")

    return transcript, duration


async def _analyze_transcript(
    transcript: TranscriptionResult,
    output_dir: Path,
    input_stem: str,
    analysis_style: str,
    cm: ConsoleManager,
) -> tuple[list[str], float]:
    """Analyze transcript and save results.

    Returns:
        Tuple of (analysis_files, analysis_duration)
    """
    cm.print_stage("Analysis", "starting")
    start = time.time()

    with cm.progress_context("Analyzing content...", total=100) as progress:
        progress.update(20)

        if analysis_style == "concise":
            analyzer = ConciseAnalyzer()
            progress.update(60)
            result_path = await asyncio.to_thread(
                analyzer.analyze_and_save, transcript, output_dir, input_stem
            )
            progress.update(100)
            analysis_files = [str(result_path)]
        else:
            analyzer = FullAnalyzer()
            progress.update(60)
            paths = await asyncio.to_thread(
                analyzer.analyze_and_save, transcript, output_dir, input_stem
            )
            progress.update(100)
            analysis_files = [str(p) for p in paths.values()]

    duration = time.time() - start
    cm.print_stage("Analysis", "complete")
    logger.info(f"Analysis completed ({duration:.2f}s)")

    return analysis_files, duration


def _cleanup_on_failure(files: list[str]) -> None:
    """Clean up partial files on pipeline failure."""
    for file_path in files:
        try:
            p = Path(file_path)
            if p.exists():
                p.unlink()
                logger.debug(f"Cleaned up partial file: {file_path}")
        except Exception as e:
            logger.warning(f"Failed to cleanup {file_path}: {e}")


async def process_pipeline(
    input_path: str | Path,
    output_dir: str | Path,
    quality: AudioQuality = AudioQuality.SPEECH,
    language: str = "en",
    provider: str = "auto",
    analysis_style: str = "full",
    console_manager: ConsoleManager | None = None,
) -> dict[str, Any]:
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
    results = {
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
            audio_path, extraction_duration = await _extract_audio(input_path, output_dir, cm)
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
            logger.error(f"Audio extraction failed: {e}")
            raise

        # Stage 2: Transcription (reuse service instance)
        try:
            transcript, transcription_duration = await _transcribe_audio(
                audio_path, provider, language, cm, service
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
            logger.error(f"Transcription failed: {e}")
            results["success"] = False
            return results

        # Stage 3: Analysis
        try:
            analysis_files, analysis_duration = await _analyze_transcript(
                transcript, output_dir, input_path.stem, analysis_style, cm
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
            logger.error(f"Analysis failed: {e}")
            results["success"] = len(results["stages_completed"]) >= 2

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
        _cleanup_on_failure(results.get("files_created", []))
        return results
