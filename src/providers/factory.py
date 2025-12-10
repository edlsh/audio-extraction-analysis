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
import os
from typing import TYPE_CHECKING, Any

from src.utils.logger import get_logger

from ..config import get_config
from ..utils.retry import RetryConfig
from .base import BaseTranscriptionProvider, CircuitBreakerConfig, ProviderMeta
from .provider_utils import check_sdk_available, get_default_configs

if TYPE_CHECKING:
    from pathlib import Path

logger = get_logger(__name__)

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
        local providers (requiring Python packages). Uses provider META for
        configuration requirements.

        Returns:
            List of provider names that are properly configured and ready to use

        Note:
            This checks configuration only, not provider health or availability.
            Use check_provider_health() for runtime health validation.
        """
        configured = []
        config = get_config()

        for provider_name in _PROVIDER_IMPORTS:
            try:
                provider_class = cls._get_provider_class(provider_name)
                meta: ProviderMeta | None = getattr(provider_class, "META", None)
                
                if meta is None:
                    continue
                    
                if meta.is_local:
                    # Local provider - check SDK imports are available via unified helper
                    if check_sdk_available(meta):
                        configured.append(provider_name)
                else:
                    # Cloud provider - check API key is configured
                    if meta.api_key_env:
                        api_key = getattr(config, meta.api_key_env, None)
                        if api_key and len(api_key) >= meta.api_key_min_length:
                            configured.append(provider_name)
            except ImportError:
                # Provider dependencies not installed - skip silently
                pass

        return configured

    @classmethod
    def auto_select_provider(
        cls, audio_file_path: Path | None = None, preferred_features: list[str] | None = None
    ) -> str:
        """Auto-select the best available provider based on configuration and file.

        Selection priority:
        1. Deepgram (most features, fastest for API-based)
        2. ElevenLabs (good alternative API)
        3. Whisper (local, no API key needed)
        4. Parakeet (local, specialized)

        Args:
            audio_file_path: Optional path to audio file (for size-based selection)
            preferred_features: Optional list of required features

        Returns:
            Name of the selected provider

        Raises:
            ValueError: If no providers are configured
        """
        configured = cls.get_configured_providers()

        if not configured:
            raise ValueError(
                "No transcription providers configured. "
                "Set DEEPGRAM_API_KEY or ELEVENLABS_API_KEY, or install whisper/parakeet."
            )

        # Priority order for selection
        priority_order = ["deepgram", "elevenlabs", "whisper", "parakeet"]

        # If file is very large (>100MB), prefer local providers to avoid upload time
        if audio_file_path is not None:
            try:
                file_size_mb = audio_file_path.stat().st_size / (1024 * 1024)
                if file_size_mb > 100:
                    # Prefer local providers for large files
                    priority_order = ["whisper", "parakeet", "deepgram", "elevenlabs"]
                    logger.debug(f"Large file ({file_size_mb:.1f}MB), preferring local providers")
            except (OSError, AttributeError):
                pass  # File doesn't exist or path is None

        # Select first available provider in priority order
        for provider_name in priority_order:
            if provider_name in configured:
                logger.debug(f"Auto-selected provider: {provider_name}")
                return provider_name

        # Fallback to first configured provider
        return configured[0]

    @classmethod
    def validate_provider_for_file(cls, provider_name: str, file_path: Path) -> bool:
        """Validate that a provider can handle the given file.

        Checks:
        - Provider is available and configured
        - File size is within provider limits
        - File format is supported

        Args:
            provider_name: Name of the provider to validate
            file_path: Path to the audio file

        Returns:
            True if provider can handle the file, False otherwise
        """
        # Check provider is configured
        configured = cls.get_configured_providers()
        if provider_name not in configured:
            logger.warning(f"Provider '{provider_name}' is not configured")
            return False

        # Check file exists and get size
        try:
            file_size_mb = file_path.stat().st_size / (1024 * 1024)
        except (OSError, AttributeError) as e:
            logger.warning(f"Cannot access file '{file_path}': {e}")
            return False

        # Provider-specific size limits (in MB)
        size_limits = {
            "deepgram": 2000,  # 2GB limit
            "elevenlabs": 500,  # 500MB limit
            "whisper": float("inf"),  # Local, no limit
            "parakeet": float("inf"),  # Local, no limit
        }

        max_size = size_limits.get(provider_name, 100)  # Default 100MB
        if file_size_mb > max_size:
            logger.warning(
                f"File size ({file_size_mb:.1f}MB) exceeds {provider_name} limit ({max_size}MB)"
            )
            return False

        # Check file extension is audio
        audio_extensions = {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".opus", ".webm", ".mp4"}
        if file_path.suffix.lower() not in audio_extensions:
            logger.warning(f"File extension '{file_path.suffix}' may not be supported")
            # Don't fail, just warn - provider might still handle it

        return True

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
