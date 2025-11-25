"""
Type stubs for NeMo ASR (Automatic Speech Recognition) module.

This stub file provides type annotations for nemo.collections.asr,
used by the Parakeet provider for speech-to-text transcription.
"""

from typing import Any, Protocol
from pathlib import Path


class ASRModel(Protocol):
    """Protocol for NeMo ASR model interface."""

    def transcribe(
        self,
        paths2audio_files: list[str] | list[Path],
        batch_size: int = 1,
        logprobs: bool = False,
        return_hypotheses: bool = False,
        num_workers: int = 0,
        channel_selector: int | str | None = None,
        augmentor: Any = None,
        verbose: bool = True,
    ) -> list[str] | list[Any]:
        """Transcribe audio files.

        Args:
            paths2audio_files: List of paths to audio files
            batch_size: Batch size for processing
            logprobs: Whether to return log probabilities
            return_hypotheses: Whether to return full hypotheses
            num_workers: Number of workers for data loading
            channel_selector: Channel selection for multi-channel audio
            augmentor: Optional audio augmentation
            verbose: Whether to print progress

        Returns:
            List of transcriptions or hypotheses
        """
        ...

    def to(self, device: str) -> ASRModel:
        """Move model to specified device.

        Args:
            device: Device identifier ('cpu', 'cuda', 'cuda:0', etc.)

        Returns:
            Self for method chaining
        """
        ...

    def eval(self) -> ASRModel:
        """Set model to evaluation mode.

        Returns:
            Self for method chaining
        """
        ...

    def train(self, mode: bool = True) -> ASRModel:
        """Set model to training mode.

        Args:
            mode: Whether to enable training mode

        Returns:
            Self for method chaining
        """
        ...


class EncDecCTCModel(ASRModel):
    """Encoder-Decoder CTC-based ASR model.

    Used for Parakeet-TDT and similar models.
    """

    @classmethod
    def from_pretrained(
        cls,
        model_name: str,
        refresh_cache: bool = False,
        override_config_path: str | Path | None = None,
        map_location: str | None = None,
        strict: bool = True,
        return_config: bool = False,
    ) -> EncDecCTCModel:
        """Load a pretrained model from NGC.

        Args:
            model_name: Name of the model (e.g., 'nvidia/parakeet-tdt-1.1b')
            refresh_cache: Whether to refresh cached model
            override_config_path: Path to custom config file
            map_location: Device to load model on
            strict: Whether to strictly enforce config match
            return_config: Whether to also return config

        Returns:
            Loaded ASR model
        """
        ...

    @classmethod
    def restore_from(
        cls,
        restore_path: str | Path,
        override_config_path: str | Path | None = None,
        map_location: str | None = None,
        strict: bool = True,
        return_config: bool = False,
    ) -> EncDecCTCModel:
        """Restore model from local checkpoint.

        Args:
            restore_path: Path to .nemo checkpoint file
            override_config_path: Path to custom config file
            map_location: Device to load model on
            strict: Whether to strictly enforce config match
            return_config: Whether to also return config

        Returns:
            Restored ASR model
        """
        ...


def models() -> dict[str, type[ASRModel]]:
    """Get dictionary of available ASR model classes.

    Returns:
        Dictionary mapping model names to model classes
    """
    ...


__all__ = [
    "ASRModel",
    "EncDecCTCModel",
    "models",
]
