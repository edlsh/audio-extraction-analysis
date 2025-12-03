# Technical Debt Report

## High Priority
- [ ] **Consolidate Audio Extraction**: Merge logic between `src/services/audio_extraction.py` and `src/services/audio_extraction_async.py`.
    - *Issue*: Both files contain significant duplicated logic for ffmpeg operations.
    - *Recommendation*: Refactor into a shared `ffmpeg_wrapper.py` or `shell_utils.py`.
- [ ] **Type Safety (Pipeline)**: Enable strict type checking for `src/pipeline/simple_pipeline.py`.
    - *Issue*: `pyproject.toml` has `disallow_untyped_defs = false` for this module.
    - *Recommendation*: Add missing type hints and enable strict mode.

## Medium Priority
- [ ] **Type Safety (UI)**: Add type annotations to `src/ui/tui` and remove loose mypy overrides.
    - *Issue*: Extensive mypy overrides disable type checking for TUI components.
- [ ] **Provider Refactoring**: Extract common API error handling logic from providers into `src/providers/base.py`.
    - *Issue*: Similar error handling patterns are repeated in `Deepgram` and `Whisper` providers.

## Low Priority
- [ ] **Dependency Audit**: Review `parakeet` optional dependencies for staleness.
- [ ] **Docstrings**: Improve coverage for CLI and TUI modules.
