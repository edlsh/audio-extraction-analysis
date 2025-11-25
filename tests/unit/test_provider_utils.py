"""Tests for provider configuration utilities."""

import pytest

from src.providers.provider_utils import get_default_configs
from src.providers.base import CircuitBreakerConfig
from src.utils.retry import RetryConfig


class TestGetDefaultConfigs:
    """Test get_default_configs function."""

    def test_returns_tuple(self):
        """Test that function returns a tuple of configs."""
        result = get_default_configs()
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_returns_retry_config(self):
        """Test that first element is RetryConfig."""
        retry_config, _ = get_default_configs()
        assert isinstance(retry_config, RetryConfig)

    def test_returns_circuit_breaker_config(self):
        """Test that second element is CircuitBreakerConfig."""
        _, circuit_config = get_default_configs()
        assert isinstance(circuit_config, CircuitBreakerConfig)

    def test_uses_custom_retry_config(self):
        """Test that custom retry config is returned when provided."""
        custom = RetryConfig(max_attempts=10)
        retry_config, _ = get_default_configs(retry_config=custom)
        assert retry_config is custom
        assert retry_config.max_attempts == 10

    def test_uses_custom_circuit_config(self):
        """Test that custom circuit config is returned when provided."""
        custom = CircuitBreakerConfig(failure_threshold=20)
        _, circuit_config = get_default_configs(circuit_config=custom)
        assert circuit_config is custom
        assert circuit_config.failure_threshold == 20

    def test_defaults_from_global_config(self):
        """Test that defaults come from global config."""
        retry_config, circuit_config = get_default_configs()
        # Just verify they have reasonable values
        assert retry_config.max_attempts > 0
        assert circuit_config.failure_threshold > 0
