"""Pipeline result types with typed error preservation and artifact tiering.

This module provides structured result types that:
- Preserve typed errors (not just string messages)
- Support artifact tiering for selective cleanup
- Enable better user feedback and mappable exit codes
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from ..models.transcription import TranscriptionResult


class ArtifactTier(Enum):
    """Artifact importance tiers for cleanup decisions.

    Higher-tier artifacts are preserved even on partial failures.
    """

    EPHEMERAL = auto()  # Temp files, can always delete
    INTERMEDIATE = auto()  # Stage outputs, delete on stage failure
    VALUABLE = auto()  # User-facing outputs, preserve on partial success
    CRITICAL = auto()  # Must never delete automatically


@dataclass
class PipelineArtifact:
    """Tracked artifact produced during pipeline execution.

    Attributes:
        path: File path
        stage: Stage that produced this artifact
        tier: Importance tier for cleanup decisions
        artifact_type: Type of artifact (audio, transcript, analysis, etc.)
    """

    path: Path
    stage: str
    tier: ArtifactTier = ArtifactTier.INTERMEDIATE
    artifact_type: str = "file"

    def should_cleanup_on_failure(self, failed_stage: str | None) -> bool:
        """Determine if artifact should be cleaned up on failure.

        Args:
            failed_stage: Stage that failed, or None for general failure

        Returns:
            True if artifact should be deleted
        """
        if self.tier == ArtifactTier.CRITICAL:
            return False
        if self.tier == ArtifactTier.VALUABLE:
            return False
        if self.tier == ArtifactTier.EPHEMERAL:
            return True
        # INTERMEDIATE: only cleanup if from failed stage or later
        if failed_stage is None:
            return True
        stage_order = ["extract", "transcribe", "analyze"]
        try:
            artifact_idx = stage_order.index(self.stage)
            failed_idx = stage_order.index(failed_stage)
            return artifact_idx >= failed_idx
        except ValueError:
            return True


@dataclass
class PipelineError:
    """Structured pipeline error with type preservation.

    Attributes:
        message: Human-readable error message
        error_type: Exception class name
        stage: Stage where error occurred
        context: Additional error context
        original_exception: Original exception (not serializable)
    """

    message: str
    error_type: str
    stage: str | None = None
    context: dict[str, Any] = field(default_factory=dict)
    original_exception: Exception | None = field(default=None, repr=False)

    @classmethod
    def from_exception(
        cls,
        exc: Exception,
        stage: str | None = None,
    ) -> PipelineError:
        """Create PipelineError from an exception.

        Args:
            exc: The exception to wrap
            stage: Stage where exception occurred

        Returns:
            PipelineError with preserved type information
        """
        context: dict[str, Any] = {}

        # Extract context from our custom exceptions using getattr for type safety
        exc_context = getattr(exc, "context", None)
        if exc_context is not None:
            context = exc_context
        if hasattr(exc, "status_code"):
            context["status_code"] = exc.status_code
        if hasattr(exc, "response_body"):
            context["response_body"] = exc.response_body

        return cls(
            message=str(exc),
            error_type=type(exc).__name__,
            stage=stage,
            context=context,
            original_exception=exc,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "message": self.message,
            "error_type": self.error_type,
            "stage": self.stage,
            "context": self.context,
        }

    @property
    def exit_code(self) -> int:
        """Get suggested exit code based on error type.

        Returns:
            Unix-style exit code (0-255)
        """
        # Map error types to exit codes
        error_code_map = {
            # Validation errors (user input issues)
            "ValidationError": 64,  # EX_USAGE
            "AudioFileNotFoundError": 66,  # EX_NOINPUT
            "FileAccessError": 77,  # EX_NOPERM
            "FileSizeError": 65,  # EX_DATAERR
            "PathTraversalError": 77,  # EX_NOPERM
            # Provider errors
            "ProviderNotAvailableError": 69,  # EX_UNAVAILABLE
            "ProviderAuthenticationError": 78,  # EX_CONFIG
            "ProviderRateLimitError": 75,  # EX_TEMPFAIL
            "ProviderTimeoutError": 75,  # EX_TEMPFAIL
            "ProviderAPIError": 70,  # EX_SOFTWARE
            # Configuration errors
            "ConfigurationError": 78,  # EX_CONFIG
            "InvalidConfigError": 78,  # EX_CONFIG
            "MissingConfigError": 78,  # EX_CONFIG
            # Extraction errors
            "FFmpegNotFoundError": 69,  # EX_UNAVAILABLE
            "FFmpegExecutionError": 70,  # EX_SOFTWARE
            "AudioExtractionTimeoutError": 75,  # EX_TEMPFAIL
            # Transcription errors
            "TranscriptionError": 70,  # EX_SOFTWARE
            # Analysis errors
            "AnalysisError": 70,  # EX_SOFTWARE
            "AnalysisTimeoutError": 75,  # EX_TEMPFAIL
        }
        return error_code_map.get(self.error_type, 1)


@dataclass
class StageResult:
    """Result details for a single pipeline stage.

    Attributes:
        status: Completion status
        duration: Processing duration in seconds
        output: Primary output path or value
        files: List of files produced
        error: Structured error if failed
    """

    status: Literal["complete", "error", "skipped"]
    duration: float = 0.0
    output: str = ""
    files: list[str] = field(default_factory=list)
    error: PipelineError | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        result: dict[str, Any] = {
            "status": self.status,
            "duration": self.duration,
        }
        if self.output:
            result["output"] = self.output
        if self.files:
            result["files"] = self.files
        if self.error:
            result["error"] = self.error.to_dict()
        return result


@dataclass
class PipelineResult:
    """Complete pipeline execution result with typed errors.

    Attributes:
        success: Whether pipeline completed successfully
        audio_path: Path to extracted audio
        transcript: Transcription result object
        analysis_files: Paths to generated analysis files
        stages_completed: List of completed stage names
        artifacts: Tracked artifacts with tier information
        errors: Structured error objects (not just strings)
        stage_results: Detailed results per stage
    """

    success: bool = False
    audio_path: str = ""
    transcript: TranscriptionResult | None = None
    analysis_files: list[str] = field(default_factory=list)
    stages_completed: list[str] = field(default_factory=list)
    artifacts: list[PipelineArtifact] = field(default_factory=list)
    errors: list[PipelineError] = field(default_factory=list)
    stage_results: dict[str, StageResult] = field(default_factory=dict)

    # Computed properties
    @property
    def files_created(self) -> list[str]:
        """Get all files created during pipeline (for compatibility)."""
        return [str(a.path) for a in self.artifacts]

    @property
    def error_messages(self) -> list[str]:
        """Get error messages as strings (for compatibility)."""
        return [e.message for e in self.errors]

    @property
    def primary_error(self) -> PipelineError | None:
        """Get the first/primary error if any."""
        return self.errors[0] if self.errors else None

    @property
    def exit_code(self) -> int:
        """Get suggested exit code based on errors.

        Returns:
            0 for success, error-specific code otherwise
        """
        if self.success:
            return 0
        if self.primary_error:
            return self.primary_error.exit_code
        return 1

    def add_artifact(
        self,
        path: Path | str,
        stage: str,
        tier: ArtifactTier = ArtifactTier.INTERMEDIATE,
        artifact_type: str = "file",
    ) -> None:
        """Add a tracked artifact.

        Args:
            path: File path
            stage: Stage that produced this
            tier: Importance tier
            artifact_type: Type of artifact
        """
        self.artifacts.append(
            PipelineArtifact(
                path=Path(path) if isinstance(path, str) else path,
                stage=stage,
                tier=tier,
                artifact_type=artifact_type,
            )
        )

    def add_error(
        self,
        exc: Exception,
        stage: str | None = None,
    ) -> None:
        """Add an error from an exception.

        Args:
            exc: Exception to record
            stage: Stage where error occurred
        """
        self.errors.append(PipelineError.from_exception(exc, stage))

    def add_error_message(
        self,
        message: str,
        stage: str | None = None,
        error_type: str = "PipelineError",
    ) -> None:
        """Add an error from a message string.

        Args:
            message: Error message
            stage: Stage where error occurred
            error_type: Exception type name
        """
        self.errors.append(
            PipelineError(
                message=message,
                error_type=error_type,
                stage=stage,
            )
        )

    def get_cleanup_targets(self, failed_stage: str | None = None) -> list[Path]:
        """Get list of artifacts that should be cleaned up.

        Args:
            failed_stage: Stage that failed, for selective cleanup

        Returns:
            List of paths to delete
        """
        return [a.path for a in self.artifacts if a.should_cleanup_on_failure(failed_stage)]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization.

        Returns backward-compatible dict structure.
        """
        return {
            "success": self.success,
            "audio_path": self.audio_path,
            "transcript": self.transcript,
            "analysis_files": self.analysis_files,
            "stages_completed": self.stages_completed,
            "files_created": self.files_created,
            "errors": self.error_messages,  # Backward compat: string list
            "error_details": [e.to_dict() for e in self.errors],  # New: typed errors
            "stage_results": {k: v.to_dict() for k, v in self.stage_results.items()},
            "exit_code": self.exit_code,
        }

    def to_legacy_dict(self) -> dict[str, Any]:
        """Convert to legacy PipelineResult TypedDict format.

        This method produces the exact format expected by legacy consumers,
        including the stage_results with error messages (not full PipelineError).

        Returns:
            Dict matching the legacy PipelineResult TypedDict structure
        """
        legacy: dict[str, Any] = {
            "success": self.success,
            "stages_completed": self.stages_completed,
            "files_created": self.files_created,
            "errors": self.error_messages,
            "stage_results": {},
        }

        if self.audio_path:
            legacy["audio_path"] = self.audio_path
        if self.transcript:
            legacy["transcript"] = self.transcript
        if self.analysis_files:
            legacy["analysis_files"] = self.analysis_files

        for name, stage_result in self.stage_results.items():
            legacy["stage_results"][name] = {
                "status": stage_result.status,
                "duration": stage_result.duration,
            }
            if stage_result.output:
                legacy["stage_results"][name]["output"] = stage_result.output
            if stage_result.files:
                legacy["stage_results"][name]["files"] = stage_result.files
            if stage_result.error:
                legacy["stage_results"][name]["error"] = stage_result.error.message

        return legacy


__all__ = [
    "ArtifactTier",
    "PipelineArtifact",
    "PipelineError",
    "PipelineResult",
    "StageResult",
]
