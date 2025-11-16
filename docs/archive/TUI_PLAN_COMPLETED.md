# TUI Implementation Plan

**Goal**: Deliver a full Textual TUI that runs on the new event stream and reaches feature parity with the CLI.

---

## 0) Targets

### Success Criteria
- ✅ End-to-end run from file selection → config → live progress → results
- ✅ Cancel works; cleanup preserved; partial artifacts visible
- ✅ Provider health visible before run
- ✅ Event stream parity with `--jsonl`
- ✅ Tests cover event→UI flow and cancellation

---

## 1) Architecture Shape

### State + Reducers
**`src/ui/tui/state.py`**
- `AppState` (dataclass):
  - inputs, config, run_id, status, metrics, artifacts
  - logs (ring buffer), provider_health, errors
- `apply_event(state, event) -> state` reducer
  - No UI code here
- Ring buffer size: 2–5k lines with middle truncation

### Event Ingestion
**`src/ui/tui/events.py`**
- `EventConsumer(queue, callback, *, throttle_ms=33)`:
  - Reads queue
  - Batches progress
  - Calls `callback(batched_events)` to update state once per frame

### Services
**`src/ui/tui/services/run_service.py`**
- `run_pipeline(input, config, sink) -> task`:
  - Spawns pipeline
  - Returns `asyncio.Task`

**`src/ui/tui/services/health_service.py`**
- Async wrapper for `TranscriptionProviderFactory.check_provider_health_sync` (thread pool)
- Caching

### OS Helpers
**`src/ui/tui/services/os_open.py`**
- `open_path(path)`: cross-platform file/folder opener

---

## 2) Screens and Widgets

### Screens
1. **HomeScreen**: file picker + recent list
2. **ConfigScreen**: quality, provider (auto), language, analysis style, flags (export_markdown, html_dashboard), output dir
3. **RunScreen**: progress board + collapsible log panel + ETA
4. **ResultsScreen**: artifacts table, timings, "open dir" + "open dashboard"

### Widgets
- **FilePicker**: keyboard (arrows, `/` filter, Tab focus)
- **ProgressBoard**: cards for extract/transcribe/analyze/save; % + ETA
- **LogPanel**: search, pause/resume
- **ProviderHealth**: table of providers, status, notes
- **ShortcutsHelp**: overlay on `?`

### Key Bindings

#### Global
- `q`: quit
- `?`: help
- `F2`: theme

#### Home
- `Enter`: select
- `/`: filter
- `Tab`: switch pane

#### Config
- `arrows`: navigate
- `Space`: toggle
- `Enter`: edit
- `s`: save → Run

#### Run
- `c`: cancel
- `l`: logs toggle
- `v`: verbose logs toggle

#### Results
- `o`: open folder
- `d`: open dashboard
- `y`: copy path

---

## 3) Event→State Mapping (Reducer Contract)

- `stage_start` → set `state.stages[stage].status="running"`, total
- `stage_progress` → update completed/total, ETA smoothing
- `stage_end` → mark `status="done"`, record duration
- `artifact` → append to `state.artifacts`
- `log|warning|error` → append to log ring; bump `state.error_count` on error
- `summary` → set `state.metrics`, `state.status="complete"`
- `cancelled` → `state.status="cancelled"`

**Note**: Batch + coalesce progress events inside `EventConsumer` to avoid UI thrash.

---

## 4) Concurrency and Lifecycle

### Run Start
1. Create `run_id`, `asyncio.Queue[Event]`
2. Create `CompositeSink([QueueEventSink, ConsoleEventSink?])` if desired
3. Attach `EventLogHandler` with the same `run_id`
4. Keep `pipeline_task`

### Cancellation
- On `c`, call `pipeline_task.cancel()`
- In pipeline, catch `CancelledError`, emit `cancelled`, then cleanup

### Teardown
- On app exit: cancel tasks, drain queue
- Graceful teardown

---

## 5) Config and Persistence

### Storage
- Use `platformdirs` for `~/.config/audio-extraction-analysis/settings.json`

### Persisted Settings
- Last input dir
- Output dir
- Provider
- Quality
- Theme
- Log verbosity

### Theming
- Respect `NO_COLOR`
- Provide high-contrast theme switch (`styles/theme.tcss`)

---

## 6) Provider Health Surface

### Implementation
- At `Home` mount, call `health_service.fetch()` in background
- Display statuses and hints:
  - "missing DEEPGRAM_API_KEY", etc.
- Cache until user refreshes (`r`)

---

## 7) Packaging

### `pyproject.toml`
```toml
[project.optional-dependencies]
tui = [
    "textual>=0.52",
    "platformdirs>=3.0"
]
```

