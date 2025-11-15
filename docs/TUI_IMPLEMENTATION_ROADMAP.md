# TUI Implementation Roadmap

**Status**: Planning Phase  
**Goal**: Deliver full Textual TUI with feature parity to CLI and event-streaming flow  
**Target**: 6 stacked PRs, shippable incrementally

---

## Executive Summary

This roadmap transforms the existing TUI skeleton (`src/ui/tui/app.py`, `state.py`) into a production-ready interactive interface. The architecture follows an **event-driven reducer pattern**: pipeline services emit typed `Event` objects → `EventConsumer` batches/throttles → `apply_event()` reducer updates `AppState` → Textual widgets reactively render.

**Key Principles**:
- **Incremental delivery**: Each PR is independently testable and shippable
- **Event stream parity**: TUI consumes the same events as `--jsonl` output
- **State-first design**: All UI logic derives from immutable state transitions
- **Graceful degradation**: Missing Textual deps fall back to CLI mode

---

## Phase 0: Pre-Implementation Setup

### Resolve Ambiguities

#### 1. Directory Layout & Import Rules

**Confirmed Structure**:
```
src/ui/tui/
├── __init__.py                 # Exports: AudioExtractionApp, main
├── app.py                      # Main App class, screen routing
├── state.py                    # AppState, apply_event reducer
├── events.py                   # EventConsumer (NEW)
├── services/
│   ├── __init__.py             # Exports service classes
│   ├── run_service.py          # Pipeline wrapper (NEW)
│   ├── health_service.py       # Provider health checks (NEW)
│   └── os_open.py              # Cross-platform file opener (NEW)
├── views/
│   ├── __init__.py             # Exports screen classes
│   ├── home.py                 # HomeScreen (NEW)
│   ├── config.py               # ConfigScreen (NEW)
│   ├── run.py                  # RunScreen (NEW)
│   └── results.py              # ResultsScreen (NEW)
├── widgets/
│   ├── __init__.py             # Exports widget classes
│   ├── file_picker.py          # FilePicker widget (NEW)
│   ├── progress_board.py       # ProgressBoard widget (NEW)
│   ├── log_panel.py            # LogPanel widget (NEW)
│   ├── provider_health.py      # ProviderHealth widget (NEW)
│   └── shortcuts_help.py       # ShortcutsHelp overlay (NEW)
└── styles/
    └── theme.tcss              # Textual CSS (NEW)
```

**Import Layer Enforcement**:
- ✅ TUI can import: `src.services.*`, `src.pipeline.*`, `src.models.*`, `src.utils.*`
- ✅ TUI can import: `src.providers.factory` (for health checks only)
- ❌ TUI **cannot** import: `src.providers.deepgram`, `src.providers.elevenlabs` (use factory)
- ❌ TUI **cannot** import: `src.cli` (circular dependency)

**Validation**: Add to `pyproject.toml` `import-linter`:
```toml
[[tool.importlinter.contracts]]
name = "TUI must not import CLI"
type = "forbidden"
source_modules = ["src.ui.tui"]
forbidden_modules = ["src.cli"]

[[tool.importlinter.contracts]]
name = "TUI uses provider factory only"
type = "layers"
layers = [
    "src.ui.tui",
    "src.providers.factory",
]
```

#### 2. Event Field Mapping (Reducer Contract)

**Canonical Event Schema** (from `src/models/events.py`):
```python
@dataclass
class Event:
    type: EventType  # "stage_start" | "stage_progress" | "stage_end" | ...
    ts: str          # ISO 8601 timestamp
    run_id: str      # UUID
    stage: str | None  # "extract" | "transcribe" | "analyze" | None
    data: dict[str, Any]  # Type-specific payload
```

**Reducer Mapping** (`apply_event` function signature):
```python
def apply_event(state: AppState, event: Event) -> AppState:
    """Pure reducer: (state, event) -> new_state.
    
    NEVER mutates input state; returns updated copy.
    """
    match event.type:
        case "stage_start":
            # data: {"description": str, "total": int}
            return dataclasses.replace(
                state,
                current_stage=event.stage,
                current_message=event.data.get("description", ""),
                stage_totals={**state.stage_totals, event.stage: event.data.get("total", 100)},
                stage_completed={**state.stage_completed, event.stage: 0},
                is_running=True,
            )
        
        case "stage_progress":
            # data: {"completed": int, "total": int, "message": str}
            return dataclasses.replace(
                state,
                stage_completed={**state.stage_completed, event.stage: event.data["completed"]},
                current_message=event.data.get("message", state.current_message),
            )
        
        case "stage_end":
            # data: {"duration": float, "status": str}
            return dataclasses.replace(
                state,
                stage_durations={**state.stage_durations, event.stage: event.data["duration"]},
                current_stage=None,
            )
        
        case "artifact":
            # data: {"kind": str, "path": str}
            return dataclasses.replace(
                state,
                artifacts=[*state.artifacts, event.data],
            )
        
        case "log" | "warning":
            # data: {"message": str, "level": str, "logger": str}
            return dataclasses.replace(
                state,
                logs=_append_to_ring(state.logs, event.to_dict(), max_size=2000),
            )
        
        case "error":
            # data: {"message": str, "level": str, "logger": str}
            return dataclasses.replace(
                state,
                errors=[*state.errors, event.data["message"]],
                logs=_append_to_ring(state.logs, event.to_dict(), max_size=2000),
            )
        
        case "summary":
            # data: {"metrics": dict, "provider": str, "output_dir": str}
            return dataclasses.replace(
                state,
                summary=event.data,
                is_running=False,
            )
        
        case "cancelled":
            # data: {"reason": str}
            return dataclasses.replace(
                state,
                is_running=False,
                current_message=f"Cancelled: {event.data.get('reason', 'User interrupt')}",
            )
        
        case _:
            return state  # Unknown event type; preserve state
```

**State Extensions Needed** (add to `AppState`):
```python
@dataclass
class AppState:
    # ... existing fields ...
    
    # Stage tracking (NEW)
    stage_totals: dict[str, int] = field(default_factory=dict)      # {stage: total_units}
    stage_completed: dict[str, int] = field(default_factory=dict)   # {stage: completed_units}
    stage_durations: dict[str, float] = field(default_factory=dict) # {stage: duration_sec}
    
    # Ring buffer helper
    def _append_to_ring(items: list, item: Any, max_size: int) -> list:
        """Append to ring buffer; truncate oldest if exceeds max_size."""
        result = [*items, item]
        if len(result) > max_size:
            # Keep first 500, last 1500 (middle truncation)
            return result[:500] + [{"truncated": True}] + result[-(max_size - 500):]
        return result
```

#### 3. Throttling & Queue Bounds

**EventConsumer Configuration**:
```python
@dataclass
class EventConsumerConfig:
    """Configuration for event batching and throttling."""
    
    throttle_ms: int = 50           # Batch interval (50ms = 20 updates/sec)
    max_queue_size: int = 1000      # Backpressure threshold
    coalesce_progress: bool = True  # Merge multiple progress events per stage
    drop_policy: str = "oldest"     # "oldest" | "newest" when queue full
```

