#!/usr/bin/env python3
"""Manual test for JSONL event streaming.

This script demonstrates the event streaming functionality.
Run with: python tests/manual/test_jsonl_streaming.py

Expected output: JSONL events emitted to stdout showing pipeline stages.
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.models.events import (
    EventSinkContext,
    JsonLinesSink,
    emit_event,
)


def test_basic_event_emission():
    """Test basic event emission to JSONL."""
    print("=== Testing Basic Event Emission ===\n", file=sys.stderr)

    # Create a sink that writes to stdout
    sink = JsonLinesSink()

    with EventSinkContext(sink):
        # Emit various event types
        emit_event(
            "stage_start",
            stage="extract",
            data={"description": "Extracting audio from media file", "total": 100},
            run_id="test-run-001",
        )

        emit_event(
            "stage_progress",
            stage="extract",
            data={"completed": 25, "total": 100},
            run_id="test-run-001",
        )

        emit_event(
            "stage_progress",
            stage="extract",
            data={"completed": 75, "total": 100},
            run_id="test-run-001",
        )

        emit_event(
            "stage_end",
            stage="extract",
            data={"duration": 5.23, "status": "complete"},
            run_id="test-run-001",
        )

        emit_event(
            "artifact",
            stage="extract",
            data={"kind": "audio", "path": "/tmp/test.mp3"},
            run_id="test-run-001",
        )

        emit_event(
            "stage_start",
            stage="transcribe",
            data={"description": "Transcribing audio to text", "total": 100},
            run_id="test-run-001",
        )

        emit_event(
            "stage_progress",
            stage="transcribe",
            data={"completed": 50, "total": 100},
            run_id="test-run-001",
        )

        emit_event(
            "stage_end",
            stage="transcribe",
            data={"duration": 12.45, "status": "complete"},
            run_id="test-run-001",
        )

        emit_event(
            "artifact",
            stage="transcribe",
            data={"kind": "transcript", "path": "/tmp/transcript.txt"},
            run_id="test-run-001",
        )

        emit_event(
            "summary",
            data={
                "metrics": {
                    "total_duration": 17.68,
                    "stages_completed": ["extract", "transcribe"],
                    "files_created": 2,
                },
                "provider": "deepgram",
                "output_dir": "/tmp/output",
            },
            run_id="test-run-001",
        )

    print("\n=== Test Complete ===", file=sys.stderr)
    print("✓ All events emitted successfully", file=sys.stderr)


def test_error_events():
    """Test error and warning events."""
    print("\n=== Testing Error Events ===\n", file=sys.stderr)

    sink = JsonLinesSink()

    with EventSinkContext(sink):
        emit_event(
            "warning",
            data={"message": "Low disk space warning"},
            run_id="test-run-002",
        )

        emit_event(
            "error",
            stage="extract",
            data={"message": "Failed to extract audio: file not found"},
            run_id="test-run-002",
        )

        emit_event(
            "cancelled",
            data={"reason": "User interrupted the operation"},
            run_id="test-run-002",
        )

    print("\n=== Test Complete ===", file=sys.stderr)
    print("✓ Error events emitted successfully", file=sys.stderr)


if __name__ == "__main__":
    print("JSONL Event Streaming Test", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    print("Each line below is a JSON event object:", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    print("", file=sys.stderr)

    test_basic_event_emission()
    test_error_events()

    print("", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    print("To parse events, pipe through jq:", file=sys.stderr)
    print("  python tests/manual/test_jsonl_streaming.py | jq .", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
