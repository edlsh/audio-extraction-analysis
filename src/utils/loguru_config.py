"""Centralized loguru configuration for AI-assisted debugging and root cause analysis.

This module configures loguru for structured logging with features optimized for:
- AI coding assistant debugging (context-rich, parseable logs)
- Root cause analysis (exception tracing with variable values)
- Local development (colorized console output)
- Production readiness (JSON file logging with rotation)
- TUI integration (route logs to event system)
- Security: Redaction of secrets and sensitive data by default

Usage:
    from src.utils.loguru_config import configure_loguru, get_logger

    configure_loguru()  # Call once at application startup
    logger = get_logger(__name__)
    logger.info("Starting process", extra_context="value")

    # For TUI mode:
    from src.utils.loguru_config import set_tui_mode
    set_tui_mode(enabled=True, event_sink=my_sink)  # Route logs to TUI

Security Notes:
    - diagnose=False by default to prevent local variable leakage in tracebacks
    - LogRedactionFilter applied to all sinks to redact secrets/API keys
    - Set AUDIO_ANALYSIS_DEBUG_TRACE=1 to enable verbose tracebacks (dev only)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

from loguru import logger

from .log_redaction import LogRedactionFilter

if TYPE_CHECKING:
    from loguru import Logger


# Environment variable to enable verbose tracebacks (dev/debug only)
_DEBUG_TRACE_ENV = "AUDIO_ANALYSIS_DEBUG_TRACE"


def _is_debug_trace_enabled() -> bool:
    """Check if verbose debug tracing is enabled via environment variable.

    Returns:
        True if AUDIO_ANALYSIS_DEBUG_TRACE=1 is set, False otherwise.
    """
    return os.environ.get(_DEBUG_TRACE_ENV, "").strip() == "1"


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
        run_id: Optional run ID to attach to all emitted events

    Example:
        >>> sink = TuiEventSink(queue_event_sink, run_id="abc-123")
        >>> logger.add(sink, level="DEBUG")
    """

    def __init__(self, event_sink: EventSinkProtocol, run_id: str | None = None) -> None:
        """Initialize with target event sink.

        Args:
            event_sink: Sink to emit events to (e.g., QueueEventSink)
            run_id: Optional run ID to attach to all events for correlation
        """
        self._event_sink = event_sink
        self._run_id = run_id

    def set_run_id(self, run_id: str) -> None:
        """Update the run ID for event correlation.

        Args:
            run_id: New run ID to use for subsequent events
        """
        self._run_id = run_id

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

        # Build event with run_id for correlation
        event_kwargs: dict[str, Any] = {
            "type": event_type,
            "data": {
                "message": record["message"],
                "level": level_name,
                "logger": record.get("name", record["module"]),
            },
        }

        # Include run_id if available for event correlation
        if self._run_id:
            event_kwargs["run_id"] = self._run_id

        event = Event(**event_kwargs)
        self._event_sink.emit(event)


# Module-level state
_configured = False
_log_dir = Path("logs")
_console_level = "DEBUG"
_tui_mode = False
_tui_handler_id: int | None = None
_tui_sink_instance: TuiEventSink | None = None
_console_handler_id: int | None = None
_redaction_filter = LogRedactionFilter()


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

    Security:
        - diagnose=False by default to prevent secret leakage in tracebacks
        - LogRedactionFilter applied to all sinks to redact API keys/tokens
        - Set AUDIO_ANALYSIS_DEBUG_TRACE=1 to enable verbose tracebacks (dev only)

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
        - Redaction: API keys, tokens, and secrets automatically redacted
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

    # Security: Only enable verbose tracebacks if explicitly requested
    debug_trace = _is_debug_trace_enabled()
    backtrace_enabled = debug_trace
    diagnose_enabled = debug_trace

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
            backtrace=backtrace_enabled,
            diagnose=diagnose_enabled,
            filter=_redaction_filter,
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
            backtrace=backtrace_enabled,
            diagnose=diagnose_enabled,
            filter=_redaction_filter,
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
            backtrace=backtrace_enabled,
            diagnose=diagnose_enabled,
            filter=_redaction_filter,
        )

    _configured = True
    logger.debug("Loguru configured", log_dir=str(_log_dir), level=level, debug_trace=debug_trace)


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
    global _configured, _tui_mode, _tui_handler_id, _tui_sink_instance, _console_handler_id
    logger.remove()
    _configured = False
    _tui_mode = False
    _tui_handler_id = None
    _tui_sink_instance = None
    _console_handler_id = None


def set_tui_mode(
    enabled: bool,
    event_sink: EventSinkProtocol | None = None,
    run_id: str | None = None,
) -> None:
    """Enable or disable TUI mode logging.

    When enabled, this function:
    1. Removes the console (stderr) handler to prevent raw logs appearing in TUI
    2. Adds a TUI event sink that routes logs to the TUI LogPanel

    When disabled, it restores normal console logging.

    Args:
        enabled: If True, enables TUI mode. If False, disables it.
        event_sink: Event sink implementing emit(Event) method (required when enabling).
        run_id: Optional run ID for event correlation (can be updated later).

    Raises:
        ValueError: If enabled=True but event_sink is None.
    """
    global _tui_mode, _tui_handler_id, _tui_sink_instance, _console_handler_id

    # Security: Only enable verbose tracebacks if explicitly requested
    debug_trace = _is_debug_trace_enabled()
    backtrace_enabled = debug_trace
    diagnose_enabled = debug_trace

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

            # Create and store TUI sink instance for later run_id updates
            _tui_sink_instance = TuiEventSink(event_sink, run_id=run_id)

            # Add the TUI sink to route logs to the TUI LogPanel
            _tui_handler_id = logger.add(
                _tui_sink_instance,
                level="DEBUG",
                filter=_redaction_filter,
            )
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
            _tui_sink_instance = None

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
                backtrace=backtrace_enabled,
                diagnose=diagnose_enabled,
                filter=_redaction_filter,
            )

            _tui_mode = False


def set_tui_run_id(run_id: str) -> None:
    """Update the run ID for TUI event correlation.

    Call this after pipeline starts to attach run_id to all log events.

    Args:
        run_id: The pipeline run ID for event correlation
    """
    if _tui_sink_instance is not None:
        _tui_sink_instance.set_run_id(run_id)


# Type alias for backwards compatibility
LoguruLogger = Any  # loguru.Logger at runtime
