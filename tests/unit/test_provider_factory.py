"""Unit tests for TranscriptionProviderFactory."""

from pathlib import Path
from tempfile import NamedTemporaryFile
from unittest.mock import Mock, patch

import pytest

from src.providers.base import BaseTranscriptionProvider
from src.providers.factory import TranscriptionProviderFactory


@pytest.fixture(autouse=True)
def clear_api_keys(monkeypatch):
    """Clear all API keys before each test."""
    monkeypatch.delenv("DEEPGRAM_API_KEY", raising=False)
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)


@pytest.fixture(autouse=True)
def clear_provider_registry():
    """Clear provider registry before each test and restore after."""
    original_providers = TranscriptionProviderFactory._providers.copy()
    TranscriptionProviderFactory._providers.clear()
    yield
    TranscriptionProviderFactory._providers.clear()
    TranscriptionProviderFactory._providers.update(original_providers)


@pytest.fixture
def mock_provider_class():
    """Create a mock provider class for testing."""

    class MockProvider(BaseTranscriptionProvider):
        def __init__(self, api_key=None):
            super().__init__(api_key)
            self.api_key = api_key or "mock_key"

        async def transcribe_async(self, audio_file_path, language="en"):
            return None

        def validate_configuration(self):
            return bool(self.api_key)

        def get_provider_name(self):
            return "MockProvider"

        def get_supported_features(self):
            return ["basic_transcription", "timestamps"]

    return MockProvider


@pytest.fixture
def temp_audio_file():
    """Create a temporary audio file for testing."""
    with NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
        # Small file (< 50MB)
        temp_file.write(b"fake_audio_data" * 1000)  # ~15KB
        temp_path = Path(temp_file.name)

    yield temp_path

    if temp_path.exists():
        temp_path.unlink()


@pytest.fixture
def large_audio_file():
    """Create a large audio file for testing."""
    with NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
        # Large file (> 50MB)
        temp_file.write(b"fake_audio_data" * 4000000)  # ~60MB
        temp_path = Path(temp_file.name)

    yield temp_path

    if temp_path.exists():
        temp_path.unlink()


class TestTranscriptionProviderFactoryRegistration:
    """Test provider registration functionality."""

    def test_register_provider(self, mock_provider_class):
        """Test registering a new provider."""
        # Clear existing providers
        TranscriptionProviderFactory._providers.clear()

        TranscriptionProviderFactory.register_provider("mock", mock_provider_class)

        assert "mock" in TranscriptionProviderFactory._providers
        assert TranscriptionProviderFactory._providers["mock"] == mock_provider_class

    def test_get_available_providers(self, mock_provider_class):
        """Test getting list of available providers."""
        TranscriptionProviderFactory._providers.clear()
        TranscriptionProviderFactory.register_provider("mock1", mock_provider_class)
        TranscriptionProviderFactory.register_provider("mock2", mock_provider_class)

        providers = TranscriptionProviderFactory.get_available_providers()

        assert "mock1" in providers
        assert "mock2" in providers
        assert len(providers) == 2

    def test_get_available_providers_empty(self):
        """Test getting providers when none are registered."""
        TranscriptionProviderFactory._providers.clear()

        providers = TranscriptionProviderFactory.get_available_providers()

        assert providers == []


