# Transcription Providers

This guide covers detailed configuration for all supported transcription providers.

## Overview

| Provider | Type | API Key Required | Best For |
|----------|------|------------------|----------|
| Deepgram Nova 3 | Cloud | Yes | Production, accuracy, speaker diarization |
| ElevenLabs | Cloud | Yes | High-quality voice processing |
| Whisper | Local | No | Privacy, offline use, 100+ languages |

## Deepgram

Cloud-based provider with excellent accuracy and full feature support.

### Setup

```bash
# Get API key from: https://console.deepgram.com/
export DEEPGRAM_API_KEY='your-api-key-here'

# Or add to .env file
echo "DEEPGRAM_API_KEY=your-api-key-here" >> .env
```

### Features

- Speaker diarization
- Punctuation and formatting
- Topic detection
- Sentiment analysis
- Real-time streaming

---

## ElevenLabs

Cloud-based provider optimized for voice processing.

### Setup

```bash
# Get API key from: https://elevenlabs.io/api
export ELEVENLABS_API_KEY='your-api-key-here'

# Or add to .env file
echo "ELEVENLABS_API_KEY=your-api-key-here" >> .env
```

---

## Whisper (Local)

OpenAI's Whisper runs locally—no API key needed. Supports 100+ languages.

### Installation

```bash
# Basic installation
uv add openai-whisper torch

# For GPU acceleration (CUDA 11.8)
uv add openai-whisper torch torchaudio --index-url https://download.pytorch.org/whl/cu118

# Verify installation
python -c "import whisper; print('Whisper installed successfully')"
```

### Model Selection

| Model | Parameters | Disk Space | RAM Usage | VRAM Usage | Quality |
|-------|------------|------------|-----------|------------|---------|
| tiny  | 39M        | 75MB       | ~1GB      | ~1GB       | Basic   |
| base  | 74M        | 142MB      | ~1GB      | ~1GB       | Good    |
| small | 244M       | 461MB      | ~2GB      | ~2GB       | Better  |
| medium| 769M       | 1.5GB      | ~5GB      | ~5GB       | Great   |
| large | 1.5B       | 2.9GB      | ~10GB     | ~10GB      | Best    |

### Configuration

```bash
export WHISPER_MODEL='base'        # Model size: tiny, base, small, medium, large
export WHISPER_DEVICE='cuda'       # Device: cuda or cpu
export WHISPER_COMPUTE_TYPE='float16'  # Precision: float16 or float32
```

### Performance Tips

- **tiny/base**: Fast, good for drafts or real-time use
- **small/medium**: Balanced accuracy and speed
- **large**: Best accuracy, requires significant VRAM
- Use `cuda` device when GPU is available for 5-10x speedup

---

## Parakeet (Removed)

Parakeet support is no longer part of this repository. If you need local
transcription without API keys, use Whisper.

---

## Provider Selection

The CLI supports automatic provider selection or explicit choice:

```bash
# Auto-select based on available API keys/models
audio-extraction-analysis transcribe audio.mp3 --provider auto

# Explicit provider selection
audio-extraction-analysis transcribe audio.mp3 --provider deepgram
audio-extraction-analysis transcribe audio.mp3 --provider whisper
```

### Selection Priority (auto mode)

1. Deepgram (if `DEEPGRAM_API_KEY` is set)
2. ElevenLabs (if `ELEVENLABS_API_KEY` is set)
3. Whisper (if installed)

---

## Environment Variables Reference

| Variable | Provider | Description |
|----------|----------|-------------|
| `DEEPGRAM_API_KEY` | Deepgram | API key for Deepgram |
| `ELEVENLABS_API_KEY` | ElevenLabs | API key for ElevenLabs |
| `WHISPER_MODEL` | Whisper | Model size (tiny/base/small/medium/large) |
| `WHISPER_DEVICE` | Whisper | Device (cuda/cpu) |
| `WHISPER_COMPUTE_TYPE` | Whisper | Precision (float16/float32) |
