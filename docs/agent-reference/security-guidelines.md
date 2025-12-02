# Security Guidelines

## API Keys & Secrets

- **NEVER** commit API keys, tokens, or credentials
- Use `.env` file or environment variables
- Required vars: `DEEPGRAM_API_KEY`, `ELEVENLABS_API_KEY`

## Path Security

Always validate user-provided paths:

```python
from src.utils.paths import ensure_subpath, sanitize_dirname
```

- `ensure_subpath(base, user_path)` - Prevents directory traversal
- `sanitize_dirname(name)` - Cleans filenames

Reference: `src/utils/paths.py`

## AI-Generated Files

Add to `.git/info/exclude`:

```
*_SUMMARY.md
*_ANALYSIS.md
*_REVIEW.md
*_PLAN.md
IMPLEMENTATION_*.md
```

## Testing Security

Security tests: `tests/security_fix_test.py`
