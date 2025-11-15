# Audio Extraction Analysis v3.0

🎥➡️🎵➡️📝 **Professional Audio-to-Transcript Pipeline with Multiple Providers**

A comprehensive, production-ready Python package that transforms video recordings into structured, actionable documentation. Features a unified CLI, robust error handling, and extensive transcription analysis including speaker diarization, topic detection, and sentiment analysis. Supports multiple transcription providers including Deepgram Nova 3, ElevenLabs, OpenAI Whisper, and NVIDIA Parakeet.

## 🚀 Quick Start (3 Steps)

### 1. Install
```bash
# Clone and install
git clone <repository-url>
cd audio-extraction-analysis
pip install -e .

# Install FFmpeg
# macOS: brew install ffmpeg
# Ubuntu: sudo apt install ffmpeg  
# Windows: choco install ffmpeg
```

### 2. Configure API Key (or install Whisper)
```bash
# Option 1: Use Deepgram (cloud-based, full features)
# Get your API key from: https://console.deepgram.com/
export DEEPGRAM_API_KEY='your-key-here'

# Option 2: Use Whisper (local processing, no API key needed)
pip install openai-whisper torch

# Or create .env file for API keys
echo "DEEPGRAM_API_KEY=your-key-here" > .env
```

### 3. Process Your First Video
```bash
# Complete pipeline (concise default): video → audio → transcript → single analysis
audio-extraction-analysis process meeting.mp4

# Custom output directory
audio-extraction-analysis process video.mp4 --output-dir ./results

# Full 5-file analysis output
audio-extraction-analysis process video.mp4 --analysis-style full --output-dir ./results
```

## 🎯 Complete Workflow

```
MP4 Video → Audio Extraction → Deepgram Nova 3 → AI Analysis → 5 Structured Files
    ↓             ↓                    ↓                ↓               ↓
 FFmpeg      Quality Presets    Advanced Features   Smart Analysis   Actionable Docs
```

## 📋 CLI Commands

### Main Commands
```bash
# Full pipeline (recommended)
audio-extraction-analysis process video.mp4              # Complete workflow (concise)
audio-extraction-analysis process video.mp4 --output-dir ./results
audio-extraction-analysis process video.mp4 --analysis-style full --output-dir ./results  # five files

# Individual steps
audio-extraction-analysis extract video.mp4              # Audio extraction only  
audio-extraction-analysis transcribe audio.mp3           # Transcription only

# Help and info
audio-extraction-analysis --help                         # Show all commands
audio-extraction-analysis --version                      # Show version

# Markdown export (timestamps + speakers by default)
audio-extraction-analysis export-markdown audio.mp3 \
  --output-dir ./output \
  --template default \
  --timestamps --speakers

# Or add Markdown export to existing commands
audio-extraction-analysis transcribe audio.mp3 --export-markdown --md-template detailed
audio-extraction-analysis process video.mp4 --export-markdown --md-no-speakers --md-template minimal
```

### Common Options
| Option | Values | Description |
|--------|--------|-----------|
| `--quality` | `speech`, `standard`, `high`, `compressed` | Audio extraction quality |
| `--language` | `en`, `es`, `fr`, `de`, etc. | Transcription language |
| `--output-dir` | Directory path | Where to save results |
| `--analysis-style` | `concise`, `full` | Output style: single analysis vs. 5 files |
| `--verbose` | Flag | Detailed logging |

## 🖥️ Interactive TUI (Terminal User Interface)

For a guided, interactive experience with live progress monitoring, use the TUI mode:

```bash
# Launch interactive TUI
audio-extraction-analysis tui

# Or with pre-populated paths
audio-extraction-analysis tui --input video.mp4 --output-dir ./results
```

### TUI Features
- **📊 Live Progress Monitoring**: Real-time progress cards for extraction, transcription, and analysis with ETAs
- **📝 Log Streaming**: Filterable, color-coded logs (DEBUG, INFO, WARNING, ERROR)
- **🏥 Provider Health**: Monitor transcription provider status (Deepgram, ElevenLabs, Whisper, Parakeet)
- **💾 Auto-Save Settings**: Configuration and recent files persist across sessions
- **⌨️ Keyboard Shortcuts**: Full keyboard navigation (press `h` or `?` for help)
- **🎯 File Browser**: Browse and select files with recent files quick access