class TestTranscriptionProviderFactoryConfiguredProviders:
    """Test configured provider detection."""

    def test_get_configured_providers_none(self):
        """Test getting configured providers when none are configured."""
        with patch("src.providers.factory.get_config") as mock_get_config:
            mock_config = Mock()
            mock_config.DEEPGRAM_API_KEY = None
            mock_config.ELEVENLABS_API_KEY = None
            mock_get_config.return_value = mock_config
            configured = TranscriptionProviderFactory.get_configured_providers()
            assert configured == []

    def test_get_configured_providers_deepgram_only(self, monkeypatch):
        """Test getting configured providers with only Deepgram configured."""
        with patch("src.providers.factory.get_config") as mock_get_config:
            mock_config = Mock()
            mock_config.DEEPGRAM_API_KEY = "test_deepgram_key"
            mock_config.ELEVENLABS_API_KEY = None
            mock_get_config.return_value = mock_config

            configured = TranscriptionProviderFactory.get_configured_providers()

            assert "deepgram" in configured
            assert "elevenlabs" not in configured

    def test_get_configured_providers_elevenlabs_only(self, monkeypatch):
        """Test getting configured providers with only ElevenLabs configured."""
        with patch("src.providers.factory.get_config") as mock_get_config:
            mock_config = Mock()
            mock_config.DEEPGRAM_API_KEY = None
            mock_config.ELEVENLABS_API_KEY = "test_elevenlabs_key"
            mock_get_config.return_value = mock_config

            configured = TranscriptionProviderFactory.get_configured_providers()

            assert "elevenlabs" in configured
            assert "deepgram" not in configured

    def test_get_configured_providers_both(self, monkeypatch):
        """Test getting configured providers with both configured."""
        with patch("src.providers.factory.get_config") as mock_get_config:
            mock_config = Mock()
            mock_config.DEEPGRAM_API_KEY = "test_deepgram_key"
            mock_config.ELEVENLABS_API_KEY = "test_elevenlabs_key"
            mock_get_config.return_value = mock_config

            configured = TranscriptionProviderFactory.get_configured_providers()

            assert "deepgram" in configured
            assert "elevenlabs" in configured
            assert len(configured) == 2


class TestTranscriptionProviderFactoryCreateProvider:
    """Test provider creation functionality."""

    def test_create_provider_success(self, mock_provider_class):
        """Test successfully creating a provider."""
        TranscriptionProviderFactory._providers.clear()
        TranscriptionProviderFactory.register_provider("mock", mock_provider_class)

        provider = TranscriptionProviderFactory.create_provider("mock", api_key="test_key")

        assert isinstance(provider, mock_provider_class)
        assert provider.api_key == "test_key"

    def test_create_provider_unknown(self):
        """Test creating unknown provider raises ValueError."""
        TranscriptionProviderFactory._providers.clear()

        with pytest.raises(ValueError, match="Unknown provider 'unknown'"):
            TranscriptionProviderFactory.create_provider("unknown")

    def test_create_provider_invalid_config(self, mock_provider_class):
        """Test creating provider with invalid configuration."""
        TranscriptionProviderFactory._providers.clear()

        # Create a mock provider class that fails validation
        class InvalidMockProvider(mock_provider_class):
            def validate_configuration(self):
                return False

        TranscriptionProviderFactory.register_provider("invalid", InvalidMockProvider)

        with pytest.raises(ValueError, match="Provider 'invalid' is not properly configured"):
            TranscriptionProviderFactory.create_provider("invalid")

    def test_create_provider_initialization_error(self, mock_provider_class):
        """Test creating provider when initialization fails."""
        TranscriptionProviderFactory._providers.clear()

        # Create a mock provider class that raises exception during init
        class FailingMockProvider(mock_provider_class):
            def __init__(self, api_key=None):
                raise Exception("Initialization failed")

        TranscriptionProviderFactory.register_provider("failing", FailingMockProvider)

        with pytest.raises(Exception, match="Initialization failed"):
            TranscriptionProviderFactory.create_provider("failing")


