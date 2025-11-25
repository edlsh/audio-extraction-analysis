"""Provider configuration utilities."""

from __future__ import annotations

from ..config import get_config
from ..utils.retry import RetryConfig
from .base import CircuitBreakerConfig


def get_default_configs(
    retry_config: RetryConfig | None = None,
    circuit_config: CircuitBreakerConfig | None = None,
) -> tuple[RetryConfig, CircuitBreakerConfig]:
    """Get retry and circuit breaker configs with defaults from global config."""
    config = get_config()
    
    if retry_config is None:
        retry_config = RetryConfig(
            max_attempts=config.max_retries,
            base_delay=config.retry_delay,
            max_delay=config.max_retry_delay,
            exponential_base=config.retry_exponential_base,
            jitter=config.retry_jitter,
        )
    
    if circuit_config is None:
        circuit_config = CircuitBreakerConfig(
            failure_threshold=config.circuit_breaker_failure_threshold,
            recovery_timeout=config.circuit_breaker_recovery_timeout,
        )
    
    return retry_config, circuit_config
