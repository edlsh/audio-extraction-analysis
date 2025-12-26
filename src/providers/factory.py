"""Factory for creating and managing transcription service providers.

This module implements the Factory Pattern for transcription providers, providing:
- Direct provider registration and discovery
- Configuration validation and optional health checking
- Policy-based provider selection (delegated to ProviderSelectionPolicy)

Example:
    >>> provider = TranscriptionProviderFactory.create_provider("deepgram")
    >>> result = await provider.transcribe_async(audio_file_path)
"""

from __future__ import annotations

import asyncio
import os
import threading
from typing import TYPE_CHECKING, Any

from src.utils.logger import get_logger

from ..config import get_config
from ..utils.retry import RetryConfig
from .base import BaseTranscriptionProvider, ProviderMeta
from .policy import ProviderSelectionPolicy
from .provider_utils import check_sdk_available, get_default_configs

if TYPE_CHECKING:
    from pathlib import Path

logger = get_logger(__name__)

# Provider registry: maps provider names to import path strings OR class objects.
# String paths enable lazy loading; class objects support local/test classes.
_providers: dict[str, str | type[BaseTranscriptionProvider]] = {
    "deepgram": "src.providers.deepgram.DeepgramTranscriber",
    "elevenlabs": "src.providers.elevenlabs.ElevenLabsTranscriber",
    "whisper": "src.providers.whisper.WhisperTranscriber",
    "parakeet": "src.providers.parakeet.ParakeetTranscriber",
    "stub": "src.providers.stub.StubTranscriptionProvider",
}


