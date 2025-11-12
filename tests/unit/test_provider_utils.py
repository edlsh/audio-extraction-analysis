"""Unit tests for provider utilities.

Tests cover initialization, configuration, and availability checking with edge cases.
"""

import logging
from unittest.mock import MagicMock, Mock, patch

import pytest

from src.providers.base import CircuitBreakerConfig
from src.providers.provider_utils import (
    ProviderAvailabilityChecker,
    ProviderInitializer,
    initialize_provider_with_defaults,
)
from src.utils.retry import RetryConfig


@pytest.fixture(autouse=True)
def mock_config():
    """Mock get_config() function to return config with test values."""
    with patch("src.providers.provider_utils.get_config") as mock_get_config:
        # Create mock config instance with test values
        mock_cfg = Mock()
        mock_cfg.MAX_API_RETRIES = 3
        mock_cfg.API_RETRY_DELAY = 1.0
        mock_cfg.MAX_RETRY_DELAY = 60.0
        mock_cfg.RETRY_EXPONENTIAL_BASE = 2.0
        mock_cfg.RETRY_JITTER_ENABLED = True
        mock_cfg.CIRCUIT_BREAKER_FAILURE_THRESHOLD = 5
        mock_cfg.CIRCUIT_BREAKER_RECOVERY_TIMEOUT = 60.0
        mock_get_config.return_value = mock_cfg
        yield mock_cfg


class TestProviderInitializerGetRetryConfig:
    """Test suite for ProviderInitializer.get_retry_config()."""

    def test_get_retry_config_with_none_uses_defaults(self) -> None:
        """Test that None retry_config returns default configuration."""
        result = ProviderInitializer.get_retry_config(None, "test_provider")

        assert isinstance(result, RetryConfig)
        assert result.max_attempts == 3  # Config.MAX_API_RETRIES
        assert result.base_delay == 1.0  # Config.API_RETRY_DELAY
        assert result.max_delay == 60.0  # Config.MAX_RETRY_DELAY
        assert result.exponential_base == 2.0  # Config.RETRY_EXPONENTIAL_BASE
        assert result.jitter is True  # Config.RETRY_JITTER_ENABLED

    def test_get_retry_config_with_custom_config_returns_as_is(self) -> None:
        """Test that custom retry_config is returned unchanged."""
        custom_config = RetryConfig(
            max_attempts=5,
            base_delay=2.0,
            max_delay=120.0,
            exponential_base=3.0,
            jitter=False,
        )

        result = ProviderInitializer.get_retry_config(custom_config, "test_provider")

        assert result is custom_config
        assert result.max_attempts == 5
        assert result.base_delay == 2.0
        assert result.max_delay == 120.0
        assert result.exponential_base == 3.0
        assert result.jitter is False

    def test_get_retry_config_logs_default_usage(self, caplog) -> None:
        """Test that using default config generates debug log."""
        with caplog.at_level(logging.DEBUG):
            ProviderInitializer.get_retry_config(None, "test_provider")

        assert any(
            "Using default retry config for test_provider" in record.message
            for record in caplog.records
        )

    def test_get_retry_config_different_provider_names(self) -> None:
        """Test retry config with various provider names."""
        provider_names = ["deepgram", "whisper", "assemblyai", "custom_provider"]

        for provider_name in provider_names:
            result = ProviderInitializer.get_retry_config(None, provider_name)
            assert isinstance(result, RetryConfig)


class TestProviderInitializerGetCircuitBreakerConfig:
    """Test suite for ProviderInitializer.get_circuit_breaker_config()."""

    def test_get_circuit_breaker_config_with_none_uses_defaults(self) -> None:
        """Test that None circuit_config returns default configuration."""
        result = ProviderInitializer.get_circuit_breaker_config(None, "test_provider")

        assert isinstance(result, CircuitBreakerConfig)
        assert result.failure_threshold == 5  # Config.CIRCUIT_BREAKER_THRESHOLD
        assert result.recovery_timeout == 60.0  # Config.CIRCUIT_BREAKER_TIMEOUT
        assert ConnectionError in result.expected_exception_types
        assert TimeoutError in result.expected_exception_types

    def test_get_circuit_breaker_config_with_custom_config_returns_as_is(self) -> None:
        """Test that custom circuit_config is returned unchanged."""
        custom_config = CircuitBreakerConfig(
            failure_threshold=10,
            recovery_timeout=120.0,
            expected_exception_types=(ValueError, RuntimeError),
        )

        result = ProviderInitializer.get_circuit_breaker_config(custom_config, "test_provider")

        assert result is custom_config
        assert result.failure_threshold == 10
        assert result.recovery_timeout == 120.0
        assert result.expected_exception_types == (ValueError, RuntimeError)

    def test_get_circuit_breaker_config_logs_default_usage(self, caplog) -> None:
        """Test that using default config generates debug log."""
        with caplog.at_level(logging.DEBUG):
            ProviderInitializer.get_circuit_breaker_config(None, "test_provider")

        assert any(
            "Using default circuit breaker config for test_provider" in record.message
            for record in caplog.records
        )

    def test_get_circuit_breaker_config_exception_types_tuple(self) -> None:
        """Test that expected exception types are correctly configured as tuple."""
        result = ProviderInitializer.get_circuit_breaker_config(None, "test_provider")

        assert isinstance(result.expected_exception_types, tuple)
        assert len(result.expected_exception_types) == 2


