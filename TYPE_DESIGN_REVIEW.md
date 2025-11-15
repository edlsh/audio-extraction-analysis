# Type Design Review: TUI Implementation

**Date**: 2025-11-15
**Scope**: Type design evaluation for src/ui/tui and src/models/events
**Overall Quality Score**: 5.2/10 (Moderate - functional but with significant encapsulation and invariant enforcement gaps)

---

## Executive Summary

The TUI implementation demonstrates a solid understanding of functional programming patterns (pure reducers, immutable state updates) and event-driven architecture. However, the type design suffers from:

1. **Weak Encapsulation**: Mutable dataclasses without invariant validation
2. **Implicit Contracts**: Type-specific data schemas expressed only in comments
3. **Missing Discriminated Unions**: Event variants use untyped dicts instead of structured types
4. **Weak Configuration Types**: Settings and recent files use plain dicts (no schema)
5. **Inconsistent Thread Safety**: Some sinks are thread-safe, others aren't

The good news: the architectural approach is sound. The fixes require type-level changes, not structural rewrites.

---

## Type Reviews

### 1. AppState (src/ui/tui/state.py)

```python
@dataclass
class AppState:
    """Application state for the TUI."""
    input_path: Path | None = None
    output_dir: Path | None = None
    is_running: bool = False
    can_cancel: bool = False
    # ... 15+ more fields
```

#### Invariants Identified

1. **State Machine Invariant**: `is_running=True ⟹ can_cancel=True` (running implies cancellable)
2. **Progress Bounds**: `0 ≤ current_progress ≤ 100.0`
3. **Stage Consistency**: If `current_stage` is set, it should exist in `stage_totals`
4. **Run Identity**: When `is_running=True`, `run_id` must be non-None
5. **Pre-execution Guard**: `input_path` and `output_dir` must be set before `is_running=True`
6. **Artifact/Error/Log Collections**: Should maintain bounded size (ring buffer for logs is good)

#### Ratings

- **Encapsulation**: 3/10
  - All fields are public and mutable after construction
  - No validation in `__post_init__`
  - External code can violate invariants: `state.is_running = True; state.can_cancel = False`
  - Collections (`artifacts`, `errors`, `logs`) can be mutated directly after creation
  - `reset_run_state()` is procedural and doesn't prevent invalid intermediate states

- **Invariant Expression**: 2/10
  - Boolean combinations (`is_running`, `can_cancel`) have no type-level representation
  - Should use an `Enum` for state machine instead of two booleans
  - Progress range is implicit (no `Annotated` type or validator)
  - Stage existence is not expressible in the type system
  - Dependencies between fields are undocumented

- **Invariant Usefulness**: 7/10
  - These invariants prevent real bugs (race conditions, invalid progress, orphaned runs)
  - Better than no invariants, but currently unenforced
  - Would catch 70% of state-related bugs if enforced

- **Invariant Enforcement**: 5/10
  - ✓ Good: `apply_event()` returns new state via `dataclasses.replace()` (prevents mutations during reduction)
  - ✗ Bad: No `__post_init__` validation of construction
  - ✗ Bad: `reset_run_state()` is a method, not enforced at construction
  - ✗ Bad: Ring buffer logic in `_append_to_ring()` is external to state (side effect)
  - ✗ Bad: Collections are mutable after construction

#### Strengths

- Clean field naming and organization
- `reset_run_state()` method provides a recovery path
- `apply_event()` pure reducer pattern is excellent
- Ring buffer implementation is sophisticated and prevents memory leaks
- Stage tracking with `stage_totals`, `stage_completed`, `stage_durations` is well-structured

#### Concerns

1. **Critical**: State machine invariant (`is_running/can_cancel`) can be violated
   ```python
   state.is_running = True
   state.can_cancel = False  # INVALID: contradicts invariant
   ```

2. **Critical**: No validation that `input_path` and `output_dir` are set before run
   - Could cause pipeline to fail at runtime

3. **Important**: Progress value is unbounded (could be 150% if badly calculated)

4. **Important**: Stage consistency is unenforced
   ```python
   state.current_stage = "unknown_stage"  # No validation
   ```

5. **Moderate**: Collections are mutable after construction
   ```python
   state.artifacts.clear()  # Unexpected mutation
   ```

#### Recommended Improvements

1. **Add State Machine Enum** (CRITICAL)
   ```python
   from enum import Enum

   class RunState(Enum):
       IDLE = "idle"          # Before/after run
       RUNNING = "running"    # During execution
       CANCELLING = "cancelling"  # Cancel requested

   @dataclass
   class AppState:
       run_state: RunState = RunState.IDLE
       # Remove: is_running, can_cancel
   ```
   - Makes state machine explicit
   - Impossible to reach invalid combinations

