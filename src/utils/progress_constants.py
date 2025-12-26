"""Progress constants for transcription simulation."""

from dataclasses import dataclass


@dataclass
class ProgressConstants:
    """Constants for progress simulation in transcription."""

    MINIMUM_SECONDS: float = 5.0
    DURATION_RATIO: float = 0.1
    PROCESSING_SPEED_MB_PER_SEC: float = 2.0
    SIGMOID_RANGE_MIN: float = -6.0
    SIGMOID_RANGE_MAX: float = 6.0
    MAX_PROGRESS_PERCENT: float = 95.0
    DEFAULT_AUDIO_DURATION: float = 30.0
