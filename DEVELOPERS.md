# Audio Extraction Analysis - Developer Guide

## Architecture Overview

### Project Structure

```
src/
├── api/                    # API client wrappers
│   ├── __init__.py
│   ├── base_client.py      # Base API client with retry/timeout/error handling
│   ├── deepgram_client.py  # Deepgram SDK wrapper
│   └── elevenlabs_client.py  # ElevenLabs SDK wrapper
├── config/                 # Configuration management
├── exceptions/             # Custom exceptions
├── models/                 # Data models
├── providers/              # Transcription providers
│   ├── base.py           # BaseTranscriptionProvider class
│   ├── deepgram.py       # Deepgram provider
│   ├── elevenlabs.py    # ElevenLabs provider
│   ├── whisper.py        # Whisper local provider
│   ├── logging.py        # Provider logging helpers
│   ├── factory.py        # Provider factory
│   ├── policy.py         # Provider selection policy
│   └── provider_utils.py # Provider utilities
├── services/              # Business logic services
├── tests/                  # Test helpers and fixtures
│   ├── __init__.py
│   ├── helpers.py        # Test utilities (mock responses, test files)
│   └── provider_fixtures.py  # Mock providers, test audio fixtures
├── ui/                    # User interface
├── utils/                  # Utility modules
│   ├── constants.py      # Centralized constants
│   ├── file_validation.py # File validation (backward compatible)
│   ├── logger.py         # Logging utilities
│   ├── retry.py          # Retry logic
│   └── sanitization.py   # Path sanitization
└── validation/             # Validation package
    ├── __init__.py
    ├── validators.py      # Core validator classes
    ├── file_validators.py # Standalone validation functions
    └── rules.py          # Validation rules (size limits, formats)
```

### Key Design Patterns

#### API Client Wrapper Pattern

All external API clients are wrapped through `src/api/` package:

```python
from src.api import DeepgramAPIClient

client = DeepgramAPIClient(api_key="...")
result = await client.transcribe_file(audio_file, options)
```

Benefits:
- Consistent retry logic
- Centralized timeout handling
- Standardized error mapping
- Easier testing with mocks

#### Provider Pattern

All transcription providers inherit from `BaseTranscriptionProvider`:

```python
from src.providers.base import BaseTranscriptionProvider, ProviderMeta

class MyProvider(BaseTranscriptionProvider):
    META = ProviderMeta(
        name="My Provider",
        provider_key="myprovider",
        supported_features=["timestamps", "language_detection"],
        api_key_env="MYPROVIDER_API_KEY",
    )

    @provider_error_handler("myprovider", "uv add myprovider-sdk")
    async def _transcribe_impl(
        self, audio_file_path: Path, language: str = "en"
    ) -> TranscriptionResult | None:
        # Provider-specific logic only
        ...
```

Benefits:
- Consistent error handling via `@provider_error_handler` decorator
- Automatic retry logic via retry_async wrapper
- Standardized logging via `ProviderLogger`
- Factory pattern for provider selection

#### Validation Package Pattern

All validation is centralized in `src/validation/`:

```python
from src.validation import validate_audio_file, FileValidator

# Standalone function
path = validate_audio_file(audio_file, max_file_size=50_000_000)

# Or use class directly
FileValidator.validate_audio_file(audio_file, max_file_size=50_000_000)
```

Benefits:
- Single source of truth for validation rules
- Consistent error messages
- Easy to add new validation rules

## Adding a New Provider

1. Create provider class in `src/providers/myprovider.py`:

```python
from pathlib import Path
from src.providers.base import BaseTranscriptionProvider, ProviderMeta
from src.providers.provider_utils import provider_error_handler

class MyTranscriber(BaseTranscriptionProvider):
    META = ProviderMeta(
        name="My Provider",
        provider_key="myprovider",
        supported_features=["timestamps"],
        api_key_env="MYPROVIDER_API_KEY",
        install_command="uv add myprovider-sdk",
    )

    @provider_error_handler("myprovider", "uv add myprovider-sdk")
    async def _transcribe_impl(
        self, audio_file_path: Path, language: str = "en"
    ) -> TranscriptionResult | None:
        # Your transcription logic here
        pass
```

2. Add provider to `src/providers/__init__.py`:

```python
from .myprovider import MyTranscriber

__all__ = [..., "MyTranscriber"]
```

3. Register provider in factory (if needed):

```python
# src/providers/factory.py

PROVIDER_REGISTRY: dict[str, type[BaseTranscriptionProvider]] = {
    "myprovider": MyTranscriber,
    # ...
}
```

4. Create wrapper in `src/api/myprovider_client.py` (optional):

