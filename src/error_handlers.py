"""
CLI Error Handlers

This module provides user-friendly error handling for CLI commands,
mapping internal exceptions to clear error messages and exit codes.
"""

from __future__ import annotations

import logging
import sys
from typing import NoReturn

from src.exceptions import (
    AudioAnalysisError,
    AudioExtractionError,
    ConfigurationError,
    FFmpegExecutionError,
    FFmpegNotFoundError,
    ProviderAPIError,
    ProviderAuthenticationError,
    ProviderNotAvailableError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    TranscriptionError,
    UrlIngestionError,
    ValidationError,
)

logger = logging.getLogger(__name__)


def handle_validation_error(error: ValidationError) -> None:
    """Handle file validation errors with user-friendly messages.

    Args:
        error: Validation error to handle
    """
    print(f"✗ Invalid input: {error.message}", file=sys.stderr)

    # Provide helpful tips based on error context
    msg_lower = error.message.lower()
    if "not found" in msg_lower:
        print("  💡 Tip: Check that the file path is correct", file=sys.stderr)
    elif "permission" in msg_lower:
        print("  💡 Tip: Check file permissions with: ls -l <file>", file=sys.stderr)
    elif "size" in msg_lower:
        if "limit" in error.context:
            limit_mb = error.context["limit"]
            print(f"  💡 Tip: File size limit is {limit_mb}MB", file=sys.stderr)
    elif "traversal" in msg_lower:
        print("  💡 Tip: Path contains invalid directory references", file=sys.stderr)

    logger.error("Validation error: %s", error.message, extra={"context": error.context})


def handle_ffmpeg_error(error: FFmpegNotFoundError | FFmpegExecutionError) -> None:
    """Handle FFmpeg-related errors with installation instructions.

    Args:
        error: FFmpeg error to handle
    """
    print(f"✗ FFmpeg Error: {error.message}", file=sys.stderr)

    if isinstance(error, FFmpegNotFoundError):
        print("\n📦 FFmpeg is required but not installed.", file=sys.stderr)
        print("Install instructions:", file=sys.stderr)
        print("  macOS:   brew install ffmpeg", file=sys.stderr)
        print("  Ubuntu:  sudo apt-get install ffmpeg", file=sys.stderr)
        print("  Windows: Download from https://ffmpeg.org/download.html", file=sys.stderr)
    elif isinstance(error, FFmpegExecutionError):
        if "stderr" in error.context:
            stderr = error.context["stderr"][:200]  # Limit output
            print(f"\n📋 FFmpeg output: {stderr}", file=sys.stderr)
        print("\n💡 Common issues:", file=sys.stderr)
        print("  - Unsupported codec or format", file=sys.stderr)
        print("  - Corrupted input file", file=sys.stderr)
        print("  - Insufficient disk space", file=sys.stderr)

    logger.error("FFmpeg error: %s", error.message, extra={"context": error.context})


def handle_audio_extraction_error(error: AudioExtractionError) -> None:
    """Handle general audio extraction errors.

    Args:
        error: Audio extraction error to handle
    """
    print(f"✗ Extraction Error: {error.message}", file=sys.stderr)

    # Provide context if available
    if error.context:
        if "video_path" in error.context:
            print(f"  File: {error.context['video_path']}", file=sys.stderr)
        if "timeout" in error.context:
            print(f"  Timeout: {error.context['timeout']}s", file=sys.stderr)

    logger.error("Audio extraction error: %s", error.message, extra={"context": error.context})


def handle_provider_error(error: ProviderNotAvailableError | ProviderAuthenticationError) -> None:
    """Handle transcription provider errors.

    Args:
        error: Provider error to handle
    """
    print(f"✗ Provider Error: {error.message}", file=sys.stderr)

    if isinstance(error, ProviderNotAvailableError):
        _handle_provider_not_available(error)
    elif isinstance(error, ProviderAuthenticationError):
        _handle_provider_auth_error(error)

    logger.error("Provider error: %s", error.message, extra={"context": error.context})


