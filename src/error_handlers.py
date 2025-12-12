"""CLI Error Handlers - Maps exceptions to user-friendly messages."""

from __future__ import annotations

import sys
from collections.abc import Callable
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
from src.utils.logger import get_logger

logger = get_logger(__name__)


def handle_validation_error(error: ValidationError) -> None:
    """Handle file validation errors."""
    print(f"✗ Invalid input: {error.message}", file=sys.stderr)
    msg_lower = error.message.lower()
    if "not found" in msg_lower:
        print("  💡 Tip: Check that the file path is correct", file=sys.stderr)
    elif "permission" in msg_lower:
        print("  💡 Tip: Check file permissions with: ls -l <file>", file=sys.stderr)
    elif "size" in msg_lower and "limit" in error.context:
        print(f"  💡 Tip: File size limit is {error.context['limit']}MB", file=sys.stderr)
    elif "traversal" in msg_lower:
        print("  💡 Tip: Path contains invalid directory references", file=sys.stderr)
    logger.error("Validation error: %s", error.message, extra={"context": error.context})


def handle_ffmpeg_error(error: FFmpegNotFoundError | FFmpegExecutionError) -> None:
    """Handle FFmpeg-related errors."""
    print(f"✗ FFmpeg Error: {error.message}", file=sys.stderr)
    if isinstance(error, FFmpegNotFoundError):
        print("\n📦 FFmpeg is required but not installed.", file=sys.stderr)
        print("Install: brew install ffmpeg (macOS) | apt install ffmpeg (Ubuntu)", file=sys.stderr)
    elif "stderr" in error.context:
        print(f"\n📋 FFmpeg output: {error.context['stderr'][:200]}", file=sys.stderr)
    logger.error("FFmpeg error: %s", error.message, extra={"context": error.context})


def handle_audio_extraction_error(error: AudioExtractionError) -> None:
    """Handle audio extraction errors."""
    print(f"✗ Extraction Error: {error.message}", file=sys.stderr)
    if error.context:
        if "video_path" in error.context:
            print(f"  File: {error.context['video_path']}", file=sys.stderr)
        if "timeout" in error.context:
            print(f"  Timeout: {error.context['timeout']}s", file=sys.stderr)
    logger.error("Audio extraction error: %s", error.message, extra={"context": error.context})


def handle_provider_not_available(error: ProviderNotAvailableError) -> None:
    """Handle provider not available errors."""
    print(f"✗ Provider Error: {error.message}", file=sys.stderr)
    if error.context:
        if available := error.context.get("available_providers"):
            print(f"\n📋 Available providers: {', '.join(available)}", file=sys.stderr)
        if "missing_module" in error.context:
            module = error.context["missing_module"]
            provider = error.context.get("provider_name", "")
            print(f"\n📦 Missing dependency: {module}", file=sys.stderr)
            cmd = {
                "whisper": "pip install openai-whisper",
                "parakeet": "pip install audio-extraction-analysis[parakeet]",
            }.get(provider, f"pip install audio-extraction-analysis[{provider}]")
            print(f"  Install with: {cmd}", file=sys.stderr)
    logger.error("Provider error: %s", error.message, extra={"context": error.context})


def handle_provider_auth_error(error: ProviderAuthenticationError) -> None:
    """Handle provider authentication errors."""
    print(f"✗ Provider Error: {error.message}", file=sys.stderr)
    print("\n🔑 Check your API key configuration:", file=sys.stderr)
    if error.context and (provider := error.context.get("provider_name")):
        key_vars = {"deepgram": "DEEPGRAM_API_KEY", "elevenlabs": "ELEVENLABS_API_KEY"}
        if key_var := key_vars.get(provider):
            print(f"  Set: export {key_var}='your-key'", file=sys.stderr)
    logger.error("Provider error: %s", error.message, extra={"context": error.context})


def handle_provider_api_error(error: ProviderAPIError) -> None:
    """Handle provider API errors."""
    print(f"✗ API Error: {error.message}", file=sys.stderr)
    if error.status_code:
        print(f"  Status: {error.status_code}", file=sys.stderr)
        tips = {
            401: "Check your API key",
            429: "Rate limit exceeded - wait before retrying",
            503: "Service temporarily unavailable",
        }
        if tip := tips.get(error.status_code):
            print(f"  💡 {tip}", file=sys.stderr)
        elif error.status_code >= 500:
            print("  💡 Provider server error - try again later", file=sys.stderr)
    logger.error("Provider API error: %s (status=%s)", error.message, error.status_code)