**Rationale**:
- **50ms throttle**: Balances responsiveness (20 FPS) with CPU efficiency
- **1000 event queue**: Handles bursts without OOM (event size ~200 bytes → 200KB max)
- **Coalescing**: Only latest `stage_progress` per stage matters; drop intermediate
- **Drop oldest**: Preserve latest errors/artifacts; sacrifice older progress

**Validation**: Integration test emits 100 events/sec; verify UI updates smoothly and queue doesn't grow unbounded.

#### 4. CLI `tui` Subcommand Flags

**Proposed Signature** (`src/cli.py`):
```python
def _create_tui_subparser(subparsers) -> None:
    """Create TUI subcommand parser."""
    tui = subparsers.add_parser(
        "tui",
        help="Launch interactive Text User Interface",
        description="Full-featured TUI with live progress and provider health",
    )
    
    # Pre-populate options
    tui.add_argument(
        "--input", "-i",
        type=Path,
        help="Pre-populate input file path"
    )
    tui.add_argument(
        "--output-dir", "-o",
        type=Path,
        help="Pre-populate output directory"
    )
    
    # Appearance
    tui.add_argument(
        "--theme",
        choices=["dark", "light", "auto"],
        default="auto",
        help="Color theme (default: auto-detect)"
    )
    tui.add_argument(
        "--no-color",
        action="store_true",
        help="Disable colors (respects NO_COLOR env)"
    )
    
    # Logging
    tui.add_argument(
        "--verbose-logs",
        action="store_true",
        help="Show DEBUG-level logs in log panel"
    )
    
    # Pass-through pipeline flags (optional)
    tui.add_argument("--quality", choices=["speech", "standard", "high", "compressed"], default="speech")
    tui.add_argument("--language", default="en")
    tui.add_argument("--provider", default="auto")
    tui.add_argument("--analysis-style", choices=["concise", "full"], default="concise")
    
    tui.set_defaults(func=tui_command)
```

**Integration with Existing CLI**:
- ✅ **No conflicts**: TUI flags are namespaced under `tui` subcommand
- ✅ **Backward compatible**: `--verbose` still works globally; `--verbose-logs` is TUI-specific
- ❌ **Does NOT support**: `--jsonl` inside TUI (redundant; TUI consumes events directly)

#### 5. Persistence (platformdirs)

**Location**:
```python
from platformdirs import user_config_dir

CONFIG_DIR = Path(user_config_dir("audio-extraction-analysis", appauthor=False))
SETTINGS_FILE = CONFIG_DIR / "tui_settings.json"
RECENT_FILES = CONFIG_DIR / "recent.json"
```

**Schema** (`tui_settings.json`):
```json
{
  "version": "1.0",
  "last_input_dir": "/Users/user/Videos",
  "last_output_dir": "/Users/user/Documents/transcripts",
  "defaults": {
    "quality": "speech",
    "language": "en",
    "provider": "auto",
    "analysis_style": "concise"
  },
  "ui": {
    "theme": "dark",
    "verbose_logs": false,
    "log_panel_height": 10
  }
}
```

**Schema** (`recent.json`):
```json
{
  "files": [
    {
      "path": "/path/to/video.mp4",
      "last_used": "2025-11-15T18:00:00Z",
      "size_mb": 125.3
    }
  ],
  "max_entries": 20
}
```

**Migration Strategy**:
- **v1.0 → v1.1**: Add new fields with defaults; ignore unknown fields
- **Validation**: Use Pydantic models for schema validation (already in deps)
- **Corruption handling**: If JSON parse fails, reset to defaults and backup corrupted file

---

## Phase 1: Foundation (PR 1)

### Objective
Build core state management, event batching, and service wrappers **without** UI screens. Fully unit-testable in isolation.

### Files to Create

#### `src/ui/tui/state.py` (ENHANCE)
**Add**:
- `apply_event(state: AppState, event: Event) -> AppState` reducer (pure function)
- `stage_totals`, `stage_completed`, `stage_durations` fields to `AppState`
- `_append_to_ring()` helper for log truncation

**Tests**: `tests/unit/test_tui_state_reducer.py`
```python
def test_apply_event_stage_start():
    state = AppState()
    event = Event(type="stage_start", stage="extract", data={"description": "Extracting", "total": 100})
    new_state = apply_event(state, event)
    
    assert new_state.current_stage == "extract"
    assert new_state.stage_totals["extract"] == 100
    assert new_state.is_running is True
    assert state.is_running is False  # Original unchanged

def test_apply_event_coalescing():
    """Test that rapid progress events update correctly."""
    state = AppState(stage_completed={"extract": 0})
    
    for i in range(10, 101, 10):
        event = Event(type="stage_progress", stage="extract", data={"completed": i, "total": 100})
        state = apply_event(state, event)
    
    assert state.stage_completed["extract"] == 100

def test_apply_event_ring_buffer_truncation():
    """Test log ring buffer limits."""
    state = AppState()
    
    for i in range(3000):
        event = Event(type="log", data={"message": f"Log {i}", "level": "INFO"})
        state = apply_event(state, event)
    
    assert len(state.logs) <= 2000
    # Verify middle truncation marker
    assert any(item.get("truncated") for item in state.logs)
```

#### `src/ui/tui/events.py` (NEW)
**Purpose**: Batch and throttle events to prevent UI thrashing.

**Interface**:
```python
@dataclass
class EventConsumerConfig:
    throttle_ms: int = 50
    max_queue_size: int = 1000
    coalesce_progress: bool = True
    drop_policy: str = "oldest"

class EventConsumer:
    """Consumes events from queue, batches, and calls reducer.
    
    Usage:
        consumer = EventConsumer(queue, on_batch, config)
        task = asyncio.create_task(consumer.run())
        # ... later ...
        await consumer.stop()
    """
    
    def __init__(
        self,
        queue: asyncio.Queue[Event],
        on_batch: Callable[[list[Event]], None],
        config: EventConsumerConfig = EventConsumerConfig(),
    ):
        self.queue = queue
        self.on_batch = on_batch
        self.config = config
        self._running = False
        self._batch: list[Event] = []
        self._last_progress: dict[str, Event] = {}  # {stage: latest_progress_event}
    
    async def run(self) -> None:
        """Main event loop; call as background task."""
        self._running = True
        
        while self._running:
            # Collect events for throttle_ms duration
            deadline = asyncio.get_event_loop().time() + (self.config.throttle_ms / 1000)
            
            while asyncio.get_event_loop().time() < deadline:
                try:
                    event = await asyncio.wait_for(
                        self.queue.get(),
                        timeout=(deadline - asyncio.get_event_loop().time())
                    )
                    self._add_to_batch(event)
                except asyncio.TimeoutError:
                    break
            
            # Flush batch
            if self._batch:
                coalesced = self._coalesce_batch()
                self.on_batch(coalesced)
                self._batch.clear()
                self._last_progress.clear()
    
    def _add_to_batch(self, event: Event) -> None:
        """Add event to batch with coalescing."""
        if self.config.coalesce_progress and event.type == "stage_progress":
            # Keep only latest progress per stage
            if event.stage:
                self._last_progress[event.stage] = event
        else:
            self._batch.append(event)
    
    def _coalesce_batch(self) -> list[Event]:
        """Merge coalesced progress events into batch."""
        return [*self._batch, *self._last_progress.values()]
    
    async def stop(self) -> None:
        """Stop consumer gracefully."""
        self._running = False
```

