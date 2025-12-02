# Verification Commands

## Quick Pre-PR Check

```bash
black src/ tests/ && ruff check src tests && pytest --cov=src && ./scripts/run_static_checks.sh
```

## Individual Commands

| Task | Command |
|------|---------|
| Format | `black src/ tests/` |
| Lint | `ruff check src tests` |
| Test all | `pytest` |
| Test + coverage | `pytest --cov=src --cov-report=term` |
| Static checks | `./scripts/run_static_checks.sh` |
| Build | `python -m build` |
| Submit stack | `gt submit --no-interactive` |

## Test Categories

```bash
pytest -m unit           # Fast unit tests
pytest -m integration    # Requires FFmpeg
pytest -m "not slow"     # Skip slow tests
pytest -m "not network"  # Skip API tests
```

## Coverage Target

Aim for >80%: `pytest --cov=src --cov-fail-under=80`
