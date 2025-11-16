"""Common utilities for provider initialization and configuration.

This module standardizes the initialization pattern for all providers,
reducing code duplication and ensuring consistent configuration.
"""

from __future__ import annotations

import logging
from typing import Any

from ..config import get_config
from ..utils.retry import RetryConfig
from .base import CircuitBreakerConfig

logger = logging.getLogger(__name__)


class ProviderInitializer:
    """Standardized provider initialization utilities."""

    @staticmethod
    def get_retry_config(
        retry_config: RetryConfig | None = None, provider_name: str = "provider"
    ) -> RetryConfig:
        """Get retry configuration with defaults.

        Args:
            retry_config: Optional custom retry configuration
            provider_name: Name of the provider for logging

        Returns:
            RetryConfig instance with either custom or default values
        """
        if retry_config is None:
            logger.debug(f"Using default retry config for {provider_name}")
            config = get_config()
            retry_config = RetryConfig(
                max_attempts=config.MAX_API_RETRIES,
                base_delay=config.API_RETRY_DELAY,
                max_delay=config.MAX_RETRY_DELAY,
                exponential_base=config.RETRY_EXPONENTIAL_BASE,
                jitter=config.RETRY_JITTER_ENABLED,
            )
        return retry_config

    @staticmethod
    def get_circuit_breaker_config(
        circuit_config: CircuitBreakerConfig | None = None, provider_name: str = "provider"
    ) -> CircuitBreakerConfig:
        """Get circuit breaker configuration with defaults.

        Args:
            circuit_config: Optional custom circuit breaker configuration
            provider_name: Name of the provider for logging

        Returns:
            CircuitBreakerConfig instance with either custom or default values
        """
        if circuit_config is None:
            logger.debug(f"Using default circuit breaker config for {provider_name}")
            config = get_config()
            circuit_config = CircuitBreakerConfig(
                failure_threshold=config.CIRCUIT_BREAKER_FAILURE_THRESHOLD,
                recovery_timeout=config.CIRCUIT_BREAKER_RECOVERY_TIMEOUT,
            )
        return circuit_config

    @classmethod
    def initialize_provider_configs(
        cls,
        provider_name: str,
        retry_config: RetryConfig | None = None,
        circuit_config: CircuitBreakerConfig | None = None,
    ) -> tuple[RetryConfig, CircuitBreakerConfig]:
        """Initialize both retry and circuit breaker configs for a provider.

        Args:
            provider_name: Name of the provider
            retry_config: Optional custom retry configuration
            circuit_config: Optional custom circuit breaker configuration

        Returns:
            Tuple of (retry_config, circuit_config) with defaults applied
        """
        retry_config = cls.get_retry_config(retry_config, provider_name)
        circuit_config = cls.get_circuit_breaker_config(circuit_config, provider_name)
        return retry_config, circuit_config


class ProviderAvailabilityChecker:
    """Check and handle provider availability."""

    @staticmethod
    def check_import(
        module_name: str, package_name: str, provider_name: str
    ) -> tuple[bool, type | None]:
        """Check if a provider's required package is available.

        Args:
            module_name: Full module path to import
            package_name: Package name for error messages
            provider_name: Provider name for logging

        Returns:
            Tuple of (is_available, imported_class)
        """
        try:
            import importlib

            module = importlib.import_module(module_name)
            # Try to get the main class from the module
            # This assumes the class name matches the last part of the module
            class_name = module_name.split(".")[-1]
            imported_class = getattr(module, class_name, None)
            logger.debug(f"{provider_name} dependencies available")
            return True, imported_class
        except ImportError as e:
            logger.warning(
                f"{provider_name} dependencies not installed. "
                f"Install with: uv add {package_name}. Error: {e}"
            )
            return False, None

    @staticmethod
    def ensure_available(is_available: bool, provider_name: str) -> None:
        """Ensure a provider is available, raising an error if not.

        Args:
            is_available: Whether the provider is available
            provider_name: Provider name for error messages

        Raises:
            ImportError: If the provider is not available
        """
        if not is_available:
            raise ImportError(
                f"{provider_name} is not available. Please install the required dependencies."
            )


def initialize_provider_with_defaults(
    provider_class: type,
    provider_name: str,
    api_key: str | None = None,
    retry_config: RetryConfig | None = None,
    circuit_config: CircuitBreakerConfig | None = None,
    **kwargs: Any,
) -> object:
    """Initialize a provider with standardized configuration.

    Args:
        provider_class: The provider class to instantiate
        provider_name: Name of the provider for logging
        api_key: Optional API key
        retry_config: Optional retry configuration
        circuit_config: Optional circuit breaker configuration
        **kwargs: Additional provider-specific arguments

    Returns:
        Initialized provider instance
    """
    # Get standardized configs
    retry_config, circuit_config = ProviderInitializer.initialize_provider_configs(
        provider_name, retry_config, circuit_config
    )

    # Initialize the provider
    logger.info(f"Initializing {provider_name} provider")

    # Build initialization arguments
    init_args = {"retry_config": retry_config, "circuit_config": circuit_config, **kwargs}

    # Add API key if provided
    if api_key is not None:
        init_args["api_key"] = api_key

    return provider_class(**init_args)