class TestTranscriptionProviderFactoryAutoSelection:
    """Test automatic provider selection."""

    def test_auto_select_provider_no_configured(self):
        """Test auto-selection when no providers are configured."""
        with patch("src.providers.factory.get_config") as mock_get_config:
            mock_config = Mock()
            mock_config.DEEPGRAM_API_KEY = None
            mock_config.ELEVENLABS_API_KEY = None
            mock_get_config.return_value = mock_config
            with pytest.raises(ValueError, match="No transcription providers are configured"):
                TranscriptionProviderFactory.auto_select_provider()

    def test_auto_select_provider_single_configured(self, monkeypatch):
        """Test auto-selection with single configured provider."""
        with patch("src.providers.factory.get_config") as mock_get_config:
            mock_config = Mock()
            mock_config.DEEPGRAM_API_KEY = "test_key"
            mock_config.ELEVENLABS_API_KEY = None
            mock_get_config.return_value = mock_config

            selected = TranscriptionProviderFactory.auto_select_provider()

            assert selected == "deepgram"

    def test_auto_select_provider_file_size_constraint(self, monkeypatch, large_audio_file):
        """Test auto-selection considers file size constraints."""
        with patch("src.providers.factory.get_config") as mock_get_config:
            mock_config = Mock()
            mock_config.DEEPGRAM_API_KEY = "test_deepgram_key"
            mock_config.ELEVENLABS_API_KEY = "test_elevenlabs_key"
            mock_get_config.return_value = mock_config

            # Large file should force Deepgram selection
            selected = TranscriptionProviderFactory.auto_select_provider(
                audio_file_path=large_audio_file
            )

            assert selected == "deepgram"

    def test_auto_select_provider_file_size_no_deepgram(self, monkeypatch, large_audio_file):
        """Test auto-selection with large file but no Deepgram configured."""
        with patch("src.providers.factory.get_config") as mock_get_config:
            mock_config = Mock()
            mock_config.DEEPGRAM_API_KEY = None
            mock_config.ELEVENLABS_API_KEY = "test_elevenlabs_key"
            mock_get_config.return_value = mock_config

            # This should use auto_select_provider on the class, not instance
            with pytest.raises(ValueError, match="File size .* exceeds limits"):
                TranscriptionProviderFactory.auto_select_provider(audio_file_path=large_audio_file)

    def test_auto_select_provider_small_file_both_configured(self, monkeypatch, temp_audio_file):
        """Test auto-selection with small file and both providers configured."""
        with patch("src.providers.factory.get_config") as mock_get_config:
            mock_config = Mock()
            mock_config.DEEPGRAM_API_KEY = "test_deepgram_key"
            mock_config.ELEVENLABS_API_KEY = "test_elevenlabs_key"
            mock_get_config.return_value = mock_config

            selected = TranscriptionProviderFactory.auto_select_provider(
                audio_file_path=temp_audio_file
            )

            # Should prefer Deepgram by default priority
            assert selected == "deepgram"

    def test_auto_select_provider_feature_requirements(self, monkeypatch, mock_provider_class):
        """Test auto-selection based on feature requirements."""
        with patch("src.providers.factory.get_config") as mock_get_config:
            mock_config = Mock()
            mock_config.DEEPGRAM_API_KEY = "test_deepgram_key"
            mock_config.ELEVENLABS_API_KEY = "test_elevenlabs_key"
            mock_get_config.return_value = mock_config

            # Mock provider creation for feature checking
            with patch.object(TranscriptionProviderFactory, "create_provider") as mock_create:
                # Mock Deepgram provider with more features
                deepgram_mock = Mock()
                deepgram_mock.get_supported_features.return_value = [
                    "basic_transcription",
                    "speaker_diarization",
                    "topic_detection",
                ]

                # Mock ElevenLabs provider with fewer features
                elevenlabs_mock = Mock()
                elevenlabs_mock.get_supported_features.return_value = [
                    "basic_transcription",
                    "timestamps",
                ]

                def mock_create_side_effect(provider_name):
                    if provider_name == "deepgram":
                        return deepgram_mock
                    elif provider_name == "elevenlabs":
                        return elevenlabs_mock
                    raise ValueError(f"Unknown provider {provider_name}")

                mock_create.side_effect = mock_create_side_effect

                # Request features that Deepgram has but ElevenLabs doesn't
                selected = TranscriptionProviderFactory.auto_select_provider(
                    preferred_features=["speaker_diarization", "topic_detection"]
                )

                assert selected == "deepgram"

    def test_auto_select_provider_only_elevenlabs_configured(self, monkeypatch):
        """Test auto-selection with only ElevenLabs configured."""
        with patch("src.providers.factory.get_config") as mock_get_config:
            mock_config = Mock()
            mock_config.DEEPGRAM_API_KEY = None
            mock_config.ELEVENLABS_API_KEY = "test_elevenlabs_key"
            mock_get_config.return_value = mock_config

            selected = TranscriptionProviderFactory.auto_select_provider()

            assert selected == "elevenlabs"


