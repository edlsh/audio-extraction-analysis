"""Console output with Rich formatting for CLI."""

from __future__ import annotations

import html
import json
import logging
import re
import sys
import time
from contextlib import contextmanager
from datetime import datetime
from typing import Any

from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeRemainingColumn,
)
from rich.table import Table


class ConsoleManager:
    """Console output with Rich formatting."""

    def __init__(self, verbose: bool = False, json_output: bool = False):
        self.verbose = verbose
        self.json_output = json_output
        self._json_max_field_length = 200
        self._json_max_nesting_depth = 10
        self.is_tty = sys.stderr.isatty()

        if self.json_output:
            self.console = None
        else:
            self.console = Console(stderr=True, force_terminal=True)

        self._active_progress: Progress | None = None

    def setup_logging(self, logger: logging.Logger) -> None:
        """Configure logging with Rich handler or JSON/plain formatter.

        Adds a handler and sets logger level based on `verbose`.
        """

        # Prevent duplicate handlers if called multiple times
        def _has_handler_of_type(h_type):
            return any(isinstance(h, h_type) for h in logger.handlers)

        if self.json_output:
            if not _has_handler_of_type(logging.StreamHandler):
                handler = logging.StreamHandler(sys.stderr)
                handler.setFormatter(logging.Formatter("%(message)s"))
                logger.addHandler(handler)
        else:
            if not _has_handler_of_type(RichHandler):
                handler = RichHandler(
                    console=self.console,
                    show_time=True,
                    show_path=self.verbose,
                    rich_tracebacks=True,
                )
                logger.addHandler(handler)
        logger.setLevel(logging.DEBUG if self.verbose else logging.INFO)

    @contextmanager
    def progress_context(self, description: str, total: int | None = None):
        """Progress context manager with cleanup."""
        task_id = None
        progress = None

        try:
            if self.json_output:
                tracker = JsonProgressTracker(description)
                yield tracker
                return
            elif self.is_tty and self.console is not None:
                progress = Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    BarColumn(),
                    TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                    TimeRemainingColumn(),
                    console=self.console,
                )
                progress.start()
                self._active_progress = progress
                task_id = progress.add_task(description, total=total or 100)
                tracker = RichProgressTracker(progress, task_id)
            else:
                tracker = FallbackProgressTracker(description)

            yield tracker

        except Exception as e:
            self._log_error(f"Progress context failed: {e}")
            raise
        finally:
            if progress and self._active_progress:
                try:
                    progress.stop()
                except Exception:
                    pass
                finally:
                    self._active_progress = None

    def print_stage(self, stage: str, status: str = "starting") -> None:
        """Print stage information with appropriate renderer."""
        if self.json_output:
            sanitized_stage = self._sanitize_json_field(stage)
            sanitized_status = self._sanitize_json_field(status)
            print(
                json.dumps(
                    {
                        "timestamp": self._get_timestamp(),
                        "stage": sanitized_stage,
                        "status": sanitized_status,
                    }
                ),
                file=sys.stderr,
            )
        elif self.console:
            status_color = {
                "starting": "blue",
                "complete": "green",
                "error": "red",
                "warning": "yellow",
            }.get(status, "white")

            self.console.print(Panel(f"[bold]{stage}[/bold]", style=status_color, padding=(0, 1)))
        else:
            print(f"[{status.upper()}] {stage}", file=sys.stderr)

    def print_summary(self, results: dict[str, Any]) -> None:
        """Print execution summary table or JSON/plain fallback."""
        if self.json_output:
            sanitized_results = self._sanitize_json_value(results)
            print(
                json.dumps(
                    {
                        "timestamp": self._get_timestamp(),
                        "type": "summary",
                        "results": sanitized_results,
                    }
                )
            )
        elif self.console:
            table = Table(title="Processing Summary")
            table.add_column("Stage", style="cyan")
            table.add_column("Duration", style="green")
            table.add_column("Status", style="bold")

            for stage, data in results.items():
                table.add_row(
                    stage,
                    f"{data.get('duration', 0):.1f}s",
                    str(data.get("status", "unknown")),
                )

            self.console.print(table)
        else:
            print("Processing Summary:", file=sys.stderr)
            for stage, data in results.items():
                print(
                    f"  {stage}: {data.get('status')} ({data.get('duration', 0):.1f}s)",
                    file=sys.stderr,
                )

    def _get_timestamp(self) -> str:
        """Get ISO timestamp for JSON output."""
        return datetime.now().isoformat()

    def _log_error(self, message: str) -> None:
        """Log error message to stderr."""
        if self.json_output:
            print(
                json.dumps(
                    {"timestamp": self._get_timestamp(), "type": "error", "message": message}
                ),
                file=sys.stderr,
            )
        elif self.console:
            self.console.print(f"[red]ERROR: {message}[/red]")
        else:
            print(f"ERROR: {message}", file=sys.stderr)

    def _sanitize_json_value(self, value: Any, depth: int = 0) -> Any:
        """Comprehensive JSON value sanitization with depth limiting."""
        if depth > self._json_max_nesting_depth:
            return "[TRUNCATED: Max depth exceeded]"

        if isinstance(value, str):
            return self._sanitize_string_field(value)
        elif isinstance(value, (int, float)):
            return self._sanitize_numeric_field(value)
        elif isinstance(value, bool):
            return value
        elif isinstance(value, dict):
            return {
                self._sanitize_string_field(str(k)): self._sanitize_json_value(v, depth + 1)
                for k, v in list(value.items())[:50]  # Limit dict size
            }
        elif isinstance(value, (list, tuple)):
            return [
                self._sanitize_json_value(item, depth + 1) for item in list(value)[:100]
            ]  # Limit list size
        elif value is None:
            return None
        else:
            # Convert unknown types to string and sanitize
            return self._sanitize_string_field(str(value))

    def _sanitize_string_field(self, value: str) -> str:
        """Sanitize string values for JSON output."""
        if not isinstance(value, str):
            value = str(value)

        # Remove control characters (except tab, newline, carriage return)
        value = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", value)

        # HTML encode to prevent injection
        value = html.escape(value, quote=True)

        # Limit length
        if len(value) > self._json_max_field_length:
            value = value[: self._json_max_field_length - 3] + "..."

        # Remove potential log injection patterns
        value = re.sub(r"[\r\n]+", " ", value)  # Convert newlines to spaces

        return value

    def _sanitize_numeric_field(self, value: float) -> float:
        """Sanitize numeric values for JSON output."""
        # Handle special float values that are not JSON serializable
        if value != value:  # NaN check
            return 0.0
        if value == float("inf"):
            return 1e308  # Large finite number
        if value == float("-inf"):
            return -1e308  # Large finite negative number
        return value

    def _sanitize_json_field(self, value: str) -> str:
        """Sanitize field values for JSON output."""
        if not isinstance(value, str):
            value = str(value)
        # Remove control characters and limit length
        sanitized = "".join(char for char in value if ord(char) >= 32)
        return sanitized[:200]  # Limit length to prevent abuse


