"""
Type stubs for PyTorch (torch) library.

Minimal stubs covering the subset used in audio-extraction-analysis.
For full PyTorch type coverage, install torch-stubs package.
"""

from typing import Any, Literal, overload


class Tensor:
    """PyTorch tensor."""

    def to(self, device: str | device) -> Tensor: ...
    def cpu(self) -> Tensor: ...
    def cuda(self, device: int | None = None) -> Tensor: ...
    @property
    def shape(self) -> tuple[int, ...]: ...
    @property
    def device(self) -> device: ...


class device:
    """PyTorch device."""

    def __init__(self, type: str, index: int | None = None) -> None: ...
    @property
    def type(self) -> str: ...
    @property
    def index(self) -> int | None: ...


class cuda:
    """CUDA utilities."""

    @staticmethod
    def is_available() -> bool:
        """Check if CUDA is available.

        Returns:
            True if CUDA GPU is available
        """
        ...

    @staticmethod
    def device_count() -> int:
        """Get number of available CUDA devices.

        Returns:
            Number of CUDA devices
        """
        ...

    @staticmethod
    def get_device_name(device: int | device | None = None) -> str:
        """Get name of CUDA device.

        Args:
            device: Device index or device object

        Returns:
            Device name string
        """
        ...

    @staticmethod
    def get_device_properties(device: int | device) -> Any:
        """Get properties of CUDA device.

        Args:
            device: Device index or device object

        Returns:
            Device properties object
        """
        ...

    @staticmethod
    def memory_allocated(device: int | device | None = None) -> int:
        """Get currently allocated memory on device.

        Args:
            device: Device index or device object

        Returns:
            Bytes of memory allocated
        """
        ...

    @staticmethod
    def memory_reserved(device: int | device | None = None) -> int:
        """Get total reserved memory on device.

        Args:
            device: Device index or device object

        Returns:
            Bytes of memory reserved
        """
        ...

    @staticmethod
    def max_memory_allocated(device: int | device | None = None) -> int:
        """Get maximum memory allocated on device.

        Args:
            device: Device index or device object

        Returns:
            Maximum bytes of memory allocated
        """
        ...

    @staticmethod
    def reset_peak_memory_stats(device: int | device | None = None) -> None:
        """Reset peak memory statistics.

        Args:
            device: Device index or device object
        """
        ...

    @staticmethod
    def empty_cache() -> None:
        """Release all unoccupied cached memory."""
        ...

    @staticmethod
    def synchronize(device: int | device | None = None) -> None:
        """Wait for all kernels in all streams on device to complete.

        Args:
            device: Device index or device object
        """
        ...


def load(
    f: str | Any,
    map_location: str | device | dict[str, str] | None = None,
    pickle_module: Any = None,
    **pickle_load_args: Any,
) -> Any:
    """Load a saved object.

    Args:
        f: File path or file-like object
        map_location: Device location for loading
        pickle_module: Custom pickle module
        **pickle_load_args: Additional pickle arguments

    Returns:
        Loaded object
    """
    ...


def save(obj: Any, f: str | Any, pickle_module: Any = None, **pickle_save_args: Any) -> None:
    """Save an object.

    Args:
        obj: Object to save
        f: File path or file-like object
        pickle_module: Custom pickle module
        **pickle_save_args: Additional pickle arguments
    """
    ...


def no_grad() -> Any:
    """Context manager for disabling gradient calculation.

    Returns:
        Context manager
    """
    ...


def inference_mode() -> Any:
    """Context manager for inference mode.

    Returns:
        Context manager
    """
    ...


__all__ = [
    "Tensor",
    "device",
    "cuda",
    "load",
    "save",
    "no_grad",
    "inference_mode",
]
