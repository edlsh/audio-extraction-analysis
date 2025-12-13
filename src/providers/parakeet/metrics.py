"""Metrics tracking for Parakeet transcriptions."""

from __future__ import annotations


class ParakeetMetrics:
    """Tracks metrics for Parakeet transcriptions."""

    def __init__(self) -> None:
        self.total_duration = 0.0
        self.total_processing_time = 0.0

    def log_transcription(self, duration: float, audio_length: float) -> None:
        """Log a transcription event.

        Args:
            duration: Processing time in seconds
            audio_length: Audio length in seconds
        """
        self.total_duration += audio_length
        self.total_processing_time += duration

    def get_rtf(self) -> float:
        """Get real-time factor (processing time / audio time).

        Returns:
            RTF value, or 0.0 if no data
        """
        if self.total_duration > 0:
            return self.total_processing_time / self.total_duration
        return 0.0


__all__ = ["ParakeetMetrics"]
