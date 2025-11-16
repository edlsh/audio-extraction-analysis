"""Audio processing pipeline that chains extraction and transcription.

DEPRECATED: This class is deprecated as of v1.2.0 and will be removed in v2.0.0.
Please use `src.pipeline.simple_pipeline.process_pipeline()` instead, which provides
a simpler, more maintainable API with the same functionality.

Migration example:
    # Old (deprecated):
    pipeline = AudioProcessingPipeline(temp_dir=temp_dir, console_manager=console)
    result = await pipeline.process_file(input_path, output_dir, **options)

    # New (recommended):
    from src.pipeline.simple_pipeline import process_pipeline
    result = await process_pipeline(input_path, output_dir, console_manager=console, **options)

Enhanced with optional progress tracking via a ConsoleManager for
interactive runs, while preserving the original synchronous API.
"""

from __future__ import annotations

import asyncio
import logging
import os
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from ..ui.console import RichProgressTracker

from ..analysis.concise_analyzer import ConciseAnalyzer
from ..analysis.full_analyzer import FullAnalyzer

if TYPE_CHECKING:
    from ..models.transcription import TranscriptionResult
from ..services.audio_extraction import AudioExtractor, AudioQuality
from ..services.transcription import TranscriptionService
from ..ui.console import ConsoleManager
from ..utils.paths import ensure_subpath, safe_write_json, sanitize_dirname

logger = logging.getLogger(__name__)


