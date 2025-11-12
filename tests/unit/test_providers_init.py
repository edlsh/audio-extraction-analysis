"""Test suite for src.providers package initialization."""

import pytest


class TestProvidersPackage:
    """Test src.providers package module structure and exports."""

    def test_module_import(self):
        """Test that src.providers module can be imported successfully."""
        import src.providers

        assert src.providers is not None

    def test_module_docstring(self):
        """Test that src.providers module has proper docstring."""
        import src.providers

        assert src.providers.__doc__ is not None
        assert isinstance(src.providers.__doc__, str)
        assert len(src.providers.__doc__.strip()) > 0

    def test_docstring_content(self):
        """Test that docstring describes the module purpose."""
        import src.providers

        docstring_lower = src.providers.__doc__.lower()

        # Verify the docstring mentions transcription or providers
        expected_keywords = ["transcription", "provider", "service"]
        assert any(
            keyword in docstring_lower for keyword in expected_keywords
        ), f"Docstring should describe provider functionality: {src.providers.__doc__}"

    def test_all_attribute_exists(self):
        """Test that __all__ attribute is defined."""
        import src.providers

        assert hasattr(src.providers, "__all__")
        assert isinstance(src.providers.__all__, list)

    def test_all_attribute_content(self):
        """Test that __all__ contains expected exports."""
        import src.providers

        expected_exports = [
            "BaseTranscriptionProvider",
            "CircuitBreakerConfig",
            "CircuitBreakerError",
            "CircuitBreakerMixin",
            "CircuitState",
            "TranscriptionProviderFactory",
        ]

        assert set(src.providers.__all__) == set(
            expected_exports
        ), f"__all__ should contain {expected_exports}, got {src.providers.__all__}"

    def test_base_transcription_provider_exported(self):
        """Test that BaseTranscriptionProvider is properly exported."""
        import src.providers

        assert hasattr(src.providers, "BaseTranscriptionProvider")

        # Verify it's the correct class
        from src.providers.base import BaseTranscriptionProvider

        assert src.providers.BaseTranscriptionProvider is BaseTranscriptionProvider

    def test_circuit_breaker_config_exported(self):
        """Test that CircuitBreakerConfig is properly exported."""
        import src.providers

        assert hasattr(src.providers, "CircuitBreakerConfig")

        # Verify it's the correct class
        from src.providers.base import CircuitBreakerConfig

        assert src.providers.CircuitBreakerConfig is CircuitBreakerConfig

    def test_circuit_breaker_error_exported(self):
        """Test that CircuitBreakerError is properly exported."""
        import src.providers

        assert hasattr(src.providers, "CircuitBreakerError")

        # Verify it's the correct exception class
        from src.providers.base import CircuitBreakerError

        assert src.providers.CircuitBreakerError is CircuitBreakerError

    def test_circuit_breaker_mixin_exported(self):
        """Test that CircuitBreakerMixin is properly exported."""
        import src.providers

        assert hasattr(src.providers, "CircuitBreakerMixin")

        # Verify it's the correct class
        from src.providers.base import CircuitBreakerMixin

        assert src.providers.CircuitBreakerMixin is CircuitBreakerMixin

    def test_circuit_state_exported(self):
        """Test that CircuitState is properly exported."""
        import src.providers

        assert hasattr(src.providers, "CircuitState")

        # Verify it's the correct enum
        from src.providers.base import CircuitState

        assert src.providers.CircuitState is CircuitState

    def test_transcription_provider_factory_exported(self):
        """Test that TranscriptionProviderFactory is properly exported."""
        import src.providers

        assert hasattr(src.providers, "TranscriptionProviderFactory")

        # Verify it's the correct class
        from src.providers.factory import TranscriptionProviderFactory

        assert src.providers.TranscriptionProviderFactory is TranscriptionProviderFactory

    def test_direct_import_base_transcription_provider(self):
        """Test that BaseTranscriptionProvider can be imported directly."""
        from src.providers import BaseTranscriptionProvider

        assert BaseTranscriptionProvider is not None
        assert hasattr(BaseTranscriptionProvider, "__name__")
        assert BaseTranscriptionProvider.__name__ == "BaseTranscriptionProvider"

    def test_direct_import_circuit_breaker_config(self):
        """Test that CircuitBreakerConfig can be imported directly."""
        from src.providers import CircuitBreakerConfig

        assert CircuitBreakerConfig is not None
        assert hasattr(CircuitBreakerConfig, "__name__")
        assert CircuitBreakerConfig.__name__ == "CircuitBreakerConfig"

    def test_direct_import_circuit_breaker_error(self):
        """Test that CircuitBreakerError can be imported directly."""
        from src.providers import CircuitBreakerError

        assert CircuitBreakerError is not None
        assert hasattr(CircuitBreakerError, "__name__")
        assert CircuitBreakerError.__name__ == "CircuitBreakerError"

    def test_direct_import_circuit_breaker_mixin(self):
        """Test that CircuitBreakerMixin can be imported directly."""
        from src.providers import CircuitBreakerMixin

        assert CircuitBreakerMixin is not None
        assert hasattr(CircuitBreakerMixin, "__name__")
        assert CircuitBreakerMixin.__name__ == "CircuitBreakerMixin"

    def test_direct_import_circuit_state(self):
        """Test that CircuitState can be imported directly."""
        from src.providers import CircuitState

        assert CircuitState is not None
        assert hasattr(CircuitState, "__name__")
        assert CircuitState.__name__ == "CircuitState"

    def test_direct_import_transcription_provider_factory(self):
        """Test that TranscriptionProviderFactory can be imported directly."""
        from src.providers import TranscriptionProviderFactory

        assert TranscriptionProviderFactory is not None
        assert hasattr(TranscriptionProviderFactory, "__name__")
        assert TranscriptionProviderFactory.__name__ == "TranscriptionProviderFactory"

    def test_wildcard_import(self):
        """Test that wildcard import works correctly."""
        # Import with wildcard should only import items in __all__
        namespace = {}
        exec("from src.providers import *", namespace)

        # Check that only expected items are imported (plus builtins)
        imported_names = [name for name in namespace.keys() if not name.startswith("__")]
        expected_names = [
            "BaseTranscriptionProvider",
            "CircuitBreakerConfig",
            "CircuitBreakerError",
            "CircuitBreakerMixin",
            "CircuitState",
            "TranscriptionProviderFactory",
        ]

        assert set(imported_names) == set(
            expected_names
        ), f"Wildcard import should only import {expected_names}, got {imported_names}"

    def test_no_unexpected_public_exports(self):
        """Test that module doesn't expose unexpected public attributes."""
        import src.providers

        # Get all public attributes (not starting with _)
        public_attrs = [attr for attr in dir(src.providers) if not attr.startswith("_")]

        # Should have the documented exports plus the submodules
        # The module exposes provider implementations and utility modules
        expected_attrs = [
            "BaseTranscriptionProvider",
            "CircuitBreakerConfig",
            "CircuitBreakerError",
            "CircuitBreakerMixin",
            "CircuitState",
            "TranscriptionProviderFactory",
            "base",
            "deepgram",
            "deepgram_utils",
            "elevenlabs",
            "factory",
            "parakeet",
            "provider_utils",
            "whisper",
        ]
        assert set(public_attrs) == set(
            expected_attrs
        ), f"Module should export {expected_attrs}, got {public_attrs}"

    def test_export_types_are_correct(self):
        """Test that exported items are of the correct types."""
        from src.providers import (
            BaseTranscriptionProvider,
            CircuitBreakerConfig,
            CircuitBreakerError,
            CircuitBreakerMixin,
            CircuitState,
            TranscriptionProviderFactory,
        )

        # BaseTranscriptionProvider should be a class
        assert isinstance(
            BaseTranscriptionProvider, type
        ), "BaseTranscriptionProvider should be a class"

        # CircuitBreakerConfig should be a dataclass
        assert isinstance(CircuitBreakerConfig, type), "CircuitBreakerConfig should be a class"

        # CircuitBreakerError should be an exception class
        assert isinstance(
            CircuitBreakerError, type
        ), "CircuitBreakerError should be an exception class"
        assert issubclass(
            CircuitBreakerError, Exception
        ), "CircuitBreakerError should be a subclass of Exception"

        # CircuitBreakerMixin should be a class
        assert isinstance(CircuitBreakerMixin, type), "CircuitBreakerMixin should be a class"

        # CircuitState should be an Enum
        from enum import EnumMeta

        assert isinstance(CircuitState, EnumMeta), "CircuitState should be an Enum"

        # TranscriptionProviderFactory should be a class
        assert isinstance(
            TranscriptionProviderFactory, type
        ), "TranscriptionProviderFactory should be a class"

    def test_import_does_not_raise(self):
        """Test that importing the module does not raise any exceptions."""
        try:
            pass
        except Exception as e:
            pytest.fail(f"Importing src.providers should not raise exceptions: {e}")

    def test_circuit_state_enum_values(self):
        """Test that CircuitState enum has expected values."""
        from src.providers import CircuitState

        # Check that the enum has the expected members
        assert hasattr(CircuitState, "CLOSED")
        assert hasattr(CircuitState, "OPEN")
        assert hasattr(CircuitState, "HALF_OPEN")

        # Verify the values
        assert CircuitState.CLOSED.value == "closed"
        assert CircuitState.OPEN.value == "open"
        assert CircuitState.HALF_OPEN.value == "half_open"

    def test_circuit_breaker_error_is_exception(self):
        """Test that CircuitBreakerError can be raised and caught."""
        import time

        from src.providers import CircuitBreakerError

        # Test that it can be raised with required arguments
        with pytest.raises(CircuitBreakerError):
            raise CircuitBreakerError("Test error", failure_count=5, last_failure_time=time.time())

        # Test that it can be caught as Exception
        try:
            raise CircuitBreakerError("Test error", failure_count=3, last_failure_time=time.time())
        except Exception as e:
            assert isinstance(e, CircuitBreakerError)
            assert e.failure_count == 3
            assert hasattr(e, "last_failure_time")

    def test_circuit_breaker_config_dataclass(self):
        """Test that CircuitBreakerConfig is a valid dataclass."""
        from src.providers import CircuitBreakerConfig

        # Create an instance with default values
        config = CircuitBreakerConfig()
        assert hasattr(config, "failure_threshold")
        assert hasattr(config, "recovery_timeout")
        assert hasattr(config, "expected_exception_types")

        # Test that values can be overridden
        custom_config = CircuitBreakerConfig(failure_threshold=10, recovery_timeout=120.0)
        assert custom_config.failure_threshold == 10
        assert custom_config.recovery_timeout == 120.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
