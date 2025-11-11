"""Processing pipelines for audio transcription workflows.

Recommended:
    - `process_pipeline`: Modern, simplified pipeline API (recommended)

Deprecated:
    - `AudioProcessingPipeline`: Legacy class-based API (deprecated, will be removed in v2.0.0)
      Use `process_pipeline()` instead.
"""
from .audio_pipeline import AudioProcessingPipeline
from .simple_pipeline import process_pipeline

__all__ = ["process_pipeline", "AudioProcessingPipeline"]