**Tests**: `tests/unit/test_tui_event_consumer.py`
```python
@pytest.mark.asyncio
async def test_event_consumer_throttling():
    """Verify batching at throttle interval."""
    queue = asyncio.Queue()
    batches = []
    
    def on_batch(events):
        batches.append(events)
    
    consumer = EventConsumer(queue, on_batch, EventConsumerConfig(throttle_ms=100))
    task = asyncio.create_task(consumer.run())
    
    # Emit 10 events rapidly
    for i in range(10):
        await queue.put(Event(type="log", data={"message": f"Event {i}"}))
        await asyncio.sleep(0.01)  # 10ms apart
    
    await asyncio.sleep(0.15)  # Wait for batch
    await consumer.stop()
    await task
    
    # Should have 1-2 batches (100ms throttle)
    assert 1 <= len(batches) <= 2
    assert sum(len(b) for b in batches) == 10

@pytest.mark.asyncio
async def test_event_consumer_coalescing():
    """Verify progress event coalescing."""
    queue = asyncio.Queue()
    batches = []
    
    consumer = EventConsumer(queue, lambda e: batches.append(e), EventConsumerConfig(throttle_ms=50))
    task = asyncio.create_task(consumer.run())
    
    # Emit 100 progress events for same stage
    for i in range(100):
        await queue.put(Event(type="stage_progress", stage="extract", data={"completed": i, "total": 100}))
    
    await asyncio.sleep(0.1)
    await consumer.stop()
    await task
    
    # Should coalesce to ~1-2 progress events
    all_events = [e for batch in batches for e in batch]
    progress_events = [e for e in all_events if e.type == "stage_progress"]
    assert len(progress_events) <= 2
```

#### `src/ui/tui/services/run_service.py` (NEW)
**Purpose**: Wrapper for `process_pipeline` with event sink attachment.

**Interface**:
```python
async def run_pipeline(
    input_path: Path,
    output_dir: Path,
    quality: str,
    language: str,
    provider: str,
    analysis_style: str,
    event_sink: EventSink,
    run_id: str,
) -> dict[str, Any]:
    """Run pipeline with event streaming.
    
    Returns:
        Pipeline result dict (summary data)
    
    Raises:
        Exception: Pipeline errors (emits error event before raising)
    """
    from ....models.events import set_event_sink
    from ....pipeline.simple_pipeline import process_pipeline
    
    # Attach sink to thread-local registry
    set_event_sink(event_sink)
    
    try:
        result = await process_pipeline(
            input_path=input_path,
            output_dir=output_dir,
            quality=quality,
            language=language,
            provider=provider,
            analysis_style=analysis_style,
            console_manager=None,  # Disable console output
        )
        return result
    
    except asyncio.CancelledError:
        # Emit cancellation event
        from ....models.events import emit_event
        emit_event("cancelled", data={"reason": "User interrupted"}, run_id=run_id)
        raise
    
    except Exception as e:
        from ....models.events import emit_event
        emit_event("error", data={"message": str(e)}, run_id=run_id)
        raise
    
    finally:
        set_event_sink(None)  # Detach
```

**Tests**: `tests/unit/test_tui_run_service.py`
```python
@pytest.mark.asyncio
async def test_run_service_emits_events():
    """Verify service emits events to sink."""
    queue = asyncio.Queue()
    sink = QueueEventSink(queue)
    
    with patch("src.ui.tui.services.run_service.process_pipeline") as mock_pipeline:
        mock_pipeline.return_value = {"status": "success"}
        
        result = await run_pipeline(
            input_path=Path("test.mp4"),
            output_dir=Path("output"),
            quality="speech",
            language="en",
            provider="auto",
            analysis_style="concise",
            event_sink=sink,
            run_id="test-123",
        )
        
        assert result["status"] == "success"

@pytest.mark.asyncio
async def test_run_service_cancellation():
    """Verify cancellation emits cancelled event."""
    queue = asyncio.Queue()
    sink = QueueEventSink(queue)
    
    async def slow_pipeline(*args, **kwargs):
        await asyncio.sleep(10)
    
    with patch("src.ui.tui.services.run_service.process_pipeline", side_effect=slow_pipeline):
        task = asyncio.create_task(run_pipeline(
            input_path=Path("test.mp4"),
            output_dir=Path("output"),
            quality="speech",
            language="en",
            provider="auto",
            analysis_style="concise",
            event_sink=sink,
            run_id="test-123",
        ))
        
        await asyncio.sleep(0.1)
        task.cancel()
        
        with pytest.raises(asyncio.CancelledError):
            await task
        
        # Should have emitted cancelled event
        event = await asyncio.wait_for(queue.get(), timeout=1.0)
        assert event.type == "cancelled"
```

#### `src/ui/tui/services/health_service.py` (NEW)
**Purpose**: Async wrapper for provider health checks (runs in thread pool).

**Interface**:
```python
class HealthService:
    """Provider health check service.
    
    Caches results for 60 seconds to avoid redundant checks.
    """
    
    def __init__(self):
        self._cache: dict[str, tuple[dict[str, Any], float]] = {}
        self._cache_ttl = 60.0
        self._executor = ThreadPoolExecutor(max_workers=4)
    
    async def check_all_providers(self) -> dict[str, dict[str, Any]]:
        """Check health of all registered providers.
        
        Returns:
            {provider_name: {"status": "ok"|"error", "message": str, ...}}
        """
        from ....providers.factory import TranscriptionProviderFactory
        
        providers = TranscriptionProviderFactory.get_available_providers()
        
        # Run checks in parallel
        tasks = [self._check_provider(name) for name in providers]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        return {
            name: result if not isinstance(result, Exception) else {"status": "error", "message": str(result)}
            for name, result in zip(providers, results)
        }
    
    async def _check_provider(self, name: str) -> dict[str, Any]:
        """Check single provider (with caching)."""
        now = time.time()
        
        # Check cache
        if name in self._cache:
            result, timestamp = self._cache[name]
            if now - timestamp < self._cache_ttl:
                return result
        
        # Run in thread pool (blocking API)
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            self._executor,
            self._sync_check,
            name,
        )
        
        self._cache[name] = (result, now)
        return result
    
    def _sync_check(self, name: str) -> dict[str, Any]:
        """Synchronous health check (runs in thread pool)."""
        from ....providers.factory import TranscriptionProviderFactory
        
        try:
            return TranscriptionProviderFactory.check_provider_health_sync(name)
        except Exception as e:
            return {"status": "error", "message": str(e)}
```