### TUI Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `h`, `?` | Show help screen |
| `q` | Quit application |
| `d` | Toggle dark mode |
| `Esc` | Go back / Close screen |

**In Run Screen:**
- `c` - Cancel pipeline
- `o` - Open output directory
- `a/d/i/w/e` - Filter logs (all/debug+/info+/warning+/error)

### TUI Workflow
```
Welcome → Select File → Configure → Run → View Results
   ↓           ↓            ↓         ↓        ↓
 Start      Browse       Settings  Progress  Open Output
```

## 💡 CLI Usage Examples

### Basic Usage
```bash
# Process a meeting recording
audio-extraction-analysis process team-meeting.mp4

# Process with custom settings
audio-extraction-analysis process interview.mp4 \
  --output-dir ./transcripts \
  --quality high \
  --language en

# Extract audio only (for manual transcription)
audio-extraction-analysis extract presentation.mp4 --quality speech

# Transcribe existing audio file
audio-extraction-analysis transcribe recording.mp3 --language es
```

### Batch Processing
```bash
# Process multiple videos
for video in *.mp4; do
  audio-extraction-analysis process "$video" --output-dir "./results/${video%.*}"
done
```

### Quality Settings
- **`speech`** (default): Optimized for meetings, interviews
- **`standard`**: Balanced quality for general content
- **`high`**: Maximum quality for archival
- **`compressed`**: Smaller files for quick tests

## 📁 Output Structure

Depends on `--analysis-style`:

### Concise (default)
- `{video}.mp3` - Extracted audio
- `{video}_analysis.md` - Single comprehensive analysis
- `{video}_transcript.txt` - Provider-formatted transcript

### Full
Each processed video generates **5 structured markdown files**:

| File | Purpose | Target Audience |
|------|---------|----------------|
| `01_executive_summary.md` | High-level overview with metadata | Executives, managers |
| `02_chapter_overview.md` | Detailed content breakdown by topic | Project managers, team leads |
| `03_key_topics_and_intents.md` | Technical analysis of discussion themes | Analysts, researchers |
| `04_full_transcript_with_timestamps.md` | Complete searchable record | All stakeholders, archives |
| `05_key_insights_and_takeaways.md` | Strategic insights and action items | Decision makers, implementers |

### Sample Output
```
./output/
├── meeting_2024.mp3                    # Extracted audio
├── 01_executive_summary.md              # 2-3 KB overview
├── 02_chapter_overview.md               # 4-5 KB chapters  
├── 03_key_topics_and_intents.md         # 5-6 KB analysis
├── 04_full_transcript_with_timestamps.md # 100+ KB transcript
└── 05_key_insights_and_takeaways.md     # 3-4 KB insights
```

### Markdown Export Output

When exporting markdown, files are organized as:

```
./output/
└── <source_name>/
    ├── transcript.md
    ├── metadata.json
    └── segments.json
```

## ⚙️ Configuration

### Environment Variables
```bash
# Required for cloud providers
export DEEPGRAM_API_KEY='your-api-key-here'     # Get from console.deepgram.com

# Optional - Whisper configuration
export WHISPER_MODEL='base'                     # tiny, base, small, medium, large
export WHISPER_DEVICE='cuda'                    # cuda or cpu
export WHISPER_COMPUTE_TYPE='float16'           # float16 or float32

# Optional - Parakeet configuration
export PARAKEET_MODEL='stt_en_conformer_ctc_large'  # stt_en_conformer_ctc_large, stt_en_conformer_transducer_large, stt_en_fastconformer_ctc_large
export PARAKEET_DEVICE='auto'                   # auto, cuda or cpu
export PARAKEET_BATCH_SIZE=8                    # Batch size for processing
export PARAKEET_BEAM_SIZE=10                    # Beam size for decoding
export PARAKEET_USE_FP16=true                   # Use FP16 for faster processing
export PARAKEET_CHUNK_LENGTH=30                 # Audio chunk length in seconds
export PARAKEET_MODEL_CACHE_DIR='~/.cache/parakeet'  # Model cache directory

# Optional - General configuration
export LOG_LEVEL='INFO'                         # DEBUG, INFO, WARNING, ERROR
export TEMP_DIR='/custom/temp/path'              # Custom temporary directory
```