class TestProviderInitializerInitializeProviderConfigs:
    """Test suite for ProviderInitializer.initialize_provider_configs()."""

    def test_initialize_provider_configs_with_no_custom_configs(self) -> None:
        """Test initialization with no custom configs uses all defaults."""
        retry_config, circuit_config = ProviderInitializer.initialize_provider_configs(
            "test_provider"
        )

        assert isinstance(retry_config, RetryConfig)
        assert isinstance(circuit_config, CircuitBreakerConfig)
        assert retry_config.max_attempts == 3  # Config.MAX_API_RETRIES
        assert circuit_config.failure_threshold == 5  # Config.CIRCUIT_BREAKER_THRESHOLD

    def test_initialize_provider_configs_with_custom_retry_config(self) -> None:
        """Test initialization with custom retry config."""
        custom_retry = RetryConfig(max_attempts=7, base_delay=3.0)

        retry_config, circuit_config = ProviderInitializer.initialize_provider_configs(
            "test_provider", retry_config=custom_retry
        )

        assert retry_config is custom_retry
        assert isinstance(circuit_config, CircuitBreakerConfig)

    def test_initialize_provider_configs_with_custom_circuit_config(self) -> None:
        """Test initialization with custom circuit breaker config."""
        custom_circuit = CircuitBreakerConfig(failure_threshold=8, recovery_timeout=90.0)

        retry_config, circuit_config = ProviderInitializer.initialize_provider_configs(
            "test_provider", circuit_config=custom_circuit
        )

        assert isinstance(retry_config, RetryConfig)
        assert circuit_config is custom_circuit

    def test_initialize_provider_configs_with_all_custom_configs(self) -> None:
        """Test initialization with both custom configs."""
        custom_retry = RetryConfig(max_attempts=4)
        custom_circuit = CircuitBreakerConfig(failure_threshold=6)

        retry_config, circuit_config = ProviderInitializer.initialize_provider_configs(
            "test_provider",
            retry_config=custom_retry,
            circuit_config=custom_circuit,
        )

        assert retry_config is custom_retry
        assert circuit_config is custom_circuit

    def test_initialize_provider_configs_returns_tuple(self) -> None:
        """Test that method returns a tuple of (retry_config, circuit_config)."""
        result = ProviderInitializer.initialize_provider_configs("test_provider")

        assert isinstance(result, tuple)
        assert len(result) == 2