**Tests**: `tests/unit/test_tui_health_service.py`
```python
@pytest.mark.asyncio
async def test_health_service_caching():
    """Verify health check caching."""
    service = HealthService()
    
    with patch("src.providers.factory.TranscriptionProviderFactory.check_provider_health_sync") as mock:
        mock.return_value = {"status": "ok"}
        
        # First call
        result1 = await service._check_provider("deepgram")
        assert result1["status"] == "ok"
        assert mock.call_count == 1
        
        # Second call (should use cache)
        result2 = await service._check_provider("deepgram")
        assert result2 == result1
        assert mock.call_count == 1  # No additional call
```

#### `src/ui/tui/services/os_open.py` (NEW)
**Purpose**: Cross-platform file/folder opener.

**Interface**:
```python
def open_path(path: Path) -> bool:
    """Open file or folder in default application.
    
    Args:
        path: Path to open
    
    Returns:
        True if successful, False otherwise
    """
    import platform
    import subprocess
    
    # Validate path
    from ....utils.paths import ensure_subpath
    # (Add base path validation as needed)
    
    if not path.exists():
        return False
    
    system = platform.system()
    
    try:
        if system == "Darwin":  # macOS
            subprocess.run(["open", str(path)], check=True)
        elif system == "Windows":
            subprocess.run(["cmd", "/c", "start", "", str(path)], check=True)
        else:  # Linux
            subprocess.run(["xdg-open", str(path)], check=True)
        
        return True
    
    except Exception:
        return False
```

**Tests**: `tests/unit/test_tui_os_open.py`
```python
def test_open_path_macos(tmp_path):
    """Test macOS path opening."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("content")
    
    with patch("platform.system", return_value="Darwin"):
        with patch("subprocess.run") as mock_run:
            result = open_path(test_file)
            
            assert result is True
            mock_run.assert_called_once_with(["open", str(test_file)], check=True)

def test_open_path_nonexistent():
    """Test opening nonexistent path fails gracefully."""
    result = open_path(Path("/nonexistent/path"))
    assert result is False
```

### PR 1 Deliverables

**Files Added**:
- `src/ui/tui/events.py`
- `src/ui/tui/services/__init__.py`
- `src/ui/tui/services/run_service.py`
- `src/ui/tui/services/health_service.py`
- `src/ui/tui/services/os_open.py`

**Files Modified**:
- `src/ui/tui/state.py` (add reducer, fields)
- `pyproject.toml` (add import-linter rules)

**Tests Added**:
- `tests/unit/test_tui_state_reducer.py`
- `tests/unit/test_tui_event_consumer.py`
- `tests/unit/test_tui_run_service.py`
- `tests/unit/test_tui_health_service.py`
- `tests/unit/test_tui_os_open.py`

**Test Coverage**: >90% for new modules

**Acceptance Criteria**:
- ✅ `apply_event()` passes all state transition tests
- ✅ `EventConsumer` throttles/coalesces correctly
- ✅ `run_service` emits events and handles cancellation
- ✅ All tests pass: `pytest tests/unit/test_tui_*.py -v`

---

## Phase 2: Screens Foundation (PR 2)

### Objective
Build `Home` and `Config` screens with navigation, persistence, and minimal wiring to `AudioExtractionApp`.

### Files to Create

#### `src/ui/tui/views/home.py` (NEW)
**Purpose**: File picker + recent files list.

**Key Features**:
- Dual-pane layout: directory tree (left) + recent files (right)
- Keyboard navigation: arrows, Enter, Tab, `/` filter
- Loads recent files from `platformdirs` config
- Emits custom `FileSelected` event with path

**Widget Composition**:
```python
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import DirectoryTree, DataTable, Input

class HomeScreen(Screen):
    BINDINGS = [
        ("enter", "select_file", "Select"),
        ("tab", "switch_pane", "Switch Pane"),
        ("/", "filter", "Filter"),
        ("r", "refresh_recent", "Refresh Recent"),
    ]
    
    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            yield DirectoryTree("/", id="file-tree")
            yield DataTable(id="recent-files")
        yield Input(placeholder="Filter files...", id="filter-input")
        yield Footer()
    
    def on_mount(self) -> None:
        self._load_recent_files()
    
    def _load_recent_files(self) -> None:
        """Load from platformdirs config."""
        # Implementation
```

**Tests**: `tests/ui/test_tui_home_screen.py` (Textual Pilot)
```python
@pytest.mark.asyncio
async def test_home_screen_file_selection():
    """Test file selection flow."""
    app = AudioExtractionApp()
    async with app.run_test() as pilot:
        # Navigate to HomeScreen
        # ... simulate key presses ...
        # Verify FileSelected event emitted
```

#### `src/ui/tui/views/config.py` (NEW)
**Purpose**: Configuration panel for quality, provider, language, etc.

**Key Features**:
- Form layout with Select, Input, Checkbox widgets
- Auto-save on change (debounced)
- "Start Run" button emits `StartRun` event
- Validates inputs (e.g., output dir exists/creatable)

**Widget Composition**:
```python
from textual.widgets import Select, Input, Checkbox, Button

class ConfigScreen(Screen):
    BINDINGS = [
        ("s", "start_run", "Start"),
        ("r", "reset_defaults", "Reset"),
    ]
    
    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll():
            yield Label("Configuration")
            yield Select(options=QUALITY_OPTIONS, id="quality-select")
            yield Select(options=PROVIDER_OPTIONS, id="provider-select")
            yield Input(placeholder="Language (en, es, ...)", id="language-input")
            yield Select(options=ANALYSIS_OPTIONS, id="analysis-select")
            yield Input(placeholder="Output directory", id="output-input")
            yield Checkbox("Export Markdown", id="export-md-checkbox")
            yield Button("Start Run", variant="primary", id="start-btn")
        yield Footer()
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "start-btn":
            self.post_message(StartRun(config=self._gather_config()))
```

**Tests**: `tests/ui/test_tui_config_screen.py`
```python
@pytest.mark.asyncio
async def test_config_screen_validation():
    """Test config validation."""
    # Simulate invalid output dir
    # Verify error message shown
```

#### `src/ui/tui/styles/theme.tcss` (NEW)
**Purpose**: Textual CSS for consistent styling.

**Key Styles**:
```css
Screen {
    background: $surface;
}

Header {
    background: $primary;
    color: $text;
}

Footer {
    background: $panel;
}

.progress-card {
    border: solid $accent;
    padding: 1;
    margin: 1;
}

.log-entry {
    color: $text-muted;
}

.log-error {
    color: $error;
}
```

#### Persistence Integration

