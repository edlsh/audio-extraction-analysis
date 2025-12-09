"""Centralized loguru configuration for AI-assisted debugging and root cause analysis.

This module configures loguru for structured logging with features optimized for:
- AI coding assistant debugging (context-rich, parseable logs)
- Root cause analysis (exception tracing with variable values)
- Local development (colorized console output)
- Production readiness (JSON file logging with rotation)
- TUI integration (route logs to event system)

Usage:
    from src.utils.loguru_config import configure_loguru, get_logger

    configure_loguru()  # Call once at application startup
    logger = get_logger(__name__)
    logger.info("Starting process", extra_context="value")

    # For TUI mode:
    from src.utils.loguru_config import set_tui_mode
    set_tui_mode(enabled=True, event_sink=my_sink)  # Route logs to TUI
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

from loguru import logger

if TYPE_CHECKING:
    from loguru import Logger


class EventSinkProtocol(Protocol):
    """Protocol for event sinks that can receive log events."""

    def emit(self, event: Any) -> None:
        """Emit an event to the sink."""
        ...


class TuiEventSink:
    """Custom loguru sink that emits TUI events.

    This sink converts loguru log records into TUI Event objects and emits them
    to the provided event sink, allowing logs to appear in the TUI LogPanel.

    Args:
        event_sink: Event sink implementing emit(Event) method

    Example:
        >>> sink = TuiEventSink(queue_event_sink)
        >>> logger.add(sink, level="DEBUG")
    """

    def __init__(self, event_sink: EventSinkProtocol) -> None:
        """Initialize with target event sink.

        Args:
            event_sink: Sink to emit events to (e.g., QueueEventSink)
        """
        self._event_sink = event_sink

    def __call__(self, message: Any) -> None:
        """Handle loguru message by emitting TUI event.

        Args:
            message: Loguru message object with .record attribute
        """
        # Import here to avoid circular imports
        from src.models.events import Event

        record = message.record
        level_name = record["level"].name

        # Map loguru levels to event types
        if level_name in ("WARNING", "WARN"):
            event_type = "warning"
        elif level_name in ("ERROR", "CRITICAL"):
            event_type = "error"
        else:
            event_type = "log"

        event = Event(
            type=event_type,
            data={
                "message": record["message"],
                "level": level_name,
                "logger": record.get("name", record["module"]),
            },
        )
        self._event_sink.emit(event)


# Module-level state
_configured = False
_log_dir = Path("logs")
_console_level = "DEBUG"
_tui_mode = False
_tui_handler_id: int | None = None
_console_handler_id: int | None = None


def configure_loguru(
    log_dir: Path | str | None = None,
    level: str = "DEBUG",
    console: bool = True,
    json_file: bool = True,
    debug_file: bool = True,
) -> None:
    """Configure loguru for the entire application.

    This function should be called once at application startup. Subsequent calls
    are ignored to prevent duplicate handlers.

    Args:
        log_dir: Directory for log files (default: "logs")
        level: Minimum log level for console output (default: "DEBUG")
        console: Enable colorized console output (default: True)
        json_file: Enable JSON log file for structured analysis (default: True)
        debug_file: Enable verbose debug log file (default: True)

    Features enabled:
        - Console: Colorized output with module:function:line context
        - JSON file: Structured logs for AI/RCA parsing (5MB rotation, 7-day retention)
        - Debug file: Full verbose logs for deep debugging (10MB rotation, 3-day retention)
        - Exception diagnosis: Variable values included in tracebacks
    """
    global _configured, _log_dir, _console_level, _console_handler_id

    if _configured:
        return

    if log_dir:
        _log_dir = Path(log_dir)

    _log_dir.mkdir(parents=True, exist_ok=True)
    _console_level = level

    # Remove default handler
    logger.remove()

    # Console handler: colorized, human-readable
    if console:
        _console_handler_id = logger.add(
            sys.stderr,
            level=level,
            format=(
                "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
                "<level>{level: <8}</level> | "
                "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
                "<level>{message}</level>"
                "{exception}"
            ),
            colorize=True,
            backtrace=True,
            diagnose=True,  # Include variable values in exceptions
        )

    # JSON file handler: structured for AI/RCA analysis
    if json_file:
        logger.add(
            _log_dir / "app.json",
            level="DEBUG",
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level} | {name}:{function}:{line} | {message}",
            serialize=True,  # JSON output
            rotation="5 MB",
            retention="7 days",
            compression="gz",
            backtrace=True,
            diagnose=True,
        )

    # Debug file handler: verbose text logs
    if debug_file:
        logger.add(
            _log_dir / "debug.log",
            level="DEBUG",
            format=(
                "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | "
                "{name}:{function}:{line} | {message}"
            ),
            rotation="10 MB",
            retention="3 days",
            backtrace=True,
            diagnose=True,
        )

    _configured = True
    logger.debug("Loguru configured", log_dir=str(_log_dir), level=level)


def get_logger(name: str | None = None) -> Logger:
    """Get a loguru logger bound with the given module name.

    This function maintains API compatibility with the standard logging pattern:
        logger = get_logger(__name__)

    The returned logger has the module name bound as context, which appears
    in log output as {name}.

    Args:
        name: Module name (typically __name__). If None, uses "audio_extraction_analysis"

    Returns:
        Loguru logger instance bound with module context
    """
    global _configured

    # Auto-configure with defaults if not already configured
    if not _configured:
        configure_loguru()

    if name is None:
        # Try to get caller's module name
        import inspect

        frame = inspect.currentframe()
        if frame and frame.f_back:
            name = frame.f_back.f_globals.get("__name__", "audio_extraction_analysis")
        else:
            name = "audio_extraction_analysis"

    return logger.bind(name=name)


def set_level(name: str, level: str) -> None:
    """Set the logging level filter for a specific module.

    Note: Loguru uses a different filtering mechanism than stdlib logging.
    This function adds a filter that only affects messages from the specified module.

    Args:
        name: Module name to filter
        level: Level name (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    # Loguru handles this through filtering - for now, this is a placeholder
    # that maintains API compatibility. Full filtering requires custom handlers.
    logger.debug(f"Level filter requested for {name}: {level}")


def configure_verbose(verbose: bool = False) -> None:
    """Configure verbosity for all loggers.

    Args:
        verbose: If True, sets DEBUG level. If False, sets INFO level.
    """
    global _configured

    level = "DEBUG" if verbose else "INFO"

    # Reconfigure by removing all handlers and adding new ones
    logger.remove()
    _configured = False
    configure_loguru(log_dir=_log_dir, level=level)


def reset() -> None:
    """Reset loguru configuration (primarily for testing)."""
    global _configured
    logger.remove()
    _configured = False


def set_tui_mode(enabled: bool, event_sink: EventSinkProtocol | None = None) -> None:
    """Enable or disable TUI mode logging.

    When enabled, this function:
    1. Removes the console (stderr) handler to prevent raw logs appearing in TUI
    2. Adds a TUI event sink that routes logs to the TUI LogPanel

    When disabled, it restores normal console logging.

    Args:
        enabled: If True, enables TUI mode. If False, disables it.
        event_sink: Event sink implementing emit(Event) method (required when enabling).

    Raises:
        ValueError: If enabled=True but event_sink is None.
    """
    global _tui_mode, _tui_handler_id, _console_handler_id

    if enabled:
        if event_sink is None:
            raise ValueError("event_sink is required when enabling TUI mode")

        if not _tui_mode:
            # Remove the console handler to prevent raw logs in TUI
            if _console_handler_id is not None:
                try:
                    logger.remove(_console_handler_id)
                except ValueError:
                    pass  # Handler already removed

            # Add the TUI sink to route logs to the TUI LogPanel
            _tui_handler_id = logger.add(TuiEventSink(event_sink), level="DEBUG")
            _tui_mode = True
    else:
        if _tui_mode:
            # Remove the TUI sink
            if _tui_handler_id is not None:
                try:
                    logger.remove(_tui_handler_id)
                except ValueError:
                    pass  # Handler already removed
                _tui_handler_id = None

            # Restore the console handler
            _console_handler_id = logger.add(
                sys.stderr,
                level=_console_level,
                format=(
                    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
                    "<level>{level: <8}</level> | "
                    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
                    "<level>{message}</level>"
                    "{exception}"
                ),
                colorize=True,
                backtrace=True,
                diagnose=True,
            )

            _tui_mode = False


# Type alias for backwards compatibility
LoguruLogger = Any  # loguru.Logger at runtime