class TestProviderAvailabilityCheckerCheckImport:
    """Test suite for ProviderAvailabilityChecker.check_import()."""

    def test_check_import_successful(self) -> None:
        """Test successful module import."""
        # Use a real importable module path
        is_available, imported_class = ProviderAvailabilityChecker.check_import(
            "json", "json", "test_provider"
        )

        assert is_available is True
        # json module should be imported, but there's no 'json' class in json module
        # so imported_class will be None (as tested in another test)
        assert imported_class is None

    def test_check_import_module_not_found(self, caplog) -> None:
        """Test import failure when module doesn't exist."""
        with caplog.at_level(logging.WARNING):
            is_available, imported_class = ProviderAvailabilityChecker.check_import(
                "nonexistent.module.Class",
                "nonexistent-package",
                "test_provider",
            )

        assert is_available is False
        assert imported_class is None
        assert any(
            "test_provider dependencies not installed" in record.message
            for record in caplog.records
        )
        assert any("pip install nonexistent-package" in record.message for record in caplog.records)

    def test_check_import_module_exists_but_class_not_found(self) -> None:
        """Test when module exists but expected class doesn't match."""
        # Import os module, but it won't have an 'os' class
        is_available, imported_class = ProviderAvailabilityChecker.check_import(
            "os", "os", "test_provider"
        )

        assert is_available is True
        # imported_class will be None because there's no 'os' class in os module
        assert imported_class is None

    def test_check_import_logs_success(self, caplog) -> None:
        """Test that successful import logs debug message."""
        with caplog.at_level(logging.DEBUG):
            ProviderAvailabilityChecker.check_import("json", "json", "test_provider")

        assert any(
            "test_provider dependencies available" in record.message for record in caplog.records
        )

    def test_check_import_includes_error_in_warning(self, caplog) -> None:
        """Test that ImportError details are included in warning log."""
        with patch("importlib.import_module") as mock_import:
            mock_import.side_effect = ImportError("Specific import error")

            with caplog.at_level(logging.WARNING):
                # Function catches ImportError and returns False, doesn't raise
                is_available, _ = ProviderAvailabilityChecker.check_import(
                    "fake.module", "fake-package", "test_provider"
                )

            # Verify function returned False
            assert is_available is False

            # Verify error message is in logs
            assert any("Specific import error" in record.message for record in caplog.records)

    def test_check_import_successful_with_class(self) -> None:
        """Test successful import when class exists in module."""
        # Create a mock module with a class that matches the module name
        with patch("importlib.import_module") as mock_import:
            mock_module = Mock()
            # Create a mock class that should be returned
            mock_class = Mock()
            # Set the class as an attribute on the module
            mock_module.RetryConfig = mock_class
            mock_import.return_value = mock_module

            is_available, imported_class = ProviderAvailabilityChecker.check_import(
                "src.utils.retry.RetryConfig", "retry-package", "test_provider"
            )

            assert is_available is True
            assert imported_class is mock_class

    def test_check_import_multi_part_module_name(self) -> None:
        """Test class name extraction from multi-part module path."""
        with patch("importlib.import_module") as mock_import:
            mock_module = Mock()
            mock_class = Mock()
            # For module "a.b.c.ClassName", it should extract "ClassName"
            mock_module.ClassName = mock_class
            mock_import.return_value = mock_module

            is_available, imported_class = ProviderAvailabilityChecker.check_import(
                "package.subpackage.module.ClassName", "package-name", "test_provider"
            )

            assert is_available is True
            assert imported_class is mock_class
            # Verify the correct module was imported
            mock_import.assert_called_once_with("package.subpackage.module.ClassName")

    def test_check_import_returns_none_when_class_attribute_missing(self) -> None:
        """Test that None is returned when module lacks expected class attribute."""
        with patch("importlib.import_module") as mock_import:
            mock_module = Mock()
            # Module exists but doesn't have the expected class
            mock_module.SomeClass = Mock()  # Different class
            delattr(mock_module, "ExpectedClass") if hasattr(mock_module, "ExpectedClass") else None
            mock_import.return_value = mock_module

            # Try to import "some.module.ExpectedClass"
            is_available, imported_class = ProviderAvailabilityChecker.check_import(
                "some.module.ExpectedClass", "some-package", "test_provider"
            )

            # Module import succeeds, but class extraction returns None
            assert is_available is True
            assert imported_class is None


class TestProviderAvailabilityCheckerEnsureAvailable:
    """Test suite for ProviderAvailabilityChecker.ensure_available()."""

    def test_ensure_available_when_available(self) -> None:
        """Test that no exception is raised when provider is available."""
        # Should not raise
        ProviderAvailabilityChecker.ensure_available(True, "test_provider")

    def test_ensure_available_when_not_available(self) -> None:
        """Test that ImportError is raised when provider is not available."""
        with pytest.raises(ImportError) as exc_info:
            ProviderAvailabilityChecker.ensure_available(False, "test_provider")

        assert "test_provider is not available" in str(exc_info.value)
        assert "Please install the required dependencies" in str(exc_info.value)

    def test_ensure_available_error_message_includes_provider_name(self) -> None:
        """Test that error message includes the provider name."""
        provider_names = ["deepgram", "whisper", "custom_provider"]

        for provider_name in provider_names:
            with pytest.raises(ImportError) as exc_info:
                ProviderAvailabilityChecker.ensure_available(False, provider_name)

            assert provider_name in str(exc_info.value)