### .env File (Alternative)
```bash
# Create .env file in project root
echo "DEEPGRAM_API_KEY=your-key-here" > .env
echo "WHISPER_MODEL=base" >> .env
echo "WHISPER_DEVICE=cuda" >> .env
echo "LOG_LEVEL=DEBUG" >> .env
```

### Supported Languages
- `en` - English (default)
- `es` - Spanish  
- `fr` - French
- `de` - German
- `it` - Italian
- `pt` - Portuguese
- `auto` - Auto-detect

### Whisper Model Sizes
Whisper supports multiple model sizes with different performance characteristics:

| Model | Parameters | Disk Space | RAM Usage | VRAM Usage | Quality |
|-------|------------|------------|-----------|------------|---------|
| tiny  | 39M        | 75MB       | ~1GB      | ~1GB       | Basic   |
| base  | 74M        | 142MB      | ~1GB      | ~1GB       | Good    |
| small | 244M       | 461MB      | ~2GB      | ~2GB       | Better  |
| medium| 769M       | 1.5GB      | ~5GB      | ~5GB       | Great   |
| large | 1.5B       | 2.9GB      | ~10GB     | ~10GB      | Best    |

Set model size with: `export WHISPER_MODEL=medium`

### Parakeet Model Options
Parakeet supports multiple model architectures with different performance characteristics:

| Model | Type | Accuracy | Speed | Memory | Languages |
|-------|------|----------|-------|--------|-----------|
| stt_en_conformer_ctc_large | CTC | High | Fast | 4GB | English |
| stt_en_conformer_transducer_large | RNN-T | Highest | Medium | 6GB | English |
| stt_en_fastconformer_ctc_large | CTC | Medium | Fastest | 2GB | English |

Set model with: `export PARAKEET_MODEL=stt_en_conformer_ctc_large`

## 🧩 Templates

Templates are defined in `src/formatters/templates.py`:

- `default`: Rich header, timestamps, speaker prefixes
- `minimal`: Title only + text
- `detailed`: Report-style header, stats, bold timestamps

Each template accepts placeholders in strings:
- Header: `{title}`, `{source}`, `{duration}`, `{processed_at}`, `{provider}`, `{segment_count}`, `{avg_confidence}`
- Segment: `{timestamp}`, `{speaker_prefix}`, `{text}`, `{confidence}`

To customize, add a new entry to `TEMPLATES` with keys:
`header`, `segment`, `speaker_prefix`, `timestamp_format`.

## 🎯 Key Features

### Intelligent Content Organization
- **Automatic Chapter Detection**: Identifies topic transitions and creates logical sections
- **Speaker Separation**: Maintains clear attribution with timestamps
- **Topic Extraction**: Identifies and ranks discussion themes by frequency and importance

### Advanced Analysis
- **Intent Detection**: Recognizes underlying purposes in discussions
- **Sentiment Analysis**: Tracks positive, neutral, and negative segments
- **Insight Generation**: Extracts actionable takeaways with supporting evidence

### Production Ready
- **Unified CLI**: Simple commands for complex workflows
- **Quality Presets**: Optimized audio extraction for different needs
- **Error Handling**: Robust processing with detailed logging
- **Fast Processing**: 2-hour meetings processed in ~5-7 minutes

## 🛠️ System Requirements

### Prerequisites
- **Python 3.8+** (3.9+ recommended)
- **FFmpeg** (for audio extraction)
- **Deepgram API Key** (for transcription)
- **Internet connection** (for API calls)

### Installation Steps
1. **Install FFmpeg**: `brew install ffmpeg` (macOS) or `sudo apt install ffmpeg` (Ubuntu)
2. **Clone repository**: `git clone <repository-url>`
3. **Install package**: `pip install -e .`
4. **Install transcription provider**:
   - For Deepgram: `export DEEPGRAM_API_KEY='your-key'`
   - For Whisper: `pip install openai-whisper torch`
   - For Parakeet: `pip install nemo-toolkit[asr]`