### Import Rules
- Keep lazy import in `tui` subcommand
- Respect `import-linter` layers:
  - TUI uses services/pipeline, not providers directly
  - Health checks via factory only

---

## 8) Tests

### Unit Tests

**`tests/ui/test_state_reducer.py`**
- Event sequences → expected state snapshots

**`tests/ui/test_event_consumer.py`**
- Throttling and coalescing

**`tests/unit/test_os_open.py`**
- Path open mapping per platform (mocked)

### Component Tests (Textual Pilot)

**`tests/ui/test_tui_navigation.py`**
- Home→Config→Run→Results key flow
- Mocked pipeline task and synthetic events

**`tests/ui/test_cancel.py`**
- Send `cancelled` mid-run
- Ensure UI returns to Results with partial artifacts

### Integration Tests

**`tests/integration/test_tui_pipeline_bridge.py`**
- Run a short mocked pipeline emitting real events
- Assert widgets reflect progress
- No exceptions

---

## 9) PR Stack (Stacked, Shippable)

### PR 1 – `feat(tui-core): State, reducer, consumer, services skeleton`
**Files:**
- `src/ui/tui/state.py`
- `src/ui/tui/events.py`
- `src/ui/tui/services/run_service.py`
- `src/ui/tui/services/health_service.py`
- `src/ui/tui/services/os_open.py`

**Tests:**
- Reducer + consumer

---

### PR 2 – `feat(tui-screens): Home + Config screens, minimal wiring`
**Files:**
- `src/ui/tui/app.py` (enhanced)
- `src/ui/tui/views/home.py`
- `src/ui/tui/views/config.py`
- `src/ui/tui/styles/theme.tcss`

**Features:**
- Adds persistence via `platformdirs`

---

### PR 3 – `feat(tui-run): Run screen, progress board, log panel, cancellation`
**Files:**
- `src/ui/tui/views/run.py`
- `src/ui/tui/widgets/progress_board.py`
- `src/ui/tui/widgets/log_panel.py`

**Features:**
- Hook `EventLogHandler`

**Tests:**
- Cancel flow

---

### PR 4 – `feat(tui-results): Results screen, artifacts actions, open dashboard`
**Files:**
- `src/ui/tui/views/results.py`
- `src/ui/tui/widgets/artifacts_table.py`

**Tests:**
- Artifact actions

---

### PR 5 – `feat(tui-health): Provider health widget + background refresh`
**Files:**
- `src/ui/tui/widgets/provider_health.py`

**Tests:**
- Health display

---

### PR 6 – `chore(cli): TUI flags, defaults, docs`
**Changes:**
- Extend `tui` subcommand to accept:
  - `--input`
  - `--output-dir`
  - `--theme`
  - `--verbose-logs`
- Docs updates

---

## 10) Implementation Notes

### Run ID
- Generate once per run
- Inject into sinks and logger

### Backpressure
- Use `queue.put_nowait` + bounded queue (e.g., 1k)
- If full, drop oldest progress event
- Never drop error/summary/artifact

### ETA Smoothing
- Exponential moving average on `remaining = (total-completed)/rate`

### Path Safety
- Reuse `PathSanitizer.ensure_safe_subpath` in open actions

### Cross-Platform Open
```python
subprocess.Popen([
    "open"|"xdg-open"|"cmd", "/c", "start", path
]) # after validation
```

### KeyboardInterrupt
- Map to cancel
- Do not kill the app abruptly

---

## 11) Documentation

### Files to Update

**`README.md`**
- Add "TUI mode" section
- Screenshots
- Key bindings

**`docs/EVENT_STREAMING.md`**
- Add "Consuming events in TUI"

**`docs/TUI.md`** (new)
- Troubleshooting:
  - Term size
  - Fonts
  - Missing Textual
- Accessibility notes

---

## 12) Risks

| Risk | Mitigation |
|------|------------|
| UI thrash | Event coalescing + 30–60 ms throttle |
| Blocking health checks | Thread executor wrapper |
| Windows open quirks | Unit tests, single helper |
| Large logs | Ring buffer with truncation |

---

## 13) Acceptance Checklist

- [ ] `audio-extraction-analysis tui` runs in a 80×24 terminal
- [ ] Navigate Home→Config→Run→Results by keyboard alone
- [ ] Live progress mirrors `--jsonl`
- [ ] Cancel shows `cancelled` and preserves artifacts
- [ ] Results allow opening output dir and dashboard
- [ ] Provider health panel warns on missing API keys
- [ ] All new tests pass

---

## Next Steps

**Pick PR 1 and build up.**

Start with the foundational state management, reducer, and event consumer infrastructure before building the UI screens on top.
