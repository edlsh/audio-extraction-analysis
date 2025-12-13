"""GPU resource management for Parakeet models."""

from __future__ import annotations

import gc
from typing import TYPE_CHECKING

from src.utils.logger import get_logger

from .deps import TORCH_AVAILABLE, torch

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


class GPUManager:
    """Manages GPU resources for Parakeet models."""

    def __init__(self) -> None:
        """Initialize GPU manager with device detection."""
        self._device: str | None = None
        self._device_id: int | None = None
        if TORCH_AVAILABLE:
            self._device = self._detect_best_device()
            if self._device.startswith("cuda"):
                self._device_id = int(self._device.split(":")[-1]) if ":" in self._device else 0

    @property
    def device(self) -> str:
        """Get the current device string (e.g., 'cuda:0', 'cpu')."""
        if not self._device:
            return "cpu"
        return self._device

    @property
    def device_id(self) -> int | None:
        """Get the CUDA device ID if using GPU."""
        return self._device_id

    def _detect_best_device(self) -> str:
        """Detect the best available device for model execution."""
        if not TORCH_AVAILABLE:
            return "cpu"

        try:
            cuda_device = self._detect_cuda_device()
            if cuda_device:
                return cuda_device

            if self._is_mps_available():
                logger.info("Using Apple Metal Performance Shaders (MPS)")
                return "mps"
        except Exception as e:
            logger.warning(f"Error detecting GPU device: {e}")

        return "cpu"

    def _detect_cuda_device(self) -> str | None:
        """Detect best CUDA device. Returns device string or None."""
        if not torch.cuda.is_available():
            return None

        device_count = torch.cuda.device_count()
        if device_count == 0:
            return None

        best_device = 0
        max_free_memory = 0

        for i in range(device_count):
            free_memory = torch.cuda.mem_get_info(i)[0]
            if free_memory > max_free_memory:
                max_free_memory = free_memory
                best_device = i

        logger.info(
            f"Selected CUDA device {best_device} with {max_free_memory / 1e9:.2f}GB free memory"
        )
        return f"cuda:{best_device}"

    @staticmethod
    def _is_mps_available() -> bool:
        """Check if Apple MPS is available."""
        return hasattr(torch.backends, "mps") and torch.backends.mps.is_available()

    def get_available_memory(self) -> int | None:
        """Get available memory on current device in bytes."""
        if not TORCH_AVAILABLE:
            return None

        try:
            if self._device and self._device.startswith("cuda"):
                if self._device_id is not None:
                    free, _total = torch.cuda.mem_get_info(self._device_id)
                    return free
            elif self._device == "mps":
                return 4 * 1024 * 1024 * 1024  # 4GB conservative estimate
        except Exception as e:
            logger.warning(f"Could not get available memory: {e}")

        return None

    def can_allocate_model(self, estimated_model_size: int) -> bool:
        """Check if there's enough memory to allocate a model."""
        available = self.get_available_memory()
        if available is None:
            return True

        buffer = 500 * 1024 * 1024  # 500MB buffer
        return available > (estimated_model_size + buffer)

    def cleanup_gpu_memory(self) -> None:
        """Force GPU memory cleanup."""
        if not TORCH_AVAILABLE:
            return

        try:
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                logger.debug("GPU memory cache cleared")
        except Exception as e:
            logger.warning(f"Error cleaning up GPU memory: {e}")


__all__ = ["GPUManager"]
