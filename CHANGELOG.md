# Changelog

All notable changes to the Audio Extraction Analysis project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0+emergency] - 2024-11-15

### Added
- Full Terminal User Interface (TUI) with Textual
  - Interactive file browser with directory navigation
  - Visual configuration management with persistence
  - Real-time progress monitoring with ETAs
  - Color-coded, filterable log viewing
  - Dark/light theme toggle
  - Provider health status display
  - Automatic output folder opening
- Event streaming system with JSONL output
  - Comprehensive event model (stage_start, stage_progress, stage_end, etc.)
  - Multiple event sink implementations (JsonLines, Queue, Composite)
  - Integration with monitoring tools
  - Support for custom event consumers
- Circuit breaker pattern for provider fault tolerance
- Provider health checking system
- Configuration persistence using platformdirs
- Comprehensive test coverage (100+ tests)
  - Unit tests for all TUI components
  - End-to-end integration tests
  - Event streaming tests
  - Provider tests with mocking

### Changed
- Updated CLI to support `--jsonl` flag for event streaming
- Deprecated `--json-output` flag in favor of `--jsonl`
- Enhanced pipeline with event instrumentation
- Improved error handling with detailed event reporting
- Refactored provider factory with health checking

### Fixed
- Path sanitization security vulnerabilities
- Provider fallback logic
- Memory leaks in long-running processes
- Unicode handling in transcripts

### Documentation
- Added comprehensive TUI documentation (docs/TUI.md)
- Added event streaming guide (docs/EVENT_STREAMING.md)
- Added detailed provider setup guide (docs/PROVIDERS.md)
- Completely rewrote production deployment guide
- Updated README with current features and correct version

## [0.9.0] - 2024-11-01

### Added
- NVIDIA Parakeet provider support for GPU-accelerated transcription
- OpenAI Whisper provider for local, privacy-preserving transcription
- Provider auto-selection based on availability
- Batch processing improvements
- HTML dashboard generation
- Markdown export with multiple templates

### Changed
- Refactored provider architecture for better extensibility
- Improved audio extraction quality presets
- Enhanced analysis output with sentiment analysis

### Fixed
- FFmpeg compatibility issues on Windows
- Large file handling (>2GB)
- Memory optimization for Whisper models

## [0.8.0] - 2024-10-15

### Added
- ElevenLabs provider integration
- Speaker diarization for all providers
- Topic detection and extraction
- Executive summary generation
- Five-file analysis output mode

### Changed
- Migrated from argparse subparsers to unified CLI
- Improved progress reporting
- Enhanced error messages

### Fixed
- Deepgram API timeout issues
- Temporary file cleanup
- Unicode character handling

## [0.7.0] - 2024-09-20

### Added
- Deepgram Nova 3 provider
- Basic transcription pipeline
- Audio extraction from video
- Simple analysis output

### Changed
- Initial architecture design
- Project structure setup

### Fixed
- Initial bug fixes and improvements

## [0.6.0] - 2024-09-01

### Added
- Project initialization
- Basic project structure
- Initial documentation

---

## Migration Guides

### Migrating from 0.9.x to 1.0.0

#### New Features to Enable

1. **Enable TUI**: Install with TUI support
   ```bash
   uv sync --extra tui
   ```

2. **Use Event Streaming**: Add `--jsonl` flag for monitoring
   ```bash
   audio-extraction-analysis process video.mp4 --jsonl
   ```

3. **Launch Interactive Interface**: Use the new TUI command
   ```bash
   audio-extraction-analysis tui
   ```

#### Breaking Changes

- `--json-output` flag deprecated (still works but shows warning)
- Provider health checking may reject previously working configurations

#### Configuration Changes

- TUI settings are now persisted in platform-specific directories
- New environment variables for TUI configuration

### Migrating from 0.8.x to 0.9.x

#### New Providers

1. **Whisper Setup**:
   ```bash
   uv add openai-whisper torch
   export WHISPER_MODEL=base
   ```

2. **Parakeet Setup**:
   ```bash
   uv add "nemo-toolkit[asr]@1.20.0" --extra parakeet
   export PARAKEET_MODEL=stt_en_conformer_ctc_large
   ```

#### API Changes

- Provider selection now uses `--provider auto` by default
- New quality presets for audio extraction

### Migrating from 0.7.x to 0.8.x

#### Multiple Providers

- Add ElevenLabs API key: `export ELEVENLABS_API_KEY=your-key`
- Update scripts to specify provider: `--provider deepgram`

#### Analysis Output

- Default output changed to single analysis file
- Use `--analysis-style full` for five-file output

---

## Versioning Policy

This project follows Semantic Versioning:
- **MAJOR** version for incompatible API changes
- **MINOR** version for backwards-compatible functionality additions  
- **PATCH** version for backwards-compatible bug fixes
- **+suffix** for special releases (e.g., +emergency for hotfixes)

## Release Schedule

- **Major releases**: Annually (January)
- **Minor releases**: Quarterly
- **Patch releases**: As needed for critical fixes
- **Emergency releases**: Within 24 hours for security issues

## Support Policy

- **Current version**: Full support
- **Previous minor**: Security fixes only
- **Older versions**: No support

---

*For more details on each release, see the [GitHub Releases](https://github.com/your-org/audio-extraction-analysis/releases) page.*