def handle_rate_limit_error(error: ProviderRateLimitError) -> None:
    """Handle rate limit errors."""
    print(f"✗ Rate Limit: {error.message}", file=sys.stderr)
    print("  💡 Wait a few minutes before retrying", file=sys.stderr)
    logger.error("Rate limit: %s", error.message, extra={"context": error.context})


def handle_timeout_error(error: ProviderTimeoutError) -> None:
    """Handle timeout errors."""
    print(f"✗ Timeout: {error.message}", file=sys.stderr)
    print("  💡 Try again or use a smaller audio file", file=sys.stderr)
    logger.error("Timeout: %s", error.message, extra={"context": error.context})


def handle_transcription_error(error: TranscriptionError) -> None:
    """Handle transcription errors."""
    print(f"✗ Transcription Error: {error.message}", file=sys.stderr)
    if error.context:
        for key, value in error.context.items():
            if not key.startswith("_"):
                print(f"  {key}: {value}", file=sys.stderr)
    logger.error("Transcription error: %s", error.message, extra={"context": error.context})


def handle_url_ingestion_error(error: UrlIngestionError) -> None:
    """Handle URL ingestion errors."""
    print(f"✗ URL Error: {error.message}", file=sys.stderr)
    if error.context and "url" in error.context:
        print(f"  URL: {error.context['url']}", file=sys.stderr)
    print(
        "\n💡 Common issues: invalid URL, network issues, or private/deleted content",
        file=sys.stderr,
    )
    logger.error("URL ingestion error: %s", error.message, extra={"context": error.context})


def handle_configuration_error(error: ConfigurationError) -> None:
    """Handle configuration errors."""
    print(f"✗ Configuration Error: {error.message}", file=sys.stderr)
    if error.context:
        if "key" in error.context:
            print(f"  Config key: {error.context['key']}", file=sys.stderr)
        if "allowed" in error.context:
            print(f"  Allowed values: {error.context['allowed']}", file=sys.stderr)
    logger.error("Configuration error: %s", error.message, extra={"context": error.context})


def handle_unexpected_error(error: Exception, command: str = "command") -> None:
    """Handle unexpected errors."""
    print(f"✗ An unexpected error occurred in {command}", file=sys.stderr)
    print(f"  {error}", file=sys.stderr)
    print("\n💡 Please report this issue with the log files", file=sys.stderr)
    logger.critical("Unexpected error in %s: %s", command, error, exc_info=True)


def handle_keyboard_interrupt() -> NoReturn:
    """Handle user cancellation (Ctrl+C)."""
    print("\n✗ Operation cancelled by user", file=sys.stderr)
    logger.info("User cancelled operation")
    sys.exit(130)


# Exception type to handler dispatch table
_ERROR_HANDLERS: dict[type[Exception], Callable[[Exception], None]] = {
    ValidationError: handle_validation_error,
    FFmpegNotFoundError: handle_ffmpeg_error,
    FFmpegExecutionError: handle_ffmpeg_error,
    AudioExtractionError: handle_audio_extraction_error,
    ProviderNotAvailableError: handle_provider_not_available,
    ProviderAuthenticationError: handle_provider_auth_error,
    ProviderAPIError: handle_provider_api_error,
    ProviderRateLimitError: handle_rate_limit_error,
    ProviderTimeoutError: handle_timeout_error,
    TranscriptionError: handle_transcription_error,
    UrlIngestionError: handle_url_ingestion_error,
    ConfigurationError: handle_configuration_error,
}


def handle_cli_error(error: Exception, command: str = "command") -> int:
    """Main error handler dispatcher using lookup table."""
    if isinstance(error, KeyboardInterrupt):
        handle_keyboard_interrupt()

    # Find and execute the appropriate handler
    for error_type, handler in _ERROR_HANDLERS.items():
        if isinstance(error, error_type):
            handler(error)
            return 1

    # Fallback for AudioAnalysisError subclasses not in dispatch table
    if isinstance(error, AudioAnalysisError):
        print(f"✗ Error: {error.message}", file=sys.stderr)
        logger.error("Audio analysis error: %s", error.message, extra={"context": error.context})
        return 1

    # Unexpected error
    handle_unexpected_error(error, command)
    return 1
