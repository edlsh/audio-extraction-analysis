"""Core transcription orchestration service.

This module provides the TranscriptionService which coordinates transcription
operations across providers. Key features:
- Policy-based timeout/retry configuration (TranscriptionPolicy)
- Unified async transcription with thin sync wrapper
- Automatic provider selection via ProviderSelectionPolicy
- Caching support
"""

from __future__ import annotations

import asyncio
import math
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from src.utils.logger import get_logger

if TYPE_CHECKING:
    from collections.abc import Callable

    from ..models.transcription import TranscriptionResult
    from .cache import TranscriptionCache
from ..config import get_config
from ..exceptions import ProviderTimeoutError, TranscriptionError
from ..providers.factory import TranscriptionProviderFactory
from ..utils.constants import Timeouts
from ..utils.file_validation import validate_audio_file_or_raise
from .ffmpeg_core import probe_media_async

logger = get_logger(__name__)


class TranscriptionService:
    """Coordinates transcription operations across providers.

    Uses Config directly for timeout/retry configuration.
    Provider layer implements only _transcribe_impl (async), this service
    layer exposes transcribe_async + thin sync wrapper.
    """

    def __init__(
        self,
        cache: TranscriptionCache | None = None,
        *,
        test_override_provider: str | None = None,
        is_test_environment: bool = False,
    ) -> None:
        """Initialize transcription service.

        Args:
            cache: Optional TranscriptionCache instance for caching results.
                   If None, caching is disabled.
            test_override_provider: Optional provider override used only when
                auto-selecting providers in controlled test scenarios.
            is_test_environment: Explicit test-mode flag for mapping provider
                auto-selection failures to ProviderNotAvailableError.
        """
        self.factory = TranscriptionProviderFactory
        self._config = get_config()
        self._cache = cache
        self._test_override_provider = test_override_provider
        self._is_test_environment = is_test_environment

    @property
    def _provider_timeout(self) -> float:
        """Get transcription timeout from config."""
        return float(self._config.transcription_timeout_seconds)

    def _prepare_transcription(
        self,
        audio_file_path: Path,
        provider_name: str | None = None,
        *,
        test_override_provider: str | None = None,
        is_test_environment: bool | None = None,
    ) -> tuple[Path, str]:
        """Validate audio file and select provider for transcription.

        Args:
            audio_file_path: Path to the audio file to transcribe
            provider_name: Optional provider name. If None, auto-selects best provider
            test_override_provider: Optional provider override used only for this call
            is_test_environment: Optional test-mode override for this call

        Returns:
            Tuple of (validated_path, provider_name)

        Raises:
            ValidationError: If audio file validation fails
            ProviderSelectionError: If no suitable provider can be found
            ProviderValidationError: If provider cannot handle the file
            ProviderNotAvailableError: If no providers configured (test environments)
        """
        from ..exceptions import (
            ProviderNotAvailableError,
            ProviderSelectionError,
            ProviderValidationError,
        )

        effective_test_override = (
            self._test_override_provider
            if test_override_provider is None
            else test_override_provider
        )
        effective_test_environment = (
            self._is_test_environment if is_test_environment is None else is_test_environment
        )

        # Validate audio file
        validated_path = validate_audio_file_or_raise(audio_file_path)

        # Auto-select provider if not specified
        if not provider_name:
            try:
                provider_name = self.factory.auto_select_provider(
                    audio_file_path=validated_path,
                    test_override=effective_test_override,
                    include_test_providers=effective_test_environment,
                )
                logger.info(f"Auto-selected provider: {provider_name}")
            except ValueError as e:
                if effective_test_environment:
                    raise ProviderNotAvailableError(
                        "No providers configured in test environment",
                        context={"environment": "test", "ci": False},
                    ) from e
                raise ProviderSelectionError(
                    f"Failed to auto-select provider: {e}",
                    context={"file_path": str(validated_path)},
                ) from e

        # Validate provider can handle the file
        if not self.factory.validate_provider_for_file(provider_name, validated_path):
            raise ProviderValidationError(
                f"Provider '{provider_name}' cannot handle file",
                context={
                    "provider": provider_name,
                    "file_path": str(validated_path),
                    "file_size": validated_path.stat().st_size,
                },
            )

        return validated_path, provider_name

    def _configure_provider_timeout(self, provider: Any) -> None:
        """Apply config timeouts to provider instances when supported."""
        if hasattr(provider, "update_transcription_timeout"):
            try:
                provider.update_transcription_timeout(
                    float(self._config.transcription_timeout_seconds)
                )
            except Exception as exc:  # pragma: no cover - defensive
                logger.debug("Failed to update provider timeout: %s", exc)

    def _create_provider(self, provider_name: str) -> Any:
        """Create provider instance with config-based configuration."""
        return self.factory.create_provider(
            provider_name,
            include_test_providers=self._is_test_environment,
        )

    def transcribe(
        self,
        audio_file_path: Path,
        provider_name: str | None = None,
        language: str = "en",
        *,
        use_cache: bool = True,
    ) -> TranscriptionResult:
        """Transcribe an audio file using the specified or auto-selected provider.

        Args:
            audio_file_path: Path to the audio file to transcribe
            provider_name: Optional provider name. If None, auto-selects best provider
            language: Language code for transcription (default: 'en')
            use_cache: Whether to use caching (default: True). Requires cache to be configured.

        Returns:
            TranscriptionResult with available features

        Raises:
            ValidationError: If audio file validation fails
            ProviderSelectionError: If no suitable provider found
            ProviderNotAvailableError: If provider SDK not installed
            ProviderAuthenticationError: If API key invalid
            ProviderRateLimitError: If rate limit exceeded
            ProviderTimeoutError: If request times out
            ProviderAPIError: If provider API fails
            TranscriptionError: If transcription produces no result or fails
        """
        # Validate and prepare for transcription (now raises exceptions)
        audio_file_path, provider_name = self._prepare_transcription(audio_file_path, provider_name)

        # Check cache first if enabled
        if use_cache and self._cache is not None:
            try:
                cached_result = self._cache.get(audio_file_path, provider_name, language)
                if cached_result is not None:
                    logger.info(f"Using cached transcription for {audio_file_path.name}")
                    return cached_result
            except Exception as e:
                # Log but don't fail on cache errors
                logger.warning(f"Cache lookup failed, proceeding with transcription: {e}")

        # Create provider instance with policy-based configuration
        provider = self._create_provider(provider_name)

        # Perform transcription (let provider exceptions propagate)
        logger.info(f"Starting transcription with {provider.get_provider_name()}")
        try:
            result = provider.transcribe(audio_file_path, language, timeout=self._provider_timeout)
        except TimeoutError as exc:
            raise ProviderTimeoutError(
                f"Transcription timed out after {self._provider_timeout}s",
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

        # Cache the result if enabled
        if use_cache and self._cache is not None:
            try:
                self._cache.put(audio_file_path, provider_name, language, result)
            except Exception as e:
                logger.warning(f"Failed to cache transcription result: {e}")

        assert isinstance(result, TranscriptionResult)
        return result

    async def transcribe_async(
        self,
        audio_file_path: Path,
        provider_name: str | None = None,
        language: str = "en",
        *,
        use_cache: bool = True,
    ) -> TranscriptionResult:
        """Transcribe an audio file asynchronously.

        Args:
            audio_file_path: Path to the audio file to transcribe
            provider_name: Optional provider name. If None, auto-selects best provider
            language: Language code for transcription (default: 'en')
            use_cache: Whether to use caching (default: True). Requires cache to be configured.

        Returns:
            TranscriptionResult with available features

        Raises:
            ValidationError: If audio file validation fails
            ProviderSelectionError: If no suitable provider found
            ProviderNotAvailableError: If provider SDK not installed
            ProviderAuthenticationError: If API key invalid
            ProviderRateLimitError: If rate limit exceeded
            ProviderTimeoutError: If request times out
            ProviderAPIError: If provider API fails
            TranscriptionError: If transcription produces no result or fails
        """
        # Validate and prepare for transcription (now raises exceptions)
        audio_file_path, provider_name = self._prepare_transcription(audio_file_path, provider_name)

        # Check cache first if enabled
        if use_cache and self._cache is not None:
            try:
                cached_result = self._cache.get(audio_file_path, provider_name, language)
                if cached_result is not None:
                    logger.info(f"Using cached transcription for {audio_file_path.name}")
                    return cached_result
            except Exception as e:
                # Log but don't fail on cache errors
                logger.warning(f"Cache lookup failed, proceeding with transcription: {e}")

        # Create provider instance with policy-based configuration
        provider = self._create_provider(provider_name)
        timeout_seconds = self._provider_timeout

        logger.info(f"Starting async transcription with {provider.get_provider_name()}")

        try:
            result = await provider.transcribe_async(
                audio_file_path, language, timeout=timeout_seconds
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

        if use_cache and self._cache is not None:
            try:
                self._cache.put(audio_file_path, provider_name, language, result)
            except Exception as e:
                logger.warning(f"Failed to cache transcription result: {e}")

        assert isinstance(result, TranscriptionResult)
        return result

    async def transcribe_with_progress(
        self,
        audio_file_path: Path | str,
        provider_name: str | None = None,
        language: str = "en",
        progress_callback: Callable[[int, int], None] | None = None,
        **kwargs: Any,
    ) -> TranscriptionResult:
        """Transcribe with progress estimation based on file characteristics.

        Args:
            audio_file_path: Path to the audio file to transcribe
            provider_name: Optional provider name. If None or "auto", auto-selects best provider
            language: Language code for transcription (default: 'en')
            progress_callback: Optional callback for progress updates

        Returns:
            TranscriptionResult with available features

        Raises:
            ValidationError: If audio file validation fails
            ProviderSelectionError: If no suitable provider found
            ProviderNotAvailableError: If provider SDK not installed
            ProviderAuthenticationError: If API key invalid
            ProviderRateLimitError: If rate limit exceeded
            ProviderTimeoutError: If request times out
            ProviderAPIError: If provider API fails
            TranscriptionError: If transcription produces no result or fails
        """
        resolved_provider = provider_name if provider_name and provider_name != "auto" else None
        path, resolved_provider = self._prepare_transcription(
            Path(audio_file_path), resolved_provider
        )

        # Calculate estimated processing time based on file characteristics
        file_size_mb = path.stat().st_size / (1024 * 1024)
        audio_duration = await self._get_audio_duration(str(path))

        # Estimate transcription time (empirical formula based on provider speed)
        from src.utils.progress_constants import ProgressConstants

        processing_speed = self._get_provider_speed_by_name(resolved_provider)  # MB per second

        estimated_time = max(
            file_size_mb / processing_speed,  # Based on file size
            (audio_duration or ProgressConstants.DEFAULT_AUDIO_DURATION)
            * ProgressConstants.DURATION_RATIO,  # Based on duration
            ProgressConstants.MINIMUM_SECONDS,  # Minimum
        )

        # Create progress update task inside try block to ensure cleanup on exception
        progress_task = None
        try:
            if progress_callback:
                progress_task = asyncio.create_task(
                    self._simulate_progress(estimated_time, progress_callback)
                )

            # Run actual transcription
            result = await self.transcribe_async(
                path, provider_name=resolved_provider, language=language
            )

            # Complete progress
            if progress_task:
                progress_task.cancel()
                try:
                    await progress_task
                except asyncio.CancelledError:
                    pass
                if progress_callback:
                    try:
                        progress_callback(100, 100)
                    except Exception as e:
                        logger.debug(f"Failed to update progress: {e}")

            return result

        except Exception as e:
            # Catch all exceptions for cleanup: cancel progress task before re-raising
            logger.debug(f"Transcription failed, cleaning up: {e}")
            if progress_task:
                progress_task.cancel()
                try:
                    await progress_task
                except asyncio.CancelledError:
                    pass
            raise

    async def _simulate_progress(
        self, estimated_time: float, progress_callback: Callable[[int, int], None]
    ) -> None:
        """Simulate progress during transcription."""
        start_time = time.time()

        try:
            while True:
                elapsed = time.time() - start_time

                # Use sigmoid function for realistic progress curve
                # Fast start, slower middle, fast finish
                if elapsed >= estimated_time:
                    try:
                        progress_callback(100, 100)
                    except Exception:
                        pass
                    break

                progress_pct = self._calculate_sigmoid_progress(elapsed, estimated_time)
                try:
                    progress_callback(int(progress_pct), 100)
                except Exception:
                    pass

                await asyncio.sleep(0.5)  # Update every 500ms

        except asyncio.CancelledError:
            pass  # Task was cancelled, transcription completed

    def _calculate_sigmoid_progress(self, elapsed: float, total: float) -> float:
        """Calculate realistic progress using sigmoid curve."""
        # Normalize time to 0-1 range
        x = (elapsed / total) * 12 - 6  # Map to -6 to +6 for good sigmoid shape

        # Sigmoid function: 1 / (1 + e^(-x))
        sigmoid = 1 / (1 + math.exp(-x))

        # Scale to 0-95% (leave 5% for completion)
        return sigmoid * 95

    def _get_provider_speed_by_name(self, provider_name: str) -> float:
        """Get estimated processing speed by provider name (MB/second)."""
        try:
            provider = self._create_provider(provider_name)
            if hasattr(provider, "META") and provider.META:
                return provider.META.estimated_speed_mb_per_sec
        except Exception:
            pass
        return 1.5  # Default fallback

    async def _get_audio_duration(self, audio_path: str) -> float | None:
        """Get audio duration in seconds using ffprobe.

        Returns:
            Duration in seconds, or None if unable to determine
        """
        try:
            probe_result = await probe_media_async(
                Path(audio_path),
                timeout=Timeouts.FFMPEG_PROBE,
            )
            return probe_result.duration

        except asyncio.CancelledError:
            raise
        except FileNotFoundError:
            logger.debug("ffprobe not found in PATH")
            return None
        except Exception as e:
            logger.warning(f"Unexpected error getting audio duration: {e}")
            return None

    # Convenience alias for compatibility with progress-enabled pipeline tests
    async def transcribe_file(
        self,
        audio_file_path: Path | str,
        provider_name: str | None = None,
        language: str = "en",
        progress_callback: Callable[[int, int], None] | None = None,  # Ignored for now
        **_: Any,
    ) -> TranscriptionResult:
        """Alias to transcribe_async that accepts a progress callback (ignored).

        Accepts both Path and string paths and forwards to transcribe_async.
        """
        path = Path(audio_file_path)
        return await self.transcribe_async(path, provider_name=provider_name, language=language)

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
            provider = self._create_provider(provider_name)
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
                provider = self._create_provider(provider_key)
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
        available = self.factory.get_available_providers(
            include_test_providers=self._is_test_environment
        )
        if mapped_key not in available:
            raise ValueError(
                f"Unknown provider '{provider_name}'. Available providers: {available}"
            )

        return mapped_key
