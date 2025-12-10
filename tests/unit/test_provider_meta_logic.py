"""Unit tests for ProviderMeta-based factory logic.

Tests the get_configured_providers() method and its use of ProviderMeta
for determining configured providers based on API keys and SDK availability.
"""

from unittest.mock import MagicMock, Mock, patch

import pytest

from src.providers.base import ProviderMeta
from src.providers.factory import TranscriptionProviderFactory
from src.providers.provider_utils import check_sdk_available


class TestProviderMetaBasedConfiguration:
    """Test get_configured_providers() with ProviderMeta."""

    @pytest.fixture(autouse=True)
    def clear_provider_registry(self):
        """Clear provider registry before each test and restore after."""
        original_providers = TranscriptionProviderFactory._providers.copy()
        TranscriptionProviderFactory._providers.clear()
        yield
        TranscriptionProviderFactory._providers.clear()
        TranscriptionProviderFactory._providers.update(original_providers)

    def test_cloud_provider_requires_api_key_min_length(self):
        """Cloud providers must have API key meeting minimum length from META."""
        with patch("src.providers.factory.get_config") as mock_get_config:
            mock_config = Mock()
            # Deepgram requires 20 chars, ElevenLabs requires 10 chars
            mock_config.DEEPGRAM_API_KEY = "short"  # Too short (5 chars)
            mock_config.ELEVENLABS_API_KEY = "also_short"  # Exactly 10 chars
            mock_get_config.return_value = mock_config

            configured = TranscriptionProviderFactory.get_configured_providers()

            # Deepgram should NOT be configured (key too short)
            assert "deepgram" not in configured
            # ElevenLabs should be configured (exactly meets min length)
            assert "elevenlabs" in configured

    def test_cloud_provider_with_sufficient_key_length(self):
        """Cloud providers with keys meeting minimum length should be configured."""
        with patch("src.providers.factory.get_config") as mock_get_config:
            mock_config = Mock()
            # Deepgram requires 20 chars
            mock_config.DEEPGRAM_API_KEY = "12345678901234567890"  # Exactly 20 chars
            mock_config.ELEVENLABS_API_KEY = "1234567890"  # Exactly 10 chars
            mock_get_config.return_value = mock_config

            configured = TranscriptionProviderFactory.get_configured_providers()

            assert "deepgram" in configured
            assert "elevenlabs" in configured

    def test_cloud_provider_with_no_key(self):
        """Cloud providers without API key should not be configured."""
        with patch("src.providers.factory.get_config") as mock_get_config:
            mock_config = Mock()
            mock_config.DEEPGRAM_API_KEY = None
            mock_config.ELEVENLABS_API_KEY = ""
            mock_get_config.return_value = mock_config

            configured = TranscriptionProviderFactory.get_configured_providers()

            assert "deepgram" not in configured
            assert "elevenlabs" not in configured

    def test_local_provider_uses_sdk_check(self):
        """Local providers (Whisper, Parakeet) use SDK availability checks."""
        with (
            patch("src.providers.factory.get_config") as mock_get_config,
            patch(
                "src.providers.factory.check_sdk_available"
            ) as mock_sdk_check,
        ):
            mock_config = Mock()
            mock_config.DEEPGRAM_API_KEY = None
            mock_config.ELEVENLABS_API_KEY = None
            mock_get_config.return_value = mock_config

            # SDK available for whisper, not for parakeet
            def sdk_side_effect(meta):
                return meta.provider_key == "whisper"

            mock_sdk_check.side_effect = sdk_side_effect

            configured = TranscriptionProviderFactory.get_configured_providers()

            # Only whisper should be configured (SDK available)
            assert "whisper" in configured
            assert "parakeet" not in configured


class TestCheckSdkAvailable:
    """Test the check_sdk_available helper function."""

    def test_sdk_available_all_imports_succeed(self):
        """Returns True when all SDK imports succeed."""
        meta = ProviderMeta(
            name="Test",
            provider_key="test",
            supported_features=[],
            sdk_imports=["os", "sys"],  # Standard library - always available
            is_local=True,
        )
        assert check_sdk_available(meta) is True

    def test_sdk_not_available_import_fails(self):
        """Returns False when any SDK import fails."""
        meta = ProviderMeta(
            name="Test",
            provider_key="test",
            supported_features=[],
            sdk_imports=["nonexistent_module_12345"],
            is_local=True,
        )
        assert check_sdk_available(meta) is False

    def test_sdk_available_empty_imports(self):
        """Returns True when no SDK imports required."""
        meta = ProviderMeta(
            name="Test",
            provider_key="test",
            supported_features=[],
            sdk_imports=[],
            is_local=True,
        )
        assert check_sdk_available(meta) is True

    def test_sdk_available_mixed_imports(self):
        """Returns False if any import in list fails."""
        meta = ProviderMeta(
            name="Test",
            provider_key="test",
            supported_features=[],
            sdk_imports=["os", "nonexistent_module_12345"],  # First succeeds, second fails
            is_local=True,
        )
        assert check_sdk_available(meta) is False


class TestProviderMetaDefaults:
    """Test ProviderMeta default values."""

    def test_default_api_key_min_length(self):
        """Default api_key_min_length should be 10."""
        meta = ProviderMeta(
            name="Test",
            provider_key="test",
            supported_features=[],
        )
        assert meta.api_key_min_length == 10

    def test_default_is_local(self):
        """Default is_local should be False (cloud provider)."""
        meta = ProviderMeta(
            name="Test",
            provider_key="test",
            supported_features=[],
        )
        assert meta.is_local is False

    def test_default_sdk_imports(self):
        """Default sdk_imports should be empty list."""
        meta = ProviderMeta(
            name="Test",
            provider_key="test",
            supported_features=[],
        )
        assert meta.sdk_imports == []