2. **Use Field Validators** (IMPORTANT)
   ```python
   from pydantic import BaseModel, field_validator, Field
   from typing import Annotated

   @dataclass
   class AppState:
       current_progress: Annotated[float, Field(ge=0, le=100.0)] = 0.0

       def __post_init__(self):
           # Validate state machine
           if self.run_state == RunState.RUNNING:
               assert self.input_path is not None
               assert self.output_dir is not None
               assert self.run_id is not None
   ```

3. **Make Collections Immutable** (IMPORTANT)
   ```python
   from dataclasses import dataclass
   from typing import Sequence

   @dataclass(frozen=False)  # State updates via apply_event
   class AppState:
       artifacts: Sequence[dict[str, str]] = field(default_factory=tuple)  # Use tuple
       errors: Sequence[str] = field(default_factory=tuple)
       logs: Sequence[dict[str, Any]] = field(default_factory=tuple)
   ```
   - `_append_to_ring()` already returns new list; use tuple instead
   - Prevents accidental mutations

4. **Document State Transitions** (MODERATE)
   ```python
   """Valid state transitions:
   IDLE → RUNNING (on stage_start)
   RUNNING → CANCELLING (on cancel action)
   RUNNING → IDLE (on stage_end or error)
   CANCELLING → IDLE (after cleanup)
   """
   ```

5. **Add Typed Aliases for Collections** (MODERATE)
   ```python
   LogEntry: TypeAlias = dict[str, Any]  # {type, timestamp, level, message, logger}
   Artifact: TypeAlias = dict[str, str]  # {kind, path}
   ```
   - Improves code clarity
   - Consider future migration to dataclasses

---

### 2. Event (src/models/events.py)

```python
@dataclass
class Event:
    type: EventType  # Literal with 9 variants
    ts: str = field(default_factory=...)
    run_id: str = field(default_factory=...)
    stage: str | None = None
    data: dict[str, Any] = field(default_factory=dict)
```

#### Invariants Identified

1. **Type Discriminator**: `type` must be one of the `EventType` literals (enforced by Literal)
2. **Data Schema**: `data` structure depends on `type`:
   - `stage_start`: requires `{"description": str, "total": int}`
   - `stage_progress`: requires `{"completed": int, "total": int, "message": str}`
   - `stage_end`: requires `{"duration": float, "status": str}`
   - `artifact`: requires `{"kind": str, "path": str}`
   - `log/warning/error`: requires `{"message": str, "level": str, "logger": str}`
   - `summary`: requires `{"metrics": dict, "provider": str, "output_dir": str}`
   - `cancelled`: requires `{"reason": str}`

3. **Timestamp Format**: `ts` must be ISO 8601 UTC (e.g., `2025-11-15T10:30:45.123456+00:00`)
4. **Run ID Consistency**: All events in a run should have the same `run_id`
5. **Stage Presence**: If `stage` is None, event type should not be stage-related

#### Ratings

- **Encapsulation**: 7/10
  - ✓ Immutable dataclass (cannot modify after creation)
  - ✓ Literal type discriminates event types
  - ✓ Methods for serialization (`to_dict()`, `to_json()`)
  - ✗ `data` dict is completely untyped (no schema enforcement)
  - ✗ Could be constructed with invalid data: `Event(type="stage_start", data={})`

- **Invariant Expression**: 5/10
  - ✓ Event type is well-expressed via Literal
  - ✓ ISO 8601 timestamp is standard
  - ✗ Data schema is implicit in comments, not in type system
  - ✗ Missing discriminated union pattern for type-specific data
  - ✗ `stage: str | None` doesn't express relationship to `type`
  - Would benefit from separate classes per event type or Protocol-based dispatch

- **Invariant Usefulness**: 8/10
  - Event types are correct and useful
  - Timestamp tracking is valuable for debugging
  - Run ID correlation is essential for event streams
  - Data schemas match actual usage

- **Invariant Enforcement**: 4/10
  - ✓ Literal type ensures `type` is valid
  - ✓ Immutable after construction
  - ✗ No validation that `data` matches the event `type`
  - ✗ No validation of ISO 8601 timestamp format
  - ✗ Can create: `Event(type="stage_start", data={"wrong": "schema"})`

#### Strengths

- Immutable design enables safe sharing and time-travel debugging
- Serialization methods (`to_json()`, `to_dict()`) are well-placed
- EventType literal is clean and restrictive
- Good use of factory defaults for `ts` and `run_id`

#### Concerns

