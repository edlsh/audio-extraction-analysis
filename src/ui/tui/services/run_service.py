"""Pipeline execution service for TUI."""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

from ....config import get_config
from ....exceptions import AudioAnalysisError
from ....models import events as event_models
from ....pipeline import simple_pipeline
from ....services.audio_extraction import AudioQuality
from ....services.url_ingestion import UrlIngestionError, UrlIngestionService
from ....utils.loguru_config import set_tui_mode


async def run_pipeline(
    input_path: Path | None,
    output_dir: Path,
    quality: str,
    language: str,
    provider: str,
    analysis_style: str,
    event_sink: Any,  # EventSink protocol
    run_id: str,
    *,
    url: str | None = None,
    keep_downloaded_videos: bool | None = None,
) -> dict[str, Any]:
    """Run pipeline with event streaming and optional URL ingestion.

    If ``url`` is provided, the media is first downloaded via UrlIngestionService,
    then the resulting audio path is passed into the main pipeline.
    """
    # Attach sink to thread-local registry
    event_models.set_event_sink(event_sink)

    # Enable TUI mode: routes logs to TUI LogPanel instead of stderr
    set_tui_mode(enabled=True, event_sink=event_sink)

    try:
        # Convert quality string to enum with validation
        try:
            quality_enum = AudioQuality[quality.upper()]
        except KeyError:
            valid_qualities = [q.name.lower() for q in AudioQuality]
            event_models.emit_event(
                "error",
                data={
                    "message": f"Invalid quality '{quality}'. Must be one of: {', '.join(valid_qualities)}"
                },
                run_id=run_id,
            )
            raise ValueError(
                f"Invalid quality '{quality}'. Must be one of: {', '.join(valid_qualities)}"
            )

        cfg = get_config()

        # Optional URL ingestion
        effective_input_path = input_path
        if url:
            if not cfg.url_ingest_enabled:
                event_models.emit_event(
                    "error",
                    data={"message": "URL ingestion is disabled by configuration."},
                    run_id=run_id,
                )
                raise ValueError("URL ingestion is disabled by configuration.")

            event_models.emit_event(
                "stage_start",
                stage="url_download",
                data={"description": "Downloading media from URL", "total": 100},
                run_id=run_id,
            )

            download_start = time.time()
            ingestion_service = UrlIngestionService(
                download_dir=cfg.url_ingest_download_dir,
                prefer_audio_only=cfg.url_ingest_prefer_audio_only,
                keep_video=(
                    keep_downloaded_videos
                    if keep_downloaded_videos is not None
                    else cfg.url_ingest_keep_video_default
                ),
                event_sink=event_sink,
            )
            try:
                # Run blocking ingest() in thread pool to avoid blocking event loop
                ingest_result = await asyncio.to_thread(
                    ingestion_service.ingest, url, quality=quality_enum
                )
            except UrlIngestionError as exc:
                event_models.emit_event(
                    "error",
                    stage="url_download",
                    data={"message": str(exc)},
                    run_id=run_id,
                )
                raise

            effective_input_path = ingest_result.audio_path
            download_duration = time.time() - download_start

            event_models.emit_event(
                "stage_end",
                stage="url_download",
                data={"duration": download_duration, "status": "complete"},
                run_id=run_id,
            )

            # url_prepare stage is handled automatically by the pipeline
            # The ingest() call already processed the file (extracted audio if video)

        if effective_input_path is None:
            raise ValueError("No input path provided for pipeline run.")

        # Run pipeline
        result = await simple_pipeline.process_pipeline(
            input_path=effective_input_path,
            output_dir=output_dir,
            quality=quality_enum,
            language=language,
            provider=provider,
            analysis_style=analysis_style,
            console_manager=None,  # Disable console output in TUI mode
            run_id=run_id,
            event_sink=event_sink,  # Pass event sink for direct emission
        )
        return result

    except asyncio.CancelledError:
        # Emit cancellation event
        event_models.emit_event("cancelled", data={"reason": "User interrupted"}, run_id=run_id)
        raise

    except (AudioAnalysisError, ValueError) as exc:
        event_models.emit_event("error", data={"message": str(exc)}, run_id=run_id)
        raise
    except Exception as exc:
        event_models.emit_event(
            "error",
            data={"message": "Unexpected pipeline failure", "detail": str(exc)},
            run_id=run_id,
        )
        raise AudioAnalysisError(
            "Unexpected pipeline failure",
            context={"run_id": run_id or "unknown"},
            original_error=exc,
        ) from exc

    finally:
        # Disable TUI mode: restores console logging
        set_tui_mode(enabled=False)

        # Detach sink
        event_models.set_event_sink(None)