class RichProgressTracker:
    """Progress tracker using Rich progress bars."""

    def __init__(self, progress: Progress, task_id: Any):
        self.progress = progress
        self.task_id = task_id

    def update(
        self, completed: int, total: int | None = None, description: str | None = None
    ) -> None:
        """Update progress position."""
        kwargs = {}
        if completed is not None:
            kwargs["completed"] = completed
        if total is not None:
            kwargs["total"] = total
        if description is not None:
            kwargs["description"] = description
        
        self.progress.update(self.task_id, **kwargs)


class JsonProgressTracker:
    """Progress tracker for JSON output."""

    def __init__(self, description: str):
        self.description = description
        self.start_time = time.time()

    def update(
        self, completed: int, total: int | None = None, description: str | None = None
    ) -> None:
        """Update progress as JSON lines on stderr."""
        sanitized_description = self._sanitize_json_field(description or self.description)
        sanitized_completed = max(0, min(completed or 0, total or 100))
        sanitized_total = max(1, total or 100)

        progress_data: dict[str, Any] = {
            "timestamp": datetime.now().isoformat(),
            "type": "progress",
            "stage": sanitized_description,
            "completed": sanitized_completed,
            "elapsed": time.time() - self.start_time,
        }
        if total is not None and total > 0:
            progress_data["total"] = sanitized_total
            progress_data["percentage"] = round((sanitized_completed / sanitized_total) * 100, 1)

        with self._lock:
            print(json.dumps(progress_data), file=sys.stderr)

    def _sanitize_json_field(self, value: str) -> str:
        """Sanitize field values for JSON output."""
        if not isinstance(value, str):
            value = str(value)
        # Remove control characters and limit length
        sanitized = "".join(char for char in value if ord(char) >= 32)
        return sanitized[:200]  # Limit length to prevent abuse


class FallbackProgressTracker:
    """Fallback progress tracker for non-TTY environments."""

    def __init__(self, description: str):
        self.description = description
        self.last_reported = 0.0
        self._lock = threading.Lock()

    def update(
        self, completed: int, total: int | None = None, description: str | None = None
    ) -> None:
        """Update progress with simple periodic text output."""
        if total:
            percentage = (completed / total) * 100
            with self._lock:
                if percentage - self.last_reported >= 10:  # every 10%
                    desc = description or self.description
                    print(f"{desc}: {percentage:.0f}% complete", file=sys.stderr)
                    self.last_reported = percentage