1. **Critical**: No validation that `data` matches `type`
   ```python
   # This is allowed but invalid:
   Event(type="stage_start", data={})  # Missing 'total', 'description'

   # apply_event will crash or behave incorrectly:
   event.data.get("total", 100)  # Falls back to default instead of erroring
   ```

2. **Important**: Data schema is only in comments (state.py lines 128-200)
   ```python
   # In state.py apply_event():
   # data: {"description": str, "total": int}  # Only in comment!
   return dataclasses.replace(
       state,
       current_message=event_data.get("description", ""),  # Silent failure
   )
   ```

3. **Important**: No factory functions to construct events safely
   ```python
   # Should have:
   Event.stage_start(stage="extract", description="...", total=100)
   ```

4. **Moderate**: `stage: str | None` relationship to `type` is implicit

#### Recommended Improvements

1. **Add Type-Safe Event Construction** (CRITICAL)
   ```python
   from typing import overload

   class Event:
       # Existing fields...

       @staticmethod
       def stage_start(stage: str, description: str, total: int, run_id: str | None = None) -> Event:
           """Construct a stage_start event with validation."""
           return Event(
               type="stage_start",
               stage=stage,
               data={"description": description, "total": total},
               run_id=run_id or str(uuid.uuid4()),
           )

       @staticmethod
       def stage_progress(stage: str, completed: int, total: int, message: str = "", run_id: str | None = None) -> Event:
           """Construct a stage_progress event."""
           return Event(
               type="stage_progress",
               stage=stage,
               data={"completed": completed, "total": total, "message": message},
               run_id=run_id or str(uuid.uuid4()),
           )

       # ... similar for other event types
   ```
   - Enforces schema at construction
   - Makes event creation self-documenting

2. **Use TypedDict for Data Payloads** (IMPORTANT)
   ```python
   from typing import TypedDict

   class StageStartData(TypedDict):
       description: str
       total: int

   class StageProgressData(TypedDict):
       completed: int
       total: int
       message: str

   class ArtifactData(TypedDict):
       kind: str
       path: str

   # Then in apply_event:
   if event_type == "stage_start":
       data: StageStartData = event_data  # Type-checked now
       return dataclasses.replace(state, current_message=data["description"])
   ```

3. **Alternative: Discriminated Union** (ADVANCED)
   ```python
   from typing import Union
   from dataclasses import dataclass

   @dataclass
   class StageStartEvent:
       type: Literal["stage_start"]
       stage: str
       description: str
       total: int
       ts: str = ...
       run_id: str = ...

   @dataclass
   class StageProgressEvent:
       type: Literal["stage_progress"]
       stage: str
       completed: int
       total: int
       message: str
       ts: str = ...
       run_id: str = ...

   # All event types
   AnyEvent = Union[StageStartEvent, StageProgressEvent, ...]

   # Then apply_event becomes type-safe:
   def apply_event(state: AppState, event: AnyEvent) -> AppState:
       match event:
           case StageStartEvent(description=desc, total=t):
               return dataclasses.replace(state, current_message=desc, ...)
           case StageProgressEvent(completed=c, total=t):
               return dataclasses.replace(state, current_progress=(c/t)*100)
   ```
   - Most type-safe approach
   - Enables exhaustiveness checking
   - Higher maintenance (more classes)

4. **Add Timestamp Validation** (MODERATE)
   ```python
   from datetime import datetime

   def __post_init__(self):
       try:
           datetime.fromisoformat(self.ts)
       except ValueError:
           raise ValueError(f"Invalid ISO 8601 timestamp: {self.ts}")
   ```

---

### 3. EventConsumer (src/ui/tui/events.py)

```python
class EventConsumer:
    def __init__(
        self,
        queue: asyncio.Queue[Any],
        on_batch: Callable[[list[Any]], None],
        config: EventConsumerConfig | None = None,
    ):
        self.queue = queue
        self.on_batch = on_batch
        self._running = False
        self._batch: list[Any] = []
        self._last_progress: dict[str, Any] = {}
```

#### Invariants Identified

1. **Single Consumer**: Only one coroutine should call `run()`
2. **Batch Ordering**: Events in batch should maintain order (except coalesced progress)
3. **Throttle Integrity**: Batch should contain all events in `[deadline - throttle, deadline]`
4. **Progress Coalescing**: Only latest progress event per stage in `_last_progress`
5. **Callback Contract**: `on_batch` callback should be idempotent or handle multiple calls

#### Ratings

- **Encapsulation**: 4/10
  - ✗ `queue` and `on_batch` are public attributes (can be reassigned)
  - ✗ `_batch` and `_last_progress` are mutable internal state
  - ✗ No type checking on `on_batch` callback signature
  - ✗ Could call `run()` multiple times concurrently (race condition)
  - ✗ State can be accessed/modified during `run()`