**New Module**: `src/ui/tui/persistence.py`
```python
from platformdirs import user_config_dir

CONFIG_DIR = Path(user_config_dir("audio-extraction-analysis", appauthor=False))
SETTINGS_FILE = CONFIG_DIR / "tui_settings.json"

def load_settings() -> dict[str, Any]:
    """Load TUI settings from disk."""
    if not SETTINGS_FILE.exists():
        return default_settings()
    
    try:
        with open(SETTINGS_FILE) as f:
            return json.load(f)
    except Exception:
        return default_settings()

def save_settings(settings: dict[str, Any]) -> None:
    """Save TUI settings to disk."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings, f, indent=2)
```

### PR 2 Deliverables

**Files Added**:
- `src/ui/tui/views/__init__.py`
- `src/ui/tui/views/home.py`
- `src/ui/tui/views/config.py`
- `src/ui/tui/styles/theme.tcss`
- `src/ui/tui/persistence.py`

**Files Modified**:
- `src/ui/tui/app.py` (add screen routing)
- `pyproject.toml` (add `platformdirs>=3.0` to `[tui]` deps)

**Tests Added**:
- `tests/ui/test_tui_home_screen.py`
- `tests/ui/test_tui_config_screen.py`
- `tests/ui/test_tui_persistence.py`

**Acceptance Criteria**:
- ✅ Navigate Home → Config by keyboard
- ✅ File selection updates AppState
- ✅ Config changes persist to disk
- ✅ "Start Run" transitions to Run screen (stub)

---

## Phase 3: Run Screen & Progress (PR 3)

### Objective
Build `RunScreen` with live progress board, log panel, and cancellation.

### Files to Create

#### `src/ui/tui/views/run.py` (NEW)
**Purpose**: Real-time progress display during pipeline run.

**Key Features**:
- `ProgressBoard` widget: 3 cards (extract, transcribe, analyze)
- `LogPanel` widget: scrollable, filterable logs
- Cancel button → sends `CancelledError` to pipeline task
- ETA calculation using exponential moving average

**Widget Composition**:
```python
from ..widgets.progress_board import ProgressBoard
from ..widgets.log_panel import LogPanel

class RunScreen(Screen):
    BINDINGS = [
        ("c", "cancel_run", "Cancel"),
        ("l", "toggle_logs", "Toggle Logs"),
        ("v", "toggle_verbose", "Verbose"),
    ]
    
    def compose(self) -> ComposeResult:
        yield Header()
        yield ProgressBoard(id="progress-board")
        yield LogPanel(id="log-panel")
        yield Button("Cancel", variant="error", id="cancel-btn")
        yield Footer()
    
    def on_mount(self) -> None:
        # Start EventConsumer
        self.consumer = EventConsumer(
            queue=self.app.event_queue,
            on_batch=self._handle_event_batch,
            config=EventConsumerConfig(throttle_ms=50),
        )
        self.consumer_task = asyncio.create_task(self.consumer.run())
    
    def _handle_event_batch(self, events: list[Event]) -> None:
        """Process batched events and update UI."""
        for event in events:
            new_state = apply_event(self.app.state, event)
            self.app.state = new_state
        
        # Update widgets
        self.query_one(ProgressBoard).update(self.app.state)
        self.query_one(LogPanel).update(self.app.state)
```

#### `src/ui/tui/widgets/progress_board.py` (NEW)
**Purpose**: Visual progress cards for each stage.

**Design**:
```
┌─ Extract Audio ─────────────┐
│ ████████████░░░░░░ 65%     │
│ ETA: 00:15                  │
└─────────────────────────────┘

┌─ Transcribe ────────────────┐
│ ██████████████████░ 95%    │
│ ETA: 00:02                  │
└─────────────────────────────┘

┌─ Analyze ───────────────────┐
│ ░░░░░░░░░░░░░░░░░░░ 0%     │
│ Waiting...                  │
└─────────────────────────────┘
```

**Implementation**:
```python
from textual.widgets import Static
from rich.progress import Progress, BarColumn

class ProgressBoard(Static):
    def update(self, state: AppState) -> None:
        """Update progress cards from state."""
        cards = []
        
        for stage in ["extract", "transcribe", "analyze"]:
            completed = state.stage_completed.get(stage, 0)
            total = state.stage_totals.get(stage, 100)
            pct = (completed / total) * 100 if total > 0 else 0
            
            card = self._render_card(stage, pct, self._calculate_eta(state, stage))
            cards.append(card)
        
        self.update(Panel(Group(*cards), title="Pipeline Progress"))
    
    def _calculate_eta(self, state: AppState, stage: str) -> str:
        """Calculate ETA using stage metrics."""
        # Exponential moving average logic
        # ...
```

#### `src/ui/tui/widgets/log_panel.py` (NEW)
**Purpose**: Scrollable, filterable log viewer.

**Features**:
- Ring buffer (last 2000 entries)
- Search/filter (`/` key)
- Auto-scroll toggle
- Color-coded levels (ERROR=red, WARNING=yellow, INFO=white)

**Implementation**:
```python
from textual.widgets import RichLog

class LogPanel(Static):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.auto_scroll = True
        self.filter_text = ""
    
    def update(self, state: AppState) -> None:
        """Update log panel from state."""
        log_widget = self.query_one(RichLog)
        
        for log_entry in state.logs:
            if self.filter_text and self.filter_text not in log_entry.get("message", ""):
                continue
            
            level = log_entry.get("level", "INFO")
            message = log_entry.get("message", "")
            
            color = {"ERROR": "red", "WARNING": "yellow"}.get(level, "white")
            log_widget.write(f"[{color}]{level}[/]: {message}")
```

### EventLogHandler Integration

**Modify**: `src/utils/logging_factory.py`
```python
def attach_event_sink(cls, event_sink: EventSink, run_id: str | None = None) -> None:
    """Attach event sink to root logger."""
    # ... existing code ...
    
    # ALSO attach to EventConsumer if in TUI mode
    # (Handled by RunScreen mounting EventConsumer)
```

### PR 3 Deliverables

**Files Added**:
- `src/ui/tui/views/run.py`
- `src/ui/tui/widgets/__init__.py`
- `src/ui/tui/widgets/progress_board.py`
- `src/ui/tui/widgets/log_panel.py`

**Files Modified**:
- `src/ui/tui/app.py` (add RunScreen routing)

**Tests Added**:
- `tests/ui/test_tui_run_screen.py`
- `tests/ui/test_cancel_flow.py`
- `tests/integration/test_tui_pipeline_bridge.py`

**Acceptance Criteria**:
- ✅ Progress board updates in real-time (50ms throttle)
- ✅ Log panel shows all events
- ✅ Cancel button stops pipeline and transitions to Results
- ✅ No UI thrashing with 100 events/sec

---

## Phase 4: Results Screen (PR 4)

### Objective
Display artifacts, timings, and provide "open folder" / "open dashboard" actions.

### Files to Create

#### `src/ui/tui/views/results.py` (NEW)
**Purpose**: Post-run results display and actions.

**Key Features**:
- Artifacts table (kind, path, size)
- Stage timing breakdown
- Action buttons: "Open Folder", "Open Dashboard", "Copy Path"
- "New Run" button → reset state and go to Home

