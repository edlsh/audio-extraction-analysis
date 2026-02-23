# Stabilization and Direction Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Re-establish predictable runtime behavior by eliminating accidental test-mode coupling, clarifying TUI runtime support, and aligning docs with actual supported providers.

**Architecture:** Treat provider selection and CLI runtime detection as trust boundaries. Keep test-only behavior explicitly gated behind test-mode checks. Keep user docs as executable truth by removing commands/options that no longer exist.

**Tech Stack:** Python 3.11+, pytest, Ruff, Bun/OpenTUI frontend, Markdown docs.

---

### Task 1: Provider Selection Hardening

**Files:**
- Modify: `src/providers/factory.py`
- Test: `tests/unit/test_provider_meta_logic.py`

**Outcome:** Auto-selection no longer picks test-only providers in normal runtime.

### Task 2: TUI Runtime Hardening

**Files:**
- Modify: `src/cli/commands/tui.py`
- Test: `tests/unit/test_tui_command_runtime.py`

**Outcome:** TUI runtime detection is deterministic and avoids broken Node execution paths for `.tsx`.

### Task 3: Documentation Truth Alignment

**Files:**
- Modify: `README.md`
- Modify: `docs/TROUBLESHOOTING.md`
- Modify: `docs/TUI.md`
- Modify: `docs/PROVIDERS.md`

**Outcome:** Setup and provider docs match current code behavior and supported options.

### Task 4: Verification Baseline

**Commands:**
- `uv run python -m pytest tests/unit/test_provider_meta_logic.py::TestProviderMetaBasedConfiguration::test_test_providers_not_treated_as_configured_in_normal_runtime tests/unit/test_provider_meta_logic.py::TestProviderMetaBasedConfiguration::test_auto_select_without_real_providers_raises tests/unit/test_tui_command_runtime.py -q`
- `uv run ruff check src/providers/factory.py src/cli/commands/tui.py tests/unit/test_provider_meta_logic.py tests/unit/test_tui_command_runtime.py`

**Outcome:** Regression tests and lint checks pass for the hardened paths.

### Task 5: Distribution Strategy Decision

**Files:**
- Evaluate: `pyproject.toml`
- Evaluate: `src/cli/commands/tui.py`

**Outcome:** Selected strategy `source-checkout-only` and enforced it via:
1) explicit runtime policy messaging in `tui` command, and
2) wheel packaging policy tests to detect drift.

### Task 6: Transcription Service Boundary Hardening

**Files:**
- Modify: `src/services/transcription.py`
- Test: `tests/unit/test_transcription_service_runtime_policy.py`

**Outcome:** Transcription runtime behavior no longer depends on ambient test/CI env vars.
Provider selection override/test-mode intent is explicit via service construction, and
audio duration probing routes through `ffmpeg_core` wrappers instead of raw subprocess logic.

### Task 7: Provider Factory Runtime Policy Hardening

**Files:**
- Modify: `src/providers/factory.py`
- Modify: `src/services/transcription.py`
- Test: `tests/unit/test_provider_runtime_policy.py`
- Test: `tests/unit/test_transcription_service_runtime_policy.py`

**Outcome:** Test-only provider aliases are gated exclusively by explicit runtime policy
(`include_test_providers` and `set_test_mode`) rather than ambient environment variables,
and service-to-factory calls propagate runtime intent consistently.