class TestInitializeProviderWithDefaults:
    """Test suite for initialize_provider_with_defaults()."""

    def test_initialize_provider_with_defaults_minimal_args(self) -> None:
        """Test provider initialization with minimal arguments."""
        mock_provider_class = Mock()
        mock_instance = MagicMock()
        mock_provider_class.return_value = mock_instance

        result = initialize_provider_with_defaults(mock_provider_class, "test_provider")

        assert result is mock_instance
        mock_provider_class.assert_called_once()

        # Check that retry_config and circuit_config were passed
        call_kwargs = mock_provider_class.call_args[1]
        assert "retry_config" in call_kwargs
        assert "circuit_config" in call_kwargs
        assert isinstance(call_kwargs["retry_config"], RetryConfig)
        assert isinstance(call_kwargs["circuit_config"], CircuitBreakerConfig)

    def test_initialize_provider_with_defaults_with_api_key(self) -> None:
        """Test provider initialization with API key."""
        mock_provider_class = Mock()
        mock_instance = MagicMock()
        mock_provider_class.return_value = mock_instance

        api_key = "test-api-key-12345"
        result = initialize_provider_with_defaults(
            mock_provider_class, "test_provider", api_key=api_key
        )

        assert result is mock_instance
        call_kwargs = mock_provider_class.call_args[1]
        assert call_kwargs["api_key"] == api_key

    def test_initialize_provider_with_defaults_with_custom_retry_config(self) -> None:
        """Test provider initialization with custom retry config."""
        mock_provider_class = Mock()
        mock_instance = MagicMock()
        mock_provider_class.return_value = mock_instance

        custom_retry = RetryConfig(max_attempts=10)

        result = initialize_provider_with_defaults(
            mock_provider_class, "test_provider", retry_config=custom_retry
        )

        assert result is mock_instance
        call_kwargs = mock_provider_class.call_args[1]
        assert call_kwargs["retry_config"] is custom_retry

    def test_initialize_provider_with_defaults_with_custom_circuit_config(
        self,
    ) -> None:
        """Test provider initialization with custom circuit breaker config."""
        mock_provider_class = Mock()
        mock_instance = MagicMock()
        mock_provider_class.return_value = mock_instance

        custom_circuit = CircuitBreakerConfig(failure_threshold=15)

        result = initialize_provider_with_defaults(
            mock_provider_class, "test_provider", circuit_config=custom_circuit
        )

        assert result is mock_instance
        call_kwargs = mock_provider_class.call_args[1]
        assert call_kwargs["circuit_config"] is custom_circuit

    def test_initialize_provider_with_defaults_with_extra_kwargs(self) -> None:
        """Test provider initialization with additional keyword arguments."""
        mock_provider_class = Mock()
        mock_instance = MagicMock()
        mock_provider_class.return_value = mock_instance

        result = initialize_provider_with_defaults(
            mock_provider_class,
            "test_provider",
            custom_param1="value1",
            custom_param2=42,
            custom_param3=True,
        )

        assert result is mock_instance
        call_kwargs = mock_provider_class.call_args[1]
        assert call_kwargs["custom_param1"] == "value1"
        assert call_kwargs["custom_param2"] == 42
        assert call_kwargs["custom_param3"] is True

    def test_initialize_provider_with_defaults_all_parameters(self) -> None:
        """Test provider initialization with all possible parameters."""
        mock_provider_class = Mock()
        mock_instance = MagicMock()
        mock_provider_class.return_value = mock_instance

        custom_retry = RetryConfig(max_attempts=8)
        custom_circuit = CircuitBreakerConfig(failure_threshold=12)
        api_key = "complete-test-key"

        result = initialize_provider_with_defaults(
            mock_provider_class,
            "test_provider",
            api_key=api_key,
            retry_config=custom_retry,
            circuit_config=custom_circuit,
            extra_param="extra_value",
        )

        assert result is mock_instance
        call_kwargs = mock_provider_class.call_args[1]
        assert call_kwargs["api_key"] == api_key
        assert call_kwargs["retry_config"] is custom_retry
        assert call_kwargs["circuit_config"] is custom_circuit
        assert call_kwargs["extra_param"] == "extra_value"

    def test_initialize_provider_with_defaults_logs_initialization(self, caplog) -> None:
        """Test that initialization logs info message."""
        mock_provider_class = Mock()
        mock_provider_class.return_value = MagicMock()

        with caplog.at_level(logging.INFO):
            initialize_provider_with_defaults(mock_provider_class, "test_provider")

        assert any(
            "Initializing test_provider provider" in record.message for record in caplog.records
        )

    def test_initialize_provider_with_defaults_api_key_none_not_passed(self) -> None:
        """Test that api_key is not passed if it's None."""
        mock_provider_class = Mock()
        mock_instance = MagicMock()
        mock_provider_class.return_value = mock_instance

        result = initialize_provider_with_defaults(
            mock_provider_class, "test_provider", api_key=None
        )

        assert result is mock_instance
        call_kwargs = mock_provider_class.call_args[1]
        # api_key should NOT be in kwargs when it's None
        assert "api_key" not in call_kwargs

    def test_initialize_provider_with_defaults_preserves_kwargs_order(self) -> None:
        """Test that kwargs are properly merged with configs."""
        mock_provider_class = Mock()
        mock_instance = MagicMock()
        mock_provider_class.return_value = mock_instance

        result = initialize_provider_with_defaults(
            mock_provider_class,
            "test_provider",
            first_param="first",
            second_param="second",
            third_param="third",
        )

        assert result is mock_instance
        call_kwargs = mock_provider_class.call_args[1]
        assert "first_param" in call_kwargs
        assert "second_param" in call_kwargs
        assert "third_param" in call_kwargs
        assert "retry_config" in call_kwargs
        assert "circuit_config" in call_kwargs

    def test_initialize_provider_with_defaults_propagates_initialization_error(
        self,
    ) -> None:
        """Test that exceptions during provider initialization are propagated."""
        mock_provider_class = Mock()
        mock_provider_class.side_effect = ValueError("Invalid configuration")

        with pytest.raises(ValueError) as exc_info:
            initialize_provider_with_defaults(mock_provider_class, "test_provider")

        assert "Invalid configuration" in str(exc_info.value)

    def test_initialize_provider_with_defaults_with_empty_kwargs(self) -> None:
        """Test that empty kwargs dict doesn't cause issues."""
        mock_provider_class = Mock()
        mock_instance = MagicMock()
        mock_provider_class.return_value = mock_instance

        # Explicitly pass empty kwargs
        result = initialize_provider_with_defaults(mock_provider_class, "test_provider", **{})

        assert result is mock_instance
        call_kwargs = mock_provider_class.call_args[1]
        # Should still have retry_config and circuit_config
        assert "retry_config" in call_kwargs
        assert "circuit_config" in call_kwargs