**Widget Composition**:
```python
from ..widgets.artifacts_table import ArtifactsTable

class ResultsScreen(Screen):
    BINDINGS = [
        ("o", "open_folder", "Open Folder"),
        ("d", "open_dashboard", "Open Dashboard"),
        ("y", "copy_path", "Copy Path"),
        ("n", "new_run", "New Run"),
    ]
    
    def compose(self) -> ComposeResult:
        yield Header()
        yield Label("Pipeline Complete!", id="title")
        yield ArtifactsTable(id="artifacts")
        yield Static(id="timings")
        with Horizontal():
            yield Button("Open Folder", id="open-folder-btn")
            yield Button("Open Dashboard", id="open-dashboard-btn")
            yield Button("New Run", variant="primary", id="new-run-btn")
        yield Footer()
    
    def on_mount(self) -> None:
        self._populate_results()
    
    def _populate_results(self) -> None:
        artifacts = self.query_one(ArtifactsTable)
        artifacts.update(self.app.state.artifacts)
        
        timings = self.query_one("#timings", Static)
        timings.update(self._render_timings(self.app.state.stage_durations))
    
    def action_open_folder(self) -> None:
        from ..services.os_open import open_path
        output_dir = self.app.state.summary.get("output_dir")
        if output_dir:
            open_path(Path(output_dir))
    
    def action_open_dashboard(self) -> None:
        from ..services.os_open import open_path
        dashboard_path = self._find_dashboard_artifact()
        if dashboard_path:
            open_path(Path(dashboard_path))
```

#### `src/ui/tui/widgets/artifacts_table.py` (NEW)
**Purpose**: DataTable of created artifacts.

**Columns**: Kind | Path | Size

**Implementation**:
```python
from textual.widgets import DataTable

class ArtifactsTable(DataTable):
    def update(self, artifacts: list[dict[str, str]]) -> None:
        """Populate table from artifact list."""
        self.clear()
        self.add_columns("Kind", "Path", "Size")
        
        for artifact in artifacts:
            kind = artifact.get("kind", "unknown")
            path = artifact.get("path", "")
            size = self._format_size(Path(path).stat().st_size) if Path(path).exists() else "N/A"
            
            self.add_row(kind, path, size)
```

### PR 4 Deliverables

**Files Added**:
- `src/ui/tui/views/results.py`
- `src/ui/tui/widgets/artifacts_table.py`

**Files Modified**:
- `src/ui/tui/app.py` (add ResultsScreen routing)

**Tests Added**:
- `tests/ui/test_tui_results_screen.py`
- `tests/ui/test_artifact_actions.py`

**Acceptance Criteria**:
- ✅ Results screen shows all artifacts
- ✅ "Open Folder" launches file manager
- ✅ "Open Dashboard" opens HTML file
- ✅ "New Run" resets state and returns to Home

---

## Phase 5: Provider Health (PR 5)

### Objective
Add provider health widget and background refresh.

### Files to Create

#### `src/ui/tui/widgets/provider_health.py` (NEW)
**Purpose**: Display provider status and configuration hints.

**Design**:
```
┌─ Provider Health ───────────────────────────┐
│ Provider    Status  Message                │
│ deepgram    ✓ OK    API key configured      │
│ elevenlabs  ✗ ERR   Missing API key         │
│ whisper     ✓ OK    Model: base (local)     │
│ parakeet    ✗ ERR   Dependencies missing    │
└─────────────────────────────────────────────┘
Press 'r' to refresh
```

**Implementation**:
```python
from textual.widgets import DataTable
from ..services.health_service import HealthService

class ProviderHealth(DataTable):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.health_service = HealthService()
    
    async def on_mount(self) -> None:
        await self.refresh_health()
    
    async def refresh_health(self) -> None:
        """Fetch and display provider health."""
        health = await self.health_service.check_all_providers()
        
        self.clear()
        self.add_columns("Provider", "Status", "Message")
        
        for provider, status in health.items():
            icon = "✓" if status["status"] == "ok" else "✗"
            message = status.get("message", "")
            
            self.add_row(provider, f"{icon} {status['status'].upper()}", message)
```

**Integration**:
- Add to `HomeScreen` (displayed before file selection)
- Add to `ConfigScreen` (provider selection context)
- Background refresh on `r` key

### PR 5 Deliverables

**Files Added**:
- `src/ui/tui/widgets/provider_health.py`

**Files Modified**:
- `src/ui/tui/views/home.py` (embed ProviderHealth widget)
- `src/ui/tui/views/config.py` (embed ProviderHealth widget)

**Tests Added**:
- `tests/ui/test_provider_health_widget.py`

**Acceptance Criteria**:
- ✅ Health checks run in background (thread pool)
- ✅ Cache lasts 60 seconds
- ✅ "Refresh" (`r` key) forces re-check
- ✅ Missing API keys show helpful hints

---

## Phase 6: CLI Integration & Docs (PR 6)

### Objective
Wire TUI to CLI, add flags, update documentation.

### CLI Changes

#### Modify `src/cli.py`

**Add TUI subcommand**:
```python
def _create_tui_subparser(subparsers) -> None:
    """Create TUI subcommand parser."""
    tui = subparsers.add_parser(
        "tui",
        help="Launch interactive Text User Interface",
        description="Full-featured TUI with live progress and provider health",
    )
    
    # ... (flags from Phase 0 - CLI Flags section)
    
    tui.set_defaults(func=tui_command)

def tui_command(args: argparse.Namespace) -> int:
    """Launch TUI application."""
    try:
        from .ui.tui.app import AudioExtractionApp
    except ImportError:
        logger.error("TUI dependencies not installed. Run: pip install audio-extraction-analysis[tui]")
        return 1
    
    app = AudioExtractionApp(
        input_path=str(args.input) if args.input else None,
        output_dir=str(args.output_dir) if args.output_dir else None,
    )
    
    # Set theme
    if args.theme == "dark":
        app.dark = True
    elif args.theme == "light":
        app.dark = False
    # "auto" uses Textual default
    
    app.run()
    return 0
```

**Add to `create_parser()`**:
```python
def create_parser() -> argparse.ArgumentParser:
    # ... existing code ...
    
    _create_tui_subparser(subparsers)  # ADD THIS LINE
    
    return parser
```

### Documentation Updates

#### `README.md`

**Add TUI section** (after "CLI Commands"):
```markdown
## 🖥️ Interactive TUI

Launch the interactive Text User Interface for a visual, real-time experience:

```bash
# Launch TUI
audio-extraction-analysis tui

# Pre-populate input file
audio-extraction-analysis tui --input video.mp4

