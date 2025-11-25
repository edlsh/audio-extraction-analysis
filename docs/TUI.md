# 🖥️ Terminal User Interface (TUI) Documentation

## Overview

The Audio Extraction Analysis TUI provides a modern, interactive terminal interface for processing audio and video files. Built with [Textual](https://textual.textualize.io/), it offers real-time progress monitoring, visual configuration management, and an intuitive file browser.

## Installation

### Requirements
- Python 3.8+
- Terminal with 256-color support
- Minimum terminal size: 80x24 characters

### Install TUI Dependencies
```bash
# Install with TUI support
uv sync --extra tui

# Or install Textual separately
uv add "textual>=0.47.0" --extra tui

# Verify installation
audio-extraction-analysis tui --help
```

## Quick Start

### Basic Launch
```bash
# Launch interactive TUI
audio-extraction-analysis tui

# Pre-populate input file
audio-extraction-analysis tui --input video.mp4

# Pre-set output directory
audio-extraction-analysis tui --output-dir ./results

# Both input and output
audio-extraction-analysis tui -i video.mp4 -o ./output
```

## Features

### 📊 Live Progress Monitoring
- **Real-time Progress Bars**: Visual indicators for each processing stage
- **ETA Calculation**: Smart time estimates based on actual work rate
- **Stage Tracking**: Separate cards for extraction, transcription, and analysis
- **Color-coded Status**: Green (success), Yellow (running), Red (error)

### 📁 Advanced File Browser
- **Directory Tree Navigation**: Explore filesystem hierarchically
- **Recent Files List**: Quick access to previously processed files
- **Smart Filtering**: Real-time file search with pattern matching
- **File Preview**: Shows file size, modification date, and type
- **Keyboard Navigation**: Arrow keys, Enter to select, Tab to switch panes

### ⚙️ Configuration Management
- **Visual Settings Editor**: Intuitive interface for all options
- **Persistent Configuration**: Settings saved across sessions
- **Provider Selection**: Choose from available transcription providers
- **Quality Presets**: Quick selection of audio extraction quality
- **Language Support**: Select transcription language
- **Output Options**: Configure analysis style and export formats

### 📝 Run Screen Features
- **Progress Board**: Visual cards showing stage progress
- **Log Panel**: Scrollable, searchable, color-coded logs
- **Log Filtering**: Show All/Info/Warning/Error levels
- **Cancel Support**: Graceful pipeline cancellation
- **Auto-open Results**: Automatically opens output folder on completion
- **Artifact Display**: Shows generated files with sizes

### 🎨 Themes & Customization
- **Dark/Light Mode**: Toggle with 'd' key
- **Color Themes**: Syntax highlighting for logs
- **Responsive Layout**: Adapts to terminal size
- **Customizable Shortcuts**: Configurable keybindings

## Navigation Flow

```mermaid
graph LR
    A[Welcome Screen] --> B[File Selection]
    B --> C[Configuration]
    C --> D[Processing]
    D --> E[Results]
    E --> B
```

### Screen Descriptions

#### Welcome Screen
- Application branding and version
- Quick start options
- Keyboard shortcut hints
- Provider health status

#### Home Screen (File Selection)
- Split-pane layout: File tree | Recent files
- Directory navigation with expansion/collapse
- File filtering with `/` or `f` key
- Recent files with timestamps
- Validation of selected file

#### Configuration Screen
- Provider selection with availability status
- Audio quality presets (speech/standard/high/compressed)
- Language selection dropdown
- Analysis style (concise/full)
- Export options (Markdown, HTML dashboard)
- Output directory selection
- Settings validation before run

#### Run Screen (Processing)
- Progress cards for each stage:
  - **Extract**: Audio extraction from video
  - **Transcribe**: Speech-to-text conversion
  - **Analyze**: Content analysis and structuring
  - **Save**: Writing output files
- Live log panel with:
  - Color-coded messages by level
  - Timestamp for each entry
  - Searchable content
  - Pause/resume scrolling
- Cancel button (responsive, with confirmation)
- ETA display with smart calculation

#### Results Screen
- Generated files table with sizes
- Processing metrics (duration, tokens, etc.)
- Quick actions:
  - Open output directory
  - View HTML dashboard
  - Copy file paths
- Return to file selection

## Keyboard Shortcuts

### Global Shortcuts
| Key | Action | Available In |
|-----|--------|--------------|
| `q` | Quit application | All screens |
| `Q` | Force quit (no confirmation) | All screens |
| `d` | Toggle dark/light mode | All screens |
| `?` or `h` | Show help overlay | All screens |
| `F1` | Show context help | All screens |
| `Escape` | Go back/Cancel | All screens |

### Home Screen
| Key | Action |
|-----|--------|
| `Enter` | Select file/directory |
| `Space` | Expand/collapse directory |
| `/` or `f` | Focus filter input |
| `Tab` | Switch between panes |
| `r` | Refresh file list |
| `↑↓` | Navigate items |
| `Page Up/Down` | Jump navigation |
| `Home/End` | Go to first/last item |

### Configuration Screen
| Key | Action |
|-----|--------|
| `s` | Start processing |
| `r` | Reset to defaults |
| `Tab` | Navigate fields |
| `Space` | Toggle checkbox |
| `Enter` | Edit field |
| `↑↓` | Select from dropdown |

### Run Screen
| Key | Action |
|-----|--------|
| `c` | Cancel processing |
| `l` | Toggle log panel |
| `v` | Toggle verbose logging |
| `p` | Pause/resume log scroll |
| `a` | Show all log levels |
| `i` | Show INFO and above |
| `w` | Show WARNING and above |
| `e` | Show ERROR only |
| `o` | Open output (when complete) |
| `↑↓` | Scroll logs |

### Results Screen
| Key | Action |
|-----|--------|
| `o` | Open output folder |
| `d` | Open HTML dashboard |
| `y` | Copy selected path |
| `Enter` | Open selected file |
| `n` | New processing |
| `r` | Reprocess same file |

## Configuration Persistence

### Storage Locations
The TUI saves configuration across sessions in platform-specific directories:

- **macOS**: `~/Library/Application Support/audio-extraction-analysis/`
- **Linux**: `~/.config/audio-extraction-analysis/`
- **Windows**: `%APPDATA%\audio-extraction-analysis\`

### Saved Settings
```json
{
  "provider": "auto",
  "quality": "speech",
  "language": "en",
  "analysis_style": "concise",
  "output_dir": "./output",
  "export_markdown": true,
  "html_dashboard": false,
  "recent_files": [...],
  "theme": "dark",
  "log_level": "INFO"
}
```

### Reset Configuration
```bash
# Remove saved configuration
rm -rf ~/Library/Application\ Support/audio-extraction-analysis/  # macOS
rm -rf ~/.config/audio-extraction-analysis/  # Linux
```

## Event Integration

The TUI integrates with the event streaming system for real-time updates:

```python
# Internal event flow
Event Stream → Queue → Event Consumer → State Reducer → UI Update
```

### Event Types Handled
- `stage_start`: Initialize progress card
- `stage_progress`: Update progress bar and ETA
- `stage_end`: Mark stage complete, show duration
- `artifact`: Add to results list
- `log`, `warning`, `error`: Display in log panel
- `summary`: Show final metrics
- `cancelled`: Handle cancellation cleanup

## Architecture

### Component Structure
```
src/ui/tui/
├── app.py           # Main Textual application
├── state.py         # Application state management
├── events.py        # Event consumer and batching
├── persistence.py   # Configuration persistence
├── views/
│   ├── home.py     # File selection screen
│   ├── config.py   # Configuration screen
│   └── run.py      # Processing screen
├── widgets/
│   ├── file_tree.py    # File browser widget
│   ├── progress.py     # Progress card widget
│   └── log_panel.py    # Log display widget
├── services/
│   ├── run_service.py    # Pipeline execution
│   ├── health_service.py # Provider health checks
│   └── os_open.py        # Cross-platform file opening
└── styles/
    └── theme.css    # CSS styling

```

### State Management
The TUI uses a Redux-like state pattern:

1. **Single State Object**: All application state in `AppState`
2. **Pure Reducer**: State updates via `apply_event(state, event)`
3. **Immutable Updates**: State is never mutated directly
4. **Event-Driven**: All changes triggered by events

### Threading Model
- **Main Thread**: UI rendering and user input
- **Worker Thread**: Pipeline execution
- **Event Thread**: Event consumption and batching
- **I/O Thread Pool**: File operations and health checks

## Troubleshooting

### Common Issues

#### TUI Not Starting
```bash
# Check Textual installation
python -c "import textual; print(textual.__version__)"

# Reinstall if needed
uv pip install --upgrade textual

# Check terminal capabilities
echo $TERM  # Should be xterm-256color or similar
```

#### Display Issues
```bash
# Set proper terminal type
export TERM=xterm-256color

# Check terminal size
tput cols  # Should be >= 80
tput lines # Should be >= 24

# For Windows Terminal
# Enable "Use legacy console" in properties
```

#### Slow Performance
```bash
# Disable Unicode rendering
export TEXTUAL_NO_UNICODE=1

# Reduce log verbosity
export LOG_LEVEL=WARNING

# Use simpler theme
audio-extraction-analysis tui --theme simple
```

#### Configuration Not Saving
```bash
# Check permissions
ls -la ~/.config/  # Linux
ls -la ~/Library/Application\ Support/  # macOS

# Create directory manually if needed
mkdir -p ~/.config/audio-extraction-analysis
```

### Debug Mode
```bash
# Enable TUI debug mode
export TEXTUAL_DEBUG=1
audio-extraction-analysis tui

# Log TUI events
export TEXTUAL_LOG=tui.log
audio-extraction-analysis tui

# Profile performance
python -m textual diagnose
```

## Advanced Usage

### Custom Themes
Create a custom CSS file:
```css
/* custom_theme.css */
.progress-card {
    background: $panel;
    border: tall $primary;
    padding: 1;
}

.log-panel {
    background: $surface;
    color: $text;
}
```

Load custom theme:
```bash
audio-extraction-analysis tui --theme custom_theme.css
```

### Scripting Integration
```python
# run_with_tui.py
import subprocess
import json

# Launch TUI with pre-configured settings
result = subprocess.run(
    ['audio-extraction-analysis', 'tui', '--input', 'video.mp4', '--output-dir', './output'],
    capture_output=True,
    text=True
)

# Parse results from event stream
if result.returncode == 0:
    # Process completed successfully
    print("Processing complete!")
```

### Remote Access
For SSH/remote sessions:
```bash
# Use screen or tmux for persistent sessions
screen -S audio-tui
audio-extraction-analysis tui

# Detach: Ctrl+A, D
# Reattach: screen -r audio-tui

# For better performance over SSH
export TEXTUAL_ANIMATIONS=none
```

## Testing

### Unit Tests
```bash
# Run TUI-specific tests
pytest tests/unit/test_tui_*.py

# Test individual components
pytest tests/unit/test_tui_state_reducer.py
pytest tests/unit/test_tui_event_consumer.py
pytest tests/unit/test_tui_widgets.py
```

### Integration Tests
```bash
# Full TUI integration test
pytest tests/e2e/test_tui_integration.py

# Manual testing
python tests/manual/test_tui_screens.py
```

### Performance Testing
```bash
# Profile TUI performance
python -m cProfile -o tui_profile.stats src/ui/tui/app.py

# Analyze profile
python -m pstats tui_profile.stats
```

## Best Practices

1. **Terminal Size**: Use at least 120x40 for optimal experience
2. **Color Support**: Ensure 256-color terminal for best visuals
3. **Font**: Use monospace font with good Unicode support
4. **Performance**: Close unnecessary background apps for smooth animations
5. **Sessions**: Use tmux/screen for long-running processes

## Comparison with CLI

| Feature | CLI | TUI |
|---------|-----|-----|
| Visual Progress | Text only | Visual bars with ETA |
| Configuration | Command-line flags | Visual editor |
| File Selection | Type path | Browse and select |
| Log Viewing | Stream to terminal | Scrollable, filterable |
| Settings Persistence | Manual | Automatic |
| Provider Health | Not shown | Visual status |
| Learning Curve | Steeper | Intuitive |
| Scriptability | Excellent | Limited |
| Remote Usage | Excellent | Good with tmux |

## Future Enhancements

### Planned Features
- [ ] Multi-file batch processing
- [ ] Queue management interface
- [ ] Real-time transcript preview
- [ ] Provider cost estimation
- [ ] Processing history with search
- [ ] Export to multiple formats simultaneously
- [ ] Custom keybinding configuration
- [ ] Plugin system for custom widgets
- [ ] Web-based TUI via browser

### Community Requests
- Drag-and-drop file selection (terminal permitting)
- Integration with cloud storage (S3, GCS, Azure)
- Collaborative processing with shared queues
- Mobile-friendly responsive design
- Voice control for accessibility

## Support

For TUI-specific issues:
1. Check this documentation
2. Review [Textual documentation](https://textual.textualize.io/)
3. Enable debug mode and check logs
4. Report issues with terminal info and debug logs

---

*Last Updated: November 2024*
*TUI Version: 1.0.0*