class TestProviderUtilsIntegration:
    """Integration tests for provider utilities workflows."""

    def test_check_import_and_ensure_available_success_flow(self) -> None:
        """Test successful flow from check_import to ensure_available."""
        # Simulate successful import
        is_available, imported_class = ProviderAvailabilityChecker.check_import(
            "json", "json", "test_provider"
        )

        # Should not raise when available
        ProviderAvailabilityChecker.ensure_available(is_available, "test_provider")
        assert is_available is True

    def test_check_import_and_ensure_available_failure_flow(self) -> None:
        """Test failure flow from check_import to ensure_available."""
        # Simulate failed import
        is_available, imported_class = ProviderAvailabilityChecker.check_import(
            "nonexistent.fake.module", "fake-package", "test_provider"
        )

        # Should raise when not available
        with pytest.raises(ImportError) as exc_info:
            ProviderAvailabilityChecker.ensure_available(is_available, "test_provider")

        assert is_available is False
        assert imported_class is None
        assert "test_provider is not available" in str(exc_info.value)

    def test_full_provider_initialization_workflow(self) -> None:
        """Test complete workflow: check import, ensure available, initialize."""
        # Step 1: Check if dependencies are available (using real module)
        is_available, _ = ProviderAvailabilityChecker.check_import("json", "json", "test_provider")

        # Step 2: Ensure available
        ProviderAvailabilityChecker.ensure_available(is_available, "test_provider")

        # Step 3: Initialize provider with defaults
        mock_provider_class = Mock()
        mock_instance = MagicMock()
        mock_provider_class.return_value = mock_instance

        result = initialize_provider_with_defaults(
            mock_provider_class,
            "test_provider",
            api_key="test-key",
        )

        assert result is mock_instance
        assert is_available is True

    def test_custom_configs_flow_through_initialization(self) -> None:
        """Test that custom configs flow correctly through initialization."""
        custom_retry = RetryConfig(max_attempts=8, base_delay=5.0)
        custom_circuit = CircuitBreakerConfig(failure_threshold=20, recovery_timeout=180.0)

        mock_provider_class = Mock()
        mock_instance = MagicMock()
        mock_provider_class.return_value = mock_instance

        result = initialize_provider_with_defaults(
            mock_provider_class,
            "test_provider",
            retry_config=custom_retry,
            circuit_config=custom_circuit,
        )

        assert result is mock_instance
        call_kwargs = mock_provider_class.call_args[1]

        # Verify custom configs were passed through
        assert call_kwargs["retry_config"] is custom_retry
        assert call_kwargs["circuit_config"] is custom_circuit
        assert call_kwargs["retry_config"].max_attempts == 8
        assert call_kwargs["circuit_config"].failure_threshold == 20