# Use light theme
audio-extraction-analysis tui --theme light
```

### TUI Features

- **Live Progress**: Real-time pipeline stages with ETA
- **Provider Health**: Check API key configuration before running
- **Log Viewer**: Searchable, filterable logs with auto-scroll
- **Artifact Browser**: Quick access to generated files
- **Keyboard Driven**: Full navigation without mouse

### Key Bindings

| Screen  | Key   | Action                    |
|---------|-------|---------------------------|
| Global  | `q`   | Quit                      |
| Global  | `d`   | Toggle dark/light mode    |
| Global  | `?`   | Show help overlay         |
| Home    | `↑↓`  | Navigate file tree        |
| Home    | `Enter` | Select file             |
| Home    | `/`   | Filter files              |
| Home    | `Tab` | Switch pane               |
| Home    | `r`   | Refresh provider health   |
| Config  | `↑↓`  | Navigate fields           |
| Config  | `Space` | Toggle checkbox         |
| Config  | `Enter` | Edit field              |
| Config  | `s`   | Start run                 |
| Run     | `c`   | Cancel run                |
| Run     | `l`   | Toggle log panel          |
| Run     | `v`   | Toggle verbose logs       |
| Results | `o`   | Open output folder        |
| Results | `d`   | Open HTML dashboard       |
| Results | `y`   | Copy artifact path        |
| Results | `n`   | New run                   |

### Installing TUI

```bash
# Install with TUI dependencies
pip install audio-extraction-analysis[tui]

# Or install Textual separately
pip install textual>=0.52.0 platformdirs>=3.0
```

### Screenshots

*(TODO: Add screenshots after UI is complete)*

![TUI Home Screen](docs/images/tui-home.png)
![TUI Run Screen](docs/images/tui-run.png)
![TUI Results Screen](docs/images/tui-results.png)
```

#### `docs/TUI.md` (NEW)

Create comprehensive TUI documentation covering:
- Installation troubleshooting
- Terminal compatibility (minimum 80×24)
- Font requirements (Unicode support)
- Accessibility notes (keyboard-only navigation)
- Configuration file location
- Advanced usage (persistence, themes)

#### `pyproject.toml`

**Add TUI dependencies**:
```toml
[project.optional-dependencies]
tui = [
    "textual>=0.52.0",
    "platformdirs>=3.0",
]
```

**Update CLI entrypoint documentation** (if needed).

### PR 6 Deliverables

**Files Added**:
- `docs/TUI.md`
- `docs/images/tui-*.png` (screenshots)

**Files Modified**:
- `src/cli.py` (add `tui` subcommand)
- `README.md` (add TUI section)
- `pyproject.toml` (add `[tui]` deps)

**Tests Added**:
- `tests/integration/test_cli_tui_integration.py`

**Acceptance Criteria**:
- ✅ `audio-extraction-analysis tui` launches TUI
- ✅ `--input` and `--output-dir` pre-populate correctly
- ✅ Missing Textual deps show helpful error message
- ✅ All key bindings work as documented
- ✅ README screenshots render correctly

---

## Test Strategy

### Unit Tests (Isolated Logic)

**Coverage Target**: >90% for TUI modules

**Test Files**:
- `tests/unit/test_tui_state_reducer.py` - Pure reducer logic
- `tests/unit/test_tui_event_consumer.py` - Batching/throttling
- `tests/unit/test_tui_run_service.py` - Service wrappers
- `tests/unit/test_tui_health_service.py` - Provider health caching
- `tests/unit/test_tui_os_open.py` - Platform-specific openers
- `tests/unit/test_tui_persistence.py` - Config save/load

**Mocking Strategy**:
- Mock `process_pipeline` to return synthetic results
- Mock `TranscriptionProviderFactory.check_provider_health_sync`
- Mock `subprocess.run` for `os_open` tests
- Mock `platformdirs.user_config_dir` to use temp dirs

### Component Tests (Textual Pilot)

**Purpose**: Test screen interactions without full integration.

**Test Files**:
- `tests/ui/test_tui_home_screen.py` - File selection flow
- `tests/ui/test_tui_config_screen.py` - Config validation
- `tests/ui/test_tui_run_screen.py` - Progress updates
- `tests/ui/test_tui_results_screen.py` - Artifact actions
- `tests/ui/test_cancel_flow.py` - Cancellation handling

**Pilot Pattern**:
```python
@pytest.mark.asyncio
async def test_screen_navigation():
    app = AudioExtractionApp()
    
    async with app.run_test() as pilot:
        # Simulate key presses
        await pilot.press("tab")
        await pilot.press("enter")
        
        # Verify screen transition
        assert isinstance(app.screen, ConfigScreen)
```

### Integration Tests (Full Pipeline)

**Purpose**: Verify TUI + pipeline + events work end-to-end.

**Test Files**:
- `tests/integration/test_tui_pipeline_bridge.py` - Real events flow to UI
- `tests/integration/test_cli_tui_integration.py` - CLI launches TUI correctly

**Pattern**:
```python
@pytest.mark.asyncio
async def test_tui_processes_real_events(tmp_path):
    """Run short pipeline and verify UI updates."""
    app = AudioExtractionApp()
    
    # Set up mocked pipeline that emits real events
    with patch("src.pipeline.simple_pipeline.process_pipeline") as mock:
        mock.side_effect = synthetic_pipeline_with_events
        
        async with app.run_test() as pilot:
            # Trigger run
            # ... navigate to Config, press "Start" ...
            
            # Verify progress updates
            await asyncio.sleep(0.5)  # Let events flow
            assert app.state.current_stage is not None
```

### Manual Testing Checklist

Before each PR merge:
- [ ] Run TUI on macOS, Linux, Windows (if available)
- [ ] Test with small (< 1 MB), medium (100 MB), large (1 GB) files
- [ ] Test cancellation mid-run (verify cleanup)
- [ ] Test provider health with missing/present API keys
- [ ] Test persistence (restart TUI, verify settings restored)
- [ ] Test terminal resize (verify layout adapts)
- [ ] Test dark/light themes
- [ ] Test keyboard-only navigation (no mouse)

---

## Risk Mitigation

### Risk 1: UI Thrashing from High Event Rate

**Mitigation**:
- **EventConsumer throttling**: 50ms batches limit updates to 20 FPS
- **Progress coalescing**: Only latest progress per stage is kept
- **Integration test**: Emit 100 events/sec, verify smooth rendering

**Validation**:
```python
@pytest.mark.asyncio
async def test_high_event_rate_ui_responsiveness():
    """Verify UI remains responsive under high event load."""
    app = AudioExtractionApp()
    
    async with app.run_test() as pilot:
        # Emit 1000 progress events over 1 second
        for i in range(1000):
            await app.event_queue.put(Event(type="stage_progress", stage="extract", data={"completed": i, "total": 1000}))
            await asyncio.sleep(0.001)
        
        # UI should update smoothly (check frame rate)
        # ...
```

### Risk 2: Blocking Health Checks Freeze UI

**Mitigation**:
- **Thread pool executor**: `HealthService._sync_check()` runs in background
- **Caching**: 60-second TTL avoids redundant checks
- **Timeout**: Health checks have 5-second timeout