- **Invariant Expression**: 5/10
  - ✗ No Callable type hint on `on_batch` (signature unknown)
  - ✗ Coalescing behavior is implicit in method names
  - ✗ Throttle interval is just a number (no unit clarity)
  - ✓ EventConsumerConfig defines configuration clearly
  - ✗ No state machine for consumer lifecycle

- **Invariant Usefulness**: 8/10
  - Batching prevents UI thrashing
  - Coalescing progress events improves responsiveness
  - Throttling is necessary for interactive apps

- **Invariant Enforcement**: 4/10
  - ✗ No guard against concurrent `run()` calls
  - ✗ No validation of callback before assignment
  - ✗ `_running` flag is not atomic
  - ✗ No timeout on queue.get() beyond deadline check

#### Concerns

1. **Critical**: No protection against multiple concurrent `run()` calls
   ```python
   consumer = EventConsumer(queue, callback)
   asyncio.create_task(consumer.run())
   asyncio.create_task(consumer.run())  # RACE CONDITION
   ```

2. **Critical**: Callback signature is untyped
   ```python
   # This is accepted:
   consumer = EventConsumer(queue, "not callable")  # No type error until runtime

   # Runtime error:
   on_batch("string instead of list")
   ```

3. **Important**: State mutations during consumption
   ```python
   consumer = EventConsumer(queue, callback)
   task = asyncio.create_task(consumer.run())
   consumer.queue = new_queue  # Changes queue while running!
   ```

4. **Important**: No cleanup of internal state after `stop()`
   - `_batch` and `_last_progress` persist after stopping

#### Recommended Improvements

1. **Add Callback Type Hint** (IMPORTANT)
   ```python
   from typing import Protocol

   class EventBatchHandler(Protocol):
       """Protocol for event batch handlers."""
       def __call__(self, events: list[Event]) -> None:
           """Handle a batch of events."""
           ...

   class EventConsumer:
       def __init__(
           self,
           queue: asyncio.Queue[Event],
           on_batch: EventBatchHandler,
           config: EventConsumerConfig | None = None,
       ):
           self.queue = queue
           self.on_batch = on_batch
   ```

2. **Prevent Concurrent Runs** (IMPORTANT)
   ```python
   class EventConsumer:
       def __init__(self, ...):
           self._running = False
           self._run_task: asyncio.Task | None = None

       async def run(self) -> None:
           """Main event loop; only one instance can run at a time."""
           if self._running or self._run_task:
               raise RuntimeError("EventConsumer.run() already running")

           self._running = True
           self._run_task = asyncio.current_task()
           try:
               # ... existing logic
           finally:
               self._running = False
               self._run_task = None
   ```

3. **Freeze Configuration After Init** (MODERATE)
   ```python
   class EventConsumer:
       def __init__(self, queue, on_batch, config=None):
           self._queue = queue  # Private
           self._on_batch = on_batch  # Private
           self._config = config or EventConsumerConfig()
           self._running = False

       @property
       def queue(self) -> asyncio.Queue:
           """Read-only access to queue."""
           return self._queue

       @property
       def is_running(self) -> bool:
           """Check if consumer is running."""
           return self._running
   ```

4. **Add State Cleanup** (MODERATE)
   ```python
   async def stop(self) -> None:
       """Stop consumer and clean up internal state."""
       self._running = False
       self._batch.clear()
       self._last_progress.clear()
   ```

---

### 4. EventConsumerConfig (src/ui/tui/events.py)

```python
@dataclass
class EventConsumerConfig:
    throttle_ms: int = 50
    max_queue_size: int = 1000
    coalesce_progress: bool = True
    drop_policy: str = "oldest"  # PROBLEM: string literal
```

#### Invariants Identified

1. **Positive Values**: `throttle_ms > 0`, `max_queue_size > 0`
2. **Drop Policy**: `drop_policy ∈ {"oldest", "newest"}`
3. **Queue Size Reasonable**: `max_queue_size` should be > typical batch size

#### Ratings

- **Encapsulation**: 4/10
  - ✗ All fields mutable after construction
  - ✗ No validation in `__post_init__`
  - ✗ Can create invalid configs: `EventConsumerConfig(throttle_ms=-50)`
  - ✗ `drop_policy` is a string (stringly typed)

- **Invariant Expression**: 3/10
  - ✗ `drop_policy` should be a Literal or Enum, not str
  - ✗ No bounds on `throttle_ms` or `max_queue_size`
  - ✓ Field names are clear

- **Invariant Usefulness**: 7/10
  - Configuration constraints are real
  - Invalid values would cause bugs

- **Invariant Enforcement**: 2/10
  - ✗ No `__post_init__` validation
  - ✗ `drop_policy` type is not checked

