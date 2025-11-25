"""
Type stubs for python-dotenv library.

This stub file provides type annotations for dotenv,
which ships with partial type information.
"""

from typing import Any
from pathlib import Path
from os import PathLike


def load_dotenv(
    dotenv_path: str | PathLike[str] | None = None,
    stream: Any = None,
    verbose: bool = False,
    override: bool = False,
    interpolate: bool = True,
    encoding: str | None = "utf-8",
) -> bool:
    """Load environment variables from .env file.

    Args:
        dotenv_path: Path to .env file (searches parent dirs if None)
        stream: Text stream to read from instead of file
        verbose: Whether to print debug output
        override: Whether to override existing environment variables
        interpolate: Whether to interpolate variables
        encoding: File encoding

    Returns:
        True if .env file was found and loaded, False otherwise
    """
    ...


def find_dotenv(
    filename: str = ".env",
    raise_error_if_not_found: bool = False,
    usecwd: bool = False,
) -> str:
    """Find .env file by searching parent directories.

    Args:
        filename: Name of file to find
        raise_error_if_not_found: Whether to raise IOError if not found
        usecwd: Whether to start search from current working directory

    Returns:
        Path to .env file or empty string if not found
    """
    ...


def dotenv_values(
    dotenv_path: str | PathLike[str] | None = None,
    stream: Any = None,
    verbose: bool = False,
    interpolate: bool = True,
    encoding: str | None = "utf-8",
) -> dict[str, str | None]:
    """Parse .env file and return as dictionary.

    Args:
        dotenv_path: Path to .env file
        stream: Text stream to read from instead of file
        verbose: Whether to print debug output
        interpolate: Whether to interpolate variables
        encoding: File encoding

    Returns:
        Dictionary of environment variables
    """
    ...


def set_key(
    dotenv_path: str | PathLike[str],
    key_to_set: str,
    value_to_set: str,
    quote_mode: str = "always",
    export: bool = False,
    encoding: str | None = "utf-8",
) -> tuple[bool | None, str, str]:
    """Set or update a key in .env file.

    Args:
        dotenv_path: Path to .env file
        key_to_set: Variable name to set
        value_to_set: Value to set
        quote_mode: Quote mode ('always', 'auto', 'never')
        export: Whether to prefix with 'export '
        encoding: File encoding

    Returns:
        Tuple of (success, key, value)
    """
    ...


def unset_key(
    dotenv_path: str | PathLike[str],
    key_to_unset: str,
    quote_mode: str = "always",
    encoding: str | None = "utf-8",
) -> tuple[bool | None, str]:
    """Remove a key from .env file.

    Args:
        dotenv_path: Path to .env file
        key_to_unset: Variable name to remove
        quote_mode: Quote mode ('always', 'auto', 'never')
        encoding: File encoding

    Returns:
        Tuple of (success, key)
    """
    ...


def get_key(
    dotenv_path: str | PathLike[str],
    key_to_get: str,
    encoding: str | None = "utf-8",
) -> str | None:
    """Get value of a key from .env file.

    Args:
        dotenv_path: Path to .env file
        key_to_get: Variable name to get
        encoding: File encoding

    Returns:
        Value of the key or None if not found
    """
    ...


__all__ = [
    "load_dotenv",
    "find_dotenv",
    "dotenv_values",
    "set_key",
    "unset_key",
    "get_key",
]
