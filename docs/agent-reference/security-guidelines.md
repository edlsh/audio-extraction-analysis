# Security Guidelines

This project processes user-supplied file paths, URLs, and API credentials. Follow these rules for all code changes.

## 1) Path safety is mandatory

- Use `ensure_subpath()` from `src.utils.paths` for user-influenced paths.
- Use `PathSanitizer.validate_path_security()` for explicit path validation where needed.
- Reject path traversal attempts (`..`, escaped roots) instead of silently rewriting risky inputs.

## 2) Secrets handling

- Never commit secrets to git.
- Keep API keys in `.env` / environment variables only.
- Never print raw key values in logs or UI payloads.
- Prefer redacted markers when returning config data (for example: `"__configured__"`).

## 3) Logging and telemetry

- Use structured logging through project logger utilities.
- Avoid logging full remote URLs when they may include sensitive query params; sanitize first.
- Ensure error paths do not leak credentials or private paths unnecessarily.

## 4) URL ingestion and SSRF posture

- Keep host/IP validation in place before downloads.
- Preserve DNS-related guardrails; do not bypass URL validation for convenience.
- Any network behavior change must include tests.

## 5) File writes and permissions

- Use secure/atomic write helpers from `src.utils.secure_file` as appropriate.
- Use secure writes for sensitive settings/secrets.
- Use atomic writes for user-facing outputs when crash-safety matters.

## 6) Subprocess safety

- Use argument arrays (`subprocess.run([...])` / `Popen([...])`), not shell interpolation.
- Never concatenate untrusted strings into shell commands.

## 7) Definition of done (security)

Before merging:
- `uv run ruff check src`
- `uv run pytest`
- `uv run bandit -r src -ll`
- Verify no secrets were introduced in docs, tests, fixtures, or logs.