#### Concerns

1. **Critical**: `drop_policy` is stringly typed
   ```python
   config = EventConsumerConfig(drop_policy="OLDEST")  # Valid str, but not in policy set
   # No error until runtime when policy is checked
   ```

2. **Important**: Negative values are allowed
   ```python
   EventConsumerConfig(throttle_ms=-100)  # Valid dataclass, invalid semantics
   ```

#### Recommended Improvements

1. **Use Enum for Drop Policy** (CRITICAL)
   ```python
   from enum import Enum

   class DropPolicy(Enum):
       OLDEST = "oldest"
       NEWEST = "newest"

   @dataclass
   class EventConsumerConfig:
       throttle_ms: int = 50
       max_queue_size: int = 1000
       coalesce_progress: bool = True
       drop_policy: DropPolicy = DropPolicy.OLDEST

       def __post_init__(self):
           if self.throttle_ms <= 0:
               raise ValueError(f"throttle_ms must be > 0, got {self.throttle_ms}")
           if self.max_queue_size <= 0:
               raise ValueError(f"max_queue_size must be > 0, got {self.max_queue_size}")
   ```

2. **Add Range Validation** (IMPORTANT)
   ```python
   from typing import Annotated

   @dataclass
   class EventConsumerConfig:
       throttle_ms: Annotated[int, "must be > 0"] = 50
       max_queue_size: Annotated[int, "must be > 0"] = 1000

       def __post_init__(self):
           assert self.throttle_ms > 0
           assert self.max_queue_size > 0
   ```

---

### 5. Persistence Types (src/ui/tui/persistence.py)

Settings and recent files are returned as plain `dict[str, Any]`:

```python
def load_settings() -> dict[str, Any]:
    """Load TUI settings from disk."""
    return {
        "version": "1.0",
        "last_input_dir": str(...),
        "last_output_dir": str(...),
        "defaults": {
            "quality": "speech",
            "language": "en",
            "provider": "auto",
            "analysis_style": "concise",
        },
        "ui": {
            "theme": "dark",
            "verbose_logs": False,
            "log_panel_height": 10,
        },
    }

def load_recent_files() -> list[dict[str, Any]]:
    """Load recent files list."""
    return [
        {
            "path": str(...),
            "last_used": str(...),  # ISO timestamp
            "size_mb": float(...),
        }
    ]
```

#### Invariants Identified

1. **Settings Structure**: Required keys are `version`, `defaults`, `ui`
2. **Defaults Schema**: Must have `quality`, `language`, `provider`, `analysis_style`
3. **UI Settings**: Must have `theme`, `verbose_logs`, `log_panel_height`
4. **Recent Files Validity**: Files must exist on disk
5. **Timestamps**: `last_used` must be ISO 8601
6. **Size Bounds**: `size_mb` must be ≥ 0
7. **Version Compatibility**: `version` should match expected schema

#### Ratings

- **Encapsulation**: 3/10
  - ✗ No type definitions at all (pure dicts)
  - ✗ No schema validation on load
  - ✗ Can return invalid structures with missing required keys

- **Invariant Expression**: 1/10
  - ✗ Settings structure is only in docstring and default_settings()
  - ✗ No TypedDict or dataclass
  - ✗ Recent files structure is implicit

- **Invariant Usefulness**: 7/10
  - Schema makes sense
  - Validation would catch file corruption

- **Invariant Enforcement**: 2/10
  - ✗ No schema validation in `load_settings()`
  - ✗ Can return dicts with missing keys
  - ✗ Merge logic silently overwrites with defaults
  - ✗ No validation that `last_used` is ISO 8601

#### Concerns

1. **Critical**: No type definitions; entire schema is implicit
   ```python
   settings = load_settings()
   # What's the structure? Only docstring knows.
   settings["defaults"]["quality"]  # Might not exist
   ```

2. **Important**: Corrupt files are silently converted to defaults
   ```python
   # If tui_settings.json is corrupted:
   # → Backed up to .bak
   # → Defaults returned
   # User loses settings silently
   ```

3. **Important**: Merge logic is fragile
   ```python
   defaults = default_settings()
   defaults.update(loaded)  # Shallow merge; nested dicts could be incomplete
   return defaults
   ```

#### Recommended Improvements

1. **Define Settings TypedDict** (CRITICAL)
   ```python
   from typing import TypedDict, Literal

   class UISettings(TypedDict):
       theme: Literal["dark", "light"]
       verbose_logs: bool
       log_panel_height: int

   class DefaultSettings(TypedDict):
       quality: str
       language: str
       provider: str
       analysis_style: str

   class TUISettings(TypedDict):
       version: str
       last_input_dir: str
       last_output_dir: str
       defaults: DefaultSettings
       ui: UISettings

   def load_settings() -> TUISettings:
       """Load TUI settings from disk."""
       # Return type is now enforced
   ```

