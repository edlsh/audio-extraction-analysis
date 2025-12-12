"""JSON output utilities for CLI commands."""

import json
import sys
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CommandTiming:
    """Tracks timing for command execution stages."""

    start_time: float = field(default_factory=time.time)
    stages: dict[str, float] = field(default_factory=dict)
    _stage_starts: dict[str, float] = field(default_factory=dict)

    def start_stage(self, stage: str) -> None:
        """Start timing a stage."""
        self._stage_starts[stage] = time.time()

    def end_stage(self, stage: str) -> None:
        """End timing a stage and record duration."""
        if stage in self._stage_starts:
            self.stages[stage] = round(time.time() - self._stage_starts[stage], 3)
            del self._stage_starts[stage]

    @property
    def total_seconds(self) -> float:
        """Get total elapsed time since start."""
        return round(time.time() - self.start_time, 3)


@dataclass
class JsonCommandResult:
    """Structured result for JSON output."""

    success: bool
    command: str
    input: str
    exit_code: int = 0
    outputs: dict[str, Any] = field(default_factory=dict)
    timing: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        result: dict[str, Any] = {
            "success": self.success,
            "command": self.command,
            "input": self.input,
            "exit_code": self.exit_code,
        }

        if self.outputs:
            result["outputs"] = self.outputs

        if self.timing:
            result["timing"] = self.timing

        if self.errors:
            result["errors"] = self.errors

        if self.warnings:
            result["warnings"] = self.warnings

        if self.metadata:
            result["metadata"] = self.metadata

        return result

    def print_json(self) -> None:
        """Print result as JSON to stdout."""
        print(json.dumps(self.to_dict(), indent=2, default=str))


def print_json_error(command: str, input_path: str, error: str, exit_code: int = 1) -> None:
    """Print a JSON error result to stdout."""
    result = JsonCommandResult(
        success=False,
        command=command,
        input=input_path,
        exit_code=exit_code,
        errors=[error],
    )
    result.print_json()


def log_json_message(msg_type: str, message: str) -> None:
    """Log a JSON message to stderr."""
    from datetime import datetime

    print(
        json.dumps(
            {
                "timestamp": datetime.now().isoformat(),
                "type": msg_type,
                "message": message,
            }
        ),
        file=sys.stderr,
    )
