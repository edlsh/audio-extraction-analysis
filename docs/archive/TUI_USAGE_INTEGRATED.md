# 🖥️ TUI (Terminal User Interface) Usage Guide

## Quick Start

The TUI provides an interactive, visual interface for audio extraction and transcription with live progress monitoring.

### Launch the TUI

```bash
# Basic launch
audio-extraction-analysis tui

# With pre-populated input file
audio-extraction-analysis tui --input video.mp4

# With custom output directory
audio-extraction-analysis tui --output-dir ./results

# Both input and output pre-populated
audio-extraction-analysis tui -i video.mp4 -o ./output
```

## TUI Features

### 📊 Live Progress Monitoring
- Real-time progress bars for each stage (extraction, transcription, analysis)
- ETAs calculated based on actual work rate
- Color-coded status indicators

### 📁 File Browser
- Navigate filesystem with directory tree
- Recent files list for quick access  
- Filter files by name
- Keyboard navigation

### ⚙️ Configuration Screen
- Select audio quality presets (speech, standard, high, compressed)
- Choose transcription provider (auto, deepgram, elevenlabs, whisper, parakeet)
- Set language and analysis style
- Configure output directory
- Settings auto-save for next session

### 📝 Run Screen
- Live progress cards showing extraction, transcription, and analysis stages
- Scrollable, filterable log panel with color coding
- Cancel button to stop pipeline
- Auto-opens output folder on completion

### ⌨️ Keyboard Shortcuts

#### Global
- `q` - Quit application
- `d` - Toggle dark/light mode
- `h` or `?` - Show help screen
- `escape` - Go back/cancel

#### Home Screen
- `enter` - Select file
- `tab` - Switch between file tree and recent files
- `/` or `f` - Focus filter input
- `r` - Refresh recent files
- Arrow keys - Navigate

#### Config Screen
- `s` - Start run
- `r` - Reset to defaults
- `escape` - Back to home

#### Run Screen
- `c` - Cancel pipeline
- `o` - Open output folder (when complete)
- `escape` - Back (if not running)

#### Log Panel (on Run Screen)
- `a` - Show all logs
- `i` - Show INFO and above
- `w` - Show WARNING and above  
- `e` - Show ERROR only

## Navigation Flow

```
Welcome Screen
    ↓ [Start Processing]
Home Screen (File Selection)
    ↓ [Select File]
Config Screen (Settings)
    ↓ [Start Run]
Run Screen (Live Progress)
    ↓ [Complete]
Output Opens Automatically
```

## Requirements

The TUI requires the `textual` library. It should be installed automatically with:

```bash
uv sync
```

If not installed, install it manually:

```bash
uv add textual --extra tui
```

## Troubleshooting

### TUI won't start
- Ensure `textual` is installed: `uv add textual --extra tui`
- Try running directly: `python -m src.ui.tui.app`

### Display issues
- Ensure terminal supports Unicode and colors
- Try maximizing terminal window
- On Windows, use Windows Terminal or WSL

### Can't navigate with keyboard
- Ensure terminal is not intercepting key bindings
- Try different terminal emulator

## Advanced Usage

### Pre-populate from environment
```bash
export INPUT_FILE="/path/to/video.mp4"
export OUTPUT_DIR="/path/to/output"
audio-extraction-analysis tui
```

### Run with specific Python
```bash
python3.11 -m src.cli tui
```

### Debug mode
```bash
audio-extraction-analysis tui --verbose
```

## Screenshots

The TUI provides a modern, responsive interface:

- **Welcome Screen**: Start processing or view help
- **Home Screen**: Browse files with tree view and recent files list
- **Config Screen**: Configure all pipeline settings
- **Run Screen**: Watch live progress with ETAs
- **Help Screen**: Built-in keyboard shortcuts reference

## Tips

1. **Use Recent Files**: The TUI remembers your recently processed files for quick access
2. **Settings Persist**: Your configuration choices are saved between sessions
3. **Keyboard Navigation**: Most operations can be done without mouse
4. **Live Logs**: Filter logs by severity to focus on what matters
5. **Cancel Anytime**: Pipeline can be safely cancelled with progress saved

## Integration with CLI

The TUI is just another way to run the same pipeline. You can mix and match:

```bash
# Process with CLI
audio-extraction-analysis process video1.mp4

# Process with TUI  
audio-extraction-analysis tui --input video2.mp4

# Results are compatible regardless of interface used
```
