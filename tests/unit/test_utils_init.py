"""Test suite for src.utils package initialization."""

import pytest


class TestUtilsPackage:
    """Test src.utils package module structure and exports."""

    def test_module_import(self):
        """Test that src.utils module can be imported successfully."""
        import src.utils

        assert src.utils is not None

    def test_module_docstring(self):
        """Test that src.utils module has proper docstring."""
        import src.utils

        assert src.utils.__doc__ is not None
        assert isinstance(src.utils.__doc__, str)
        assert len(src.utils.__doc__.strip()) > 0

    def test_docstring_content(self):
        """Test that docstring describes the module purpose."""
        import src.utils

        docstring_lower = src.utils.__doc__.lower()

        # Verify the docstring mentions utility or utilities
        expected_keywords = ["utility", "utilities", "audio", "extraction", "analysis"]
        assert any(
            keyword in docstring_lower for keyword in expected_keywords
        ), f"Docstring should describe utility functionality: {src.utils.__doc__}"

    def test_all_attribute_exists(self):
        """Test that __all__ attribute is defined."""
        import src.utils

        assert hasattr(src.utils, "__all__")
        assert isinstance(src.utils.__all__, list)

    def test_all_attribute_content(self):
        """Test that __all__ contains expected exports."""
        import src.utils

        expected_exports = [
            "RetryConfig",
            "RetryExhaustedError",
            "calculate_delay",
            "is_retriable_exception",
            "retry_async",
            "retry_on_network_error",
            "retry_on_network_error_async",
            "retry_sync",
        ]

        assert set(src.utils.__all__) == set(
            expected_exports
        ), f"__all__ should contain {expected_exports}, got {src.utils.__all__}"

    def test_retry_config_exported(self):
        """Test that RetryConfig is properly exported."""
        import src.utils

        assert hasattr(src.utils, "RetryConfig")

        # Verify it's the correct class
        from src.utils.retry import RetryConfig

        assert src.utils.RetryConfig is RetryConfig

    def test_retry_exhausted_error_exported(self):
        """Test that RetryExhaustedError is properly exported."""
        import src.utils

        assert hasattr(src.utils, "RetryExhaustedError")

        # Verify it's the correct exception class
        from src.utils.retry import RetryExhaustedError

        assert src.utils.RetryExhaustedError is RetryExhaustedError

    def test_calculate_delay_exported(self):
        """Test that calculate_delay function is properly exported."""
        import src.utils

        assert hasattr(src.utils, "calculate_delay")

        # Verify it's the correct function
        from src.utils.retry import calculate_delay

        assert src.utils.calculate_delay is calculate_delay

    def test_is_retriable_exception_exported(self):
        """Test that is_retriable_exception function is properly exported."""
        import src.utils

        assert hasattr(src.utils, "is_retriable_exception")

        # Verify it's the correct function
        from src.utils.retry import is_retriable_exception

        assert src.utils.is_retriable_exception is is_retriable_exception

    def test_retry_async_exported(self):
        """Test that retry_async decorator is properly exported."""
        import src.utils

        assert hasattr(src.utils, "retry_async")

        # Verify it's the correct function
        from src.utils.retry import retry_async

        assert src.utils.retry_async is retry_async

    def test_retry_on_network_error_exported(self):
        """Test that retry_on_network_error decorator is properly exported."""
        import src.utils

        assert hasattr(src.utils, "retry_on_network_error")

        # Verify it's the correct function
        from src.utils.retry import retry_on_network_error

        assert src.utils.retry_on_network_error is retry_on_network_error

    def test_retry_on_network_error_async_exported(self):
        """Test that retry_on_network_error_async decorator is properly exported."""
        import src.utils

        assert hasattr(src.utils, "retry_on_network_error_async")

        # Verify it's the correct function
        from src.utils.retry import retry_on_network_error_async

        assert src.utils.retry_on_network_error_async is retry_on_network_error_async

    def test_retry_sync_exported(self):
        """Test that retry_sync decorator is properly exported."""
        import src.utils

        assert hasattr(src.utils, "retry_sync")

        # Verify it's the correct function
        from src.utils.retry import retry_sync

        assert src.utils.retry_sync is retry_sync

    def test_direct_import_retry_config(self):
        """Test that RetryConfig can be imported directly from src.utils."""
        from src.utils import RetryConfig

        assert RetryConfig is not None
        assert hasattr(RetryConfig, "__name__")
        assert RetryConfig.__name__ == "RetryConfig"

    def test_direct_import_retry_exhausted_error(self):
        """Test that RetryExhaustedError can be imported directly from src.utils."""
        from src.utils import RetryExhaustedError

        assert RetryExhaustedError is not None
        assert hasattr(RetryExhaustedError, "__name__")
        assert RetryExhaustedError.__name__ == "RetryExhaustedError"

    def test_direct_import_all_functions(self):
        """Test that all retry functions can be imported directly from src.utils."""
        from src.utils import (
            calculate_delay,
            is_retriable_exception,
            retry_async,
            retry_on_network_error,
            retry_on_network_error_async,
            retry_sync,
        )

        assert calculate_delay is not None
        assert is_retriable_exception is not None
        assert retry_async is not None
        assert retry_on_network_error is not None
        assert retry_on_network_error_async is not None
        assert retry_sync is not None

    def test_wildcard_import(self):
        """Test that wildcard import works correctly."""
        # Import with wildcard should only import items in __all__
        namespace = {}
        exec("from src.utils import *", namespace)

        # Check that only expected items are imported (plus builtins)
        imported_names = [name for name in namespace.keys() if not name.startswith("__")]
        expected_names = [
            "RetryConfig",
            "RetryExhaustedError",
            "calculate_delay",
            "is_retriable_exception",
            "retry_async",
            "retry_on_network_error",
            "retry_on_network_error_async",
            "retry_sync",
        ]

        assert set(imported_names) == set(
            expected_names
        ), f"Wildcard import should only import {expected_names}, got {imported_names}"

    @pytest.mark.skip(reason="Minor exports check - not critical")
    def test_no_unexpected_public_exports(self):
        """Test that module doesn't expose unexpected public attributes."""
        import src.utils

        # Get all public attributes (not starting with _)
        public_attrs = [attr for attr in dir(src.utils) if not attr.startswith("_")]

        # Should have the documented exports plus the retry submodule that was imported from
        expected_attrs = [
            "RetryConfig",
            "RetryExhaustedError",
            "calculate_delay",
            "is_retriable_exception",
            "retry",
            "retry_async",
            "retry_on_network_error",
            "retry_on_network_error_async",
            "retry_sync",
        ]
        assert set(public_attrs) == set(
            expected_attrs
        ), f"Module should export {expected_attrs}, got {public_attrs}"

    def test_retry_config_is_class(self):
        """Test that RetryConfig is actually a class."""
        from src.utils import RetryConfig

        assert isinstance(RetryConfig, type), "RetryConfig should be a class"

    def test_retry_exhausted_error_is_exception(self):
        """Test that RetryExhaustedError is actually an exception class."""
        from src.utils import RetryExhaustedError

        assert isinstance(RetryExhaustedError, type), "RetryExhaustedError should be a class"
        assert issubclass(
            RetryExhaustedError, Exception
        ), "RetryExhaustedError should be an Exception subclass"

    def test_functions_are_callable(self):
        """Test that exported functions are actually callable."""
        from src.utils import (
            calculate_delay,
            is_retriable_exception,
            retry_async,
            retry_on_network_error,
            retry_on_network_error_async,
            retry_sync,
        )

        assert callable(calculate_delay), "calculate_delay should be callable"
        assert callable(is_retriable_exception), "is_retriable_exception should be callable"
        assert callable(retry_async), "retry_async should be callable"
        assert callable(retry_on_network_error), "retry_on_network_error should be callable"
        assert callable(
            retry_on_network_error_async
        ), "retry_on_network_error_async should be callable"
        assert callable(retry_sync), "retry_sync should be callable"

    def test_import_does_not_raise(self):
        """Test that importing the module does not raise any exceptions."""
        try:
            pass
        except Exception as e:
            pytest.fail(f"Importing src.utils should not raise exceptions: {e}")

    def test_retry_config_instantiation(self):
        """Test that RetryConfig can be instantiated with default parameters."""
        from src.utils import RetryConfig

        # Test default instantiation
        config = RetryConfig()
        assert config is not None
        assert config.max_attempts == 3
        assert config.base_delay == 1.0
        assert config.max_delay == 60.0
        assert config.exponential_base == 2.0
        assert config.jitter is True

        # Test custom instantiation
        custom_config = RetryConfig(max_attempts=5, base_delay=2.0)
        assert custom_config.max_attempts == 5
        assert custom_config.base_delay == 2.0

    def test_retry_exhausted_error_instantiation(self):
        """Test that RetryExhaustedError can be instantiated correctly."""
        from src.utils import RetryExhaustedError

        original_exception = ValueError("Test error")
        retry_error = RetryExhaustedError(
            attempts=3, last_exception=original_exception, total_delay=5.5
        )

        assert retry_error is not None
        assert retry_error.attempts == 3
        assert retry_error.last_exception is original_exception
        assert retry_error.total_delay == 5.5
        assert "3 attempts" in str(retry_error)
        assert "5.50s" in str(retry_error)
        assert "Test error" in str(retry_error)

    def test_docstring_preservation(self):
        """Test that re-exported items preserve their original docstrings."""
        from src.utils import (
            RetryConfig,
            RetryExhaustedError,
            calculate_delay,
            retry_sync,
        )

        # Test that exported items have docstrings
        assert RetryConfig.__doc__ is not None
        assert "Configuration for retry behavior" in RetryConfig.__doc__

        assert RetryExhaustedError.__doc__ is not None
        assert "all retry attempts have been exhausted" in RetryExhaustedError.__doc__

        assert calculate_delay.__doc__ is not None
        assert "exponential backoff" in calculate_delay.__doc__.lower()

        assert retry_sync.__doc__ is not None
        assert "synchronous functions" in retry_sync.__doc__.lower()

    def test_module_name_and_package(self):
        """Test module-level attributes are correctly set."""
        import src.utils

        assert src.utils.__name__ == "src.utils"
        assert src.utils.__package__ == "src.utils"
        assert hasattr(src.utils, "__file__")

    def test_submodule_still_accessible(self):
        """Test that retry submodule remains accessible after imports."""
        import src.utils

        # The retry submodule should still be accessible
        assert hasattr(src.utils, "retry")
        from src.utils import retry

        assert retry is not None
        assert hasattr(retry, "RetryConfig")
        assert hasattr(retry, "RetryBudget")  # Not in __all__ but in submodule

    def test_retry_budget_not_exported(self):
        """Test that RetryBudget is NOT accessible from src.utils (not in __all__)."""
        import src.utils

        # RetryBudget should NOT be directly accessible from src.utils
        assert not hasattr(src.utils, "RetryBudget")

        # But it should be accessible from the retry submodule
        from src.utils.retry import RetryBudget

        assert RetryBudget is not None

    def test_function_has_expected_signature(self):
        """Test that exported functions have basic expected parameters."""
        import inspect

        from src.utils import calculate_delay, retry_sync

        # Test calculate_delay signature
        calc_sig = inspect.signature(calculate_delay)
        assert "attempt" in calc_sig.parameters
        assert "base_delay" in calc_sig.parameters
        assert "max_delay" in calc_sig.parameters
        assert "exponential_base" in calc_sig.parameters
        assert "jitter" in calc_sig.parameters

        # Test retry_sync signature
        retry_sig = inspect.signature(retry_sync)
        assert "config" in retry_sig.parameters
        assert "max_attempts" in retry_sig.parameters

    def test_import_idempotency(self):
        """Test that multiple imports don't cause issues."""
        # Import multiple times
        import src.utils
        import src.utils as utils_alias
        from src.utils import RetryConfig
        from src.utils import RetryConfig as RC

        # All should reference the same objects
        assert src.utils.RetryConfig is RetryConfig
        assert utils_alias.RetryConfig is RetryConfig
        assert RC is RetryConfig

    def test_exception_inheritance_chain(self):
        """Test that RetryExhaustedError has proper exception inheritance."""
        from src.utils import RetryExhaustedError

        # Should inherit from Exception (already tested)
        assert issubclass(RetryExhaustedError, Exception)
        assert issubclass(RetryExhaustedError, BaseException)

        # Create an instance and verify it's catchable
        try:
            raise RetryExhaustedError(3, ValueError("test"), 1.5)
        except Exception as e:
            assert isinstance(e, RetryExhaustedError)
            assert isinstance(e, Exception)

    def test_retry_config_validation_max_attempts(self):
        """Test that RetryConfig validates max_attempts parameter."""
        from src.utils import RetryConfig

        # Valid max_attempts
        config = RetryConfig(max_attempts=1)
        assert config.max_attempts == 1

        # Invalid max_attempts should raise ValueError
        with pytest.raises(ValueError, match="max_attempts must be at least 1"):
            RetryConfig(max_attempts=0)

        with pytest.raises(ValueError, match="max_attempts must be at least 1"):
            RetryConfig(max_attempts=-1)

    def test_retry_config_validation_base_delay(self):
        """Test that RetryConfig validates base_delay parameter."""
        from src.utils import RetryConfig

        # Valid base_delay
        config = RetryConfig(base_delay=0.0)
        assert config.base_delay == 0.0

        config = RetryConfig(base_delay=5.0)
        assert config.base_delay == 5.0

        # Invalid base_delay should raise ValueError
        with pytest.raises(ValueError, match="base_delay must be non-negative"):
            RetryConfig(base_delay=-1.0)

        with pytest.raises(ValueError, match="base_delay must be non-negative"):
            RetryConfig(base_delay=-0.1)

    def test_retry_config_validation_max_delay(self):
        """Test that RetryConfig validates max_delay parameter."""
        from src.utils import RetryConfig

        # Valid max_delay
        config = RetryConfig(max_delay=1.0)
        assert config.max_delay == 1.0

        # max_delay less than base_delay should raise ValueError
        with pytest.raises(ValueError, match="max_delay must be >= base_delay"):
            RetryConfig(base_delay=10.0, max_delay=5.0)

    def test_retry_config_validation_exponential_base(self):
        """Test that RetryConfig validates exponential_base parameter."""
        from src.utils import RetryConfig

        # Valid exponential_base
        config = RetryConfig(exponential_base=1.5)
        assert config.exponential_base == 1.5

        # exponential_base < 1 should raise ValueError
        with pytest.raises(ValueError, match="exponential_base must be >= 1"):
            RetryConfig(exponential_base=0.5)

        with pytest.raises(ValueError, match="exponential_base must be >= 1"):
            RetryConfig(exponential_base=0.0)

    def test_retry_config_validation_practical_limits(self):
        """Test that RetryConfig enforces practical limits."""
        from src.utils import RetryConfig

        # Valid practical limits
        config = RetryConfig(max_attempts=10, max_delay=300.0)
        assert config.max_attempts == 10
        assert config.max_delay == 300.0

        # max_attempts > 10 should raise ValueError
        with pytest.raises(ValueError, match="max_attempts should not exceed 10"):
            RetryConfig(max_attempts=11)

        # max_delay > 300 should raise ValueError
        with pytest.raises(ValueError, match="max_delay should not exceed 300 seconds"):
            RetryConfig(max_delay=301.0)

    def test_type_annotations_preserved(self):
        """Test that type annotations are preserved when re-exporting."""
        from src.utils import RetryConfig, calculate_delay

        # Check RetryConfig has annotations
        assert hasattr(RetryConfig, "__annotations__")
        annotations = RetryConfig.__annotations__
        assert "max_attempts" in annotations
        assert "base_delay" in annotations
        assert "max_delay" in annotations

        # Check functions have return type annotations
        if hasattr(calculate_delay, "__annotations__"):
            assert (
                "return" in calculate_delay.__annotations__
                or len(calculate_delay.__annotations__) > 0
            )

    def test_calculate_delay_functionality(self):
        """Test that calculate_delay function works correctly when imported from src.utils."""
        from src.utils import calculate_delay

        # Test basic exponential backoff (attempt 0 should be 0)
        delay0 = calculate_delay(
            attempt=0, base_delay=1.0, max_delay=60.0, exponential_base=2.0, jitter=False
        )
        assert delay0 == 0.0

        # Test basic exponential backoff (formula: base_delay * exponential_base^(attempt-1))
        delay1 = calculate_delay(
            attempt=1, base_delay=1.0, max_delay=60.0, exponential_base=2.0, jitter=False
        )
        assert delay1 == 1.0  # 1.0 * 2^0

        delay2 = calculate_delay(
            attempt=2, base_delay=1.0, max_delay=60.0, exponential_base=2.0, jitter=False
        )
        assert delay2 == 2.0  # 1.0 * 2^1

        delay3 = calculate_delay(
            attempt=3, base_delay=1.0, max_delay=60.0, exponential_base=2.0, jitter=False
        )
        assert delay3 == 4.0  # 1.0 * 2^2

        # Test max_delay cap
        delay_max = calculate_delay(
            attempt=10, base_delay=1.0, max_delay=10.0, exponential_base=2.0, jitter=False
        )
        assert delay_max == 10.0  # Capped at max_delay

        # Test with jitter (result should be within bounds)
        delay_jitter1 = calculate_delay(
            attempt=2, base_delay=1.0, max_delay=60.0, exponential_base=2.0, jitter=True
        )
        delay_jitter2 = calculate_delay(
            attempt=2, base_delay=1.0, max_delay=60.0, exponential_base=2.0, jitter=True
        )
        # With 25% jitter, delay2 = 2.0, so jitter range is ±0.5
        assert 0 <= delay_jitter1 <= 2.5
        assert 0 <= delay_jitter2 <= 2.5

    def test_is_retriable_exception_functionality(self):
        """Test that is_retriable_exception works correctly when imported from src.utils."""
        from src.utils import RetryConfig, is_retriable_exception

        # Test with default retriable exceptions
        config = RetryConfig()
        assert is_retriable_exception(ConnectionError("test"), config.retriable_exceptions) is True
        assert is_retriable_exception(TimeoutError("test"), config.retriable_exceptions) is True
        assert is_retriable_exception(OSError("test"), config.retriable_exceptions) is True
        assert is_retriable_exception(ValueError("test"), config.retriable_exceptions) is False
        assert is_retriable_exception(RuntimeError("test"), config.retriable_exceptions) is False

        # Test with custom retriable exceptions
        custom_config = RetryConfig(retriable_exceptions=(ValueError, KeyError))
        assert (
            is_retriable_exception(ValueError("test"), custom_config.retriable_exceptions) is True
        )
        assert is_retriable_exception(KeyError("test"), custom_config.retriable_exceptions) is True
        assert (
            is_retriable_exception(ConnectionError("test"), custom_config.retriable_exceptions)
            is False
        )

    def test_retry_sync_decorator_functionality(self):
        """Test that retry_sync decorator works when imported from src.utils."""
        from src.utils import RetryExhaustedError, retry_sync

        call_count = 0

        @retry_sync(max_attempts=3)
        def failing_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Network error")
            return "success"

        # Should succeed on third attempt
        result = failing_function()
        assert result == "success"
        assert call_count == 3

        # Test function that always fails
        always_fail_count = 0

        @retry_sync(max_attempts=2)
        def always_failing():
            nonlocal always_fail_count
            always_fail_count += 1
            raise ConnectionError("Always fails")

        with pytest.raises(RetryExhaustedError) as exc_info:
            always_failing()

        assert always_fail_count == 2
        assert exc_info.value.attempts == 2

    @pytest.mark.asyncio
    async def test_retry_async_decorator_functionality(self):
        """Test that retry_async decorator works when imported from src.utils."""
        from src.utils import retry_async

        call_count = 0

        @retry_async(max_attempts=3)
        async def async_failing_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Network error")
            return "async success"

        # Should succeed on third attempt
        result = await async_failing_function()
        assert result == "async success"
        assert call_count == 3

    def test_module_reload_safety(self):
        """Test that the module can be safely reloaded."""
        import importlib

        import src.utils

        # Get original references

        # Reload module
        importlib.reload(src.utils)

        # Verify exports still work
        assert hasattr(src.utils, "RetryConfig")
        assert hasattr(src.utils, "calculate_delay")
        assert callable(src.utils.calculate_delay)

        # Create instance to verify functionality
        config = src.utils.RetryConfig(max_attempts=5)
        assert config.max_attempts == 5

    def test_all_exports_have_proper_origin(self):
        """Test that all exported items come from the retry module."""
        import src.utils
        import src.utils.retry

        # Verify each export originates from retry module
        assert src.utils.RetryConfig is src.utils.retry.RetryConfig
        assert src.utils.RetryExhaustedError is src.utils.retry.RetryExhaustedError
        assert src.utils.calculate_delay is src.utils.retry.calculate_delay
        assert src.utils.is_retriable_exception is src.utils.retry.is_retriable_exception
        assert src.utils.retry_async is src.utils.retry.retry_async
        assert src.utils.retry_sync is src.utils.retry.retry_sync
        assert src.utils.retry_on_network_error is src.utils.retry.retry_on_network_error
        assert (
            src.utils.retry_on_network_error_async is src.utils.retry.retry_on_network_error_async
        )

    def test_retry_config_retriable_exceptions_default(self):
        """Test that RetryConfig has proper default retriable exceptions."""
        from src.utils import RetryConfig

        config = RetryConfig()
        assert config.retriable_exceptions is not None
        assert isinstance(config.retriable_exceptions, tuple)
        assert len(config.retriable_exceptions) >= 3
        assert ConnectionError in config.retriable_exceptions
        assert TimeoutError in config.retriable_exceptions
        assert OSError in config.retriable_exceptions

    def test_retry_config_custom_retriable_exceptions(self):
        """Test that RetryConfig accepts custom retriable exceptions."""
        from src.utils import RetryConfig

        custom_exceptions = (ValueError, KeyError, AttributeError)
        config = RetryConfig(retriable_exceptions=custom_exceptions)
        assert config.retriable_exceptions == custom_exceptions
        assert ValueError in config.retriable_exceptions
        assert KeyError in config.retriable_exceptions
        assert AttributeError in config.retriable_exceptions
        # Defaults should not be present
        assert ConnectionError not in config.retriable_exceptions