class AudioProcessingPipeline:
    """Complete pipeline for video to transcript processing.

    DEPRECATED: This class is deprecated. Use `process_pipeline()` from
    `src.pipeline.simple_pipeline` instead.

    This class maintains backward-compatible synchronous methods and adds
    optional async methods that emit rich progress when a ConsoleManager
    is supplied.
    """

    def __init__(
        self, temp_dir: Path | None = None, console_manager: ConsoleManager | None = None
    ) -> None:
        """Initialize pipeline with optional temporary directory.

        DEPRECATED: Use `process_pipeline()` instead.

        Args:
            temp_dir: Directory for temporary files. If None, uses system temp.
            console_manager: Optional ConsoleManager for rich/progress output
        """
        import warnings

        warnings.warn(
            "AudioProcessingPipeline is deprecated as of v1.2.0 and will be removed in v2.0.0. "
            "Use src.pipeline.simple_pipeline.process_pipeline() instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        if temp_dir:
            self.temp_dir = Path(temp_dir)
            self.temp_dir.mkdir(parents=True, exist_ok=True)
            self._cleanup_temp = False
        else:
            # Use system temp directory
            self.temp_dir = Path(tempfile.mkdtemp(prefix="audio_pipeline_"))
            self._cleanup_temp = True

        logger.info(f"Pipeline initialized with temp dir: {self.temp_dir}")
        self.console_manager = console_manager
        self.stage_results: dict[str, Any] = {}

    def process_video(
        self,
        video_file: Path,
        output_dir: Path,
        quality: AudioQuality = AudioQuality.SPEECH,
        language: str = "en",
        provider: str = "auto",
        analysis_style: str = "concise",
    ) -> TranscriptionResult | None:
        """Process video file through complete extraction and transcription pipeline.

        Args:
            video_file: Input video file path
            output_dir: Directory to save results
            quality: Audio extraction quality preset
            language: Language code for transcription
            provider: Transcription provider to use ('deepgram', 'elevenlabs', 'auto')
            analysis_style: Analysis style ('concise' or 'full')

        Returns:
            TranscriptionResult if successful, None otherwise
        """
        try:
            logger.info(f"Starting pipeline processing: {video_file}")
            output_dir.mkdir(parents=True, exist_ok=True)

            # Step 1: Extract audio
            audio_path = self._extract_audio_from_video(video_file, quality)
            if not audio_path:
                return None

            # Step 2: Transcribe audio
            transcription_result = self._transcribe_audio_file(audio_path, provider, language)
            if not transcription_result:
                return None

            # Step 3: Generate analysis
            self._generate_analysis(
                transcription_result, output_dir, video_file.stem, analysis_style
            )

            # Step 4: Save results
            self._save_pipeline_results(
                transcription_result, output_dir, video_file.stem, audio_path
            )

            logger.info("Pipeline processing completed successfully")
            logger.info(f"Results saved to: {output_dir}")

            return transcription_result

        except Exception as e:
            logger.error(f"Pipeline processing failed: {e}")
            return None

        finally:
            self._cleanup_temp_files()

    def _extract_audio_from_video(self, video_file: Path, quality: AudioQuality) -> Path | None:
        """Extract audio from video file.

        Args:
            video_file: Input video file path
            quality: Audio extraction quality preset

        Returns:
            Path to extracted audio file if successful, None otherwise
        """
        logger.info("Step 1: Extracting audio from video")
        audio_filename = f"{video_file.stem}.mp3"
        audio_path = self.temp_dir / audio_filename

        extractor = AudioExtractor()
        extracted_audio = extractor.extract_audio(video_file, audio_path, quality)

        if not extracted_audio:
            logger.error("Audio extraction failed")
            return None

        logger.info(f"Audio extracted to: {extracted_audio}")
        return extracted_audio

    def _transcribe_audio_file(
        self, audio_path: Path, provider: str, language: str
    ) -> TranscriptionResult | None:
        """Transcribe audio file to text.

        Args:
            audio_path: Path to audio file
            provider: Transcription provider to use ('deepgram', 'elevenlabs', 'auto')
            language: Language code for transcription

        Returns:
            TranscriptionResult if successful, None otherwise
        """
        logger.info("Step 2: Transcribing audio")

        transcription_service = TranscriptionService()
        transcription_result = transcription_service.transcribe(
            audio_path,
            provider_name=provider if provider != "auto" else None,
            language=language,
        )

        if not transcription_result:
            logger.error("Transcription failed")
            return None

        logger.info("Transcription completed successfully")
        return transcription_result

    def _generate_analysis(
        self,
        transcription_result: TranscriptionResult,
        output_dir: Path,
        base_name: str,
        analysis_style: str,
    ) -> None:
        """Generate analysis from transcription result.

        Args:
            transcription_result: Transcription result to analyze
            output_dir: Directory to save analysis
            base_name: Base name for output files
            analysis_style: Analysis style ('concise' or 'full')
        """
        logger.info("Step 3: Generating analysis")

        if analysis_style == "concise":
            analyzer = ConciseAnalyzer()
            analysis_path = analyzer.analyze_and_save(transcription_result, output_dir, base_name)
            logger.info(f"Concise analysis saved to: {analysis_path}")
        elif analysis_style == "full":
            full_analyzer = FullAnalyzer()
            files = full_analyzer.analyze_and_save(transcription_result, output_dir, base_name)
            logger.info("Full analysis saved: " + ", ".join([p.name for p in files.values()]))

    def _save_pipeline_results(
        self,
        transcription_result: TranscriptionResult,
        output_dir: Path,
        base_name: str,
        audio_path: Path,
    ) -> None:
        """Save pipeline results to output directory.

        Args:
            transcription_result: Transcription result to save
            output_dir: Directory to save results
            base_name: Base name for output files
            audio_path: Path to extracted audio file
        """
        logger.info("Step 4: Saving additional results")

        # Save main transcript file
        transcription_service = TranscriptionService()
        transcript_path = output_dir / f"{base_name}_transcript.txt"
        transcription_service.save_transcription_result(
            transcription_result,
            transcript_path,
            provider_name=transcription_result.provider_name,
        )

        # Copy audio file to output directory
        final_audio_path = output_dir / audio_path.name
        if not final_audio_path.exists():
            import shutil

            shutil.copy2(audio_path, final_audio_path)
            logger.info(f"Audio saved to: {final_audio_path}")

    # ---------------------- Async Progress-Enabled API ----------------------
    async def process_file(
        self, input_path: str, output_dir: str, **kwargs: object
    ) -> dict[str, object]:
        """Async processing with rich progress.

        This method performs extraction → transcription → analysis while emitting
        progress updates through the provided ConsoleManager (if any). Returns
        a dictionary of outputs (paths, results, and stage summaries).
        """
        total_start = time.time()

        cm = self.console_manager or ConsoleManager()
        cm.setup_logging(logger)

        results = {"success": False, "stages_completed": [], "files_created": [], "errors": []}

        try:
            # Stage 1: Audio Extraction with real progress
            cm.print_stage("Audio Extraction", "starting")
            extraction_start = time.time()
            try:
                with cm.progress_context("Extracting audio...", total=100) as progress:
                    audio_path = await self._extract_audio_with_progress(
                        input_path, output_dir, progress, **kwargs
                    )
                extraction_duration = time.time() - extraction_start
                self.stage_results["extraction"] = {
                    "status": "complete",
                    "duration": extraction_duration,
                    "output": str(audio_path),
                }
                results["stages_completed"].append("audio_extraction")
                results["files_created"].append(str(audio_path))
                cm.print_stage("Audio Extraction", "complete")
            except Exception as e:
                error_msg = f"Audio extraction failed: {e!s}"
                results["errors"].append(error_msg)
                logger.error(error_msg)
                raise  # Re-raise to prevent continuing with invalid state

            # Stage 2: Transcription with real progress
            cm.print_stage("Transcription", "starting")
            transcription_start = time.time()
            try:
                with cm.progress_context("Transcribing audio...", total=100) as progress:
                    transcript = await self._transcribe_with_progress(
                        audio_path, progress, **kwargs
                    )
                transcription_duration = time.time() - transcription_start
                self.stage_results["transcription"] = {
                    "status": "complete",
                    "duration": transcription_duration,
                }
                results["stages_completed"].append("transcription")
                cm.print_stage("Transcription", "complete")
            except Exception as e:
                error_msg = f"Transcription failed: {e!s}"
                results["errors"].append(error_msg)
                logger.error(error_msg)
                # Cannot continue without valid transcript - return early
                results["success"] = False
                return results

            # Stage 3: Analysis with real progress
            cm.print_stage("Analysis", "starting")
            analysis_start = time.time()
            analysis_results = []
            try:
                with cm.progress_context("Analyzing content...", total=100) as progress:
                    analysis_results = await self._analyze_with_progress(
                        transcript, Path(output_dir), Path(input_path).stem, progress, **kwargs
                    )
                analysis_duration = time.time() - analysis_start
                self.stage_results["analysis"] = {
                    "status": "complete",
                    "duration": analysis_duration,
                    "files": analysis_results,
                }
                results["stages_completed"].append("analysis")
                results["files_created"].extend(
                    analysis_results
                    if isinstance(analysis_results, list)
                    else [str(analysis_results)]
                )
                results["success"] = True
                cm.print_stage("Analysis", "complete")
            except Exception as e:
                error_msg = f"Analysis failed: {e!s}"
                results["errors"].append(error_msg)
                logger.error(error_msg)
                # Analysis failure doesn't prevent overall success if we have transcript
                results["success"] = len(results["stages_completed"]) >= 2

            total_duration = time.time() - total_start
            self.stage_results["total"] = {"status": "complete", "duration": total_duration}
            cm.print_summary(self.stage_results)

            results.update(
                {
                    "audio_path": str(audio_path),
                    "transcript": transcript,
                    "analysis_files": analysis_results if "analysis_results" in locals() else [],
                    "stage_results": self.stage_results,
                }
            )

            return results

        except Exception as e:
            # Final error handler
            if not results["errors"]:  # Don't duplicate errors
                results["errors"].append(f"Pipeline failed: {e!s}")

            # Emit full traceback for diagnostics
            logger.exception("Pipeline processing failed with exception")

            # Persist a debug dump for post-mortem analysis
            try:
                import json
                import traceback as _tb

                debug_dump = {
                    "error": str(e),
                    "traceback": _tb.format_exc(),
                    "stage_results": self.stage_results,
                    "files_created": results.get("files_created", []),
                }
                # Only persist if debug flag enabled
                if os.getenv("AUDIO_PIPELINE_DEBUG", "").lower() in {"1", "true", "yes"}:
                    # Persist to requested output directory if available in context
                    # Fallback to temp dir otherwise
                    dbg_dir = None
                    try:
                        # output_dir is passed into process_file via kwargs; capture from locals
                        dbg_dir = Path(locals().get("output_dir", self.temp_dir))
                    except Exception:
                        dbg_dir = self.temp_dir
                    debug_path = Path(dbg_dir) / "pipeline_debug.json"
                    with open(debug_path, "w", encoding="utf-8") as f:
                        json.dump(debug_dump, f, indent=2)
                    results["debug_path"] = str(debug_path)
            except Exception:
                pass
            cm.print_stage("Pipeline", "error")

            # Attempt graceful cleanup of partial files
            await self._cleanup_partial_files(results.get("files_created", []))

            return results

    async def _cleanup_partial_files(self, file_paths: list[Path | str]) -> None:
        """Clean up partial files on failure."""
        for file_path in file_paths:
            try:
                if Path(file_path).exists():
                    Path(file_path).unlink()
                    if self.console_manager:
                        self.console_manager.print_stage(
                            "Cleanup", f"Cleaned up partial file: {file_path}"
                        )
            except Exception as e:
                if self.console_manager:
                    self.console_manager.print_stage(
                        "Cleanup", f"Failed to cleanup {file_path}: {e}"
                    )

    async def _extract_audio_with_progress(
        self, input_path: str, output_dir: str, progress: object, **kwargs: object
    ) -> Path:
        """Extract audio with progress updates using real progress tracking."""
        # Import the async extractor
        from ..services.audio_extraction_async import AsyncAudioExtractor

        progress.update(10)  # starting
        extractor = AsyncAudioExtractor()

        quality = kwargs.get("quality", AudioQuality.SPEECH)
        # Build a temp output filename in the temp dir first
        out_path = Path(self.temp_dir) / f"{Path(input_path).stem}.mp3"

        # Define progress callback
        def progress_callback(completed: int, total: int) -> None:
            progress.update(completed, total, "Extracting audio...")

        progress.update(30)
        result_path = await extractor.extract_audio_async(
            Path(input_path), out_path, quality, progress_callback=progress_callback
        )
        progress.update(100)
        if not result_path:
            raise RuntimeError("Audio extraction failed")
        return Path(result_path)

    async def _transcribe_with_progress(
        self, audio_path: str | Path, progress: object, **kwargs: object
    ) -> TranscriptionResult:
        """Transcribe with progress updates using TranscriptionService with real progress."""
        progress.update(10)

        service = TranscriptionService()

        # Define progress callback
        def progress_callback(completed: int, total: int) -> None:
            progress.update(completed, total, "Transcribing audio...")

        # Handle "auto" provider by passing None
        provider = kwargs.get("provider")
        provider_name = None if provider == "auto" else provider

        # We emit a synthetic progress curve 10-90% to avoid tight coupling
        # to specific provider callbacks (not all providers support progress).
        result = await service.transcribe_with_progress(
            Path(audio_path),
            provider_name=provider_name,
            language=kwargs.get("language", "en"),
            progress_callback=progress_callback,
        )

        if not result:
            raise RuntimeError("Transcription failed")
        progress.update(100)
        return result

    async def _analyze_with_progress(
        self,
        transcript: TranscriptionResult,
        output_dir: Path,
        base_name: str,
        progress: object,
        **kwargs: object,
    ) -> dict[str, object]:
        """Analyze with progress updates using existing analyzers."""
        progress.update(20)
        analysis_style = kwargs.get("analysis_style", "full")
        if analysis_style == "concise":
            analyzer = ConciseAnalyzer()
            progress.update(60)
            result_path = await asyncio.to_thread(
                analyzer.analyze_and_save, transcript, output_dir, base_name
            )
            progress.update(100)
            return str(result_path)
        else:
            analyzer = FullAnalyzer()
            progress.update(60)
            paths = await asyncio.to_thread(
                analyzer.analyze_and_save, transcript, output_dir, base_name
            )
            progress.update(100)
            # Return list of generated paths for compactness
            return [str(p) for p in paths.values()]

    def _cleanup_temp_files(self) -> None:
        """Clean up temporary files if using system temp directory."""
        if self._cleanup_temp and self.temp_dir.exists():
            try:
                import shutil

                shutil.rmtree(self.temp_dir)
                logger.debug(f"Cleaned up temporary directory: {self.temp_dir}")
            except Exception as e:
                logger.warning(f"Failed to clean up temp directory: {e}")

    def __enter__(self) -> AudioProcessingPipeline:
        """Context manager entry."""
        return self

    def __exit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc_val: BaseException | None,
        _exc_tb: object | None,
    ) -> None:
        """Context manager exit with cleanup."""
        self._cleanup_temp_files()

    # ---------------------- Markdown Export ----------------------
    async def export_markdown_transcript(
        self,
        audio_source: str,
        output_dir: Path,
        markdown_options: dict[str, Any],
    ) -> Path:
        """Process audio and export as markdown transcript.

        This performs transcription (async) and writes:
        - transcript.md
        - metadata.json
        - segments.json (utterances)
        under a structured `{output_dir}/{source_name}` directory.
        """
        # Ensure output structure
        source_name = sanitize_dirname(Path(audio_source).stem)
        base_dir = ensure_subpath(Path(output_dir), Path(source_name))
        base_dir.mkdir(parents=True, exist_ok=True)

        # Transcribe
        service = TranscriptionService()
        provider_opt = markdown_options.get("provider")
        provider_name = None if (not provider_opt or provider_opt == "auto") else provider_opt
        transcript: TranscriptionResult | None = await service.transcribe_async(
            Path(audio_source),
            provider_name=provider_name,
            language=markdown_options.get("language", "en"),
        )
        if not transcript:
            raise RuntimeError("Transcription failed; cannot export markdown transcript")

        # Markdown formatting
        formatter = MarkdownFormatter()

        source_info = {
            "source": audio_source,
            "processed_at": datetime.now().isoformat(),
            "provider": transcript.provider_name,
            "total_duration": getattr(transcript, "duration", 0.0),
        }

        md_output_path = base_dir / "transcript.md"
        content = formatter.format_transcript(
            transcript,
            source_info,
            md_output_path,
            include_timestamps=markdown_options.get("include_timestamps", True),
            include_speakers=markdown_options.get("include_speakers", True),
            include_confidence=markdown_options.get("include_confidence", False),
            template=markdown_options.get("template", "default"),
        )
        formatter.save_transcript(content, md_output_path)

        # Save metadata.json
        metadata = {
            "source": source_info["source"],
            "processed_at": source_info["processed_at"],
            "provider": source_info["provider"],
            "duration_seconds": source_info["total_duration"],
            "segment_count": len(transcript.utterances or []),
        }
        try:
            safe_write_json(base_dir / "metadata.json", metadata)
        except (OSError, PermissionError) as e:
            logger.warning(f"Failed to write metadata.json: {e}")

        # Save segments.json (utterances)
        segments_payload = [
            {
                "text": getattr(u, "text", None) or getattr(u, "transcript", ""),
                "start_time": u.start,
                "end_time": u.end,
                "speaker": u.speaker,
            }
            for u in (transcript.utterances or [])
        ]
        try:
            safe_write_json(base_dir / "segments.json", segments_payload)
        except (OSError, PermissionError) as e:
            logger.warning(f"Failed to write segments.json: {e}")

        return md_output_path
