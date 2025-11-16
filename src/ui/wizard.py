"""Interactive CLI wizard helpers.

Provides a guided workflow that collects user inputs via ``ConsoleManager``
prompts and translates them into standard CLI argument vectors. The wizard is
designed to feel like a friendly onboarding flow for non-technical users while
remaining a thin wrapper around the existing argparse-powered commands.
"""

from __future__ import annotations

import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from rich.panel import Panel

from ..services.audio_extraction import AudioQuality
from .console import ConsoleManager

_ACTION_PROCESS = "process"
_ACTION_EXTRACT = "extract"
_ACTION_TRANSCRIBE = "transcribe"
_ACTION_EXPORT = "export-markdown"


@dataclass
class WizardSelection:
    """Container describing the final command chosen by the wizard."""

    argv: list[str]
    summary: Sequence[tuple[str, str]]


def run_cli_wizard(console: ConsoleManager) -> WizardSelection | None:
    """Run the interactive wizard and produce a CLI argv for execution."""

    if console.json_output:
        console.print_warning("Wizard mode is unavailable when --json-output is set.")
        return None

    console.print_info("Audio Extraction Analysis interactive wizard")
    console.print_info("Answer a few questions and we'll run the right command for you.")

    actions = {
        _ACTION_PROCESS: "Full pipeline (video → transcript & analysis)",
        _ACTION_EXTRACT: "Extract audio from a video file",
        _ACTION_TRANSCRIBE: "Transcribe an existing audio file",
        _ACTION_EXPORT: "Export Markdown from an existing transcript",
    }

    labels = list(actions.values())
    selected_label = console.prompt_choice(
        "What would you like to do?",
        labels,
        default_index=0,
    )

    reverse_lookup = {label: key for key, label in actions.items()}
    action = reverse_lookup.get(selected_label, _ACTION_PROCESS)

    if action == _ACTION_PROCESS:
        selection = _collect_process_flow(console)
    elif action == _ACTION_EXTRACT:
        selection = _collect_extract_flow(console)
    elif action == _ACTION_TRANSCRIBE:
        selection = _collect_transcribe_flow(console)
    else:
        selection = _collect_export_flow(console)

    if selection is None:
        console.print_warning("Wizard cancelled.")
        return None

    _render_summary(console, selection.summary)

    if not console.prompt_confirmation("Ready to run this command?", default=True):
        console.print_warning("Command aborted at your request.")
        return None

    return selection


# ---------------------------------------------------------------------------
# Collection helpers per flow
# ---------------------------------------------------------------------------


