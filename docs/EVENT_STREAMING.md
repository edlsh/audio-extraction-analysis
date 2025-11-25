# Event Streaming & TUI Integration

## Overview

The audio extraction analysis tool now features a typed event model that enables:
- **JSONL Event Streaming** (`--jsonl` flag): Machine-readable pipeline events
- **Interactive TUI** (`tui` subcommand): Terminal-based UI with live progress
- **Unified Event Architecture**: Consistent instrumentation across all pipeline stages

## Event Model

### Event Types

All events follow a consistent structure:

```json
{
  "type": "stage_start|stage_progress|stage_end|artifact|log|warning|error|summary|cancelled",
  "ts": "2025-11-15T18:13:23.640225+00:00",
  "run_id": "unique-run-identifier",
  "stage": "extract|transcribe|analyze",
  "data": { /* event-specific payload */ }
}
```

### Event Type Payloads

#### `stage_start`
```json
{
  "type": "stage_start",
  "stage": "extract",
  "data": {
    "description": "Extracting audio from media file",
    "total": 100
  }
}
```

#### `stage_progress`
```json
{
  "type": "stage_progress",
  "stage": "extract",
  "data": {
    "completed": 50,
    "total": 100,
    "message": "Processing frame 5000/10000"
  }
}
```

#### `stage_end`
```json
{
  "type": "stage_end",
  "stage": "extract",
  "data": {
    "duration": 5.23,
    "status": "complete"
  }
}
```

#### `artifact`
```json
{
  "type": "artifact",
  "stage": "transcribe",
  "data": {
    "kind": "audio|transcript|markdown|dashboard|metadata",
    "path": "/path/to/artifact.mp3"
  }
}
```

#### `log`, `warning`, `error`
```json
{
  "type": "error",
  "stage": "transcribe",
  "data": {
    "message": "Transcription failed: API key invalid",
    "level": "ERROR",
    "logger": "src.services.transcription"
  }
}
```

#### `summary`
```json
{
  "type": "summary",
  "data": {
    "metrics": {
      "total_duration": 17.68,
      "stages_completed": ["extract", "transcribe", "analyze"],
      "files_created": 5
    },
    "provider": "deepgram",
    "output_dir": "/path/to/output"
  }
}
```

#### `cancelled`
```json
{
  "type": "cancelled",
  "data": {
    "reason": "User interrupted the operation"
  }
}
```

## JSONL Streaming Usage

### Basic Usage

Stream events to stdout as newline-delimited JSON:

```bash
# Process command with JSONL output
audio-extraction-analysis process video.mp4 --jsonl > events.jsonl

# Extract with JSONL
audio-extraction-analysis extract video.mp4 --jsonl

# Transcribe with JSONL
audio-extraction-analysis transcribe audio.mp3 --jsonl
```

### Parsing Events

#### Using `jq` for Real-Time Monitoring

```bash
# Pretty-print all events
audio-extraction-analysis process video.mp4 --jsonl | jq .

# Filter only progress events
audio-extraction-analysis process video.mp4 --jsonl | jq 'select(.type == "stage_progress")'

# Extract artifact paths
audio-extraction-analysis process video.mp4 --jsonl | jq 'select(.type == "artifact") | .data.path'

# Monitor progress percentage
audio-extraction-analysis process video.mp4 --jsonl | \
  jq -r 'select(.type == "stage_progress") | "\(.stage): \(.data.completed)/\(.data.total)"'
```

#### Using Python

```python
import json
import sys

for line in sys.stdin:
    event = json.loads(line)
    
    if event["type"] == "stage_progress":
        stage = event["stage"]
        completed = event["data"]["completed"]
        total = event["data"]["total"]
        pct = (completed / total) * 100
        print(f"{stage}: {pct:.1f}%")
    
    elif event["type"] == "artifact":
        print(f"Created: {event['data']['path']}")
    
    elif event["type"] == "error":
        print(f"ERROR: {event['data']['message']}", file=sys.stderr)
```

