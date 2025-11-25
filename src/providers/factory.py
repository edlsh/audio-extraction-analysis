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
        except (ImportError, Exception):
            pass

        # Parakeet: NVIDIA NeMo's local speech recognition model
        try:
            import nemo.collections.asr as nemo_asr

            configured.append("parakeet")
        except (ImportError, Exception):
            pass

        return configured

    @classmethod
    def _get_default_configs(
        cls,
        provider_name: str,
        circuit_config: CircuitBreakerConfig | None,
        retry_config: RetryConfig | None,
    ) -> tuple[CircuitBreakerConfig, RetryConfig]:
        """Get default circuit breaker and retry configurations (internal helper).

        This method provides default configurations for fault tolerance and retry logic
        when not explicitly provided. Defaults are pulled from the Config singleton.

        Circuit Breaker Pattern:
            Prevents cascading failures by opening circuit after threshold failures.
            Automatically attempts recovery after timeout period.

        Retry Pattern:
            Implements exponential backoff with jitter for transient failures.
            Helps handle temporary network issues and rate limiting.

        Args:
            provider_name: Name of the provider (currently unused, reserved for
                future provider-specific default configuration)
            circuit_config: Existing circuit breaker config or None. If None,
                defaults from Config are used.
            retry_config: Existing retry config or None. If None, defaults from
                Config are used.

        Returns:
            Tuple of (circuit_config, retry_config) where None values are replaced
            with defaults from Config

        Note:
            Both configs are always returned as non-None objects. If both inputs
            are provided, they are returned unchanged for efficiency.
        """
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
        """Run health check on provider and log results (internal helper).

        This is a synchronous health check used during provider creation.
        Health check failures are logged as warnings but do not prevent provider
        creation, as the provider may recover or the issue may be transient.

        Args:
            provider: Provider instance to check
            provider_name: Name of the provider for logging purposes

        Note:
            - Skipped if get_config().HEALTH_CHECK_ENABLED is False
            - Failures are logged but not raised (non-blocking)
            - Internal method, prefer check_provider_health() for external use
        """
        if not get_config().HEALTH_CHECK_ENABLED:
            return

        try:
            health_result = provider.health_check()
            if not health_result.get("healthy", False):
                logger.warning(
                    f"Provider '{provider_name}' health check failed: {health_result.get('status')}"
                )
                # Don't raise error, just log warning - provider might recover
            else:
                logger.info(f"Provider '{provider_name}' health check passed")
        except Exception as e:
            logger.warning(f"Health check failed for '{provider_name}': {e}")
            # Don't raise error - health check is informational only

    @classmethod
    def _create_provider_instance(
        cls,
        provider_class: type[BaseTranscriptionProvider],
        provider_name: str,
        api_key: str | None,
        circuit_config: CircuitBreakerConfig,
        retry_config: RetryConfig,
    ) -> BaseTranscriptionProvider:
        """Create and validate provider instance (internal helper).

        This method instantiates a provider class and validates its configuration
        before returning it. Validation ensures API keys are present (for cloud providers)
        and all required dependencies are available.

        Args:
            provider_class: Provider class to instantiate (e.g., DeepgramTranscriber)
            provider_name: Name of the provider for error messages and logging
            api_key: Optional API key for cloud providers. None for local providers.
            circuit_config: Circuit breaker configuration for fault tolerance
            retry_config: Retry configuration for transient failures

        Returns:
            Fully initialized and validated provider instance

        Raises:
            ValueError: If provider configuration is invalid (e.g., missing API key,
                missing dependencies, or provider-specific validation failure)

        Note:
            Internal method used by create_provider(). Validation is performed by
            calling the provider's validate_configuration() method.
        """
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
        """Create a transcription provider instance with validation and health checking.

        This method creates a provider, validates its configuration, and optionally
        performs a health check. Default configurations are applied if not provided.

        Supported Providers:
            - 'deepgram': Deepgram cloud API (requires DEEPGRAM_API_KEY)
            - 'elevenlabs': ElevenLabs cloud API (requires ELEVENLABS_API_KEY)
            - 'whisper': OpenAI Whisper local model (requires torch, whisper)
            - 'parakeet': NVIDIA NeMo Parakeet local model (requires nemo)

        Args:
            provider_name: Name of the provider to create. Use get_available_providers()
                to see registered providers.
            api_key: Optional API key override. If None, reads from Config (environment).
                Not used for local providers (whisper, parakeet).
            circuit_config: Optional circuit breaker configuration. If None, uses defaults
                from Config (failure_threshold, recovery_timeout).
            retry_config: Optional retry configuration. If None, uses defaults from Config
                (max_retries, retry_delay, exponential backoff settings).
            run_health_check: Whether to run health check after creation. Health check
                failures are logged but do not prevent provider creation.

        Returns:
            Fully configured and validated provider instance ready for transcription

        Raises:
            ValueError: If provider name is not registered, configuration is invalid,
                or required dependencies are missing
            ImportError: If provider module cannot be imported

        Example:
            >>> # Create with defaults
            >>> provider = factory.create_provider('deepgram')
            >>> # Create with custom configs
            >>> provider = factory.create_provider(
            ...     'deepgram',
            ...     circuit_config=CircuitBreakerConfig(failure_threshold=5),
            ...     run_health_check=False
            ... )
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
        """Asynchronously check health of a specific provider.

        This method creates a minimal provider instance and performs a health check
        to verify the provider is operational and can accept requests.

        Args:
            provider_name: Name of the provider to check (e.g., 'deepgram', 'whisper')
            api_key: Optional API key override. If None, uses configuration.
                Not applicable to local providers.

        Returns:
            Dictionary containing health check results:
                - healthy: bool indicating if provider is operational
                - status: str status message (e.g., 'ok', 'creation_failed')
                - response_time_ms: int response time in milliseconds
                - details: dict with additional diagnostic information

        Raises:
            ValueError: If provider_name is not registered in the factory

        Note:
            For synchronous contexts, use check_provider_health_sync() instead.
            This method does not throw exceptions on provider failures; errors are
            returned in the result dictionary with healthy=False.

        Example:
            >>> health = await factory.check_provider_health('deepgram')
            >>> if health['healthy']:
            ...     print(f"Provider ready ({health['response_time_ms']}ms)")
            ... else:
            ...     print(f"Provider unavailable: {health['status']}")
        """
        if provider_name not in cls._providers:
            available = ", ".join(cls.get_available_providers())
            raise ValueError(
                f"Unknown provider '{provider_name}'. Available providers: {available}"
            )

        try:
            # Create provider without initial health check to avoid recursion
            provider = cls.create_provider(provider_name, api_key, run_health_check=False)
            return await provider.health_check_async()
        except Exception as e:
            # Return structured error response instead of raising
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
        """Synchronous wrapper for async provider health check.

        This method handles event loop management for synchronous contexts,
        using a thread pool executor when called from an async context to avoid
        "event loop already running" errors.

        Event Loop Handling:
            - Detects if there's a running event loop
            - Uses thread pool executor if in async context (prevents conflicts)
            - Uses asyncio.run() directly if in sync context (cleaner approach)

        Args:
            provider_name: Name of the provider to check (e.g., 'deepgram', 'whisper')
            api_key: Optional API key override. If None, uses configuration.

        Returns:
            Dictionary containing health check results with keys:
                - healthy: bool indicating if provider is operational
                - status: str status message
                - response_time_ms: int response time in milliseconds
                - details: dict with additional information

        Note:
            Prefer check_provider_health() (async) when in async context for better performance.
        """
        try:
            # Check if there's a running event loop
            asyncio.get_running_loop()
            # We're in async context - use thread pool to avoid conflict
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run, cls.check_provider_health(provider_name, api_key)
                )
                return future.result(timeout=30)  # 30s timeout for health check
        except RuntimeError:
            # No running loop - safe to use asyncio.run()
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
