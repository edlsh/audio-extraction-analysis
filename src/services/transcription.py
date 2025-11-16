"""Core transcription orchestration service."""

from __future__ import annotations

import asyncio
import json
import logging
import math
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from ..models.transcription import TranscriptionResult
from ..providers.factory import TranscriptionProviderFactory
from ..utils.file_validation import safe_validate_audio_file

logger = logging.getLogger(__name__)


class TranscriptionService:
    """Coordinates transcription operations across providers."""

    def __init__(self):
        self.factory = TranscriptionProviderFactory

    def get_available_providers(self) -> list[str]:
        """List all registered providers."""
        return self.factory.get_available_providers()

    def get_configured_providers(self) -> list[str]:
        """List providers with valid configuration."""
        return self.factory.get_configured_providers()

    def auto_select_provider(
        self, audio_file_path: Path | None = None, preferred_features: list[str] | None = None
    ) -> str:
        """Select best provider for transcription."""
        return self.factory.auto_select_provider(audio_file_path, preferred_features)

    def _prepare_transcription(
        self, audio_file_path: Path, provider_name: str | None = None
    ) -> tuple[Path, str] | None:
        """Validate audio file and select provider for transcription.

        Args:
            audio_file_path: Path to the audio file to transcribe
            provider_name: Optional provider name. If None, auto-selects best provider

        Returns:
            Tuple of (validated_path, provider_name) or None if validation fails
        """
        # Validate audio file
        validated_path = safe_validate_audio_file(audio_file_path)
        if validated_path is None:
            return None

        # Auto-select provider if not specified
        if not provider_name:
            try:
                # Check if we're in test mode first
                import os

                test_provider = os.getenv("AUDIO_TEST_PROVIDER")
                if test_provider:
                    provider_name = test_provider
                    logger.info(f"Using test provider: {provider_name}")
                else:
                    provider_name = self.auto_select_provider(validated_path)
                    logger.info(f"Auto-selected provider: {provider_name}")
            except ValueError as e:
                # In CI/testing, fail gracefully if no providers configured
                if os.getenv("CI") or os.getenv("PYTEST_CURRENT_TEST"):
                    logger.warning(f"No providers configured in test environment: {e}")
                    return None
                logger.error(f"Failed to auto-select provider: {e}")
                return None

        # Validate provider can handle the file
        if not self.factory.validate_provider_for_file(provider_name, validated_path):
            logger.error(f"Provider '{provider_name}' cannot handle file: {validated_path}")
            return None

        return validated_path, provider_name

    def transcribe(
        self, audio_file_path: Path, provider_name: str | None = None, language: str = "en"
    ) -> TranscriptionResult | None:
        """Transcribe an audio file using the specified or auto-selected provider.

        Args:
            audio_file_path: Path to the audio file to transcribe
            provider_name: Optional provider name. If None, auto-selects best provider
            language: Language code for transcription (default: 'en')

        Returns:
            TranscriptionResult with available features, or None if failed
        """
        # Validate and prepare for transcription
        preparation = self._prepare_transcription(audio_file_path, provider_name)
        if preparation is None:
            return None
        audio_file_path, provider_name = preparation

        try:
            # Create provider instance
            provider = self.factory.create_provider(provider_name)

            # Perform transcription
            logger.info(f"Starting transcription with {provider.get_provider_name()}")
            result = provider.transcribe(audio_file_path, language)

            if result:
                logger.info(
                    f"Transcription completed successfully with {provider.get_provider_name()}"
                )
                logger.info(f"Transcript length: {len(result.transcript)} characters")
            else:
                logger.error(f"Transcription failed with {provider.get_provider_name()}")

            return result

        except ValueError as e:
            logger.error(f"Invalid provider or configuration: {e}")
            return None
        except FileNotFoundError as e:
            logger.error(f"Audio file not found: {e}")
            return None
        except ImportError as e:
            logger.error(f"Required provider module not available: {e}")
            return None
        except ConnectionError as e:
            logger.error(f"Network connection failed during transcription: {e}")
            return None
        except TimeoutError as e:
            logger.error(f"Transcription request timed out: {e}")
            return None
        except PermissionError as e:
            logger.error(f"Permission denied: {e}")
            return None
        except OSError as e:
            logger.error(f"System error during transcription: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected transcription error: {e}")
            return None

    async def transcribe_async(
        self, audio_file_path: Path, provider_name: str | None = None, language: str = "en"
    ) -> TranscriptionResult | None:
        """Transcribe an audio file asynchronously.

        Args:
            audio_file_path: Path to the audio file to transcribe
            provider_name: Optional provider name. If None, auto-selects best provider
            language: Language code for transcription (default: 'en')

        Returns:
            TranscriptionResult with available features, or None if failed
        """
        # Validate and prepare for transcription
        preparation = self._prepare_transcription(audio_file_path, provider_name)
        if preparation is None:
            return None
        audio_file_path, provider_name = preparation

        try:
            # Create provider instance
            provider = self.factory.create_provider(provider_name)

            # Perform async transcription with safe method checking
            logger.info(f"Starting async transcription with {provider.get_provider_name()}")

            # Check for async method first
            if hasattr(provider, "transcribe_async") and callable(provider.transcribe_async):
                try:
                    result = await provider.transcribe_async(audio_file_path, language)
                except Exception as e:
                    logger.warning(f"Async transcription failed, falling back to sync: {e}")
                    # Fall through to sync method
                    result = None
            else:
                result = None

            # Fallback to sync method wrapped in thread executor if async failed or doesn't exist
            if result is None:
                if hasattr(provider, "transcribe") and callable(provider.transcribe):
                    loop = asyncio.get_event_loop()

                    def sync_transcribe():
                        return provider.transcribe(audio_file_path, language)

                    result = await loop.run_in_executor(None, sync_transcribe)
                else:
                    raise ValueError(
                        f"Provider {provider.__class__.__name__} has no suitable transcription method"
                    )

            if result:
                logger.info(
                    f"Transcription completed successfully with {provider.get_provider_name()}"
                )
                logger.info(f"Transcript length: {len(result.transcript)} characters")
            else:
                logger.error(f"Transcription failed with {provider.get_provider_name()}")

            return result

        except ValueError as e:
            logger.error(f"Invalid provider or configuration for async: {e}")
            return None
        except FileNotFoundError as e:
            logger.error(f"Audio file not found for transcription: {e}")
            return None
        except ImportError as e:
            logger.error(f"Required provider module not available: {e}")
            return None
        except ConnectionError as e:
            logger.error(f"Network connection failed during transcription: {e}")
            return None
        except TimeoutError as e:
            logger.error(f"Transcription request timed out: {e}")
            return None
        except PermissionError as e:
            logger.error(f"Permission denied for transcription: {e}")
            return None
        except OSError as e:
            logger.error(f"System error during transcription: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected transcription error: {e}")
            return None

    async def transcribe_with_progress(
        self,
        audio_file_path: Path | str,
        provider_name: str | None = None,
        language: str = "en",
        progress_callback: Callable[[int, int], None] | None = None,
        **kwargs,
    ) -> TranscriptionResult | None:
        """Transcribe with progress estimation based on file characteristics."""
        path = Path(audio_file_path)

        # Calculate estimated processing time based on file characteristics
        file_size_mb = path.stat().st_size / (1024 * 1024)
        audio_duration = await self._get_audio_duration(str(path))

        # Auto-select provider if not specified or if "auto" is specified
        if not provider_name or provider_name == "auto":
            try:
                provider_name = self.auto_select_provider(path)
                logger.info(f"Auto-selected provider: {provider_name}")
            except ValueError as e:
                logger.error(f"Failed to auto-select provider: {e}")
                return None

        # Estimate transcription time (empirical formula based on provider speed)
        processing_speed = self._get_provider_speed_by_name(provider_name)  # MB per second

        estimated_time = max(
            file_size_mb / processing_speed,  # Based on file size
            (audio_duration or 60) * 0.1,  # Based on duration (10% of audio length)
            5.0,  # Minimum 5 seconds
        )

        # Create progress update task if callback provided
        progress_task = None
        if progress_callback:
            progress_task = asyncio.create_task(
                self._simulate_progress(estimated_time, progress_callback)
            )

        try:
            # Run actual transcription
            result = await self.transcribe_async(
                path, provider_name=provider_name, language=language
            )

            # Complete progress
            if progress_task:
                progress_task.cancel()
                if progress_callback:
                    try:
                        progress_callback(100, 100)
                    except Exception as e:
                        logger.debug(f"Failed to update progress: {e}")

            return result

        except Exception:
            if progress_task:
                progress_task.cancel()
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
                    progress_callback(100, 100)
                    break

                progress_pct = self._calculate_sigmoid_progress(elapsed, estimated_time)
                progress_callback(int(progress_pct), 100)

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

    def _get_provider_speed(self, provider: Any) -> float:
        """Get estimated processing speed for provider (MB/second)."""
        provider_name = provider.__class__.__name__
        return self._get_provider_speed_by_name(provider_name)

    def _get_provider_speed_by_name(self, provider_name: str) -> float:
        """Get estimated processing speed by provider name (MB/second)."""
        # Map both internal keys and class names to speeds
        provider_speeds = {
            "deepgram": 2.0,  # 2 MB/second
            "DeepgramTranscriber": 2.0,
            "elevenlabs": 1.0,  # 1 MB/second
            "ElevenLabsTranscriber": 1.0,
        }
        return provider_speeds.get(provider_name, 1.5)  # Default 1.5 MB/s

    async def _get_audio_duration(self, audio_path: str) -> float | None:
        """Get audio duration in seconds using ffprobe.

        Returns:
            Duration in seconds, or None if unable to determine
        """
        try:
            cmd = [
                "ffprobe",
                "-v",
                "quiet",
                "-print_format",
                "json",
                "-show_entries",
                "format=duration",
                audio_path,
            ]

            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await proc.communicate()

            if proc.returncode != 0:
                logger.debug(f"ffprobe failed with code {proc.returncode}: {stderr.decode()}")
                return None

            data = json.loads(stdout.decode())
            duration = float(data.get("format", {}).get("duration", 0))
            return duration if duration > 0 else None

        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.debug(f"Failed to parse audio duration: {e}")
            return None
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
    ) -> TranscriptionResult | None:
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