Usage:
```bash
audio-extraction-analysis process video.mp4 --jsonl | python monitor.py
```

### Integration Examples

#### Monitoring Dashboard

```python
#!/usr/bin/env python3
"""Real-time pipeline monitoring dashboard."""

import json
import sys
from collections import defaultdict

stages = defaultdict(lambda: {"completed": 0, "total": 100})

for line in sys.stdin:
    event = json.loads(line)
    
    if event["type"] == "stage_start":
        stage = event["stage"]
        print(f"▶ Starting {stage}...")
    
    elif event["type"] == "stage_progress":
        stage = event["stage"]
        stages[stage] = event["data"]
        
        # Print progress bar
        completed = stages[stage]["completed"]
        total = stages[stage]["total"]
        pct = (completed / total) * 100
        bar_len = int(pct / 2)
        bar = "█" * bar_len + "░" * (50 - bar_len)
        print(f"\r{stage}: [{bar}] {pct:.1f}%", end="")
    
    elif event["type"] == "stage_end":
        print()  # New line after progress bar
        stage = event["stage"]
        duration = event["data"]["duration"]
        print(f"✓ {stage} completed in {duration:.2f}s")
    
    elif event["type"] == "summary":
        print("\n" + "=" * 60)
        metrics = event["data"]["metrics"]
        print(f"Total duration: {metrics['total_duration']:.2f}s")
        print(f"Files created: {metrics['files_created']}")
        print("=" * 60)
```

#### Slack Integration

```python
#!/usr/bin/env python3
"""Send pipeline notifications to Slack."""

import json
import sys
import requests

SLACK_WEBHOOK = "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"

for line in sys.stdin:
    event = json.loads(line)
    
    if event["type"] == "summary":
        metrics = event["data"]["metrics"]
        duration = metrics["total_duration"]
        files = metrics["files_created"]
        
        requests.post(SLACK_WEBHOOK, json={
            "text": f"✅ Pipeline completed in {duration:.2f}s ({files} files created)"
        })
    
    elif event["type"] == "error":
        message = event["data"]["message"]
        requests.post(SLACK_WEBHOOK, json={
            "text": f"❌ Pipeline error: {message}"
        })
```

## TUI (Text User Interface)

### Launching the TUI

```bash
# Launch interactive TUI
audio-extraction-analysis tui

# Pre-populate input file
audio-extraction-analysis tui --input video.mp4

# Pre-populate input and output
audio-extraction-analysis tui --input video.mp4 --output-dir ./results
```

### TUI Features (Current Implementation)

The current TUI provides:
- ✅ Welcome screen with application info
- ✅ Dark mode toggle (`d` key)
- ✅ Graceful fallback if Textual not installed
- ✅ Event consumption infrastructure ready

### TUI Features (Planned)

The full TUI will include:
- 🔲 File picker for input selection
- 🔲 Configuration panel (quality, language, provider)
- 🔲 Live progress board with stage indicators
- 🔲 Log panel with filtering
- 🔲 Provider health dashboard
- 🔲 Results screen with artifact list
- 🔲 Open/copy actions for artifacts
- 🔲 Cancellable runs with cleanup

### Installing TUI Dependencies

```bash
# Install with TUI support
pip install -e ".[tui]"

# Or install Textual separately
pip install textual>=0.47.0
```

## Architecture

### Event Flow

```
Pipeline Stage
    ↓
emit_event() ← thread-local sink registry
    ↓
EventSink Protocol
    ├─ JsonLinesSink → stdout/file
    ├─ QueueEventSink → asyncio.Queue → TUI
    ├─ ConsoleEventSink → ConsoleManager (legacy)
    └─ CompositeSink → [multiple sinks]
```

### Integration Points

#### Pipeline Instrumentation (`src/pipeline/simple_pipeline.py`)
- Emits `stage_start/progress/end` for extract/transcribe/analyze
- Emits `artifact` for all created files
- Emits `summary` on completion
- Emits `error`/`cancelled` on failures

