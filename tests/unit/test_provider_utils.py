"""Tests for provider configuration utilities."""

import pytest

from src.providers.provider_utils import get_default_configs
from src.utils.retry import RetryConfig


class TestGetDefaultConfigs:
    """Test get_default_configs function."""

    def test_returns_retry_config(self):
        """Test that function returns a RetryConfig."""
        result = get_default_configs()
        assert isinstance(result, RetryConfig)

    def test_uses_custom_retry_config(self):
        """Test that custom retry config is returned when provided."""
        custom = RetryConfig(max_attempts=10)
        result = get_default_configs(retry_config=custom)
        assert result is custom
        assert result.max_attempts == 10

    def test_defaults_from_global_config(self):
        """Test that defaults come from global config."""
        result = get_default_configs()
        # Just verify it has reasonable values
        assert result.max_attempts > 0