def register_provider(name: str, provider_class_or_path: type[BaseTranscriptionProvider] | str) -> None:
    """Register a provider class or import path.

    Args:
        name: Provider name (e.g., "custom")
        provider_class_or_path: Either a class object or a dotted import path string.
            Class objects are stored directly (supports local/test classes).
            Strings are stored as-is for lazy loading.

    Note:
        This function modifies the module-level registry. For thread safety,
        call only during module initialization.
    """
    _providers[name] = provider_class_or_path


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

    @classmethod
    def get_available_providers(cls) -> list[str]:
        """Get list of all known provider names.

        Returns:
            List of provider names available for use
        """
        # Add mock provider in test mode
        provider_names = set(_providers.keys())
        if os.getenv("AUDIO_TEST_MODE") or os.getenv("CI") or os.getenv("PYTEST_CURRENT_TEST"):
            provider_names.add("mock")
        return sorted(provider_names)

    @classmethod
    def _get_provider_class(cls, provider_name: str) -> type[BaseTranscriptionProvider]:
        """Get provider class by name.

        Args:
            provider_name: Name of the provider to load

        Returns:
            Provider class implementing BaseTranscriptionProvider

        Raises:
            ValueError: If provider name is unknown
        """
        # Handle mock provider for testing
        if provider_name == "mock":
            if os.getenv("AUDIO_TEST_MODE") or os.getenv("CI") or os.getenv("PYTEST_CURRENT_TEST"):
                from .mock import MockTranscriber

                return MockTranscriber
            raise ValueError("Mock provider only available in test mode")

        # Look up in registry
        if provider_name not in _providers:
            available = ", ".join(cls.get_available_providers())
            raise ValueError(
                f"Unknown provider '{provider_name}'. Available providers: {available}"
            )

        provider_entry = _providers[provider_name]

        # Return class directly if stored as class object (e.g., local/test classes)
        if isinstance(provider_entry, type):
            return provider_entry

        # Lazy-load provider class from import path string
        return cls._import_provider_class(provider_entry)

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

        for provider_name in _providers:
            try:
                # Lazy-load provider class to check configuration
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
            except ImportError as e:
                # Provider dependencies not installed - skip this provider
                logger.debug(f"Provider {provider_name} skipped due to missing dependencies: {e}")
            except ValueError as e:
                # Provider not available - skip this provider
                logger.debug(f"Provider {provider_name} skipped: {e}")

        return configured

    # Default selection policy instance
    _selection_policy: ProviderSelectionPolicy | None = None
    _selection_policy_lock = threading.Lock()

    @classmethod
    def get_selection_policy(cls) -> ProviderSelectionPolicy:
        """Get or create the default selection policy (thread-safe)."""
        if cls._selection_policy is None:
            with cls._selection_policy_lock:
                if cls._selection_policy is None:  # Double-check pattern
                    cls._selection_policy = ProviderSelectionPolicy.default()
        return cls._selection_policy

    @classmethod
    def set_selection_policy(cls, policy: ProviderSelectionPolicy) -> None:
        """Set a custom selection policy (thread-safe).

        Args:
            policy: Custom ProviderSelectionPolicy instance
        """
        with cls._selection_policy_lock:
            cls._selection_policy = policy

    @classmethod
    def auto_select_provider(
        cls,
        audio_file_path: Path | None = None,
        preferred_features: list[str] | None = None,
        test_override: str | None = None,
    ) -> str:
        """Auto-select the best available provider based on configuration and file.

        Delegates to ProviderSelectionPolicy for consistent, testable selection logic.

        Selection priority (default):
        1. Deepgram (most features, fastest for API-based)
        2. ElevenLabs (good alternative API)
        3. Whisper (local, no API key needed)
        4. Parakeet (local, specialized)

        For large files (>100MB), local providers are preferred.

        Args:
            audio_file_path: Optional path to audio file (for size-based selection)
            preferred_features: Optional list of required features
            test_override: Optional provider override for testing

        Returns:
            Name of the selected provider

        Raises:
            ValueError: If no providers are configured
        """
        configured = cls.get_configured_providers()
        policy = cls.get_selection_policy()

        return policy.select_provider(
            configured_providers=configured,
            file_path=audio_file_path,
            preferred_features=preferred_features,
            test_override=test_override,
        )

    @classmethod
    def validate_provider_for_file(cls, provider_name: str, file_path: Path) -> bool:
        """Validate that a provider can handle the given file.

        Delegates to ProviderSelectionPolicy for consistent validation logic.

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
        # Preserve backward compatibility for unknown/custom providers:
        # treat them as having no known constraints beyond file accessibility.
        if provider_name not in _providers:
            try:
                file_path.stat()
            except (OSError, AttributeError):
                return False
            return True

        configured = cls.get_configured_providers()
        policy = cls.get_selection_policy()
        return policy.validate_provider_for_file(provider_name, file_path, configured)

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
        retry_config: RetryConfig,
    ) -> BaseTranscriptionProvider:
        """Instantiate and validate provider. Raises ValueError if validation fails."""
        provider = provider_class(api_key=api_key, retry_config=retry_config)

        if not provider.validate_configuration():
            raise ValueError(f"Provider '{provider_name}' is not properly configured")

        return provider

    @classmethod
    def create_provider(
        cls,
        provider_name: str,
        api_key: str | None = None,
        retry_config: RetryConfig | None = None,
        run_health_check: bool = False,
    ) -> BaseTranscriptionProvider:
        """Create provider with validation and optional health check.

        Args:
            provider_name: 'deepgram', 'elevenlabs', 'whisper', or 'parakeet'
            api_key: Override API key (uses env config if None)
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
            # Get default configs if not provided
            retry_config = get_default_configs(retry_config)

            # Create and validate provider instance
            provider = cls._create_provider_instance(
                provider_class, provider_name, api_key, retry_config
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
        """Sync wrapper for check_provider_health. Uses shared executor if in async context."""
        try:
            asyncio.get_running_loop()
            # Use shared executor from async_bridge to avoid per-call ThreadPoolExecutor creation
            from src.utils.async_bridge import run_async_in_sync

            return run_async_in_sync(
                cls.check_provider_health(provider_name, api_key), timeout=30.0
            )
        except RuntimeError:
            # No event loop running - safe to use asyncio.run()
            return asyncio.run(cls.check_provider_health(provider_name, api_key))

    @classmethod
    def _import_provider_class(cls, provider_path: str) -> type[BaseTranscriptionProvider]:
        """Import and return a provider class from a dotted module path.

        Args:
            provider_path: Dotted path to provider class (e.g., "src.providers.deepgram.DeepgramTranscriber")

        Returns:
            The provider class

        Raises:
            ImportError: If the module or class cannot be imported
        """
        import importlib

        module_path, class_name = provider_path.rsplit(".", 1)
        module = importlib.import_module(module_path)
        return getattr(module, class_name)