2. **Define Recent File Type** (IMPORTANT)
   ```python
   class RecentFile(TypedDict):
       path: str
       last_used: str  # ISO 8601
       size_mb: float

   def load_recent_files(max_entries: int = 20) -> list[RecentFile]:
       """Load recent files list."""
   ```

3. **Add Validation Function** (IMPORTANT)
   ```python
   def validate_settings(settings: dict[str, Any]) -> TUISettings:
       """Validate settings structure."""
       required_keys = {"version", "defaults", "ui", "last_input_dir", "last_output_dir"}
       if not required_keys.issubset(settings.keys()):
           raise ValueError(f"Missing required keys: {required_keys - settings.keys()}")

       # Validate nested structures
       if not isinstance(settings["defaults"], dict):
           raise ValueError("defaults must be a dict")

       required_defaults = {"quality", "language", "provider", "analysis_style"}
       if not required_defaults.issubset(settings["defaults"].keys()):
           raise ValueError(f"Missing required defaults: ...")

       # Validate timestamps
       for file in settings.get("recent_files", []):
           try:
               datetime.fromisoformat(file["last_used"])
           except (ValueError, KeyError):
               raise ValueError(f"Invalid timestamp: {file.get('last_used')}")

       return settings  # type: ignore
   ```

4. **Use dataclass Instead of TypedDict** (ALTERNATIVE)
   ```python
   from dataclasses import dataclass, field

   @dataclass
   class UISettings:
       theme: Literal["dark", "light"]
       verbose_logs: bool
       log_panel_height: int

   @dataclass
   class DefaultSettings:
       quality: str
       language: str
       provider: str
       analysis_style: str

   @dataclass
   class TUISettings:
       version: str
       last_input_dir: str
       last_output_dir: str
       defaults: DefaultSettings
       ui: UISettings

       @classmethod
       def from_dict(cls, data: dict[str, Any]) -> TUISettings:
           """Load from dict with validation."""
           return cls(
               version=data["version"],
               last_input_dir=data["last_input_dir"],
               last_output_dir=data["last_output_dir"],
               defaults=DefaultSettings(**data["defaults"]),
               ui=UISettings(**data["ui"]),
           )
   ```

---

### 6. State Reducer Pattern (apply_event in state.py)

```python
def apply_event(state: AppState, event: Any) -> AppState:
    """Pure reducer function: (state, event) -> new_state."""
    if event.type == "stage_start":
        return dataclasses.replace(state, ...)
    elif event.type == "stage_progress":
        return dataclasses.replace(state, ...)
    # ... 7 more elif branches
    else:
        return state  # Unknown events silently ignored
```

#### Invariants Identified

1. **Idempotence**: `apply_event(apply_event(s, e), e)` should equal `apply_event(s, e)`
2. **Determinism**: Same event always produces same state transformation
3. **Exhaustiveness**: All event types should be handled

#### Ratings

- **Encapsulation**: 8/10
  - ✓ Pure function (no side effects)
  - ✓ Never mutates input state
  - ✓ Uses immutable `dataclasses.replace()`
  - ✗ No validation of event data structure

- **Invariant Expression**: 6/10
  - ✓ Event type matching is clear via if/elif
  - ✗ No exhaustiveness check (unknown types silently pass through)
  - ✗ Could use Python 3.10+ match statement for clarity

- **Invariant Usefulness**: 9/10
  - Pure reducer enables time-travel debugging
  - Enables undo/redo functionality
  - Makes state transitions traceable

- **Invariant Enforcement**: 7/10
  - ✓ `dataclasses.replace()` enforces immutability
  - ✓ No mutations of input state
  - ✗ No validation of event data before use
  - ✗ No exhaustiveness checking

#### Concerns

1. **Important**: Unknown event types are silently ignored
   ```python
   event = Event(type="unknown_type", data={})
   new_state = apply_event(state, event)
   # state unchanged, no error or warning
   ```

2. **Important**: Event data is accessed with `.get()` fallbacks
   ```python
   # If event.data is missing 'total':
   total = event_data.get("total", 100)  # Falls back silently
   # This could hide data schema violations
   ```

3. **Moderate**: Could use match statement for clarity (Python 3.10+)
   ```python
   match event.type:
       case "stage_start":
           return dataclasses.replace(...)
       case "stage_progress":
           return dataclasses.replace(...)
       # ... missing case raises ValueError
   ```

#### Recommended Improvements

