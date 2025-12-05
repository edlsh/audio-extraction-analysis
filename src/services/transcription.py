"""Core transcription orchestration service."""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

    from ..models.transcription import TranscriptionResult
from ..config import get_config
from ..exceptions import ProviderTimeoutError, TranscriptionError
from ..providers.factory import TranscriptionProviderFactory
from ..utils.file_validation import safe_validate_audio_file

logger = logging.getLogger(__name__)


class TranscriptionService:
    """Coordinates transcription operations across providers.

    This service provides a simplified interface for transcription with:
    - Single async entry point (transcribe_async) as the canonical method
    - Sync wrapper (transcribe) for compatibility
    - Automatic provider selection based on configuration
    """

    def __init__(self) -> None:
        self.factory = TranscriptionProviderFactory
        self._config = get_config()
        self._provider_timeout = float(self._config.transcription_timeout_seconds)

    def get_available_providers(self) -> list[str]:
        """List all registered providers."""
        return self.factory.get_available_providers()

    def get_configured_providers(self) -> list[str]:
        """List providers with valid configuration."""
        return self.factory.get_configured_providers()

    def _select_provider(self, provider_name: str | None) -> str:
        """Select provider: use specified, test env override, or default configured.

        Args:
            provider_name: Explicitly specified provider, or None for auto-select

        Returns:
            Provider name to use

        Raises:
            ValueError: If no providers are configured
        """
        # Explicit provider specified
        if provider_name and provider_name != "auto":
            return provider_name

        # Check for test environment override
        test_provider = os.getenv("AUDIO_TEST_PROVIDER")
        if test_provider:
            logger.info(f"Using test provider: {test_provider}")
            return test_provider

        # Use first configured provider
        configured = self.get_configured_providers()
        if configured:
            selected = configured[0]
            logger.info(f"Auto-selected provider: {selected}")
            return selected

        # No providers available
        raise ValueError("No transcription providers configured")

    def _prepare_transcription(
        self, audio_file_path: Path, provider_name: str | None = None
    ) -> tuple[Path, str]:
        """Validate audio file and select provider for transcription.

        Args:
            audio_file_path: Path to the audio file to transcribe
            provider_name: Optional provider name. If None, auto-selects

        Returns:
            Tuple of (validated_path, provider_name)

        Raises:
            ValidationError: If audio file validation fails
            ValueError: If no suitable provider can be found
        """
        from ..exceptions import ValidationError

        # Validate audio file
        validated_path = safe_validate_audio_file(audio_file_path)
        if validated_path is None:
            raise ValidationError(
                f"Audio file validation failed: {audio_file_path}",
                context={"file_path": str(audio_file_path)},
            )

        # Select provider
        selected_provider = self._select_provider(provider_name)

        return validated_path, selected_provider

    def _configure_provider_timeout(self, provider: Any) -> None:
        """Apply configured timeouts to provider instances when supported."""
        if hasattr(provider, "update_transcription_timeout"):
            try:
                provider.update_transcription_timeout(self._provider_timeout)
            except Exception as exc:  # pragma: no cover - defensive
                logger.debug("Failed to update provider timeout: %s", exc)

    def transcribe(
        self, audio_file_path: Path, provider_name: str | None = None, language: str = "en"
    ) -> TranscriptionResult:
        """Transcribe an audio file synchronously.

        This is a convenience wrapper around transcribe_async for sync contexts.

        Args:
            audio_file_path: Path to the audio file to transcribe
            provider_name: Optional provider name. If None, auto-selects
            language: Language code for transcription (default: 'en')

        Returns:
            TranscriptionResult with available features

        Raises:
            ValidationError: If audio file validation fails
            ProviderTimeoutError: If request times out
            TranscriptionError: If transcription fails
        """
        return asyncio.run(
            self.transcribe_async(audio_file_path, provider_name, language)
        )

    async def _execute_transcription_with_fallback(
        self,
        provider: Any,
        audio_file_path: Path,
        language: str,
        timeout_seconds: float,
    ) -> TranscriptionResult | None:
        """Execute transcription with async-to-sync fallback.

        Attempts async transcription first. If async method is unavailable or fails,
        falls back to sync transcription in a thread executor.

        Args:
            provider: Transcription provider instance
            audio_file_path: Path to the audio file
            language: Language code for transcription
            timeout_seconds: Timeout for the operation

        Returns:
            TranscriptionResult or None if transcription fails

        Raises:
            ProviderTimeoutError: If transcription times out
            ValueError: If provider has no suitable transcription method
        """
        # Try async method first
        if hasattr(provider, "transcribe_async") and callable(provider.transcribe_async):
            try:
                return await asyncio.wait_for(
                    provider.transcribe_async(
                        audio_file_path, language, timeout=timeout_seconds
                    ),
                    timeout=timeout_seconds,
                )
            except TimeoutError:
                raise  # Re-raise timeout errors
            except Exception as e:
                logger.warning(f"Async transcription failed, falling back to sync: {e}")

        # Fallback to sync method in executor
        if hasattr(provider, "transcribe") and callable(provider.transcribe):
            loop = asyncio.get_running_loop()
            return await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    lambda: provider.transcribe(
                        audio_file_path, language, timeout=timeout_seconds
                    ),
                ),
                timeout=timeout_seconds,
            )

        raise ValueError(
            f"Provider {provider.__class__.__name__} has no suitable transcription method"
        )

    async def transcribe_async(
        self, audio_file_path: Path, provider_name: str | None = None, language: str = "en"
    ) -> TranscriptionResult:
        """Transcribe an audio file asynchronously.

        Args:
            audio_file_path: Path to the audio file to transcribe
            provider_name: Optional provider name. If None, auto-selects
            language: Language code for transcription (default: 'en')

        Returns:
            TranscriptionResult with available features

        Raises:
            ValidationError: If audio file validation fails
            ProviderTimeoutError: If request times out
            TranscriptionError: If transcription fails
        """
        # Validate and prepare for transcription (now raises exceptions)
        audio_file_path, provider_name = self._prepare_transcription(audio_file_path, provider_name)

        # Create provider instance
        provider = self.factory.create_provider(provider_name)
        self._configure_provider_timeout(provider)
        timeout_seconds = self._provider_timeout

        logger.info(f"Starting async transcription with {provider.get_provider_name()}")

        try:
            result = await self._execute_transcription_with_fallback(
                provider, audio_file_path, language, timeout_seconds
            )
        except TimeoutError as exc:
            raise ProviderTimeoutError(
                f"Transcription timed out after {timeout_seconds}s",
                context={"provider": provider_name, "file_path": str(audio_file_path)},
            ) from exc

        if not result:
            raise TranscriptionError(
                "Transcription returned no result",
                context={
                    "provider": provider_name,
                    "file_path": str(audio_file_path),
                    "language": language,
                },
            )

        logger.info(f"Transcription completed successfully with {provider.get_provider_name()}")
        logger.info(f"Transcript length: {len(result.transcript)} characters")

        return result

    async def transcribe_with_progress(
        self,
        audio_file_path: Path | str,
        provider_name: str | None = None,
        language: str = "en",
        progress_callback: Callable[[int, int], None] | None = None,
        **kwargs: Any,
    ) -> TranscriptionResult | None:
        """Transcribe audio file with optional progress callback.

        Note: Progress callback receives simulated progress updates since
        providers don't report real-time progress. For production use,
        prefer transcribe_async directly.

        Args:
            audio_file_path: Path to the audio file to transcribe
            provider_name: Optional provider name. If None, auto-selects
            language: Language code for transcription (default: 'en')
            progress_callback: Optional callback(completed, total) for progress updates

        Returns:
            TranscriptionResult or None if transcription fails
        """
        path = Path(audio_file_path)

        # Signal progress start
        if progress_callback:
            progress_callback(10, 100)

        try:
            result = await self.transcribe_async(
                path, provider_name=provider_name, language=language
            )

            # Signal completion
            if progress_callback:
                progress_callback(100, 100)

            return result

        except Exception:
            raise

    # Convenience alias for compatibility with pipeline
    async def transcribe_file(
        self,
        audio_file_path: Path | str,
        provider_name: str | None = None,
        language: str = "en",
        progress_callback: Callable[[int, int], None] | None = None,
        **_: Any,
    ) -> TranscriptionResult | None:
        """Alias for transcribe_with_progress for backward compatibility."""
        return await self.transcribe_with_progress(
            audio_file_path,
            provider_name=provider_name,
            language=language,
            progress_callback=progress_callback,
        )

    def get_provider_features(self, provider_name: str) -> list[str]:
        """Get supported features for a specific provider.

        Args:
            provider_name: Name of the provider

        Returns:
            List of supported feature names

        Raises:
            ValueError: If provider is not available
        """
        try:
            provider = self.factory.create_provider(provider_name)
            return provider.get_supported_features()
        except ValueError as e:
            logger.error(f"Invalid provider '{provider_name}': {e}")
            raise
        except ImportError as e:
            logger.error(f"Provider '{provider_name}' module not available: {e}")
            raise ValueError(f"Provider '{provider_name}' not available: {e}") from e
        except Exception as e:
            logger.error(f"Failed to get features for provider '{provider_name}': {e}")
            raise ValueError(f"Provider '{provider_name}' not available: {e}") from e

    def save_transcription_result(
        self, result: TranscriptionResult, output_path: Path, provider_name: str | None = None
    ) -> None:
        """Save transcription result to file using provider-specific formatting.

        Args:
            result: TranscriptionResult to save
            output_path: Path where to save the result
            provider_name: Optional provider name for provider-specific formatting
        """
        if provider_name:
            try:
                # Map display names to internal provider keys
                provider_key = self._get_provider_key_from_name(provider_name)
                provider = self.factory.create_provider(provider_key)
                # Check if provider has save_result_to_file method
                if hasattr(provider, "save_result_to_file") and callable(
                    provider.save_result_to_file
                ):
                    provider.save_result_to_file(result, output_path)
                    return
            except (ValueError, ImportError, OSError, PermissionError) as e:
                logger.warning(f"Failed to use provider formatting: {e}")
            except Exception as e:
                logger.warning(f"Unexpected error in provider formatting: {e}")

        # Fallback to basic formatting
        try:
            self._save_basic_format(result, output_path)
        except (OSError, PermissionError) as e:
            logger.error(f"Failed to save transcription result: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error saving transcription: {e}")
            raise

    def _save_basic_format(self, result: TranscriptionResult, output_path: Path) -> None:
        """Save transcription result in basic format.

        Args:
            result: TranscriptionResult to save
            output_path: Path where to save the result
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write("TRANSCRIPTION RESULT\n")
            f.write("=" * 50 + "\n")
            f.write(f"Generated: {result.generated_at.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Provider: {result.provider_name}\n")
            f.write(f"Audio File: {Path(result.audio_file).name}\n")
            f.write(f"Duration: {result.duration:.2f} seconds\n")
            f.write("=" * 50 + "\n\n")

            f.write("TRANSCRIPT:\n")
            f.write("-" * 20 + "\n\n")
            f.write(result.transcript)
            f.write("\n\n" + "=" * 50 + "\n")

        logger.info(f"Transcription saved to: {output_path}")

    def _get_provider_key_from_name(self, provider_name: str) -> str:
        """Map display provider names to internal provider keys.

        Args:
            provider_name: Display name from provider.get_provider_name()

        Returns:
            Internal provider key used by factory

        Raises:
            ValueError: If provider name cannot be mapped
        """
        # Map from display names to internal keys
        name_mappings = {"Deepgram Nova 3": "deepgram", "ElevenLabs": "elevenlabs"}

        # Return mapped key or assume it's already an internal key
        mapped_key = name_mappings.get(provider_name, provider_name.lower())

        # Validate it's a known provider
        available = self.factory.get_available_providers()
        if mapped_key not in available:
            raise ValueError(
                f"Unknown provider '{provider_name}'. Available providers: {available}"
            )

        return mapped_key
