"""Factory for creating and managing transcription service providers.

This module implements the Factory Pattern for transcription providers, providing:
- Provider registration and discovery
- Configuration validation and health checking

The factory automatically registers available providers on module import and
supports both synchronous and asynchronous operations.

Example:
    >>> # Create a provider
    >>> provider = TranscriptionProviderFactory.create_provider("deepgram")
    >>> result = await provider.transcribe_async(audio_file_path)
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from ..config import get_config
from ..utils.retry import RetryConfig
from .base import BaseTranscriptionProvider, CircuitBreakerConfig

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)


class TranscriptionProviderFactory:
    """Factory class for creating and managing transcription service providers.

    This factory provides centralized management of transcription providers including:
    - Provider registration and lifecycle management
    - Intelligent auto-selection based on file size, features, and health
    - Configuration validation and health monitoring
    - Thread-safe class-level operations

    All methods are class methods, allowing the factory to be used without instantiation.
    The provider registry is shared across all access points.

    Thread Safety:
        Class methods are thread-safe for reading operations. Provider registration
        should only be performed during module initialization to avoid race conditions.
    """

    # Registry of available providers: maps provider names to their implementation classes
    _providers: dict[str, type[BaseTranscriptionProvider]] = {}

    @classmethod
    def register_provider(cls, name: str, provider_class: type[BaseTranscriptionProvider]) -> None:
        """Register a transcription provider.

        Args:
            name: Provider name (e.g., 'deepgram', 'elevenlabs')
            provider_class: Provider class implementing BaseTranscriptionProvider
        """
        cls._providers[name] = provider_class
        logger.debug(f"Registered transcription provider: {name}")

    @classmethod
    def get_available_providers(cls) -> list[str]:
        """Get list of registered provider names.

        Returns:
            List of provider names that are registered
        """
        return list(cls._providers.keys())

    @classmethod
    def get_configured_providers(cls) -> list[str]:
        """Get list of providers that have valid API keys or dependencies configured.

        This method checks both API-based providers (requiring API keys) and
        local providers (requiring Python packages):

        - Deepgram: Requires DEEPGRAM_API_KEY environment variable
        - ElevenLabs: Requires ELEVENLABS_API_KEY environment variable
        - Whisper: Requires torch and whisper packages (no API key needed)
        - Parakeet: Requires nemo.collections.asr package (no API key needed)

        Returns:
            List of provider names that are properly configured and ready to use

        Note:
            This checks configuration only, not provider health or availability.
            Use check_provider_health() for runtime health validation.
        """
        configured = []
        config = get_config()

        # Check API-based providers (require authentication keys)
        if config.DEEPGRAM_API_KEY:
            configured.append("deepgram")

        if config.ELEVENLABS_API_KEY:
            configured.append("elevenlabs")

        # Check local providers (require dependencies but no API keys)
        # Whisper: OpenAI's local speech recognition model
        try:
            import torch
            import whisper

            configured.append("whisper")
        except ImportError:
            pass  # Expected when whisper not installed

        # Parakeet: NVIDIA NeMo's local speech recognition model
        try:
            import nemo.collections.asr as nemo_asr

            configured.append("parakeet")
        except ImportError:
            pass  # Expected when nemo not installed

        return configured

    @classmethod
    def _get_default_configs(
        cls,
        provider_name: str,
        circuit_config: CircuitBreakerConfig | None,
        retry_config: RetryConfig | None,
    ) -> tuple[CircuitBreakerConfig, RetryConfig]:
        """Return default circuit breaker and retry configs from Config singleton."""
        if circuit_config is not None and retry_config is not None:
            return circuit_config, retry_config

        config = get_config()

        if circuit_config is None:
            circuit_config = CircuitBreakerConfig(
                failure_threshold=config.circuit_breaker_failure_threshold,
                recovery_timeout=config.circuit_breaker_recovery_timeout,
            )

        if retry_config is None:
            retry_config = RetryConfig(
                max_attempts=config.max_retries,
                base_delay=config.retry_delay,
                max_delay=config.max_retry_delay,
                exponential_base=config.retry_exponential_base,
                jitter=config.retry_jitter,
            )

        return circuit_config, retry_config

    @classmethod
    def _run_health_check(cls, provider: BaseTranscriptionProvider, provider_name: str) -> None:
        """Run health check if enabled. Failures are logged as warnings, not raised."""
        if not get_config().HEALTH_CHECK_ENABLED:
            return

        try:
            health_result = provider.health_check()
            if not health_result.get("healthy", False):
                logger.warning(
                    f"Provider '{provider_name}' health check failed: {health_result.get('status')}"
                )
            else:
                logger.info(f"Provider '{provider_name}' health check passed")
        except Exception as e:
            logger.warning(f"Health check failed for '{provider_name}': {e}")

    @classmethod
    def _create_provider_instance(
        cls,
        provider_class: type[BaseTranscriptionProvider],
        provider_name: str,
        api_key: str | None,
        circuit_config: CircuitBreakerConfig,
        retry_config: RetryConfig,
    ) -> BaseTranscriptionProvider:
        """Instantiate and validate provider. Raises ValueError if validation fails."""
        provider = provider_class(
            api_key=api_key, circuit_config=circuit_config, retry_config=retry_config
        )

        if not provider.validate_configuration():
            raise ValueError(f"Provider '{provider_name}' is not properly configured")

        return provider

    @classmethod
    def create_provider(
        cls,
        provider_name: str,
        api_key: str | None = None,
        circuit_config: CircuitBreakerConfig | None = None,
        retry_config: RetryConfig | None = None,
        run_health_check: bool = True,
    ) -> BaseTranscriptionProvider:
        """Create provider with validation and optional health check.

        Args:
            provider_name: 'deepgram', 'elevenlabs', 'whisper', or 'parakeet'
            api_key: Override API key (uses env config if None)
            circuit_config: Override circuit breaker config
            retry_config: Override retry config
            run_health_check: Run health check after creation (default: True)

        Raises:
            ValueError: If provider unknown or config invalid
        """
        if provider_name not in cls._providers:
            available = ", ".join(cls.get_available_providers())
            raise ValueError(
                f"Unknown provider '{provider_name}'. Available providers: {available}"
            )

        provider_class = cls._providers[provider_name]

        try:
            # Get default configurations if not provided
            circuit_config, retry_config = cls._get_default_configs(
                provider_name, circuit_config, retry_config
            )

            # Create and validate provider instance
            provider = cls._create_provider_instance(
                provider_class, provider_name, api_key, circuit_config, retry_config
            )

            # Run health check if requested
            if run_health_check:
                cls._run_health_check(provider, provider_name)

            logger.info(f"Created transcription provider: {provider.get_provider_name()}")
            return provider

        except ValueError as e:
            logger.error(f"Failed to create provider '{provider_name}': {e}")
            raise
        except ImportError as e:
            logger.error(f"Provider module not available '{provider_name}': {e}")
            raise ValueError(f"Provider '{provider_name}' module not available") from e
        except Exception as e:
            logger.error(f"Unexpected error creating provider '{provider_name}': {e}")
            raise ValueError(f"Failed to create provider '{provider_name}'") from e

    @classmethod
    async def check_provider_health(
        cls, provider_name: str, api_key: str | None = None
    ) -> dict[str, Any]:
        """Check if provider is operational. Returns health dict, not exceptions."""
        if provider_name not in cls._providers:
            available = ", ".join(cls.get_available_providers())
            raise ValueError(
                f"Unknown provider '{provider_name}'. Available providers: {available}"
            )

        try:
            provider = cls.create_provider(provider_name, api_key, run_health_check=False)
            return await provider.health_check_async()
        except Exception as e:
            return {
                "healthy": False,
                "status": "creation_failed",
                "response_time_ms": 0,
                "details": {
                    "provider": provider_name,
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
            }

    @classmethod
    def check_provider_health_sync(
        cls, provider_name: str, api_key: str | None = None
    ) -> dict[str, Any]:
        """Sync wrapper for check_provider_health. Uses thread pool if in async context."""
        try:
            asyncio.get_running_loop()
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run, cls.check_provider_health(provider_name, api_key)
                )
                return future.result(timeout=30)
        except RuntimeError:
            return asyncio.run(cls.check_provider_health(provider_name, api_key))


# Initialize the factory with default providers
def _initialize_factory() -> None:
    """Initialize factory with all available transcription providers.

    This function attempts to import and register each supported provider.
    Import failures are logged as warnings but do not prevent other providers
    from being registered. This allows the system to work with partial provider
    availability.

    Registered Providers:
        - Deepgram: Cloud-based API with advanced features
        - ElevenLabs: Cloud-based API with high accuracy
        - Whisper: OpenAI's local model (requires torch, whisper packages)
        - Parakeet: NVIDIA NeMo's local model (requires nemo package)

    Note:
        This function is automatically called on module import. Manual invocation
        is not necessary and may cause duplicate registration warnings.

    Raises:
        Does not raise exceptions; all import errors are caught and logged.
    """
    # Cloud-based providers (require API keys)
    try:
        from .deepgram import DeepgramTranscriber

        TranscriptionProviderFactory.register_provider("deepgram", DeepgramTranscriber)
        logger.debug("Registered Deepgram provider")
    except ImportError as e:
        logger.warning(f"Deepgram provider not available: {e}")

    try:
        from .elevenlabs import ElevenLabsTranscriber

        TranscriptionProviderFactory.register_provider("elevenlabs", ElevenLabsTranscriber)
        logger.debug("Registered ElevenLabs provider")
    except ImportError as e:
        logger.warning(f"ElevenLabs provider not available: {e}")

    # Mock provider for testing
    import os

    if os.getenv("AUDIO_TEST_MODE") or os.getenv("CI") or os.getenv("PYTEST_CURRENT_TEST"):
        try:
            from .mock import MockTranscriber

            TranscriptionProviderFactory.register_provider("mock", MockTranscriber)
            logger.debug("Registered Mock provider for testing")
        except ImportError as e:
            logger.warning(f"Mock provider not available: {e}")

    # Local model providers (require ML frameworks)
    try:
        from .whisper import WhisperTranscriber

        TranscriptionProviderFactory.register_provider("whisper", WhisperTranscriber)
        logger.debug("Registered Whisper provider")
    except ImportError as e:
        logger.warning(f"Whisper provider not available: {e}")

    try:
        from .parakeet import ParakeetTranscriber

        TranscriptionProviderFactory.register_provider("parakeet", ParakeetTranscriber)
        logger.debug("Registered Parakeet provider")
    except (ImportError, Exception) as e:
        logger.warning(f"Parakeet provider not available: {e}")


# Auto-initialize: Register all available providers when module is imported
# This ensures the factory is ready to use without manual setup
_initialize_factory()
