"""
Type stubs for openai-whisper library.

This stub file provides type annotations for the Whisper library,
which doesn't ship with its own type information.
"""

from typing import Any, Literal, Protocol, TypedDict
from pathlib import Path


class TranscriptionResult(TypedDict, total=False):
    """Result from Whisper transcription."""
    text: str
    segments: list[TranscriptionSegment]
    language: str


class TranscriptionSegment(TypedDict):
    """Individual segment in transcription result."""
    id: int
    seek: int
    start: float
    end: float
    text: str
    tokens: list[int]
    temperature: float
    avg_logprob: float
    compression_ratio: float
    no_speech_prob: float


class WhisperModel(Protocol):
    """Protocol for Whisper model interface."""

    def transcribe(
        self,
        audio: str | Path,
        *,
        language: str | None = None,
        task: Literal["transcribe", "translate"] = "transcribe",
        temperature: float | tuple[float, ...] = (0.0, 0.2, 0.4, 0.6, 0.8, 1.0),
        best_of: int | None = 5,
        beam_size: int | None = 5,
        patience: float | None = None,
        length_penalty: float | None = None,
        suppress_tokens: str | list[int] = "-1",
        initial_prompt: str | None = None,
        condition_on_previous_text: bool = True,
        fp16: bool = True,
        compression_ratio_threshold: float | None = 2.4,
        logprob_threshold: float | None = -1.0,
        no_speech_threshold: float | None = 0.6,
        word_timestamps: bool = False,
        verbose: bool | None = None,
    ) -> TranscriptionResult: ...


def load_model(
    name: str,
    device: str | None = None,
    download_root: str | None = None,
    in_memory: bool = False,
) -> WhisperModel:
    """Load a Whisper model.

    Args:
        name: Model size ('tiny', 'base', 'small', 'medium', 'large')
        device: Device to load model on ('cpu', 'cuda')
        download_root: Directory to download models to
        in_memory: Whether to load model in memory only

    Returns:
        Loaded Whisper model
    """
    ...


def available_models() -> list[str]:
    """Get list of available Whisper models.

    Returns:
        List of model names
    """
    ...


# Whisper utilities module
class utils:
    """Whisper utilities."""

    @staticmethod
    def get_writer(output_format: str, output_dir: str | Path) -> Any:
        """Get a writer for the specified output format.

        Args:
            output_format: Output format ('txt', 'vtt', 'srt', 'tsv', 'json')
            output_dir: Directory to write output files

        Returns:
            Writer instance for the specified format
        """
        ...