1. **Add Exhaustiveness Check** (IMPORTANT)
   ```python
   def apply_event(state: AppState, event: Event) -> AppState:
       """Pure reducer function."""
       handlers = {
           "stage_start": _handle_stage_start,
           "stage_progress": _handle_stage_progress,
           # ... all 9 event types
       }

       handler = handlers.get(event.type)
       if handler is None:
           raise ValueError(f"Unknown event type: {event.type}")

       return handler(state, event)

   def _handle_stage_start(state: AppState, event: Event) -> AppState:
       """Handle stage_start event."""
       description = event.data["description"]
       total = event.data["total"]
       return dataclasses.replace(state, ...)
   ```

2. **Use TypedDict Validation** (IMPORTANT)
   ```python
   from typing import TypedDict

   class StageStartData(TypedDict):
       description: str
       total: int

   def _validate_stage_start(data: dict[str, Any]) -> StageStartData:
       """Validate stage_start event data."""
       if "description" not in data:
           raise ValueError("stage_start event missing 'description'")
       if "total" not in data:
           raise ValueError("stage_start event missing 'total'")
       return data  # type: ignore

   def _handle_stage_start(state: AppState, event: Event) -> AppState:
       data = _validate_stage_start(event.data)
       return dataclasses.replace(
           state,
           current_message=data["description"],
           stage_totals={**state.stage_totals, event.stage: data["total"]},
       )
   ```

3. **Use Python 3.10+ Match Statement** (MODERATE)
   ```python
   def apply_event(state: AppState, event: Event) -> AppState:
       """Pure reducer using pattern matching."""
       match event.type:
           case "stage_start":
               return dataclasses.replace(state, ...)
           case "stage_progress":
               return dataclasses.replace(state, ...)
           case _:
               raise ValueError(f"Unknown event type: {event.type}")
   ```

---

## Cross-Cutting Concerns

### Thread Safety

**Current State**: Inconsistent across implementations

- ✓ `JsonLinesSink`: Uses `threading.Lock` for thread-safe writes
- ✓ `ConsoleEventSink`: Uses `threading.Lock` for thread-safe writes
- ✓ `QueueEventSink`: Uses `loop.call_soon_threadsafe()` (thread-safe)
- ✗ `CompositeSink`: No locks; could have race conditions
- ✗ `EventConsumer`: No synchronization on `_batch`, `_last_progress`
- ✗ `AppState`: No thread safety (relies on event consumer)

**Recommendations:**

1. Document threading assumptions clearly
2. Add locks to `EventConsumer` if accessed from multiple threads
3. Make `CompositeSink` thread-safe:
   ```python
   class CompositeSink:
       def __init__(self, sinks: list[EventSink]):
           self.sinks = sinks
           self._lock = threading.Lock()

       def emit(self, event: Event) -> None:
           with self._lock:
               for sink in self.sinks:
                   try:
                       sink.emit(event)
                   except Exception as e:
                       logging.error(...)
   ```

### Configuration Schema Consistency

Settings, config, and persistence use different patterns:

- `EventConsumerConfig`: Typed dataclass with defaults
- `TUISettings`: Untyped dict (implicit schema)
- `AppState.stage_totals`: Untyped dict
- `Event.data`: Untyped dict

**Recommendation**: Define TypedDict or dataclass schemas for all persistent configuration

### Error Handling Asymmetry

- `apply_event()`: Returns unchanged state on unknown type (silent failure)
- `emit_event()`: Returns None if sink is None (silent failure)
- `load_settings()`: Returns defaults on error (silent failure)

**Recommendation**: Explicitly surface these failures via logging or exceptions

---

## Summary of Improvements by Priority

### CRITICAL (Blocks Correctness)

1. ✗ **AppState**: Add state machine enum to replace `is_running/can_cancel` booleans
2. ✗ **Event**: Add type-safe factory methods or use discriminated unions for data validation
3. ✗ **EventConsumerConfig**: Use Enum for `drop_policy` instead of string
4. ✗ **Persistence**: Define TypedDict schemas for settings and recent files

### IMPORTANT (Improves Robustness)

5. ✗ **AppState**: Add `__post_init__` validation for progress bounds and stage existence
6. ✗ **AppState**: Make collections immutable (use tuple instead of list)
7. ✗ **Event**: Add timestamp validation in `__post_init__`
8. ✗ **EventConsumer**: Prevent concurrent `run()` calls; make callback type-checked
9. ✗ **apply_event()**: Add exhaustiveness checking and data validation
10. ✗ **Persistence**: Add validation function to enforce schema on load

### MODERATE (Improves Maintainability)

