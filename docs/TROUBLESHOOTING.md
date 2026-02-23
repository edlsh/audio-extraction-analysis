# Troubleshooting Guide

Solutions for common issues when using Audio Extraction Analysis.

## Quick Fixes

| Issue | Solution |
|-------|----------|
| Input file not found | Use absolute path |
| API key not configured | Set environment variable or `.env` |
| FFmpeg not found | Install FFmpeg for your OS |
| TUI not working | Install Bun and run `cd frontend && bun install` from a checkout |

---

## Common Issues

### "Input file not found"

```bash
# Check file exists and has correct permissions
ls -la your-file.mp4

# Use absolute path
audio-extraction-analysis process /full/path/to/video.mp4

# Check for special characters in filename
# Rename files with spaces or special characters
mv "my file (1).mp4" my_file.mp4
```

### "Deepgram API key not configured"

```bash
# Option 1: Set environment variable
export DEEPGRAM_API_KEY="your-key-here"

# Option 2: Create .env file
echo "DEEPGRAM_API_KEY=your-key-here" > .env

# Get API key from: https://console.deepgram.com/
```

### "FFmpeg not found"

```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt update && sudo apt install ffmpeg

# Windows (with Chocolatey)
choco install ffmpeg

# Windows (with winget)
winget install ffmpeg

# Verify installation
ffmpeg -version
```

### "Permission denied"

```bash
# Check output directory permissions
ls -la /path/to/output/

# Create directory with correct permissions
mkdir -p /path/to/output
chmod 755 /path/to/output
```

---

## Provider-Specific Issues

### Whisper

#### "Whisper dependencies not installed"

```bash
# Basic installation
uv add openai-whisper torch

# Verify installation
python -c "import whisper; print('Whisper installed successfully')"
```

#### "CUDA out of memory" with Whisper

```bash
# Use a smaller model
export WHISPER_MODEL=base  # or tiny

# Or force CPU processing
export WHISPER_DEVICE=cpu
```

#### GPU acceleration for Whisper

```bash
# Install with CUDA 11.8 support
uv add openai-whisper torch torchaudio --index-url https://download.pytorch.org/whl/cu118

# Verify CUDA is available
python -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}')"
```

### Parakeet (Removed)

Parakeet support was removed from this codebase. If you still have older
shell snippets using `--provider parakeet` or `uv sync --extra parakeet`,
replace them with a supported provider (`deepgram`, `elevenlabs`, or `whisper`).

### ElevenLabs

#### "ElevenLabs API key not configured"

```bash
# Set environment variable
export ELEVENLABS_API_KEY="your-key-here"

# Get API key from: https://elevenlabs.io/api
```

---

## TUI Issues

### "TUI not working / frontend not found"

```bash
# Check Bun is installed
bun --version

# Install Bun if needed
curl -fsSL https://bun.sh/install | bash

# Verify frontend directory exists
ls frontend/package.json

# Install frontend dependencies
cd frontend && bun install

# Verify TUI works
audio-extraction-analysis tui --help
```

### "TUI display issues"

```bash
# Ensure terminal supports colors
echo $TERM  # Should be xterm-256color or similar

# Try different terminal emulator
# iTerm2, Alacritty, or Windows Terminal recommended

# Check terminal size (minimum 80x24)
tput cols
tput lines
```

### "TUI settings not persisting"

Settings are saved to platform-specific directories:

| Platform | Location |
|----------|----------|
| macOS | `~/Library/Application Support/audio-extraction-analysis/` |
| Linux | `~/.config/audio-extraction-analysis/` |
| Windows | `%APPDATA%\audio-extraction-analysis\` |

```bash
# Check if directory exists and is writable
ls -la ~/.config/audio-extraction-analysis/  # Linux
ls -la ~/Library/Application\ Support/audio-extraction-analysis/  # macOS
```

---

## Performance Issues

### Slow processing

```bash
# Use speech-optimized quality (faster)
audio-extraction-analysis process video.mp4 --quality speech

# Use smaller Whisper model for local processing
export WHISPER_MODEL=base

# Ensure GPU is being used (if available)
export WHISPER_DEVICE=cuda
```

### High memory usage

```bash
# Use smaller models
export WHISPER_MODEL=tiny  # or base
```

### Large output files

```bash
# Use concise analysis style (default)
audio-extraction-analysis process video.mp4 --analysis-style concise

# Use compressed audio quality
audio-extraction-analysis process video.mp4 --quality compressed
```

---

## Network Issues

### "Connection timeout" with cloud providers

```bash
# Check internet connectivity
curl -I https://api.deepgram.com

# Retry with verbose logging
audio-extraction-analysis process video.mp4 --verbose

# Check for proxy settings
echo $HTTP_PROXY
echo $HTTPS_PROXY
```

### "Rate limit exceeded"

- Wait a few minutes before retrying
- Check your API plan limits at the provider's dashboard
- Consider using local Whisper for bulk processing

---

## Debug Mode

Enable verbose logging for detailed diagnostics:

```bash
# Via command line
audio-extraction-analysis process video.mp4 --verbose

# Via environment variable
export LOG_LEVEL=DEBUG
audio-extraction-analysis process video.mp4
```

Log files are written to:
- Current directory: `./logs/`
- Or system temp directory if `./logs/` is not writable

---

## Getting Help

If issues persist:

1. Check the [GitHub Issues](https://github.com/edlsh/audio-extraction-analysis/issues)
2. Run with `--verbose` and include logs when reporting issues
3. Include your environment info:
   ```bash
   audio-extraction-analysis --version
   python --version
   ffmpeg -version
   uname -a  # or systeminfo on Windows
   ```
