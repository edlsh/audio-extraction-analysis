"""Provider selection and transcription policy objects.

This module consolidates provider selection logic and timeout/retry configuration
into dedicated policy objects, enabling:
- Cost-based routing and user preferences
- Single source of truth for CLI vs daemon tuning
- Easier testing with injectable policies
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from src.utils.logger import get_logger

from ..config import get_config
from ..utils.constants import Limits, RetryDefaults, Timeouts
from ..utils.retry import RetryConfig
from .base import CircuitBreakerConfig

if TYPE_CHECKING:
    from .base import BaseTranscriptionProvider, ProviderMeta

logger = get_logger(__name__)


# =============================================================================
# Transcription Policy - Unified timeout/retry configuration
# =============================================================================


@dataclass
class TranscriptionPolicy:
    """Unified timeout and retry policy for transcription operations.

    Consolidates scattered timeout/retry settings into a single source of truth.
    This enables different configurations for CLI (fast fail) vs daemon (resilient).

    Attributes:
        transcription_timeout: Maximum time for transcription operation
        connect_timeout: Timeout for initial connection
        retry_config: Configuration for retry behavior
        circuit_config: Configuration for circuit breaker (optional)
        enable_circuit_breaker: Whether circuit breaker is active
    """

    transcription_timeout: float = Timeouts.TRANSCRIPTION_DEFAULT
    connect_timeout: float = float(Timeouts.CONNECT)
    retry_config: RetryConfig = field(
        default_factory=lambda: RetryConfig(
            max_attempts=RetryDefaults.MAX_ATTEMPTS,
            base_delay=RetryDefaults.BASE_DELAY,
            exponential_base=RetryDefaults.EXPONENTIAL_BASE,
            max_delay=RetryDefaults.NETWORK_MAX_DELAY,
            jitter=RetryDefaults.JITTER,
        )
    )
    circuit_config: CircuitBreakerConfig = field(
        default_factory=lambda: CircuitBreakerConfig(
            enabled=False,  # Disabled by default for CLI
            failure_threshold=Limits.CIRCUIT_FAILURE_THRESHOLD,
            recovery_timeout=Limits.CIRCUIT_RECOVERY_TIMEOUT,
        )
    )
    enable_circuit_breaker: bool = False

    @classmethod
    def from_config(cls) -> TranscriptionPolicy:
        """Create policy from global configuration."""
        config = get_config()

        # circuit_breaker_enabled may not exist in older configs
        circuit_breaker_enabled = getattr(config, "circuit_breaker_enabled", False)

        return cls(
            transcription_timeout=float(config.transcription_timeout_seconds),
            connect_timeout=float(config.connect_timeout),
            retry_config=RetryConfig(
                max_attempts=config.max_retries,
                base_delay=config.retry_delay,
                max_delay=config.max_retry_delay,
                exponential_base=config.retry_exponential_base,
                jitter=config.retry_jitter,
            ),
            circuit_config=CircuitBreakerConfig(
                enabled=circuit_breaker_enabled,
                failure_threshold=config.circuit_breaker_failure_threshold,
                recovery_timeout=config.circuit_breaker_recovery_timeout,
            ),
            enable_circuit_breaker=circuit_breaker_enabled,
        )

    @classmethod
    def cli_defaults(cls) -> TranscriptionPolicy:
        """Create policy optimized for CLI usage (fast fail, no circuit breaker)."""
        return cls(
            transcription_timeout=300.0,  # 5 minutes
            connect_timeout=10.0,
            retry_config=RetryConfig(
                max_attempts=3,
                base_delay=1.0,
                max_delay=30.0,
                exponential_base=2.0,
                jitter=True,
            ),
            circuit_config=CircuitBreakerConfig(enabled=False),
            enable_circuit_breaker=False,
        )

    @classmethod
    def daemon_defaults(cls) -> TranscriptionPolicy:
        """Create policy optimized for daemon/service usage (resilient, circuit breaker)."""
        return cls(
            transcription_timeout=600.0,  # 10 minutes
            connect_timeout=30.0,
            retry_config=RetryConfig(
                max_attempts=5,
                base_delay=2.0,
                max_delay=120.0,
                exponential_base=2.0,
                jitter=True,
            ),
            circuit_config=CircuitBreakerConfig(
                enabled=True,
                failure_threshold=5,
                recovery_timeout=60.0,
            ),
            enable_circuit_breaker=True,
        )


# =============================================================================
# Provider Selection Policy - Centralized provider selection logic
# =============================================================================


@dataclass
class ProviderSizeLimits:
    """Size limits for a provider in MB."""

    provider: str
    max_size_mb: float


# Default provider size limits
DEFAULT_PROVIDER_LIMITS: dict[str, float] = {
    "deepgram": 2000.0,  # 2GB limit
    "elevenlabs": float(Limits.MAX_FILE_SIZE_MB),  # 50MB limit
    "whisper": float("inf"),  # Local, no limit
    "parakeet": float("inf"),  # Local, no limit
}

# Provider priority for different scenarios
CLOUD_PRIORITY = ["deepgram", "elevenlabs", "whisper", "parakeet"]
LOCAL_PRIORITY = ["whisper", "parakeet", "deepgram", "elevenlabs"]
LARGE_FILE_THRESHOLD_MB = 100.0


@dataclass
class ProviderSelectionPolicy:
    """Policy for selecting transcription providers.

    Centralizes provider selection logic that was previously scattered across
    factory and service layers. Enables:
    - Cost-based routing
    - User preferences
    - File-size-aware selection
    - Test mode overrides

    Attributes:
        priority_order: Ordered list of providers to try
        size_limits: Maximum file size per provider (in MB)
        large_file_threshold_mb: Size above which local providers are preferred
        prefer_local_for_large: Whether to prefer local providers for large files
        fallback_enabled: Whether to fallback to other providers on failure
    """

    priority_order: list[str] = field(default_factory=lambda: CLOUD_PRIORITY.copy())
    size_limits: dict[str, float] = field(default_factory=lambda: DEFAULT_PROVIDER_LIMITS.copy())
    large_file_threshold_mb: float = LARGE_FILE_THRESHOLD_MB
    prefer_local_for_large: bool = True
    fallback_enabled: bool = True

    def select_provider(
        self,
        configured_providers: list[str],
        file_path: Path | None = None,
        preferred_features: list[str] | None = None,
        test_override: str | None = None,
    ) -> str:
        """Select the best provider based on policy and context.

        Args:
            configured_providers: List of providers that are properly configured
            file_path: Optional path to audio file for size-based selection
            preferred_features: Optional list of required features
            test_override: Optional provider override for testing

        Returns:
            Name of the selected provider

        Raises:
            ValueError: If no providers are configured or suitable
        """
        # Handle test mode override
        if test_override:
            if test_override in configured_providers:
                logger.debug(f"Using test override provider: {test_override}")
                return test_override
            logger.warning(f"Test override provider '{test_override}' not configured")

        if not configured_providers:
            raise ValueError(
                "No transcription providers configured. "
                "Set DEEPGRAM_API_KEY or ELEVENLABS_API_KEY, or install whisper/parakeet."
            )

        # Determine priority order based on file size
        priority = self._get_priority_for_file(file_path)

        # Select first available provider in priority order
        for provider_name in priority:
            if provider_name in configured_providers:
                if self._validate_provider_for_file(provider_name, file_path):
                    logger.debug(f"Selected provider: {provider_name}")
                    return provider_name

        # If we have file context and no provider can handle it, fail fast.
        if file_path is not None:
            try:
                file_size_mb = file_path.stat().st_size / (1024 * 1024)
            except (OSError, AttributeError):
                file_size_mb = None

            if file_size_mb is not None:
                raise ValueError(
                    f"No configured providers can handle file size ({file_size_mb:.1f}MB). "
                    f"Configured providers: {', '.join(configured_providers)}"
                )

        if self.fallback_enabled:
            logger.debug(f"Falling back to first configured provider: {configured_providers[0]}")
            return configured_providers[0]

        raise ValueError("No suitable transcription provider found")

    def _get_priority_for_file(self, file_path: Path | None) -> list[str]:
        """Get provider priority order based on file characteristics."""
        if not self.prefer_local_for_large or file_path is None:
            return self.priority_order

        try:
            file_size_mb = file_path.stat().st_size / (1024 * 1024)
            if file_size_mb > self.large_file_threshold_mb:
                logger.debug(f"Large file ({file_size_mb:.1f}MB), preferring local providers")
                return LOCAL_PRIORITY.copy()
        except (OSError, AttributeError):
            pass  # File doesn't exist or path is None

        return self.priority_order

    def _validate_provider_for_file(
        self,
        provider_name: str,
        file_path: Path | None,
    ) -> bool:
        """Check if provider can handle the given file."""
        if file_path is None:
            return True

        try:
            file_size_mb = file_path.stat().st_size / (1024 * 1024)
        except (OSError, AttributeError):
            return True  # Can't check, assume valid

        max_size = self.size_limits.get(provider_name, 100.0)
        if file_size_mb > max_size:
            logger.debug(
                f"File size ({file_size_mb:.1f}MB) exceeds {provider_name} limit ({max_size}MB)"
            )
            return False

        return True

    def validate_provider_for_file(
        self,
        provider_name: str,
        file_path: Path,
        configured_providers: list[str],
    ) -> bool:
        """Full validation of provider for a specific file.

        Args:
            provider_name: Provider to validate
            file_path: Path to audio file
            configured_providers: List of configured providers

        Returns:
            True if provider can handle the file
        """
        # Check provider is configured
        if provider_name not in configured_providers:
            logger.warning(f"Provider '{provider_name}' is not configured")
            return False

        # Check file exists
        try:
            file_size_mb = file_path.stat().st_size / (1024 * 1024)
        except (OSError, AttributeError) as e:
            logger.warning(f"Cannot access file '{file_path}': {e}")
            return False

        # Check size limit
        max_size = self.size_limits.get(provider_name, 100.0)
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
    def default(cls) -> ProviderSelectionPolicy:
        """Create default selection policy."""
        return cls()

    @classmethod
    def prefer_local(cls) -> ProviderSelectionPolicy:
        """Create policy that prefers local providers."""
        return cls(
            priority_order=LOCAL_PRIORITY.copy(),
            prefer_local_for_large=True,
        )

    @classmethod
    def prefer_cloud(cls) -> ProviderSelectionPolicy:
        """Create policy that prefers cloud providers."""
        return cls(
            priority_order=CLOUD_PRIORITY.copy(),
            prefer_local_for_large=False,
        )


__all__ = [
    "CLOUD_PRIORITY",
    "DEFAULT_PROVIDER_LIMITS",
    "LARGE_FILE_THRESHOLD_MB",
    "LOCAL_PRIORITY",
    "ProviderSelectionPolicy",
    "ProviderSizeLimits",
    "TranscriptionPolicy",
]
