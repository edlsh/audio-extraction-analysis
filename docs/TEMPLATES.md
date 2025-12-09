# Markdown Templates

Templates control how transcripts are formatted when exported to Markdown.

## Built-in Templates

| Template | Style | Best For |
|----------|-------|----------|
| `default` | Rich header, timestamps, speaker prefixes | General use, meetings |
| `minimal` | Title only + text | Clean reading, sharing |
| `detailed` | Report-style header, stats, bold timestamps | Formal reports, archives |

## Usage

```bash
# Use default template
audio-extraction-analysis export-markdown audio.mp3 --template default

# Use minimal template
audio-extraction-analysis export-markdown audio.mp3 --template minimal

# Use detailed template
audio-extraction-analysis export-markdown audio.mp3 --template detailed

# With additional options
audio-extraction-analysis export-markdown audio.mp3 \
  --template default \
  --timestamps \
  --speakers \
  --output-dir ./output
```

## Template Options

| Option | Description |
|--------|-------------|
| `--timestamps` | Include timestamps in output |
| `--speakers` | Include speaker labels |
| `--md-no-speakers` | Disable speaker labels |
| `--md-template` | Select template (default/minimal/detailed) |

---

## Custom Templates

Templates are defined in `src/formatters/templates.py`. Each template has four components:

### Template Structure

```python
TEMPLATES = {
    "my_template": {
        "header": "...",           # Document header
        "segment": "...",          # Per-segment format
        "speaker_prefix": "...",   # Speaker label format
        "timestamp_format": "...", # Timestamp format
    }
}
```

### Available Placeholders

**Header placeholders:**
- `{title}` - Document title
- `{source}` - Source file name
- `{duration}` - Total duration
- `{processed_at}` - Processing timestamp
- `{provider}` - Transcription provider used
- `{segment_count}` - Number of segments
- `{avg_confidence}` - Average confidence score

**Segment placeholders:**
- `{timestamp}` - Segment timestamp
- `{speaker_prefix}` - Speaker label
- `{text}` - Transcript text
- `{confidence}` - Confidence score

---

## Example: Creating a Custom Template

Add a new entry to `TEMPLATES` in `src/formatters/templates.py`:

```python
TEMPLATES = {
    # ... existing templates ...
    
    "meeting_notes": {
        "header": """# {title}

**Date:** {processed_at}
**Duration:** {duration}
**Source:** {source}

---

""",
        "segment": "{timestamp} {speaker_prefix}{text}\n\n",
        "speaker_prefix": "**{speaker}:** ",
        "timestamp_format": "[{start}]",
    }
}
```

Then use it:

```bash
audio-extraction-analysis export-markdown audio.mp3 --template meeting_notes
```

---

## Output Structure

When exporting markdown, files are organized as:

```
./output/
└── <source_name>/
    ├── transcript.md    # Formatted transcript
    ├── metadata.json    # Processing metadata
    └── segments.json    # Raw segment data
```