**Validation**:
```python
@pytest.mark.asyncio
async def test_health_check_does_not_block():
    """Verify health checks run asynchronously."""
    service = HealthService()
    
    start = time.time()
    
    # Simulate slow health check
    with patch("src.providers.factory.TranscriptionProviderFactory.check_provider_health_sync") as mock:
        mock.side_effect = lambda _: time.sleep(2) or {"status": "ok"}
        
        # Should not block
        task = asyncio.create_task(service.check_all_providers())
        await asyncio.sleep(0.1)  # UI should remain responsive
        
        await task
        assert time.time() - start < 3  # Runs in parallel
```

### Risk 3: Cross-Platform `os_open` Quirks

**Mitigation**:
- **Per-platform testing**: Unit tests mock `platform.system()`
- **Graceful failure**: Returns `False` instead of crashing
- **Validation**: Test on macOS, Linux, Windows before merge

**Validation**:
```python
@pytest.mark.parametrize("system,command", [
    ("Darwin", ["open", "/path"]),
    ("Windows", ["cmd", "/c", "start", "", "/path"]),
    ("Linux", ["xdg-open", "/path"]),
])
def test_open_path_platform_commands(system, command):
    with patch("platform.system", return_value=system):
        with patch("subprocess.run") as mock_run:
            open_path(Path("/path"))
            mock_run.assert_called_with(command, check=True)
```

### Risk 4: Large Logs OOM

**Mitigation**:
- **Ring buffer**: Max 2000 entries with middle truncation
- **Lazy rendering**: LogPanel only renders visible entries
- **Memory profiling**: Test with 10k log events

**Validation**:
```python
def test_log_panel_ring_buffer_memory():
    """Verify log panel doesn't grow unbounded."""
    state = AppState()
    
    # Emit 10,000 log events
    for i in range(10000):
        event = Event(type="log", data={"message": f"Log {i}" * 100})  # 500 bytes each
        state = apply_event(state, event)
    
    # Should stay under 200KB (2000 entries * 100 bytes)
    assert len(state.logs) <= 2000
    import sys
    assert sys.getsizeof(state.logs) < 500_000  # 500KB max
```

---

## Performance Targets

| Metric | Target | Validation |
|--------|--------|------------|
| Event latency (emit → UI update) | < 100ms (p99) | Integration test with timestamps |
| UI frame rate (during run) | > 15 FPS | Textual profiler |
| Memory overhead (TUI vs CLI) | < 50 MB | `memory_profiler` on 1-hour run |
| Startup time (TUI launch) | < 2 seconds | `time audio-extraction-analysis tui` |
| Health check timeout | < 5 seconds | `HealthService` timeout enforcement |

---

## Accessibility Considerations

### Keyboard-Only Navigation
- ✅ All actions accessible via keyboard shortcuts
- ✅ No mouse-required interactions
- ✅ Focus indicators clear and visible
- ✅ Tab/arrow keys navigate logically

### Screen Reader Support
- ⚠️ **Limitation**: Textual's screen reader support is experimental
- ✅ Use semantic labels (e.g., "Progress: 65% complete")
- ✅ Provide textual alternatives for visual indicators (✓/✗ icons)
- ✅ Document keyboard shortcuts in help overlay

### High Contrast / Colorblind Modes
- ✅ Support `NO_COLOR` environment variable
- ✅ Use symbols + text (not color alone) for status
- ✅ Test with macOS high-contrast mode

---

## Rollout Plan

### Alpha Release (Internal Testing)
**Target**: End of PR 3  
**Scope**: Core functionality (Home → Config → Run → Results)  
**Audience**: Development team  
**Testing**: Manual E2E on 3 platforms

### Beta Release (Early Adopters)
**Target**: End of PR 5  
**Scope**: Full feature set + provider health  
**Audience**: Selected power users via GitHub Discussions  
**Testing**: Feedback loop + bug fixes

### GA Release (v1.1.0)
**Target**: End of PR 6  
**Scope**: Fully documented, tested, and polished  
**Announcement**: Blog post + social media  
**Support**: Create GitHub Issues template for TUI bugs

---

## Success Criteria

### Functional Requirements
- ✅ TUI achieves feature parity with CLI (`process`, `transcribe`, `extract` workflows)
- ✅ Event stream matches `--jsonl` output (same events, same order)
- ✅ Cancellation cleanly stops pipeline and preserves partial artifacts
- ✅ Provider health shows actionable hints for missing API keys
- ✅ Results screen allows opening output folder and HTML dashboard

### Non-Functional Requirements
- ✅ All tests pass: `pytest tests/ -v`
- ✅ Test coverage >85% overall, >90% for TUI modules
- ✅ No `import-linter` violations
- ✅ Runs in 80×24 terminal without visual glitches
- ✅ Works on macOS, Linux, Windows (validated manually)
- ✅ Documentation complete (README, TUI.md, screenshots)

### User Experience
- ✅ First-time users can complete a run without consulting docs
- ✅ Provider health panel prevents "Missing API key" surprises
- ✅ Log panel helps debug errors without needing `--verbose` CLI flag
- ✅ Keyboard shortcuts feel intuitive (match common TUI conventions)

---

## Open Questions & Future Work

### Open Questions (Resolve Before PR 1)
1. **Event run_id tracking**: Should `AppState` store a history of past `run_id`s for debugging?  
   → **Decision**: No, only current `run_id`. Add to future "Run History" feature.

2. **ETA calculation**: Use simple linear projection or smoothed exponential average?  
   → **Decision**: Exponential moving average (α=0.3) for stability.

3. **Persistence file format**: JSON or TOML?  
   → **Decision**: JSON for simplicity; Pydantic validation.

4. **Provider selection in Config**: Show only configured providers or all available?  
   → **Decision**: Show all; mark unconfigured with "(API key missing)" suffix.

### Future Enhancements (Out of Scope)
- **Run History**: View past runs, re-open results
- **Batch Mode**: Queue multiple files for sequential processing
- **Remote Monitoring**: WebSocket streaming to browser dashboard
- **Custom Themes**: User-defined color schemes
- **Shortcuts Customization**: Rebind keys via config file
- **Export Results**: Export artifacts list to CSV/JSON
- **Diff View**: Compare transcripts between provider runs
- **Plugins**: Load custom analyzers/formatters from external modules

---

## Conclusion

This roadmap provides a concrete, phase-gated implementation plan for the TUI. Each PR is independently shippable, testable, and adds incremental value. By following the **event-driven reducer pattern** and adhering to **Textual best practices**, the TUI will achieve feature parity with the CLI while providing a superior interactive experience.

**Next Steps**:
1. Review this roadmap with stakeholders
2. Resolve any remaining ambiguities
3. Begin PR 1 implementation (Foundation)
4. Iterate based on testing feedback

**Estimated Timeline**:
- PR 1 (Foundation): 3-5 days
- PR 2 (Screens): 4-6 days
- PR 3 (Run Screen): 5-7 days
- PR 4 (Results): 2-3 days
- PR 5 (Health): 2-3 days
- PR 6 (CLI/Docs): 2-3 days
- **Total**: ~3-4 weeks (with testing and iteration)

---

*End of TUI Implementation Roadmap*