def _collect_process_flow(console: ConsoleManager) -> WizardSelection | None:
    video_file = _prompt_path(console, "Path to your video file", must_exist=True)
    if video_file is None:
        return None

    output_dir = console.prompt_text("Where should results be saved?", default="output")

    quality_options = [q.value for q in AudioQuality]
    try:
        default_quality_index = quality_options.index(AudioQuality.SPEECH.value)
    except ValueError:  # pragma: no cover - defensive
        default_quality_index = 0

    quality_choice = console.prompt_choice(
        "Choose audio quality",
        quality_options,
        default_index=default_quality_index,
    )

    provider_choice = console.prompt_choice(
        "Select transcription provider",
        ["auto", "deepgram", "elevenlabs", "whisper"],
        default_index=0,
    )

    language_code = console.prompt_text("Language code", default="en")

    analysis_style = console.prompt_choice(
        "Pick analysis style",
        ["concise", "full"],
        default_index=0,
    )

    export_markdown = console.prompt_confirmation(
        "Also produce a Markdown transcript?",
        default=True,
    )

    md_template = "default"
    md_include_timestamps = True
    md_include_speakers = True
    md_include_confidence = False
    if export_markdown:
        md_template = console.prompt_choice(
            "Markdown template",
            ["default", "minimal", "detailed"],
            default_index=0,
        )
        md_include_timestamps = console.prompt_confirmation(
            "Include timestamps?",
            default=True,
        )
        md_include_speakers = console.prompt_confirmation(
            "Include speaker labels?",
            default=True,
        )
        md_include_confidence = console.prompt_confirmation(
            "Include confidence scores?",
            default=False,
        )

    generate_html = console.prompt_confirmation(
        "Generate an HTML dashboard summary?",
        default=True,
    )

    argv: list[str] = [
        _ACTION_PROCESS,
        str(video_file),
    ]

    if output_dir:
        argv += ["--output-dir", output_dir]
    if quality_choice:
        argv += ["--quality", quality_choice]
    if provider_choice:
        argv += ["--provider", provider_choice]
    if language_code:
        argv += ["--language", language_code]
    if analysis_style:
        argv += ["--analysis-style", analysis_style]
    if export_markdown:
        argv.append("--export-markdown")
        if md_template:
            argv += ["--md-template", md_template]
        if not md_include_timestamps:
            argv.append("--md-no-timestamps")
        if not md_include_speakers:
            argv.append("--md-no-speakers")
        if md_include_confidence:
            argv.append("--md-confidence")
    if generate_html:
        argv.append("--html-dashboard")

    summary = [
        ("Operation", "Full pipeline"),
        ("Video", str(video_file)),
        ("Output directory", output_dir or "output"),
        ("Quality", quality_choice),
        ("Provider", provider_choice),
        ("Language", language_code),
        ("Analysis style", analysis_style),
        ("Export Markdown", "yes" if export_markdown else "no"),
        ("HTML dashboard", "yes" if generate_html else "no"),
    ]

    if export_markdown:
        summary.extend(
            [
                ("Markdown template", md_template),
                ("MD timestamps", "yes" if md_include_timestamps else "no"),
                ("MD speakers", "yes" if md_include_speakers else "no"),
                ("MD confidence", "yes" if md_include_confidence else "no"),
            ]
        )

    return WizardSelection(argv=argv, summary=summary)


def _collect_extract_flow(console: ConsoleManager) -> WizardSelection | None:
    video_file = _prompt_path(console, "Path to your video file", must_exist=True)
    if video_file is None:
        return None

    output_path = console.prompt_text(
        "Where should the audio be saved?",
        default=f"{video_file.stem}.mp3",
    )

    quality_options = [q.value for q in AudioQuality]
    try:
        default_quality_index = quality_options.index(AudioQuality.SPEECH.value)
    except ValueError:  # pragma: no cover
        default_quality_index = 0

    quality_choice = console.prompt_choice(
        "Choose audio quality",
        quality_options,
        default_index=default_quality_index,
    )

    argv: list[str] = [_ACTION_EXTRACT, str(video_file)]
    if output_path:
        argv += ["--output", output_path]
    if quality_choice:
        argv += ["--quality", quality_choice]

    summary = [
        ("Operation", "Extract audio"),
        ("Video", str(video_file)),
        ("Audio output", output_path),
        ("Quality", quality_choice),
    ]

    return WizardSelection(argv=argv, summary=summary)


def _collect_transcribe_flow(console: ConsoleManager) -> WizardSelection | None:
    audio_file = _prompt_path(console, "Path to your audio file", must_exist=True)
    if audio_file is None:
        return None

    output_path = console.prompt_text(
        "Where should the transcript be saved?",
        default=f"{audio_file.stem}_transcript.txt",
    )

    provider_choice = console.prompt_choice(
        "Select transcription provider",
        ["auto", "deepgram", "elevenlabs", "whisper"],
        default_index=0,
    )
    language_code = console.prompt_text("Language code", default="en")

    export_markdown = console.prompt_confirmation(
        "Export Markdown transcript as well?",
        default=True,
    )

    md_template = "default"
    md_include_timestamps = True
    md_include_speakers = True
    md_include_confidence = False

    if export_markdown:
        md_template = console.prompt_choice(
            "Markdown template",
            ["default", "minimal", "detailed"],
            default_index=0,
        )
        md_include_timestamps = console.prompt_confirmation(
            "Include timestamps?",
            default=True,
        )
        md_include_speakers = console.prompt_confirmation(
            "Include speaker labels?",
            default=True,
        )
        md_include_confidence = console.prompt_confirmation(
            "Include confidence scores?",
            default=False,
        )

    argv: list[str] = [_ACTION_TRANSCRIBE, str(audio_file)]
    if output_path:
        argv += ["--output", output_path]
    if provider_choice:
        argv += ["--provider", provider_choice]
    if language_code:
        argv += ["--language", language_code]
    if export_markdown:
        argv.append("--export-markdown")
        if md_template:
            argv += ["--md-template", md_template]
        if not md_include_timestamps:
            argv.append("--md-no-timestamps")
        if not md_include_speakers:
            argv.append("--md-no-speakers")
        if md_include_confidence:
            argv.append("--md-confidence")

    summary = [
        ("Operation", "Transcribe audio"),
        ("Audio", str(audio_file)),
        ("Transcript output", output_path),
        ("Provider", provider_choice),
        ("Language", language_code),
        ("Export Markdown", "yes" if export_markdown else "no"),
    ]

    if export_markdown:
        summary.extend(
            [
                ("Markdown template", md_template),
                ("MD timestamps", "yes" if md_include_timestamps else "no"),
                ("MD speakers", "yes" if md_include_speakers else "no"),
                ("MD confidence", "yes" if md_include_confidence else "no"),
            ]
        )

    return WizardSelection(argv=argv, summary=summary)


