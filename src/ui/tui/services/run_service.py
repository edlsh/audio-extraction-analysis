"""Pipeline execution service for TUI."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any


async def run_pipeline(
    input_path: Path,
    output_dir: Path,
    quality: str,
    language: str,
    provider: str,
    analysis_style: str,
    event_sink: Any,  # EventSink protocol
    run_id: str,
) -> dict[str, Any]:
    """Run pipeline with event streaming.

    Wraps the main pipeline execution with event sink attachment and
    proper cleanup on completion or cancellation.

    Args:
        input_path: Input media file path
        output_dir: Output directory for results
        quality: Audio quality preset ("speech", "standard", "high", "compressed")
        language: Transcription language code (e.g., "en", "es")
        provider: Transcription provider ("auto", "deepgram", "whisper", etc.)
        analysis_style: Analysis output style ("concise" or "full")
        event_sink: Event sink to emit events to
        run_id: Unique run identifier for event tracking

    Returns:
        Pipeline result dictionary with summary data

    Raises:
        asyncio.CancelledError: If run is cancelled by user
        Exception: Any pipeline errors (after emitting error event)

    Example:
        >>> from src.models.events import QueueEventSink
        >>> queue = asyncio.Queue()
        >>> sink = QueueEventSink(queue)
        >>>
        >>> result = await run_pipeline(
        ...     input_path=Path("video.mp4"),
        ...     output_dir=Path("output"),
        ...     quality="speech",
        ...     language="en",
        ...     provider="auto",
        ...     analysis_style="concise",
        ...     event_sink=sink,
        ...     run_id="run-123",
        ... )
    """
    from ....models.events import emit_event, set_event_sink
    from ....pipeline.simple_pipeline import process_pipeline
    from ....services.audio_extraction import AudioQuality

    # Attach sink to thread-local registry
    set_event_sink(event_sink)

    try:
        # Convert quality string to enum with validation
        try:
            quality_enum = AudioQuality[quality.upper()]
        except KeyError:
            valid_qualities = [q.name.lower() for q in AudioQuality]
            emit_event(
                "error",
                data={"message": f"Invalid quality '{quality}'. Must be one of: {', '.join(valid_qualities)}"},
                run_id=run_id,
            )
            raise ValueError(f"Invalid quality '{quality}'. Must be one of: {', '.join(valid_qualities)}")

        # Run pipeline
        result = await process_pipeline(
            input_path=input_path,
            output_dir=output_dir,
            quality=quality_enum,
            language=language,
            provider=provider,
            analysis_style=analysis_style,
            console_manager=None,  # Disable console output in TUI mode
        )
        return result

    except asyncio.CancelledError:
        # Emit cancellation event
        emit_event("cancelled", data={"reason": "User interrupted"}, run_id=run_id)
        raise

    except Exception as e:
        # Emit error event before re-raising
        emit_event("error", data={"message": str(e)}, run_id=run_id)
        raise

    finally:
        # Detach sink
        set_event_sink(None)
