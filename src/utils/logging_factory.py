"""Centralized logging factory for consistent logger creation across the application.

This module provides a singleton-based logging factory that ensures consistent
logger configuration throughout the application. It handles:
- Automatic initialization of the logging system
- Centralized log file management
- Consistent formatting across all loggers
- Per-module logging level configuration
- Easy verbosity control for debugging

Usage:
    # Explicit initialization (optional - auto-initializes on first use)
    LoggingFactory.initialize(log_dir=Path("logs"), level=logging.INFO)

    # Get a logger for your module
    logger = LoggingFactory.get_logger(__name__)
    logger.info("Application started")

    # Or use the convenience function
    from utils.logging_factory import get_logger
    logger = get_logger(__name__)
"""

from __future__ import annotations

import logging
from pathlib import Path


class LoggingFactory:
    """Factory for creating and configuring loggers consistently.

    This class implements a singleton pattern for logging configuration,
    ensuring that the logging system is initialized only once regardless
    of how many times initialize() is called.

    The factory provides:
    - Automatic creation of log directory
    - Dual output to both file (app.log) and console
    - Consistent formatting across all loggers
    - Per-module logging level control
    - Lazy initialization (auto-initializes on first get_logger call)

    Class Attributes:
        _initialized: Flag to ensure single initialization
        _log_dir: Directory path where log files are stored
    """

    _initialized = False  # Tracks whether logging system has been configured
    _log_dir = Path("logs")  # Default directory for log file storage

    @classmethod
    def initialize(
        cls,
        log_dir: Path | None = None,
        level: int = logging.INFO,
        format_string: str | None = None,
    ) -> None:
        """Initialize the logging system once for the entire application.

        This method uses a singleton pattern - it only performs initialization
        on the first call and ignores subsequent calls. It configures:
        - Root logger with the specified level
        - Dual output handlers (file and console)
        - Log file directory creation
        - Module-specific logging levels (transcription=DEBUG, audio_extraction=INFO)

        Note: Calling this method is optional. The factory will auto-initialize
        with defaults when get_logger() is first called.

        Args:
            log_dir: Directory for log files. If None, uses "logs" in current directory.
            level: Default logging level for root logger (default: logging.INFO).
                   Valid values: logging.DEBUG, logging.INFO, logging.WARNING,
                   logging.ERROR, logging.CRITICAL
            format_string: Custom format string for log messages. If None, uses:
                          "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

        Side Effects:
            - Creates log_dir if it doesn't exist
            - Configures root logger with file and console handlers
            - Sets specific levels for 'transcription' and 'audio_extraction' loggers
            - Sets _initialized flag to prevent re-initialization
        """
        # Skip initialization if already done (singleton pattern enforcement)
        if cls._initialized:
            return

        # Use provided log directory or keep default
        if log_dir:
            cls._log_dir = log_dir

        # Create log directory structure if it doesn't exist
        cls._log_dir.mkdir(parents=True, exist_ok=True)

        # Use default format if custom format not provided
        if format_string is None:
            format_string = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

        # Configure root logger with file and console output
        logging.basicConfig(
            level=level,
            format=format_string,
            handlers=[logging.FileHandler(cls._log_dir / "app.log"), logging.StreamHandler()],
        )

        # Set component-specific logging levels for fine-grained control
        logging.getLogger("transcription").setLevel(logging.DEBUG)
        logging.getLogger("audio_extraction").setLevel(logging.INFO)

        # Mark as initialized to prevent duplicate configuration
        cls._initialized = True

    @classmethod
    def get_logger(cls, name: str) -> logging.Logger:
        """Get a configured logger for the given module name.

        This method automatically initializes the logging system with default
        settings if initialize() has not been called explicitly. This lazy
        initialization ensures logging works without manual setup.

        Best Practice: Use __name__ as the logger name to identify the source module.

        Args:
            name: Module name for the logger. Typically __name__ for automatic
                  module identification, or a custom string for component-specific
                  loggers (e.g., 'transcription', 'audio_extraction').

        Returns:
            Configured logger instance ready for use.

        Example:
            logger = LoggingFactory.get_logger(__name__)
            logger.info("Starting process")
            logger.debug("Debug information")
        """
        # Auto-initialize with defaults if not explicitly initialized
        if not cls._initialized:
            cls.initialize()

        return logging.getLogger(name)

    @classmethod
    def set_level(cls, name: str, level: int) -> None:
        """Set the logging level for a specific logger.

        This can be called at any time to dynamically adjust logging verbosity
        for individual loggers without affecting others. Useful for debugging
        specific components.

        Args:
            name: Logger name to configure. Should match a logger name used
                  in get_logger() calls (e.g., 'transcription', 'audio_extraction',
                  or a module name like 'src.processors.audio').
            level: Logging level to set. Valid values:
                   - logging.DEBUG (10): Detailed diagnostic information
                   - logging.INFO (20): General informational messages
                   - logging.WARNING (30): Warning messages
                   - logging.ERROR (40): Error messages
                   - logging.CRITICAL (50): Critical errors

        Example:
            # Enable debug logging for transcription component only
            LoggingFactory.set_level('transcription', logging.DEBUG)
        """
        logging.getLogger(name).setLevel(level)

    @classmethod
    def configure_verbose(cls, verbose: bool = False) -> None:
        """Configure verbosity for all loggers.

        This is a convenience method for quickly switching between normal and
        verbose logging modes across the entire application. It affects:
        - Root logger
        - 'src' logger (application code)
        - 'transcription' logger
        - 'audio_extraction' logger

        Args:
            verbose: If True, sets all affected loggers to DEBUG level for
                    detailed diagnostic output. If False, sets to INFO level
                    for normal operation (default: False).

        Example:
            # Enable verbose mode for debugging
            LoggingFactory.configure_verbose(verbose=True)

            # Return to normal logging
            LoggingFactory.configure_verbose(verbose=False)
        """
        level = logging.DEBUG if verbose else logging.INFO

        # Configure root and application loggers
        logging.getLogger().setLevel(level)
        logging.getLogger("src").setLevel(level)

        # Update component-specific loggers based on verbosity
        if verbose:
            logging.getLogger("transcription").setLevel(logging.DEBUG)
            logging.getLogger("audio_extraction").setLevel(logging.DEBUG)
        else:
            logging.getLogger("transcription").setLevel(logging.INFO)
            logging.getLogger("audio_extraction").setLevel(logging.INFO)


# Convenience function for backward compatibility and simpler imports
def get_logger(name: str) -> logging.Logger:
    """Get a configured logger for the given module name.

    This is a convenience function that provides a simpler import path and
    maintains backward compatibility with the old logging_config module.
    It delegates to LoggingFactory.get_logger() internally.

    Usage Choice:
        - Use this function for cleaner imports: `from utils.logging_factory import get_logger`
        - Use LoggingFactory.get_logger() when you need other factory methods too

    Both approaches are functionally identical and support auto-initialization.

    Args:
        name: Module name for the logger. Typically __name__ for automatic
              module identification.

    Returns:
        Configured logger instance ready for use.

    Example:
        from utils.logging_factory import get_logger
        logger = get_logger(__name__)
        logger.info("Application started")
    """
    return LoggingFactory.get_logger(name)
