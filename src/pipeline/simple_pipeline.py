"""Simplified linear audio processing pipeline.

This module replaces the complex orchestration system with a straightforward
linear execution: extract → transcribe → analyze.

The previous implementation had dual orchestration systems (pipeline/ + orchestration/)
totaling ~2,700 LOC for what is fundamentally a 3-step sequential process.
"""

from __future__ import annotations

import asyncio
import logging
import tempfile
import time
from pathlib import Path
from typing import Any

from ..analysis.concise_analyzer import ConciseAnalyzer
from ..analysis.full_analyzer import FullAnalyzer
from ..services.audio_extraction import AudioQuality
from ..services.audio_extraction_async import AsyncAudioExtractor
from ..services.transcription import TranscriptionService
from ..ui.console import ConsoleManager

logger = logging.getLogger(__name__)


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

    # Create temporary directory for intermediate files
    temp_dir = Path(tempfile.mkdtemp(prefix="audio_pipeline_"))

    # Initialize result tracking
    results = {
        "success": False,
        "stages_completed": [],
        "files_created": [],
        "errors": [],
        "stage_results": {},
    }

    try:
        # Ensure output directory exists
        output_dir.mkdir(parents=True, exist_ok=True)

        # ============================================================
        # Stage 1: Audio Extraction
        # ============================================================
        cm.print_stage("Audio Extraction", "starting")
        extraction_start = time.time()

        try:
            audio_path = temp_dir / f"{input_path.stem}.mp3"

            with cm.progress_context("Extracting audio...", total=100) as progress:
                extractor = AsyncAudioExtractor()

                def progress_callback(completed: int, total: int) -> None:
                    progress.update(completed, total, "Extracting audio...")

                progress.update(10)
                extracted_path = await extractor.extract_audio_async(
                    input_path, audio_path, quality, progress_callback=progress_callback
                )
                progress.update(100)

            if not extracted_path:
                raise RuntimeError("Audio extraction failed")

            audio_path = Path(extracted_path)
            extraction_duration = time.time() - extraction_start

            results["audio_path"] = str(audio_path)
            results["files_created"].append(str(audio_path))
            results["stages_completed"].append("audio_extraction")
            results["stage_results"]["extraction"] = {
                "status": "complete",
                "duration": extraction_duration,
                "output": str(audio_path),
            }

            cm.print_stage("Audio Extraction", "complete")
            logger.info(f"Audio extracted to: {audio_path} ({extraction_duration:.2f}s)")

        except Exception as e:
            error_msg = f"Audio extraction failed: {e!s}"
            results["errors"].append(error_msg)
            logger.error(error_msg)
            raise  # Cannot continue without audio

        # ============================================================
        # Stage 2: Transcription
        # ============================================================
        cm.print_stage("Transcription", "starting")
        transcription_start = time.time()

        try:
            with cm.progress_context("Transcribing audio...", total=100) as progress:
                service = TranscriptionService()

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

            transcription_duration = time.time() - transcription_start

            results["transcript"] = transcript
            results["stages_completed"].append("transcription")
            results["stage_results"]["transcription"] = {
                "status": "complete",
                "duration": transcription_duration,
            }

            # Save transcript file
            transcript_path = output_dir / f"{input_path.stem}_transcript.txt"
            service.save_transcription_result(
                transcript,
                transcript_path,
                provider_name=transcript.provider_name,
            )
            results["files_created"].append(str(transcript_path))

            cm.print_stage("Transcription", "complete")
            logger.info(f"Transcription completed ({transcription_duration:.2f}s)")

        except Exception as e:
            error_msg = f"Transcription failed: {e!s}"
            results["errors"].append(error_msg)
            logger.error(error_msg)
            # Return early - cannot analyze without transcript
            results["success"] = False
            return results

        # ============================================================
        # Stage 3: Analysis
        # ============================================================
        cm.print_stage("Analysis", "starting")
        analysis_start = time.time()
        analysis_files = []

        try:
            with cm.progress_context("Analyzing content...", total=100) as progress:
                progress.update(20)

                if analysis_style == "concise":
                    analyzer = ConciseAnalyzer()
                    progress.update(60)
                    result_path = await asyncio.to_thread(
                        analyzer.analyze_and_save,
                        transcript,
                        output_dir,
                        input_path.stem,
                    )
                    progress.update(100)
                    analysis_files = [str(result_path)]
                else:
                    # Full analysis
                    analyzer = FullAnalyzer()
                    progress.update(60)
                    paths = await asyncio.to_thread(
                        analyzer.analyze_and_save,
                        transcript,
                        output_dir,
                        input_path.stem,
                    )
                    progress.update(100)
                    analysis_files = [str(p) for p in paths.values()]

            analysis_duration = time.time() - analysis_start

            results["analysis_files"] = analysis_files
            results["files_created"].extend(analysis_files)
            results["stages_completed"].append("analysis")
            results["stage_results"]["analysis"] = {
                "status": "complete",
                "duration": analysis_duration,
                "files": analysis_files,
            }

            # Mark overall success
            results["success"] = True

            cm.print_stage("Analysis", "complete")
            logger.info(f"Analysis completed ({analysis_duration:.2f}s)")

        except Exception as e:
            error_msg = f"Analysis failed: {e!s}"
            results["errors"].append(error_msg)
            logger.error(error_msg)
            # Analysis failure doesn't prevent overall success if we have transcript
            results["success"] = len(results["stages_completed"]) >= 2

        # ============================================================
        # Copy audio to output directory
        # ============================================================
        final_audio_path = output_dir / f"{input_path.stem}.mp3"
        if not final_audio_path.exists() and audio_path.exists():
            import shutil

            shutil.copy2(audio_path, final_audio_path)
            logger.info(f"Audio saved to: {final_audio_path}")

        # ============================================================
        # Finalize and report
        # ============================================================
        total_duration = time.time() - total_start
        results["stage_results"]["total"] = {
            "status": "complete",
            "duration": total_duration,
        }

        cm.print_summary(results["stage_results"])
        logger.info(f"Pipeline completed successfully in {total_duration:.2f}s")
        logger.info(f"Results saved to: {output_dir}")

        return results

    except Exception as e:
        # Final error handler
        if not results["errors"]:
            results["errors"].append(f"Pipeline failed: {e!s}")

        logger.exception("Pipeline processing failed")
        cm.print_stage("Pipeline", "error")

        # Clean up partial files on failure
        for file_path in results.get("files_created", []):
            try:
                if Path(file_path).exists():
                    Path(file_path).unlink()
                    logger.debug(f"Cleaned up partial file: {file_path}")
            except Exception as cleanup_error:
                logger.warning(f"Failed to cleanup {file_path}: {cleanup_error}")

        return results

    finally:
        # Clean up temporary directory
        try:
            import shutil

            if temp_dir.exists():
                shutil.rmtree(temp_dir)
                logger.debug(f"Cleaned up temporary directory: {temp_dir}")
        except Exception as e:
            logger.warning(f"Failed to clean up temp directory: {e}")
