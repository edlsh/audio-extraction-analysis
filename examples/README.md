# Example Outputs

This directory contains sample outputs from the audio extraction and analysis pipeline to help you understand what to expect from the tool.

## Sample Output Files

When you run the tool, it generates outputs similar to these examples:

### 📝 Text Output (`--format text`)
Simple, clean transcript without additional formatting or analysis.

### 📊 JSON Output (`--format json`)
Structured data including:
- Complete transcript
- Timestamps for each segment
- Speaker identification (when available)
- Metadata (duration, word count, etc.)

### 📄 Markdown Output (`--format markdown`)
Comprehensive analysis document containing:
1. **Executive Summary** - High-level overview of the content
2. **Chapter Overview** - Content broken into logical sections
3. **Key Topics & Intents** - Main themes and discussion points
4. **Full Transcript** - Complete text with timestamps
5. **Key Insights & Takeaways** - Actionable insights from the content

## How to Generate Your Own Examples

### Basic Example
```bash
audio-extraction-analysis process your-video.mp4 --format markdown
```

### Complete Pipeline Example
```bash
audio-extraction-analysis process podcast.mp4 \
    --output-dir examples/my-podcast/ \
    --quality speech \
    --provider deepgram \
    --format markdown \
    --verbose
```

## File Naming Convention

Generated files follow this pattern:
- `{filename}_transcript.txt` - Plain text transcript
- `{filename}_transcript.json` - JSON formatted data
- `{filename}_analysis.md` - Full markdown analysis
- `{filename}_audio.mp3` - Extracted audio file

## Privacy Note

The examples in this directory are for demonstration purposes. When processing your own content, outputs will be saved to `data/output/` by default, which is git-ignored to protect your privacy.

## Sample Content Types

This tool works well with:
- 🎙️ **Podcasts** - Interview style, multiple speakers
- 📺 **YouTube Videos** - Educational content, tutorials
- 🎬 **Webinars** - Presentations, Q&A sessions
- 🗣️ **Speeches** - Keynotes, lectures
- 📹 **Meetings** - Recorded video calls, conferences

Each content type may benefit from different quality settings:
- Use `--quality speech` for spoken content
- Use `--quality music` for content with background music
- Use `--quality high` for maximum fidelity