#### Logging Bridge (`src/utils/logging_factory.py`)
- `EventLogHandler` forwards log records to event sink
- Automatic level mapping (INFO→log, WARNING→warning, ERROR→error)
- Attach with `LoggingFactory.attach_event_sink(sink, run_id)`

#### CLI Integration (`src/cli.py`)
- `--jsonl` flag sets up `JsonLinesSink`
- `tui` subcommand launches Textual app
- `EventSinkContext` manages sink lifecycle
- Backward compatible with `--json-output` (deprecated)

## Testing

### Unit Tests

```bash
# Test event model
pytest tests/unit/test_events.py -v

# Test all event sinks
pytest tests/unit/test_events.py::TestJsonLinesSink -v
pytest tests/unit/test_events.py::TestQueueEventSink -v
pytest tests/unit/test_events.py::TestCompositeSink -v
```

### Manual Testing

```bash
# Test JSONL streaming
python tests/manual/test_jsonl_streaming.py

# Pretty-print with jq
python tests/manual/test_jsonl_streaming.py 2>/dev/null | jq .
```

### Integration Testing

```bash
# Process with JSONL and verify events
audio-extraction-analysis process test.mp4 --jsonl 2>/dev/null | \
  jq -s 'map(select(.type == "stage_start")) | length' # Should output 3 (extract, transcribe, analyze)
```

## Best Practices

### Event Sink Selection

- **CLI Automation**: Use `JsonLinesSink` with `--jsonl`
- **TUI/Dashboard**: Use `QueueEventSink` with `asyncio.Queue`
- **Multiple Outputs**: Use `CompositeSink([JsonLinesSink(), QueueEventSink()])`
- **Legacy Console**: Use `ConsoleEventSink` (auto-used without flags)

### Error Handling

Events are designed to be non-blocking:
- Sink errors don't crash the pipeline
- Missing sinks are silently ignored
- `CompositeSink` continues on child sink failures

### Performance

- Events are emitted synchronously (minimal overhead)
- `QueueEventSink` uses `call_soon_threadsafe` for thread safety
- JSONL streaming has negligible impact (<1% overhead)

## Migration Guide

### From `--json-output` to `--jsonl`

The old `--json-output` flag is deprecated but still works. Migrate to `--jsonl` for typed events:

**Before:**
```bash
audio-extraction-analysis process video.mp4 --json-output
```

**After:**
```bash
audio-extraction-analysis process video.mp4 --jsonl
```

### Adding Event Support to Custom Code

```python
from src.models.events import emit_event, set_event_sink, JsonLinesSink

# Set up sink
sink = JsonLinesSink()
set_event_sink(sink)

# Emit events
emit_event("stage_start", stage="custom", data={"description": "Custom stage"})
emit_event("stage_progress", stage="custom", data={"completed": 50, "total": 100})
emit_event("stage_end", stage="custom", data={"duration": 1.23, "status": "complete"})

# Clean up
set_event_sink(None)
```

## Troubleshooting

### Events Not Appearing

1. Verify event sink is set:
   ```python
   from src.models.events import get_event_sink
   print(get_event_sink())  # Should not be None
   ```

2. Check for exceptions in sink:
   ```bash
   # Enable verbose logging
   audio-extraction-analysis process video.mp4 --jsonl --verbose
   ```

### TUI Not Available

```bash
# Check if Textual is installed
python -c "import textual; print(textual.__version__)"

# Install if missing
pip install "audio-extraction-analysis[tui]"
```

### Malformed JSON Events

Events should always be valid JSON. If seeing parse errors:
```bash
# Validate JSONL output
audio-extraction-analysis process video.mp4 --jsonl 2>/dev/null | \
  while read line; do echo "$line" | jq . >/dev/null || echo "Invalid: $line"; done
```

## Future Enhancements

- [ ] HTML dashboard event sink
- [ ] WebSocket streaming for remote monitoring
- [ ] Event replay/debugging tools
- [ ] Performance profiling via events
- [ ] Distributed tracing integration
