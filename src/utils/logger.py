"""Standardized logger utility for the entire application.

This module provides backwards-compatible logging functions that use loguru
as the backend while maintaining the familiar API:

    from src.utils.logger import get_logger
    logger = get_logger(__name__)
    logger.info("Message")

The loguru backend provides:
- Structured JSON logging for AI/RCA analysis
- Automatic exception tracing with variable values
- Context binding for request tracing
- Colorized console output
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from .loguru_config import (
    configure_loguru,
    configure_verbose,
    set_level,
)
from .loguru_config import (
    get_logger as _get_loguru_logger,
)
from .loguru_config import (
    reset as reset_loguru,
)

if TYPE_CHECKING:
    from loguru import Logger


def get_logger(name: str | None = None) -> Any:
    """Get a configured logger instance.

    Args:
        name: Logger name (defaults to caller's __name__)

    Returns:
        Configured loguru logger instance bound with module name

    Usage:
        from src.utils.logger import get_logger
        logger = get_logger(__name__)
        logger.info("Application started")
        logger.debug("Debug info", request_id="abc123")
    """
    return _get_loguru_logger(name)


def configure_logger(
    level: str = "INFO",
    format_string: str | None = None,
    add_file_handler: bool = False,
    file_path: str | None = None,
) -> None:
    """Configure the root logger with standard settings.

    This function provides backwards compatibility with the previous logging API.
    Parameters are mapped to loguru equivalents where possible.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format_string: Custom format string (ignored - loguru uses its own format)
        add_file_handler: Whether to add file handler (loguru adds by default)
        file_path: Path to log file (used as log directory parent)
    """
    log_dir = None
    if add_file_handler and file_path:
        log_dir = Path(file_path).parent

    configure_loguru(
        log_dir=log_dir,
        level=level.upper(),
        console=True,
        json_file=add_file_handler,
        debug_file=add_file_handler,
    )


# Re-export for convenience
__all__ = [
    "configure_logger",
    "configure_verbose",
    "get_logger",
    "reset_loguru",
    "set_level",
]
