# Verification Commands

Use these commands to validate changes before completion.

## Core project checks (required)

```bash
uv sync
uv run pytest
uv run ruff check src
uv run lint-imports
```

## Type checking (recommended; currently has known baseline issues)

```bash
uv run mypy src
```

## Security checks (recommended)

```bash
uv run bandit -r src -ll
```

## Frontend/OpenTUI checks (when frontend or protocol code changes)

```bash
cd frontend
bun install --frozen-lockfile
bun run typecheck
bun run lint
bun test
```

## Quick TUI runtime smoke checks

```bash
# Backend module boot
uv run python -m src.ui.opentui_backend

# Full TUI launch path
uv run python -m src.cli tui
```

## Notes

- `pytest.ini` is the single source of truth for pytest options in this repository.
- If you add new commands to CI workflows, update this document and `docs/TUI.md` (if TUI-related).