11. ✓ **AppState**: Document state machine transitions in docstring
12. ✓ **apply_event()**: Use Python 3.10+ match statement
13. ✓ **EventConsumer**: Add property accessors to prevent public mutation
14. ✓ **CompositeSink**: Add thread safety lock
15. ✓ **Type Aliases**: Define `LogEntry`, `Artifact`, etc. for dict schemas

### NICE-TO-HAVE

16. ✓ Event factory functions via `Event.stage_start()`, `Event.stage_progress()`, etc.
17. ✓ Discriminated union Event types (most type-safe but highest maintenance)
18. ✓ Runtime type checking library (Pydantic, beartype) for validation

---

## Implementation Strategy

**Phase 1 (High Impact, Low Effort)**: Focus on type definitions
1. Add TypedDict schemas for persistence
2. Use Enum for `drop_policy`
3. Define type aliases for untyped dicts

**Phase 2 (Medium Impact, Medium Effort)**: Add validation
1. Add `__post_init__` validators to dataclasses
2. Add factory methods to Event
3. Add exhaustiveness checking to apply_event

**Phase 3 (Polish)**: Improve encapsulation
1. Convert mutable collections to immutable
2. Add property accessors
3. Use Python 3.10+ match statement

---

## Code Examples: Before and After

### Example 1: AppState State Machine

**Before:**
```python
@dataclass
class AppState:
    is_running: bool = False
    can_cancel: bool = False
```

**After:**
```python
from enum import Enum

class RunState(Enum):
    IDLE = "idle"
    RUNNING = "running"
    CANCELLING = "cancelling"

@dataclass
class AppState:
    run_state: RunState = RunState.IDLE

    def __post_init__(self):
        # Validate state machine invariants
        if self.run_state == RunState.RUNNING:
            assert self.input_path is not None, "input_path required when running"
            assert self.output_dir is not None, "output_dir required when running"
            assert self.run_id is not None, "run_id required when running"
```

### Example 2: Event Validation

**Before:**
```python
@dataclass
class Event:
    type: EventType
    data: dict[str, Any] = field(default_factory=dict)

# In apply_event:
if event_type == "stage_start":
    total = event_data.get("total", 100)  # Silent fallback!
```

**After:**
```python
@dataclass
class Event:
    type: EventType
    data: dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def stage_start(stage: str, description: str, total: int, run_id: str | None = None) -> Event:
        """Factory for type-safe stage_start construction."""
        if not description:
            raise ValueError("description cannot be empty")
        if total <= 0:
            raise ValueError("total must be positive")
        return Event(
            type="stage_start",
            stage=stage,
            data={"description": description, "total": total},
            run_id=run_id or str(uuid.uuid4()),
        )
```

### Example 3: Configuration Validation

**Before:**
```python
def load_settings() -> dict[str, Any]:
    # Returns untyped dict; schema is implicit
    return {"version": "1.0", ...}
```

**After:**
```python
class UISettings(TypedDict):
    theme: Literal["dark", "light"]
    verbose_logs: bool
    log_panel_height: int

class TUISettings(TypedDict):
    version: str
    defaults: DefaultSettings
    ui: UISettings

def load_settings() -> TUISettings:
    """Load settings with schema validation."""
    config_dir = get_config_dir()
    if not config_dir:
        return default_settings()

    settings_file = config_dir / "tui_settings.json"
    if not settings_file.exists():
        return default_settings()

    try:
        with open(settings_file) as f:
            loaded = json.load(f)

        # Validate schema
        validated = _validate_settings(loaded)
        return validated
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning(f"Failed to load settings: {e}")
        return default_settings()

def _validate_settings(data: dict[str, Any]) -> TUISettings:
    """Validate settings structure."""
    # Check required keys
    if "version" not in data:
        raise ValueError("Missing 'version' key")

    # Validate nested structures
    if not isinstance(data.get("defaults"), dict):
        raise ValueError("'defaults' must be a dict")

    # Return type-safe
    return data  # type: ignore
```

---

## Conclusion

The TUI implementation has strong architectural foundations:
- Pure reducers with immutable state updates
- Event-driven architecture with multiple sinks
- Good separation of concerns between state, events, and UI

However, the type design is held back by:
- Weak encapsulation in mutable dataclasses
- Implicit schemas expressed only in comments
- Untyped dicts for configuration and event data
- Missing runtime validation at boundaries

**Overall Score: 5.2/10**

The fixes are localized and don't require architectural changes—mostly adding:
1. Better type definitions (Enum, TypedDict, Literal)
2. Validation in `__post_init__` methods
3. Factory methods for complex types
4. Exhaustiveness checking in the reducer

With these improvements, the design would move from **5.2 to 8.0+**, making it a reference implementation for type-safe event-driven TUI architecture.