class TestTranscriptionProviderFactoryFileValidation:
    """Test file validation functionality."""

    def test_validate_provider_for_file_nonexistent(self):
        """Test validation with non-existent file."""
        non_existent = Path("/non/existent/file.mp3")

        result = TranscriptionProviderFactory.validate_provider_for_file("deepgram", non_existent)

        assert result is False

    def test_validate_provider_for_file_deepgram_small(self, temp_audio_file):
        """Test Deepgram validation with small file."""
        result = TranscriptionProviderFactory.validate_provider_for_file(
            "deepgram", temp_audio_file
        )

        assert result is True

    def test_validate_provider_for_file_deepgram_large(self, large_audio_file):
        """Test Deepgram validation with large file."""
        result = TranscriptionProviderFactory.validate_provider_for_file(
            "deepgram", large_audio_file
        )

        assert result is True  # Deepgram supports larger files

    def test_validate_provider_for_file_elevenlabs_small(self, temp_audio_file):
        """Test ElevenLabs validation with small file."""
        result = TranscriptionProviderFactory.validate_provider_for_file(
            "elevenlabs", temp_audio_file
        )

        assert result is True

    def test_validate_provider_for_file_elevenlabs_large(self, large_audio_file):
        """Test ElevenLabs validation with large file."""
        result = TranscriptionProviderFactory.validate_provider_for_file(
            "elevenlabs", large_audio_file
        )

        assert result is False  # ElevenLabs has 50MB limit

    def test_validate_provider_for_file_unknown_provider(self, temp_audio_file):
        """Test validation with unknown provider."""
        result = TranscriptionProviderFactory.validate_provider_for_file("unknown", temp_audio_file)

        assert result is True  # Unknown providers don't have specific constraints


class TestTranscriptionProviderFactoryIntegration:
    """Integration tests for TranscriptionProviderFactory."""

    def test_factory_initialization_registers_providers(self):
        """Test that factory initialization registers default providers."""
        # Reset the factory and re-initialize
        TranscriptionProviderFactory._providers.clear()

        # Re-run the initialization
        from src.providers.factory import _initialize_factory

        _initialize_factory()

        available = TranscriptionProviderFactory.get_available_providers()

        # Should have at least one provider (depending on imports)
        assert len(available) > 0

    @patch("src.providers.factory.logger")
    def test_factory_handles_import_errors_gracefully(self, mock_logger):
        """Test that factory handles import errors gracefully."""
        # Clear providers
        TranscriptionProviderFactory._providers.clear()

        # Simply test that ImportError in provider initialization is handled
        with patch("src.providers.deepgram.DeepgramTranscriber", side_effect=ImportError):
            with patch("src.providers.elevenlabs.ElevenLabsTranscriber", side_effect=ImportError):
                # Re-run initialization
                from src.providers.factory import _initialize_factory

                _initialize_factory()

        # Should complete without crashing (ImportErrors are caught)
        assert True  # Test passes if no exception was raised

    def test_full_workflow_with_factory(self, monkeypatch, temp_audio_file, mock_provider_class):
        """Test complete workflow using factory."""
        # Register mock provider for testing
        TranscriptionProviderFactory.register_provider("mock", mock_provider_class)

        # Test provider creation
        provider = TranscriptionProviderFactory.create_provider("mock", api_key="workflow_key")

        assert isinstance(provider, mock_provider_class)
        assert provider.validate_configuration() is True
        assert provider.get_provider_name() == "MockProvider"

        # Test file validation
        assert (
            TranscriptionProviderFactory.validate_provider_for_file("mock", temp_audio_file) is True
        )
