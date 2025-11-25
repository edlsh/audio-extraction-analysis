"""Standardized logger utility for the entire application."""

from __future__ import annotations

import logging


def get_logger(name: str | None = None) -> logging.Logger:
    """Get a configured logger instance.

    Args:
        name: Logger name (defaults to caller's __name__)

    Returns:
        Configured logger instance

    Usage:
        from src.utils.logger import get_logger
        logger = get_logger(__name__)
    """
    if name is None:
        # Get caller's module name
        import inspect

        frame = inspect.currentframe()
        if frame and frame.f_back:
            name = frame.f_back.f_globals.get("__name__", "audio_extraction_analysis")
        else:
            name = "audio_extraction_analysis"

    return logging.getLogger(name)


def configure_logger(
    level: str = "INFO",
    format_string: str | None = None,
    add_file_handler: bool = False,
    file_path: str | None = None,
) -> None:
    """Configure the root logger with standard settings.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format_string: Custom format string
        add_file_handler: Whether to add file handler
        file_path: Path to log file if add_file_handler is True
    """
    if format_string is None:
        format_string = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    logging.basicConfig(
        level=getattr(logging, level.upper()), format=format_string, datefmt="%Y-%m-%d %H:%M:%S"
    )

    if add_file_handler and file_path:
        file_handler = logging.FileHandler(file_path)
        file_handler.setFormatter(logging.Formatter(format_string))
        logging.getLogger().addHandler(file_handler)