5. **Test**: `audio-extraction-analysis --version`

### Supported Formats
- **Input**: MP4, MOV, AVI, MKV, MP3, WAV, M4A
- **Output**: MP3 (audio), Markdown (transcripts)
- **File size**: Up to 2GB
- **Duration**: No limit

## 🔧 Troubleshooting

### Common Issues

#### "Input file not found"
```bash
# Check file path and permissions
ls -la your-file.mp4
# Use absolute path if needed
audio-extraction-analysis process /full/path/to/video.mp4
```

#### "Deepgram API key not configured"
```bash
# Set API key
export DEEPGRAM_API_KEY="your-key-here"
# Or create .env file
echo "DEEPGRAM_API_KEY=your-key-here" > .env
# Get API key from: https://console.deepgram.com/
```

#### "FFmpeg not found"
```bash
# Install FFmpeg
# macOS: brew install ffmpeg
# Ubuntu: sudo apt install ffmpeg
# Windows: choco install ffmpeg
# Verify: ffmpeg -version
```

#### "Whisper dependencies not installed"
```bash
# Install Whisper and PyTorch
pip install openai-whisper torch

# For GPU acceleration (recommended):
pip install openai-whisper torch torchaudio --index-url https://download.pytorch.org/whl/cu118

# Verify installation:
python -c "import whisper; print('Whisper installed successfully')"
```

#### "Parakeet dependencies not installed"
```bash
# Install Parakeet and NeMo dependencies
pip install nemo-toolkit[asr]

# For GPU acceleration (recommended):
pip install nemo-toolkit[asr] torch torchaudio

# Verify installation:
python -c "import nemo; print('Parakeet installed successfully')"
```

#### "Permission denied"
```bash
# Check output directory permissions
ls -la /path/to/output/
# Create directory if needed
mkdir -p /path/to/output
```

### Performance Tips
- Use `--quality speech` for faster processing
- Process large files in smaller segments
- Ensure stable internet for API calls
- Monitor disk space for output files

## 📊 Use Cases

### 🏢 Business Meetings
- **Input**: 2-hour team meeting recording
- **Output**: Executive summary, action items, decisions
- **Time**: ~5-7 minutes processing

### 🎓 Training Sessions  
- **Input**: Multi-hour training video
- **Output**: Searchable reference, key concepts, Q&A
- **Benefits**: Reusable training materials

### 👥 Customer Interviews
- **Input**: Interview recordings
- **Output**: Insights, pain points, feature requests
- **Benefits**: Structured feedback analysis

### 🎧 Podcast/Webinar Analysis
- **Input**: Long-form content
- **Output**: Chapter breakdown, topics, quotes
- **Benefits**: Content repurposing, highlights

### Performance Metrics
- **Accuracy**: 95%+ with Deepgram Nova 3, 85%+ with Whisper large
- **Speed**: Real-time processing capability (cloud), 0.5-5x real-time (Whisper)
- **Output**: 5 files, 100-150KB total
- **Languages**: 10+ supported languages (Whisper supports 100+ languages)

## 📚 Documentation

For detailed information:
- **CLI Help (`audio-extraction-analysis --help`)** - Discover the latest command syntax directly from the tool
- **[HTML Dashboard Guide](docs/HTML_DASHBOARD.md)** - Learn how to render interactive dashboards from analysis output
- **[Examples Directory](examples/)** - Browse runnable samples and generated markdown outputs

## 🤝 Contributing

```bash
# Development setup
git clone <repository-url>
cd audio-extraction-analysis
pip install -e ".[dev]"

# Install Whisper for testing
pip install openai-whisper torch

# Install Parakeet for testing
pip install nemo-toolkit[asr]

# Run tests
pytest

# Code formatting
black src/ tests/
ruff check src/ tests/
```

## 📄 License

This project is provided as-is for professional use. Adapt and modify according to your organization's needs.

---

*Transform your recordings into structured, actionable documentation.*
