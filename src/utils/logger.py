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
from typing import Any

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


def log_operation(
    logger: Any,
    operation: str,
    status: str,
    **context: Any,
) -> None:
    """Log an operation with structured context.

    Args:
        logger: Logger instance
        operation: Operation name (e.g., "transcribe", "health_check")
        status: Operation status (e.g., "started", "completed", "failed")
        **context: Additional context (file_path, provider, duration, etc.)
    """
    log_data = {"operation": operation, "status": status, **context}
    if status == "started":
        logger.debug(log_data)
    elif status == "completed":
        logger.info(log_data)
    elif status == "failed":
        logger.error(log_data)
    else:
        logger.warning(log_data)


def log_performance(
    logger: Any,
    operation: str,
    duration_seconds: float,
    **context: Any,
) -> None:
    """Log performance metrics.

    Args:
        logger: Logger instance
        operation: Operation name
        duration_seconds: Duration in seconds
        **context: Additional context
    """
    logger.info(
        {
            "operation": operation,
            "duration_seconds": duration_seconds,
            "performance": True,
            **context,
        }
    )


def log_api_call(
    logger: Any,
    provider: str,
    method: str,
    status: str,
    **context: Any,
) -> None:
    """Log API calls with provider context.

    Args:
        logger: Logger instance
        provider: Provider name (e.g., "deepgram", "elevenlabs")
        method: API method name (e.g., "transcribe_file", "health_check")
        status: Call status (e.g., "started", "success", "failed")
        **context: Additional context
    """
    logger.debug(
        {
            "api_call": True,
            "provider": provider,
            "method": method,
            "status": status,
            **context,
        }
    )


__all__ = [
    "configure_logger",
    "configure_verbose",
    "get_logger",
    "log_api_call",
    "log_operation",
    "log_performance",
    "reset_loguru",
    "set_level",
]
