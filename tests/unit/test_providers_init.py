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
            "ProviderSelectionPolicy",
            "TranscriptionPolicy",
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

    def test_direct_import_transcription_provider_factory(self):
        """Test that TranscriptionProviderFactory can be imported directly."""
        from src.providers import TranscriptionProviderFactory

        assert TranscriptionProviderFactory is not None
        assert hasattr(TranscriptionProviderFactory, "__name__")
        assert TranscriptionProviderFactory.__name__ == "TranscriptionProviderFactory"

    def test_direct_import_transcription_policy(self):
        """Test that TranscriptionPolicy can be imported directly."""
        from src.providers import TranscriptionPolicy

        assert TranscriptionPolicy is not None
        assert hasattr(TranscriptionPolicy, "__name__")
        assert TranscriptionPolicy.__name__ == "TranscriptionPolicy"

    def test_direct_import_provider_selection_policy(self):
        """Test that ProviderSelectionPolicy can be imported directly."""
        from src.providers import ProviderSelectionPolicy

        assert ProviderSelectionPolicy is not None
        assert hasattr(ProviderSelectionPolicy, "__name__")
        assert ProviderSelectionPolicy.__name__ == "ProviderSelectionPolicy"

    def test_wildcard_import(self):
        """Test that wildcard import works correctly."""
        # Import with wildcard should only import items in __all__
        namespace = {}
        exec("from src.providers import *", namespace)

        # Check that only expected items are imported (plus builtins)
        imported_names = [name for name in namespace.keys() if not name.startswith("__")]
        expected_names = [
            "BaseTranscriptionProvider",
            "ProviderSelectionPolicy",
            "TranscriptionPolicy",
            "TranscriptionProviderFactory",
        ]

        assert set(imported_names) == set(
            expected_names
        ), f"Wildcard import should only import {expected_names}, got {imported_names}"

    def test_no_unexpected_public_exports(self):
        """Test that module exports the required items.

        Note: Provider submodules (deepgram, elevenlabs, whisper, parakeet, mock)
        are lazily loaded by the factory and not eagerly imported at module level.
        This keeps import times fast by avoiding heavyweight dependencies.

        The test checks for minimum required exports. Additional modules may
        appear if other tests in the suite have imported them.
        """
        from src import providers

        public_attrs = set(attr for attr in dir(providers) if not attr.startswith("_"))

        # Required exports that must always be present
        required_attrs = {
            "BaseTranscriptionProvider",
            "ProviderSelectionPolicy",
            "TranscriptionPolicy",
            "TranscriptionProviderFactory",
            "base",
            "factory",
            "policy",
        }

        # Verify all required exports are present
        missing = required_attrs - public_attrs
        assert not missing, f"Missing required exports: {missing}"

        # Verify __all__ matches expected public API
        expected_all = [
            "BaseTranscriptionProvider",
            "ProviderSelectionPolicy",
            "TranscriptionPolicy",
            "TranscriptionProviderFactory",
        ]
        assert set(providers.__all__) == set(
            expected_all
        ), f"__all__ should be {expected_all}, got {providers.__all__}"

    def test_export_types_are_correct(self):
        """Test that exported items are of the correct types."""
        from src.providers import (
            BaseTranscriptionProvider,
            ProviderSelectionPolicy,
            TranscriptionPolicy,
            TranscriptionProviderFactory,
        )

        # BaseTranscriptionProvider should be a class
        assert isinstance(
            BaseTranscriptionProvider, type
        ), "BaseTranscriptionProvider should be a class"

        # TranscriptionProviderFactory should be a class
        assert isinstance(
            TranscriptionProviderFactory, type
        ), "TranscriptionProviderFactory should be a class"

        # ProviderSelectionPolicy should be a class
        assert isinstance(
            ProviderSelectionPolicy, type
        ), "ProviderSelectionPolicy should be a class"

        # TranscriptionPolicy should be a class
        assert isinstance(TranscriptionPolicy, type), "TranscriptionPolicy should be a class"

    def test_import_does_not_raise(self):
        """Test that importing the module does not raise any exceptions."""
        try:
            import src.providers  # noqa: F401
        except Exception as e:
            pytest.fail(f"Importing src.providers should not raise exceptions: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
