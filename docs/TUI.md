# Terminal User Interface (TUI) Documentation

## Overview

The Audio Extraction Analysis TUI provides a modern, interactive terminal interface for processing audio and video files using OpenTUI - a TypeScript-based TUI built with React.

## Prerequisites

The TUI requires:

- **Bun** for running the TypeScript frontend
- Frontend dependencies installed in `frontend/` directory
- A project checkout containing the `frontend/` folder
- Distribution policy: `source-checkout-only`

```bash
# Install Bun
curl -fsSL https://bun.sh/install | bash

# Install frontend dependencies
cd frontend && bun install --frozen-lockfile

# Launch TUI
audio-extraction-analysis tui
```

## Quick Start

```bash
# Launch interactive TUI
audio-extraction-analysis tui
```

## Support Contract

- Runtime: Bun is required for this repository's TUI path.
- Distribution: `source-checkout-only`.
- Packaging boundary: Python wheels include `src` only and do not bundle `frontend/` assets.
- Required layout: run from a checkout that contains `frontend/` and installed frontend dependencies.
- CI smoke lane: `bun install --frozen-lockfile`, `bun run typecheck`, and `bun run test` when tests exist.

## Features

### Live Progress Monitoring
- Real-time progress bars for each processing stage
- ETA calculation based on actual work rate
- Stage tracking for extraction, transcription, and analysis
- Color-coded status indicators

### File Browser
- Directory tree navigation
- Recent files list for quick access
- File filtering with pattern matching
- File preview with metadata

### Configuration Management
- Visual settings editor
- Persistent configuration across sessions
- Provider selection with availability status
- Quality presets and language selection

### Run Screen
- Progress board with visual cards
- Scrollable, filterable log panel
- Cancel support with graceful cleanup
- Auto-open results on completion

## Navigation Flow

```
Welcome Screen → File Selection → Configuration → Processing → Results
```

## Keyboard Shortcuts

### Global
| Key | Action |
|-----|--------|
| `q` | Quit application |
| `d` | Toggle dark/light mode |
| `?` or `h` | Show help |
| `Escape` | Go back/Cancel |

### File Selection
| Key | Action |
|-----|--------|
| `Enter` | Select file/directory |
| `Space` | Expand/collapse directory |
| `/` or `f` | Focus filter input |
| `Tab` | Switch between panes |

### Processing
| Key | Action |
|-----|--------|
| `c` | Cancel processing |
| `l` | Toggle log panel |
| `o` | Open output (when complete) |

## Configuration Persistence

Settings are saved in platform-specific directories:

| Platform | Location |
|----------|----------|
| macOS | `~/Library/Application Support/audio-extraction-analysis/` |
| Linux | `~/.config/audio-extraction-analysis/` |
| Windows | `%APPDATA%\audio-extraction-analysis\` |

## Frontend Directory Structure

```
frontend/
├── src/
│   ├── app/              # App shell, entry point
│   ├── ipc/              # JSON-RPC client
│   ├── protocol/         # Shared type definitions  
│   ├── state/            # Zustand store, reducer
│   ├── screens/          # Screen components
│   │   ├── Home.tsx      # File/URL selection
│   │   ├── Run.tsx       # Progress display
│   │   ├── Settings.tsx  # API keys, defaults
│   │   ├── Help.tsx      # Keyboard shortcuts
│   │   └── ThemeSelector.tsx
│   └── components/       # Reusable widgets
├── package.json
└── tsconfig.json
```

## Development

```bash
# Run frontend in development mode
cd frontend && bun run dev

# Run TypeScript type checking
cd frontend && bun run typecheck

# Run frontend tests
cd frontend && bun test
```

## Troubleshooting

### TUI Not Starting

```bash
# Check Bun installation
bun --version

# Verify frontend directory exists
ls frontend/package.json

# Check for missing dependencies
cd frontend && bun install --frozen-lockfile
```

### Display Issues

```bash
# Ensure terminal supports colors
echo $TERM  # Should be xterm-256color or similar

# Check terminal size (minimum 80x24)
tput cols
tput lines
```

### Debugging

```bash
# Enable debug logging
DEBUG=true audio-extraction-analysis tui

# Run backend server standalone
python3 -m src.ui.opentui_backend
```

## Comparison with CLI

| Feature | CLI | TUI |
|---------|-----|-----|
| Visual Progress | Text only | Visual bars with ETA |
| Configuration | Command-line flags | Visual editor |
| File Selection | Type path | Browse and select |
| Log Viewing | Stream to terminal | Scrollable, filterable |
| Settings Persistence | Manual | Automatic |
| Provider Health | Not shown | Visual status |
| Scriptability | Excellent | Limited |

---

*Last Updated: January 2026*
