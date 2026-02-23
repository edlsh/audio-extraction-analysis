"""Unit tests for explicit provider runtime policy controls."""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from src.providers.factory import TranscriptionProviderFactory


class TestProviderRuntimePolicy:
    """Runtime gating tests for test-only providers."""

    @pytest.fixture(autouse=True)
    def reset_test_mode(self) -> None:
        """Reset factory test-mode state between tests when available."""
        if hasattr(TranscriptionProviderFactory, "set_test_mode"):
            TranscriptionProviderFactory.set_test_mode(False)
        yield
        if hasattr(TranscriptionProviderFactory, "set_test_mode"):
            TranscriptionProviderFactory.set_test_mode(False)

    @pytest.mark.unit
    @pytest.mark.fast
    def test_get_available_providers_excludes_test_aliases_by_default(self) -> None:
        """Normal runtime should not include test provider aliases."""
        providers = TranscriptionProviderFactory.get_available_providers()

        assert "mock" not in providers
        assert "stub" not in providers
        assert "test" not in providers

    @pytest.mark.unit
    @pytest.mark.fast
    def test_get_available_providers_can_include_test_aliases_explicitly(self) -> None:
        """Callers can opt into test aliases with an explicit runtime flag."""
        providers = TranscriptionProviderFactory.get_available_providers(include_test_providers=True)

        assert "mock" in providers
        assert "stub" in providers
        assert "test" in providers

    @pytest.mark.unit
    @pytest.mark.fast
    def test_create_test_provider_requires_explicit_runtime_policy(self) -> None:
        """Test provider creation should fail without explicit test-mode enablement."""
        with pytest.raises(ValueError, match="test providers are enabled"):
            TranscriptionProviderFactory.create_provider("test")

    @pytest.mark.unit
    @pytest.mark.fast
    def test_create_test_provider_allows_explicit_runtime_policy(self) -> None:
        """Test provider creation should work with explicit test-mode enablement."""
        provider = TranscriptionProviderFactory.create_provider(
            "test",
            include_test_providers=True,
        )

        assert provider.get_provider_name() == "test"

    @pytest.mark.unit
    @pytest.mark.fast
    def test_set_test_mode_enables_aliases_without_env_vars(self) -> None:
        """Factory-level runtime mode should control alias availability directly."""
        TranscriptionProviderFactory.set_test_mode(True)

        providers = TranscriptionProviderFactory.get_available_providers()
        provider = TranscriptionProviderFactory.create_provider("test")

        assert "test" in providers
        assert provider.get_provider_name() == "test"

    @pytest.mark.unit
    @pytest.mark.fast
    def test_auto_select_test_override_requires_explicit_runtime_policy(self) -> None:
        """Auto-select override for test alias must be rejected by default runtime policy."""
        with patch("src.providers.factory.get_config") as mock_get_config:
            mock_config = Mock()
            mock_config.DEEPGRAM_API_KEY = None
            mock_config.ELEVENLABS_API_KEY = None
            mock_get_config.return_value = mock_config

            with pytest.raises(ValueError, match="No transcription providers configured"):
                TranscriptionProviderFactory.auto_select_provider(test_override="test")

    @pytest.mark.unit
    @pytest.mark.fast
    def test_auto_select_test_override_allows_explicit_runtime_policy(self) -> None:
        """Auto-select override for test alias should work only with explicit runtime policy."""
        with patch("src.providers.factory.get_config") as mock_get_config:
            mock_config = Mock()
            mock_config.DEEPGRAM_API_KEY = None
            mock_config.ELEVENLABS_API_KEY = None
            mock_get_config.return_value = mock_config

            selected = TranscriptionProviderFactory.auto_select_provider(
                test_override="test",
                include_test_providers=True,
            )

            assert selected == "test"