def _collect_export_flow(console: ConsoleManager) -> WizardSelection | None:
    audio_path = _prompt_path(
        console,
        "Path to the audio file",
        must_exist=True,
    )
    if audio_path is None:
        return None

    output_dir = console.prompt_text(
        "Where should Markdown files be saved?",
        default="output",
    )

    provider_choice = console.prompt_choice(
        "Select transcription provider",
        ["auto", "deepgram", "elevenlabs", "whisper"],
        default_index=0,
    )

    language_code = console.prompt_text("Language code", default="en")

    template_choice = console.prompt_choice(
        "Select Markdown template",
        ["default", "minimal", "detailed"],
        default_index=0,
    )

    include_timestamps = console.prompt_confirmation(
        "Include timestamps?",
        default=True,
    )
    include_speakers = console.prompt_confirmation(
        "Include speaker labels?",
        default=True,
    )
    include_confidence = console.prompt_confirmation(
        "Include confidence scores?",
        default=False,
    )

    argv: list[str] = [
        _ACTION_EXPORT,
        str(audio_path),
        "--output-dir",
        output_dir,
        "--provider",
        provider_choice,
        "--language",
        language_code,
        "--template",
        template_choice,
    ]

    if include_timestamps:
        argv.append("--timestamps")
    else:
        argv.append("--no-timestamps")
    if include_speakers:
        argv.append("--speakers")
    else:
        argv.append("--no-speakers")
    if include_confidence:
        argv.append("--confidence")

    summary = [
        ("Operation", "Export Markdown"),
        ("Audio", str(audio_path)),
        ("Output directory", output_dir),
        ("Provider", provider_choice),
        ("Language", language_code),
        ("Template", template_choice),
        ("Include timestamps", "yes" if include_timestamps else "no"),
        ("Include speakers", "yes" if include_speakers else "no"),
        ("Include confidence", "yes" if include_confidence else "no"),
    ]

    return WizardSelection(argv=argv, summary=summary)


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------


def _prompt_path(
    console: ConsoleManager,
    message: str,
    *,
    must_exist: bool,
) -> Path | None:
    """Prompt until a valid path is supplied or the user aborts."""

    while True:
        response = console.prompt_text(f"{message} (type 'cancel' to abort)")
        if not response:
            console.print_warning("A path is required.")
            continue

        if response.lower() in {"cancel", "quit", "exit"}:
            return None

        candidate = Path(response).expanduser()
        if must_exist and not candidate.exists():
            console.print_warning(f"Cannot find {candidate}. Please enter an existing path.")
            continue

        return candidate


def _render_summary(console: ConsoleManager, summary: Sequence[tuple[str, str]]) -> None:
    if console.json_output:
        return

    if console.console:
        rows = "\n".join(f"[bold]{key}[/bold]: {value}" for key, value in summary)
        console.console.print(Panel(rows, title="Summary", padding=(1, 2)))
    else:
        print("Summary:", file=sys.stderr)
        for key, value in summary:
            print(f"  {key}: {value}", file=sys.stderr)
