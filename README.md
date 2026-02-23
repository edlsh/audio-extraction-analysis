# Audio Extraction Analysis

[![Tests](https://github.com/edlsh/audio-extraction-analysis/actions/workflows/test.yml/badge.svg)](https://github.com/edlsh/audio-extraction-analysis/actions/workflows/test.yml)
[![Quality Gates](https://github.com/edlsh/audio-extraction-analysis/actions/workflows/quality-gates.yml/badge.svg)](https://github.com/edlsh/audio-extraction-analysis/actions/workflows/quality-gates.yml)
[![codecov](https://codecov.io/gh/edlsh/audio-extraction-analysis/graph/badge.svg)](https://codecov.io/gh/edlsh/audio-extraction-analysis)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-3776ab.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Transform video and audio recordings into structured, actionable documentation. Supports multiple transcription providers (Deepgram, ElevenLabs, Whisper) with speaker diarization, topic detection, and sentiment analysis.

## Key Features

- **Multi-Provider Support** — Cloud (Deepgram, ElevenLabs) and local (Whisper) transcription
- **URL Ingestion** — Direct processing from YouTube, Vimeo, and other platforms
- **Interactive TUI** — Terminal interface with live progress and health monitoring
- **Intelligent Analysis** — Speaker separation, topic extraction, sentiment analysis
- **Production Ready** — Circuit breaker pattern, health checks, path sanitization

## Installation

### Prerequisites

- Python 3.11+ (3.12 recommended)
- FFmpeg
- API key for cloud providers OR local Whisper installation

### Setup

```bash
# Clone and install
git clone https://github.com/edlsh/audio-extraction-analysis.git
cd audio-extraction-analysis
uv sync

# Install FFmpeg
brew install ffmpeg        # macOS
sudo apt install ffmpeg    # Ubuntu
choco install ffmpeg       # Windows
```

### Optional Extras

```bash
uv add openai-whisper torch            # Local Whisper
uv sync --extra dev                    # Dev tooling (pytest, ruff, mypy)
```

### Terminal UI (OpenTUI)

The TUI requires Bun:
It currently runs from a project checkout that includes `frontend/`.

```bash
# Install Bun
curl -fsSL https://bun.sh/install | bash

# Install frontend dependencies
cd frontend && bun install
```

### Configure Provider

```bash
# Cloud: Set API key
export DEEPGRAM_API_KEY='your-key'     # From console.deepgram.com

# Or local: Whisper works without API keys after installation
```

### Verify

```bash
audio-extraction-analysis --version
```

## Quick Start

```bash
# Process a video file
audio-extraction-analysis process meeting.mp4

# Process from URL
audio-extraction-analysis process --url "https://youtube.com/watch?v=..."

# With custom output
audio-extraction-analysis process video.mp4 --output-dir ./results

# Full analysis (5 files)
audio-extraction-analysis process video.mp4 --analysis-style full
```

## CLI Reference

### Commands

| Command | Description |
|---------|-------------|
| `process` | Full pipeline: extract → transcribe → analyze |
| `extract` | Audio extraction only |
| `transcribe` | Transcription only |
| `export-markdown` | Export transcript as Markdown |
| `tui` | Launch interactive terminal UI |

### Common Options

| Option | Values | Description |
|--------|--------|-------------|
| `--quality` | `speech`, `standard`, `high`, `compressed` | Audio quality preset |
| `--language` | `en`, `es`, `fr`, `de`, `auto` | Transcription language |
| `--provider` | `auto`, `deepgram`, `elevenlabs`, `whisper` | Provider selection |
| `--output-dir` | Path | Output directory |
| `--analysis-style` | `concise`, `full` | Single file vs 5-file output |
| `--verbose` | Flag | Detailed logging |

### Examples

```bash
# High-quality transcription
audio-extraction-analysis process interview.mp4 --quality high --language en

# Extract audio only
audio-extraction-analysis extract presentation.mp4 --quality speech

# Transcribe existing audio
audio-extraction-analysis transcribe recording.mp3 --provider whisper

# Batch processing
for video in *.mp4; do
  audio-extraction-analysis process "$video" --output-dir "./results/${video%.*}"
done
```

## Interactive TUI

Launch a guided interface with real-time progress monitoring:
Current policy: `source-checkout-only` (requires project checkout with `frontend/`).

```bash
audio-extraction-analysis tui
```

### Features

- Live progress bars with ETAs
- Color-coded log streaming
- Provider health monitoring
- File browser with recent files
- Dark/light theme toggle
- Auto-saved configuration

### Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `q` | Quit |
| `d` | Toggle dark mode |
| `?` / `h` | Help |
| `c` | Cancel pipeline (run screen) |
| `o` | Open output folder (when complete) |

## Output Structure

### Concise Mode (default)

```
./output/
├── meeting.mp3                 # Extracted audio
├── meeting_analysis.md         # Single comprehensive analysis
└── meeting_transcript.txt      # Provider-formatted transcript
```

### Full Mode (`--analysis-style full`)

```
./output/
├── meeting.mp3
├── 01_executive_summary.md       # High-level overview
├── 02_chapter_overview.md        # Content breakdown by topic
├── 03_key_topics_and_intents.md  # Technical analysis
├── 04_full_transcript_with_timestamps.md
└── 05_key_insights_and_takeaways.md
```

## Configuration

### Environment Variables

```bash
# Cloud providers
export DEEPGRAM_API_KEY='...'      # console.deepgram.com
export ELEVENLABS_API_KEY='...'    # elevenlabs.io/api

# Local providers (optional)
export WHISPER_MODEL='base'        # tiny, base, small, medium, large
export WHISPER_DEVICE='cuda'       # cuda or cpu

# General
export LOG_LEVEL='INFO'            # DEBUG, INFO, WARNING, ERROR
```

For detailed provider configuration, see [docs/PROVIDERS.md](docs/PROVIDERS.md).

### Supported Languages

`en`, `es`, `fr`, `de`, `it`, `pt`, `auto` (auto-detect)

Whisper supports 100+ languages.

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Input file not found | Use absolute path: `/full/path/to/video.mp4` |
| API key not configured | `export DEEPGRAM_API_KEY='...'` or create `.env` |
| FFmpeg not found | Install: `brew install ffmpeg` (macOS) |
| TUI not working | Install Bun and run `cd frontend && bun install` |

For detailed troubleshooting, see [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md).

## Use Cases

| Scenario | Input | Output | Time |
|----------|-------|--------|------|
| Business meetings | 2-hour recording | Executive summary, action items | ~5-7 min |
| Training sessions | Multi-hour video | Searchable reference, key concepts | ~10-15 min |
| Customer interviews | Interview recordings | Insights, pain points, feature requests | ~3-5 min |
| Podcasts/Webinars | Long-form content | Chapter breakdown, topics, quotes | ~5-10 min |

### Performance

- **Accuracy**: 95%+ (Deepgram Nova 3), 85%+ (Whisper large)
- **Speed**: Real-time (cloud), 0.5-5x real-time (local)
- **Languages**: 10+ (cloud), 100+ (Whisper)

## Documentation

- [Provider Configuration](docs/PROVIDERS.md) — Whisper and cloud provider setup
- [Templates Guide](docs/TEMPLATES.md) — Customize Markdown output
- [Troubleshooting](docs/TROUBLESHOOTING.md) — Common issues and solutions
- [HTML Dashboard](docs/HTML_DASHBOARD.md) — Interactive dashboard rendering
- [Examples](examples/) — Sample outputs and scripts

## Contributing

```bash
# Development setup
git clone https://github.com/edlsh/audio-extraction-analysis.git
cd audio-extraction-analysis
uv sync --extra dev

# Run tests
pytest                                    # Unit tests
./scripts/run_tests.sh --profile all      # Full suite

# Code quality
black src/ tests/ && ruff check src/      # Format + lint
```

## License

This project is provided as-is for professional use.

---

*Transform recordings into structured, actionable documentation.*