def _handle_provider_not_available(error: ProviderNotAvailableError) -> None:
    """Handle provider not available error details."""
    if not error.context:
        return

    available = error.context.get("available_providers", [])
    if available:
        print(f"\n📋 Available providers: {', '.join(available)}", file=sys.stderr)

    if "missing_module" in error.context:
        _print_install_instructions(error.context)


def _print_install_instructions(context: dict) -> None:
    """Print installation instructions for missing provider."""
    module = context["missing_module"]
    print(f"\n📦 Missing dependency: {module}", file=sys.stderr)
    print("Install with:", file=sys.stderr)

    provider = context.get("provider_name", "")
    install_cmds = {
        "whisper": "pip install openai-whisper",
        "parakeet": "pip install audio-extraction-analysis[parakeet]",
    }
    cmd = install_cmds.get(provider, f"pip install audio-extraction-analysis[{provider}]")
    print(f"  {cmd}", file=sys.stderr)


def _handle_provider_auth_error(error: ProviderAuthenticationError) -> None:
    """Handle provider authentication error details."""
    print("\n🔑 Check your API key configuration:", file=sys.stderr)

    if not error.context:
        return

    provider = error.context.get("provider_name")
    api_key_vars = {
        "deepgram": "DEEPGRAM_API_KEY",
        "elevenlabs": "ELEVENLABS_API_KEY",
    }

    if provider in api_key_vars:
        key_var = api_key_vars[provider]
        print(f"  Set: export {key_var}='your-key'", file=sys.stderr)
        print(f"  Or create .env file with: {key_var}=your-key", file=sys.stderr)


def handle_provider_api_error(error: ProviderAPIError) -> None:
    """Handle provider API errors with status code information.

    Args:
        error: Provider API error to handle
    """
    print(f"✗ API Error: {error.message}", file=sys.stderr)

    if error.status_code:
        print(f"  Status: {error.status_code}", file=sys.stderr)

        # Provide helpful info based on status code
        if error.status_code == 401:
            print("  💡 Check your API key", file=sys.stderr)
        elif error.status_code == 429:
            print("  💡 Rate limit exceeded - wait before retrying", file=sys.stderr)
        elif error.status_code == 503:
            print("  💡 Service temporarily unavailable", file=sys.stderr)
        elif error.status_code >= 500:
            print("  💡 Provider server error - try again later", file=sys.stderr)

    logger.error(
        "Provider API error: %s (status=%s)",
        error.message,
        error.status_code,
        extra={"context": error.context, "response_body": error.response_body},
    )


def handle_transcription_error(error: TranscriptionError) -> None:
    """Handle general transcription errors.

    Args:
        error: Transcription error to handle
    """
    print(f"✗ Transcription Error: {error.message}", file=sys.stderr)

    if error.context:
        for key, value in error.context.items():
            if not key.startswith("_"):  # Skip internal context
                print(f"  {key}: {value}", file=sys.stderr)

    logger.error("Transcription error: %s", error.message, extra={"context": error.context})


def handle_url_ingestion_error(error: UrlIngestionError) -> None:
    """Handle URL ingestion errors.

    Args:
        error: URL ingestion error to handle
    """
    print(f"✗ URL Error: {error.message}", file=sys.stderr)

    if error.context and "url" in error.context:
        print(f"  URL: {error.context['url']}", file=sys.stderr)

    print("\n💡 Common issues:", file=sys.stderr)
    print("  - URL may be invalid or unsupported", file=sys.stderr)
    print("  - Network connectivity issues", file=sys.stderr)
    print("  - Video may be private or deleted", file=sys.stderr)

    logger.error("URL ingestion error: %s", error.message, extra={"context": error.context})


