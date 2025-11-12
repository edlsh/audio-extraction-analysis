"""Factory for creating and managing transcription service providers.

This module implements the Factory Pattern for transcription providers, providing:
- Provider registration and discovery
- Automatic provider selection based on capabilities and health
- Configuration validation and health checking
- File size constraint validation

The factory automatically registers available providers on module import and
supports both synchronous and asynchronous operations.

Example:
    >>> # Auto-select and create a provider
    >>> provider_name = TranscriptionProviderFactory.auto_select_provider()
    >>> provider = TranscriptionProviderFactory.create_provider(provider_name)
    >>> result = await provider.transcribe(audio_file_path)

    >>> # Get status of all providers
    >>> status = TranscriptionProviderFactory.get_provider_status()
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Type

from ..config import get_config
from ..utils.retry import RetryConfig
from .base import BaseTranscriptionProvider, CircuitBreakerConfig

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
    _providers: Dict[str, Type[BaseTranscriptionProvider]] = {}

    @classmethod
    def register_provider(cls, name: str, provider_class: Type[BaseTranscriptionProvider]) -> None:
        """Register a transcription provider.

        Args:
            name: Provider name (e.g., 'deepgram', 'elevenlabs')
            provider_class: Provider class implementing BaseTranscriptionProvider
        """
        cls._providers[name] = provider_class
        logger.debug(f"Registered transcription provider: {name}")

    @classmethod
    def get_available_providers(cls) -> List[str]:
        """Get list of registered provider names.

        Returns:
            List of provider names that are registered
        """
        return list(cls._providers.keys())

    @classmethod
    def get_configured_providers(cls) -> List[str]:
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
        circuit_config: Optional[CircuitBreakerConfig],
        retry_config: Optional[RetryConfig],
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
        provider_class: Type[BaseTranscriptionProvider],
        provider_name: str,
        api_key: Optional[str],
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
        api_key: Optional[str] = None,
        circuit_config: Optional[CircuitBreakerConfig] = None,
        retry_config: Optional[RetryConfig] = None,
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
    def auto_select_provider(
        cls,
        audio_file_path: Optional[Path] = None,
        preferred_features: Optional[List[str]] = None,
        include_health_check: bool = True,
    ) -> str:
        """Automatically select the best available provider using intelligent heuristics.

        Selection Algorithm:
            1. Filter to configured providers (have API keys or dependencies)
            2. If health checking enabled, filter to healthy providers only
            3. If only one provider remains, return it
            4. If audio file provided, check file size constraints:
               - Files >50MB: Must use Deepgram (ElevenLabs 50MB limit)
            5. If feature requirements specified, select provider with most matching features
            6. Otherwise, use default priority: Deepgram > ElevenLabs > Whisper > Parakeet
            7. Fallback: Return first available configured provider

        Args:
            audio_file_path: Optional path to audio file for size-based selection.
                If provided and file >50MB, Deepgram will be selected if available.
            preferred_features: Optional list of required features (e.g., ['timestamps', 'diarization']).
                Provider with most matching features will be selected.
            include_health_check: Whether to filter out unhealthy providers. Defaults to True.
                If all providers fail health check, falls back to all configured providers.

        Returns:
            Name of the selected provider (e.g., 'deepgram', 'whisper')

        Raises:
            ValueError: If no providers are configured or file size exceeds all provider limits

        Example:
            >>> # Auto-select for large file
            >>> provider = factory.auto_select_provider(Path("large_audio.mp3"))
            >>> # Auto-select with feature requirements
            >>> provider = factory.auto_select_provider(preferred_features=['diarization'])
        """
        configured_providers = cls.get_configured_providers()

        if not configured_providers:
            raise ValueError(
                "No transcription providers are configured. "
                "Please set DEEPGRAM_API_KEY or ELEVENLABS_API_KEY environment variables."
            )

        # Filter by health status if requested
        if include_health_check and get_config().HEALTH_CHECK_ENABLED:
            healthy_providers = []
            for provider_name in configured_providers:
                try:
                    health = cls.check_provider_health_sync(provider_name)
                    if health.get("healthy", False):
                        healthy_providers.append(provider_name)
                    else:
                        logger.warning(
                            f"Provider '{provider_name}' failed health check: {health.get('status')}"
                        )
                except Exception as e:
                    logger.warning(f"Health check failed for '{provider_name}': {e}")

            if healthy_providers:
                configured_providers = healthy_providers
                logger.info(f"Filtered to healthy providers: {configured_providers}")
            else:
                logger.warning("No providers passed health check, using all configured providers")

        # If only one provider is available, use it
        if len(configured_providers) == 1:
            selected = configured_providers[0]
            logger.info(f"Auto-selected provider (only available): {selected}")
            return selected

        # Check file size constraints if audio file provided
        if audio_file_path and audio_file_path.exists():
            file_size_mb = audio_file_path.stat().st_size / (1024 * 1024)

            # ElevenLabs has 50MB limit, Deepgram supports larger files
            if file_size_mb > 50:
                if "deepgram" in configured_providers:
                    logger.info(
                        f"Auto-selected provider (file size {file_size_mb:.1f}MB): deepgram"
                    )
                    return "deepgram"
                else:
                    raise ValueError(
                        f"File size {file_size_mb:.1f}MB exceeds limits of available providers"
                    )

        # Check feature requirements
        if preferred_features:
            best_provider = None
            max_features = 0

            for provider_name in configured_providers:
                try:
                    provider = cls.create_provider(provider_name, run_health_check=False)
                    supported_features = provider.get_supported_features()
                    matching_features = len(set(preferred_features) & set(supported_features))

                    if matching_features > max_features:
                        max_features = matching_features
                        best_provider = provider_name

                except Exception as e:
                    logger.debug(f"Could not evaluate features for '{provider_name}': {e}")
                    continue

            if best_provider:
                logger.info(f"Auto-selected provider (feature matching): {best_provider}")
                return best_provider

        # Default priority: Deepgram > ElevenLabs > Whisper > Parakeet (based on feature richness)
        priority_order = ["deepgram", "elevenlabs", "whisper", "parakeet"]

        for provider_name in priority_order:
            if provider_name in configured_providers:
                logger.info(f"Auto-selected provider (default priority): {provider_name}")
                return provider_name

        # Fallback to first available provider
        selected = configured_providers[0]
        logger.info(f"Auto-selected provider (fallback): {selected}")
        return selected

    @classmethod
    def validate_provider_for_file(cls, provider_name: str, audio_file_path: Path) -> bool:
        """Validate that a provider can handle the given audio file based on size constraints.

        This method checks provider-specific file size limits to ensure the audio file
        can be processed. Different providers have different constraints:

        File Size Limits by Provider:
            - ElevenLabs: 50MB maximum (API limitation)
            - Deepgram: ~2GB maximum (conservative estimate)
            - Whisper: Limited by Config.MAX_FILE_SIZE (local processing)
            - Parakeet: Limited by Config.MAX_FILE_SIZE (local processing)

        Args:
            provider_name: Name of the provider to validate against
                (e.g., 'deepgram', 'elevenlabs', 'whisper', 'parakeet')
            audio_file_path: Path to the audio file to validate

        Returns:
            True if the provider can handle the file size, False otherwise.
            Also returns False if the file does not exist.

        Note:
            This only validates file size constraints, not audio format compatibility.
            Validation warnings are logged when limits are exceeded.

        Example:
            >>> if factory.validate_provider_for_file('elevenlabs', Path('large.mp3')):
            ...     provider = factory.create_provider('elevenlabs')
            ... else:
            ...     provider = factory.create_provider('deepgram')  # Fallback
        """
        if not audio_file_path.exists():
            return False

        file_size_mb = audio_file_path.stat().st_size / (1024 * 1024)

        # Check provider-specific file size constraints
        if provider_name == "elevenlabs":
            if file_size_mb > 50:  # ElevenLabs API 50MB hard limit
                logger.warning(f"File size {file_size_mb:.1f}MB exceeds ElevenLabs 50MB limit")
                return False
        elif provider_name == "deepgram":
            if file_size_mb > 2000:  # Deepgram ~2GB limit (conservative estimate)
                logger.warning(f"File size {file_size_mb:.1f}MB exceeds Deepgram limit")
                return False
        elif provider_name == "whisper":
            # Whisper local model: check against global file size configuration
            config = get_config()
            if file_size_mb > (config.MAX_FILE_SIZE / (1024 * 1024)):
                logger.warning(f"File size {file_size_mb:.1f}MB exceeds global file size limit")
                return False
        elif provider_name == "parakeet":
            # Parakeet local model: check against global file size configuration
            config = get_config()
            if file_size_mb > (config.MAX_FILE_SIZE / (1024 * 1024)):
                logger.warning(f"File size {file_size_mb:.1f}MB exceeds global file size limit")
                return False

        return True

    @classmethod
    async def check_provider_health(
        cls, provider_name: str, api_key: Optional[str] = None
    ) -> Dict[str, Any]:
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
        cls, provider_name: str, api_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """Synchronous wrapper for async provider health check.

        This method handles event loop management for synchronous contexts,
        automatically creating a new event loop if one doesn't exist.

        Event Loop Handling:
            - Attempts to use existing event loop if available
            - Creates new event loop if none exists (e.g., in threaded contexts)
            - Closes the loop only if it's not currently running (prevents interference)

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
            loop = asyncio.get_event_loop()
        except RuntimeError:
            # No event loop in current thread, create a new one
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        try:
            return loop.run_until_complete(cls.check_provider_health(provider_name, api_key))
        finally:
            # Only close if loop is not running (avoid breaking existing async contexts)
            if not loop.is_running():
                loop.close()

    @classmethod
    def get_provider_status(cls) -> Dict[str, Any]:
        """Get comprehensive status of all transcription providers.

        This method provides a complete overview of provider availability, configuration,
        and health status. Useful for diagnostics and monitoring.

        Returns:
            Dictionary containing:
                - available_providers: List of registered provider names
                - configured_providers: List of providers with valid configuration
                - provider_health: Dict mapping provider names to health check results

        Health Check Results:
            Each provider_health entry contains:
                - healthy: bool indicating operational status
                - status: str status message
                - response_time_ms: int (if healthy)
                - error: str (if check failed)

        Note:
            This performs synchronous health checks on all configured providers,
            which may take several seconds if multiple providers are configured.

        Example:
            >>> status = factory.get_provider_status()
            >>> print(f"Available: {status['available_providers']}")
            >>> print(f"Configured: {status['configured_providers']}")
            >>> for name, health in status['provider_health'].items():
            ...     print(f"{name}: {'✓' if health['healthy'] else '✗'}")
        """
        status = {
            "available_providers": cls.get_available_providers(),
            "configured_providers": cls.get_configured_providers(),
            "provider_health": {},
        }

        # Perform health checks on all configured providers
        for provider_name in cls.get_configured_providers():
            try:
                health = cls.check_provider_health_sync(provider_name)
                status["provider_health"][provider_name] = health
            except Exception as e:
                status["provider_health"][provider_name] = {
                    "healthy": False,
                    "status": "check_failed",
                    "error": str(e),
                }

        return status


# Initialize the factory with default providers
def _initialize_factory():
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