```python
from src.api.base_client import BaseAPIClient

class MyProviderAPIClient(BaseAPIClient):
    def _create_sdk_client(self) -> object:
        from myprovider import MyClient
        return MyClient(api_key=self.api_key)

    async def transcribe_file(self, audio_file: Path, **kwargs):
        # Implementation
        pass
```

## Testing

### Test Helpers

Use test utilities from `src.tests.helpers`:

```python
from src.tests.helpers import (
    create_mock_transcription_result,
    create_test_audio_file,
    generate_test_data,
)

# Create mock response
result = create_mock_transcription_result(
    text="Hello world",
    duration=10.5,
)

# Create test audio file
audio_file = create_test_audio_file(duration_seconds=5.0)

# Generate test data
test_data = generate_test_data(count=10)
```

### Mock Providers

Use mock providers from `src.tests.provider_fixtures`:

```python
from src.tests.provider_fixtures import (
    MockTranscriptionProvider,
    FailingMockProvider,
    SlowMockProvider,
)

# Normal mock
mock_provider = MockTranscriptionProvider(
    mock_response={"transcript": "Test"}
)

# Failing mock (for error handling tests)
failing_provider = FailingMockProvider(fail_on_nth_call=3)

# Slow mock (for timeout tests)
slow_provider = SlowMockProvider(delay_seconds=5.0)
```

## Logging

Use standardized logging helpers:

```python
from src.utils.logger import (
    log_operation,
    log_performance,
    log_api_call,
)

# Log operation
log_operation(logger, "transcribe", "started", file_path="audio.mp3")

# Log performance
log_performance(logger, "transcribe", duration_seconds=10.5, file_path="audio.mp3")

# Log API call
log_api_call(logger, "deepgram", "transcribe_file", "success")
```

For providers, use `ProviderLogger`:

```python
from src.providers.logging import get_provider_logger

logger = get_provider_logger("deepgram")
logger.log_transcribe_start(audio_file_path)
logger.log_transcribe_complete(audio_file_path, duration_seconds=10.5)
```

## Configuration

All configuration is loaded from environment variables via `Config` class:

```python
from src.config import Config, get_config

config = get_config()

# Access configuration
api_key = config.DEEPGRAM_API_KEY
max_retries = config.max_retries
timeout = config.transcription_timeout_seconds
```

See `src/config/__init__.py` for all available configuration options.

## Constants

Use centralized constants from `src.utils.constants`:

```python
from src.utils.constants import Timeouts, Limits, RetryDefaults, MediaLimits

# Timeout constants
timeout = Timeouts.TRANSCRIPTION_DEFAULT

# File size limits
max_size = Limits.MAX_FILE_SIZE_MB

# Retry defaults
max_attempts = RetryDefaults.MAX_ATTEMPTS

# Media extensions
audio_exts = MediaLimits.ALLOWED_AUDIO_EXTENSIONS
```

## Error Handling

Use mapped exceptions from `src.providers.provider_utils`:

```python
from src.providers.provider_utils import map_provider_error

try:
    result = await provider.transcribe(audio_file)
except Exception as e:
    # Maps common exceptions to ProviderAPIError, ValidationError, etc.
    raise map_provider_error(e, "deepgram", audio_file) from e
```

Or use the `@provider_error_handler` decorator for automatic mapping.

## Code Style Guidelines

- Type hints required for all public functions
- Docstrings for all public classes and functions
- Use centralized constants from `src.utils.constants`
- Use standardized logging from `src.utils.logger`
- Use validation from `src.validation` package
- Follow PEP 8 formatting (enforced by `uv run lint`)

## Running Tests

```bash
# Run all tests
uv run pytest

# Run specific tests
uv run pytest tests/unit/test_provider_factory.py

# Run with coverage
uv run pytest --cov=src
```

## Linting

```bash
# Run linter
uv run lint

# Format code
uv run format
```

## Troubleshooting

### Import Errors

If you get import errors after restructuring:

1. Check `src/__init__.py` for module exports
2. Check `src/providers/__init__.py` for provider exports
3. Verify circular dependencies (avoid importing providers in config)
4. Run `uv sync` to update virtual environment

### Configuration Issues

If configuration values aren't being applied:

1. Check environment variable names match config field names
2. Verify `src/config/__init__.py` has correct field definitions
3. Check `get_config()` is called after environment is set

### Provider Not Found

If factory can't find your provider:

1. Verify provider is registered in `PROVIDER_REGISTRY`
2. Check provider file is in `src/providers/`
3. Ensure provider class inherits from `BaseTranscriptionProvider`
4. Verify `META` attribute has required fields

## Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md) for contribution guidelines.
