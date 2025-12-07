"""Centralized logging factory for consistent logger creation across the application.

This module provides a singleton-based logging factory that uses loguru as the
backend while maintaining the same API as the original stdlib-based implementation.

Usage:
    # Explicit initialization (optional - auto-initializes on first use)
    LoggingFactory.initialize(log_dir=Path("logs"), level="INFO")

    # Get a logger for your module
    logger = LoggingFactory.get_logger(__name__)
    logger.info("Application started")

    # Or use the convenience function
    from src.utils.logging_factory import get_logger
    logger = get_logger(__name__)
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from .loguru_config import (
    configure_loguru,
)
from .loguru_config import (
    configure_verbose as _configure_verbose,
)
from .loguru_config import (
    get_logger as _get_loguru_logger,
)
from .loguru_config import (
    reset as _reset_loguru,
)
from .loguru_config import (
    set_level as _set_level,
)

if TYPE_CHECKING:
    from loguru import Logger


class LoggingFactory:
    """Factory for creating and configuring loggers consistently.

    This class provides a singleton pattern for logging configuration using
    loguru as the backend. The API remains compatible with the original
    stdlib-based implementation.

    Class Attributes:
        _initialized: Flag to ensure single initialization
        _log_dir: Directory path where log files are stored
    """

    _initialized = False
    _log_dir = Path("logs")

    @classmethod
    def initialize(
        cls,
        log_dir: Path | None = None,
        level: int | str = "INFO",
        format_string: str | None = None,
    ) -> None:
        """Initialize the logging system once for the entire application.

        This method uses a singleton pattern - initialization only happens once.
        Uses loguru as the backend.

        Args:
            log_dir: Directory for log files. If None, uses "logs".
            level: Logging level (default: "INFO"). Can be int or string.
            format_string: Custom format string (ignored - loguru uses its own).

        Side Effects:
            - Creates log_dir if it doesn't exist
            - Configures loguru with file and console handlers
            - Sets _initialized flag to prevent re-initialization
        """
        if cls._initialized:
            return

        if log_dir:
            cls._log_dir = log_dir

        # Convert int level to string if needed (stdlib compatibility)
        if isinstance(level, int):
            import logging

            level_map = {
                logging.DEBUG: "DEBUG",
                logging.INFO: "INFO",
                logging.WARNING: "WARNING",
                logging.ERROR: "ERROR",
                logging.CRITICAL: "CRITICAL",
            }
            level = level_map.get(level, "INFO")

        configure_loguru(
            log_dir=cls._log_dir,
            level=level,
            console=True,
            json_file=True,
            debug_file=True,
        )

        cls._initialized = True

    @classmethod
    def get_logger(cls, name: str) -> Any:
        """Get a configured logger for the given module name.

        This method automatically initializes the logging system with default
        settings if initialize() has not been called explicitly.

        Args:
            name: Module name for the logger. Typically __name__.

        Returns:
            Loguru logger instance bound with module context.
        """
        if not cls._initialized:
            cls.initialize()

        return _get_loguru_logger(name)

    @classmethod
    def set_level(cls, name: str, level: int | str) -> None:
        """Set the logging level for a specific logger.

        Args:
            name: Logger name to configure.
            level: Logging level (int or string).
        """
        if isinstance(level, int):
            import logging

            level_map = {
                logging.DEBUG: "DEBUG",
                logging.INFO: "INFO",
                logging.WARNING: "WARNING",
                logging.ERROR: "ERROR",
                logging.CRITICAL: "CRITICAL",
            }
            level = level_map.get(level, "INFO")

        _set_level(name, level)

    @classmethod
    def configure_verbose(cls, verbose: bool = False) -> None:
        """Configure verbosity for all loggers.

        Args:
            verbose: If True, sets DEBUG level. If False, sets INFO level.
        """
        _configure_verbose(verbose)

    @classmethod
    def reset(cls) -> None:
        """Reset the factory state (primarily for testing)."""
        cls._initialized = False
        cls._log_dir = Path("logs")
        _reset_loguru()


# Convenience function for backward compatibility
def get_logger(name: str) -> Any:
    """Get a configured logger for the given module name.

    This is a convenience function that delegates to LoggingFactory.get_logger().

    Args:
        name: Module name for the logger. Typically __name__.

    Returns:
        Loguru logger instance bound with module context.
    """
    return LoggingFactory.get_logger(name)