def handle_configuration_error(error: ConfigurationError) -> None:
    """Handle configuration errors.

    Args:
        error: Configuration error to handle
    """
    print(f"✗ Configuration Error: {error.message}", file=sys.stderr)

    if error.context:
        if "key" in error.context:
            print(f"  Config key: {error.context['key']}", file=sys.stderr)
        if "allowed" in error.context:
            print(f"  Allowed values: {error.context['allowed']}", file=sys.stderr)

    logger.error("Configuration error: %s", error.message, extra={"context": error.context})


def handle_unexpected_error(error: Exception, command: str = "command") -> None:
    """Handle unexpected errors that weren't caught by specific handlers.

    Args:
        error: Unexpected error
        command: Name of the command that failed
    """
    # Sanitize error message (remove potential sensitive data)
    error_msg = str(error)

    print(f"✗ An unexpected error occurred in {command}", file=sys.stderr)
    print(f"  {error_msg}", file=sys.stderr)
    print("\n💡 Please report this issue with the log files", file=sys.stderr)

    logger.critical("Unexpected error in %s: %s", command, error_msg, exc_info=True)


def handle_keyboard_interrupt() -> NoReturn:
    """Handle user cancellation (Ctrl+C).

    Raises:
        SystemExit: Always exits with code 130 (standard for SIGINT)
    """
    print("\n✗ Operation cancelled by user", file=sys.stderr)
    logger.info("User cancelled operation")
    sys.exit(130)  # Standard exit code for SIGINT


def handle_cli_error(error: Exception, command: str = "command") -> int:
    """Main error handler dispatcher for CLI commands.

    Routes errors to appropriate handlers and returns exit code.

    Args:
        error: Exception to handle
        command: Name of the command that raised the error

    Returns:
        Exit code (1 for errors, 130 for user cancellation)
    """
    # Handle user cancellation
    if isinstance(error, KeyboardInterrupt):
        handle_keyboard_interrupt()

    # Handle validation errors
    if isinstance(error, ValidationError):
        handle_validation_error(error)
        return 1

    # Handle FFmpeg errors
    if isinstance(error, FFmpegNotFoundError):
        handle_ffmpeg_error(error)
        return 1
    if isinstance(error, FFmpegExecutionError):
        handle_ffmpeg_error(error)
        return 1

    # Handle general audio extraction errors
    if isinstance(error, AudioExtractionError):
        handle_audio_extraction_error(error)
        return 1

    # Handle provider errors
    if isinstance(error, ProviderNotAvailableError):
        handle_provider_error(error)
        return 1
    if isinstance(error, ProviderAuthenticationError):
        handle_provider_error(error)
        return 1
    if isinstance(error, ProviderAPIError):
        handle_provider_api_error(error)
        return 1
    if isinstance(error, ProviderRateLimitError):
        print(f"✗ Rate Limit: {error.message}", file=sys.stderr)
        print("  💡 Wait a few minutes before retrying", file=sys.stderr)
        logger.error("Rate limit: %s", error.message, extra={"context": error.context})
        return 1
    if isinstance(error, ProviderTimeoutError):
        print(f"✗ Timeout: {error.message}", file=sys.stderr)
        print("  💡 Try again or use a smaller audio file", file=sys.stderr)
        logger.error("Timeout: %s", error.message, extra={"context": error.context})
        return 1

    # Handle general transcription errors
    if isinstance(error, TranscriptionError):
        handle_transcription_error(error)
        return 1

    # Handle URL ingestion errors
    if isinstance(error, UrlIngestionError):
        handle_url_ingestion_error(error)
        return 1

    # Handle configuration errors
    if isinstance(error, ConfigurationError):
        handle_configuration_error(error)
        return 1

    # Handle any AudioAnalysisError we haven't specifically caught
    if isinstance(error, AudioAnalysisError):
        print(f"✗ Error: {error.message}", file=sys.stderr)
        logger.error("Audio analysis error: %s", error.message, extra={"context": error.context})
        return 1

    # Unexpected error
    handle_unexpected_error(error, command)
    return 1
