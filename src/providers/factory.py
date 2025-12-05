"""Factory for creating and managing transcription service providers.

This module implements the Factory Pattern for transcription providers, providing:
- Lazy provider registration and discovery (imports deferred until first use)
- Configuration validation and optional health checking

Providers are loaded lazily on first access to avoid importing heavyweight
dependencies (torch, nemo) at module import time. This significantly improves
CLI startup performance.

Example:
    >>> # Create a provider (imports happen here, not at module load)
    >>> provider = TranscriptionProviderFactory.create_provider("deepgram")
    >>> result = await provider.transcribe_async(audio_file_path)
"""

from __future__ import annotations

import asyncio
import importlib
import logging
import os
from typing import TYPE_CHECKING, Any

from ..config import get_config
from ..utils.retry import RetryConfig
from .base import BaseTranscriptionProvider, CircuitBreakerConfig
from .provider_utils import get_default_configs

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)

# Lazy provider import registry: maps provider names to (module_path, class_name)
# Providers are imported only when first accessed, not at module load time
_PROVIDER_IMPORTS: dict[str, tuple[str, str]] = {
    "deepgram": (".deepgram", "DeepgramTranscriber"),
    "elevenlabs": (".elevenlabs", "ElevenLabsTranscriber"),
    "whisper": (".whisper", "WhisperTranscriber"),
    "parakeet": (".parakeet", "ParakeetTranscriber"),
}


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
        """Get list of all known provider names.

        Returns all providers that can potentially be loaded, including those
        not yet imported. This includes both already-loaded providers and
        those in the lazy import registry.

        Returns:
            List of provider names available for use
        """
        # Combine already-loaded providers with lazy registry
        all_providers = set(cls._providers.keys()) | set(_PROVIDER_IMPORTS.keys())
        # Add mock provider in test mode
        if os.getenv("AUDIO_TEST_MODE") or os.getenv("CI") or os.getenv("PYTEST_CURRENT_TEST"):
            all_providers.add("mock")
        return sorted(all_providers)

    @classmethod
    def _get_provider_class(cls, provider_name: str) -> type[BaseTranscriptionProvider]:
        """Lazy-load and return provider class.

        Imports the provider module only on first access, caching the class
        for subsequent calls. This avoids importing heavyweight dependencies
        (torch, whisper, nemo) until actually needed.

        Args:
            provider_name: Name of the provider to load

        Returns:
            Provider class implementing BaseTranscriptionProvider

        Raises:
            ValueError: If provider name is unknown
            ImportError: If provider module cannot be imported
        """
        # Return cached provider if already loaded
        if provider_name in cls._providers:
            return cls._providers[provider_name]

        # Handle mock provider for testing
        if provider_name == "mock":
            if os.getenv("AUDIO_TEST_MODE") or os.getenv("CI") or os.getenv("PYTEST_CURRENT_TEST"):
                from .mock import MockTranscriber
                cls._providers["mock"] = MockTranscriber
                logger.debug("Lazy-loaded Mock provider for testing")
                return MockTranscriber
            raise ValueError("Mock provider only available in test mode")

        # Check if provider is in lazy registry
        if provider_name not in _PROVIDER_IMPORTS:
            available = ", ".join(cls.get_available_providers())
            raise ValueError(
                f"Unknown provider '{provider_name}'. Available providers: {available}"
            )

        # Lazy import the provider module
        module_path, class_name = _PROVIDER_IMPORTS[provider_name]
        try:
            module = importlib.import_module(module_path, package="src.providers")
            provider_class = getattr(module, class_name)
            cls._providers[provider_name] = provider_class
            logger.debug(f"Lazy-loaded provider: {provider_name}")
            return provider_class
        except ImportError as e:
            logger.warning(f"Provider '{provider_name}' not available: {e}")
            raise ImportError(f"Provider '{provider_name}' dependencies not installed: {e}") from e

    @classmethod
    def get_configured_providers(cls) -> list[str]:
        """Get list of providers that have valid API keys or dependencies configured.

        This method checks both API-based providers (requiring API keys) and
        local providers (requiring Python packages). Local provider checks are
        performed lazily to avoid importing heavyweight dependencies.

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

        # Check local providers lazily - only import if checking availability
        # Whisper: OpenAI's local speech recognition model
        try:
            import torch  # noqa: F401
            import whisper  # noqa: F401
            configured.append("whisper")
        except ImportError:
            pass  # Expected when whisper not installed

        # Parakeet: NVIDIA NeMo's local speech recognition model
        try:
            import nemo.collections.asr  # noqa: F401
            configured.append("parakeet")
        except ImportError:
            pass  # Expected when nemo not installed

        return configured

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
        run_health_check: bool = False,
    ) -> BaseTranscriptionProvider:
        """Create provider with validation and optional health check.

        Args:
            provider_name: 'deepgram', 'elevenlabs', 'whisper', or 'parakeet'
            api_key: Override API key (uses env config if None)
            circuit_config: Override circuit breaker config
            retry_config: Override retry config
            run_health_check: Run health check after creation (default: False)

        Raises:
            ValueError: If provider unknown or config invalid
            ImportError: If provider dependencies not installed
        """
        # Lazy-load provider class (imports module on first access)
        try:
            provider_class = cls._get_provider_class(provider_name)
        except ImportError as e:
            logger.error(f"Provider module not available '{provider_name}': {e}")
            raise ValueError(f"Provider '{provider_name}' module not available") from e

        try:
            # Get default configurations if not provided (from shared utility)
            retry_config, circuit_config = get_default_configs(retry_config, circuit_config)

            # Create and validate provider instance
            provider = cls._create_provider_instance(
                provider_class, provider_name, api_key, circuit_config, retry_config
            )

            # Run health check if requested (opt-in)
            if run_health_check:
                cls._run_health_check(provider, provider_name)

            logger.info(f"Created transcription provider: {provider.get_provider_name()}")
            return provider

        except ValueError as e:
            logger.error(f"Failed to create provider '{provider_name}': {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error creating provider '{provider_name}': {e}")
            raise ValueError(f"Failed to create provider '{provider_name}'") from e

    @classmethod
    async def check_provider_health(
        cls, provider_name: str, api_key: str | None = None
    ) -> dict[str, Any]:
        """Check if provider is operational. Returns health dict, not exceptions."""
        # Validate provider exists (will raise ValueError if unknown)
        try:
            cls._get_provider_class(provider_name)
        except (ValueError, ImportError) as e:
            return {
                "healthy": False,
                "status": "provider_unavailable",
                "response_time_ms": 0,
                "details": {
                    "provider": provider_name,
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
            }

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


# Note: Provider registration is now lazy - providers are imported on first use
# via _get_provider_class(), not at module import time. This improves CLI startup
# by avoiding heavyweight imports (torch, nemo) until actually needed.
