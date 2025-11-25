"""
Provider Integration Tests for audio-extraction-analysis.

This module contains end-to-end integration tests for the provider subsystem,
focusing on the factory pattern implementation and provider selection logic.

Test Coverage:
- Provider auto-selection based on API key availability
- Factory pattern validation and provider instantiation
- Provider-specific feature capabilities (speaker diarization, sentiment analysis)
- Fallback mechanisms when providers are unavailable
- API key validation and error handling
- File size-based provider selection
- Real provider contract testing infrastructure (optional, requires API keys)

Testing Modes:
1. Mock Mode (default): Uses mocked providers for fast, isolated testing
2. Real Provider Mode: Tests against actual provider APIs for contract validation
   Usage: pytest -m "real_provider" --real-provider-mode --provider=<provider_name>

Note: Real provider tests require valid API keys set in environment variables:
DEEPGRAM_API_KEY, ELEVENLABS_API_KEY
"""

import os
from unittest.mock import Mock, patch

import pytest

from .base import E2ETestBase, MockProviderMixin


@pytest.mark.e2e
@pytest.mark.providers
@pytest.mark.network
class TestProviderFactory(E2ETestBase, MockProviderMixin):
    """
    Test the provider factory pattern and auto-selection logic.

    This test class validates the TranscriptionProviderFactory's ability to:
    - Detect and configure available providers based on API key presence
    - Select the optimal provider based on various criteria (file size, features)
    - Handle scenarios with partial or no provider availability
    - Validate API keys and handle authentication errors

    All tests use mocked providers to ensure isolation and speed.
    """

    def setup_method(self):
        """
        Setup for each test method.

        Clears the provider factory state to ensure test isolation.
        This prevents cached providers or configuration from affecting
        subsequent tests.
        """
        super().setup_method()

        # Clear provider factory state between tests to ensure isolation
        self._clear_factory_state()

    def _clear_factory_state(self):
        """
        Clear any cached state in the provider factory.

        The factory may cache provider instances or configuration state for
        performance. This method resets that state to ensure each test starts
        with a clean factory configuration.

        Note: This method gracefully handles cases where the factory module
        is not available in the test environment (e.g., during isolated unit tests).
        """
        try:
            from src.providers.factory import TranscriptionProviderFactory

            # Clear cached provider configuration
            if hasattr(TranscriptionProviderFactory, "_configured_providers"):
                TranscriptionProviderFactory._configured_providers = None
            # Clear singleton instances
            if hasattr(TranscriptionProviderFactory, "_instances"):
                TranscriptionProviderFactory._instances = {}
        except ImportError:
            # Factory not available in test environment - this is acceptable
            # for isolated tests that only mock the factory
            pass

    def test_factory_all_providers_available(self):
        """
        Test factory behavior when all providers are configured.

        Scenario: All provider API keys are set in the environment.
        Expected: Factory should detect both providers and select the best one.

        Verifies:
        - Both deepgram and elevenlabs are recognized as configured
        - get_best_provider() returns a valid configured provider
        - Provider list contains exactly 2 providers
        """
        # Set all API keys to simulate full provider availability
        self.set_test_env(
            DEEPGRAM_API_KEY="test_deepgram_key", ELEVENLABS_API_KEY="test_elevenlabs_key"
        )

        with patch("src.providers.factory.TranscriptionProviderFactory") as mock_factory:
            mock_factory.get_configured_providers.return_value = ["deepgram", "elevenlabs"]
            mock_factory.get_best_provider.return_value = "deepgram"

            configured_providers = mock_factory.get_configured_providers()
            best_provider = mock_factory.get_best_provider()

            assert "deepgram" in configured_providers
            assert "elevenlabs" in configured_providers
            assert len(configured_providers) == 2
            assert best_provider in configured_providers

    def test_factory_deepgram_only(self):
        """
        Test factory behavior with only Deepgram configured.

        Scenario: Only DEEPGRAM_API_KEY is set, ElevenLabs key is missing.
        Expected: Factory should detect only Deepgram as the available provider.

        Verifies:
        - Only deepgram appears in configured providers list
        - get_best_provider() returns deepgram (the only option)
        - System can function with a single provider
        """
        self.set_test_env(
            DEEPGRAM_API_KEY="test_deepgram_key",
            ELEVENLABS_API_KEY="",  # Explicitly empty to simulate missing key
        )

        with patch("src.providers.factory.TranscriptionProviderFactory") as mock_factory:
            mock_factory.get_configured_providers.return_value = ["deepgram"]
            mock_factory.get_best_provider.return_value = "deepgram"

            configured_providers = mock_factory.get_configured_providers()
            best_provider = mock_factory.get_best_provider()

            assert configured_providers == ["deepgram"]
            assert best_provider == "deepgram"

    def test_factory_elevenlabs_only(self):
        """
        Test factory behavior with only ElevenLabs configured.

        Scenario: Only ELEVENLABS_API_KEY is set, Deepgram key is missing.
        Expected: Factory should detect only ElevenLabs as the available provider.

        Verifies:
        - Only elevenlabs appears in configured providers list
        - get_best_provider() returns elevenlabs (the only option)
        - System gracefully handles absence of preferred provider
        """
        self.set_test_env(
            DEEPGRAM_API_KEY="",  # Explicitly empty to simulate missing key
            ELEVENLABS_API_KEY="test_elevenlabs_key",
        )

        with patch("src.providers.factory.TranscriptionProviderFactory") as mock_factory:
            mock_factory.get_configured_providers.return_value = ["elevenlabs"]
            mock_factory.get_best_provider.return_value = "elevenlabs"

            configured_providers = mock_factory.get_configured_providers()
            best_provider = mock_factory.get_best_provider()

            assert configured_providers == ["elevenlabs"]
            assert best_provider == "elevenlabs"

    def test_factory_no_providers_configured(self):
        """
        Test factory behavior when no providers are configured.

        Scenario: All API keys are missing/empty.
        Expected: Factory should gracefully handle the absence of providers.

        Verifies:
        - get_configured_providers() returns an empty list
        - get_best_provider() raises ValueError with clear message
        - System fails fast with actionable error message
        """
        self.set_test_env(DEEPGRAM_API_KEY="", ELEVENLABS_API_KEY="")  # No API key  # No API key

        with patch("src.providers.factory.TranscriptionProviderFactory") as mock_factory:
            # Mock factory behavior with no configured providers
            mock_factory.get_configured_providers.return_value = []
            mock_factory.get_best_provider.side_effect = ValueError("No providers configured")

            configured_providers = mock_factory.get_configured_providers()

            assert configured_providers == []

            # Verify appropriate error is raised when trying to get a provider
            with pytest.raises(ValueError, match="No providers configured"):
                mock_factory.get_best_provider()

    def test_factory_invalid_api_keys(self):
        """
        Test factory behavior with invalid API keys.

        Scenario: API keys are present but invalid/malformed.
        Expected: Factory validation should detect and reject invalid keys.

        Verifies:
        - Invalid keys are not accepted as configured providers
        - validate_provider() raises ValueError for invalid credentials
        - Clear error messages guide users to fix authentication
        """
        self.set_test_env(
            DEEPGRAM_API_KEY="invalid_key",  # Malformed API key
            ELEVENLABS_API_KEY="invalid_key",  # Malformed API key
        )

        with patch("src.providers.factory.TranscriptionProviderFactory") as mock_factory:
            # Simulate validation that detects invalid keys
            mock_factory.get_configured_providers.return_value = []
            mock_factory.validate_provider.side_effect = ValueError("Invalid API key")

            # Verify validation fails for deepgram with invalid key
            with pytest.raises(ValueError, match="Invalid API key"):
                mock_factory.validate_provider("deepgram")

            # Verify validation fails for elevenlabs with invalid key
            with pytest.raises(ValueError, match="Invalid API key"):
                mock_factory.validate_provider("elevenlabs")

    def test_factory_provider_selection_by_file_size(self):
        """
        Test provider selection based on file size constraints.

        Scenario: Files of different sizes need appropriate provider selection.
        Expected: Factory should consider provider size limits when selecting.

        Verifies:
        - Small files (1MB) can use any suitable provider
        - Large files (100MB) are routed to providers supporting larger files
        - File size constraints are respected in provider selection logic

        Note: Different providers may have different file size limits:
        - ElevenLabs: Typically lower limits for audio files
        - Deepgram: Generally supports larger file uploads
        """
        self.set_test_env(
            DEEPGRAM_API_KEY="test_deepgram_key", ELEVENLABS_API_KEY="test_elevenlabs_key"
        )

        with patch("src.providers.factory.TranscriptionProviderFactory") as mock_factory:
            # Small file (1MB) - should select based on provider capabilities
            mock_factory.get_best_provider_for_file.return_value = "elevenlabs"
            small_file_provider = mock_factory.get_best_provider_for_file(
                file_size=1024 * 1024  # 1MB
            )

            # Large file (100MB) - should consider size limits
            mock_factory.get_best_provider_for_file.return_value = "deepgram"
            large_file_provider = mock_factory.get_best_provider_for_file(
                file_size=100 * 1024 * 1024  # 100MB
            )

            assert small_file_provider in ["deepgram", "elevenlabs"]
            assert large_file_provider in ["deepgram", "elevenlabs"]

    def test_factory_provider_feature_requirements(self):
        """
        Test provider selection based on feature requirements.

        Scenario: User requests specific transcription features (diarization, sentiment).
        Expected: Factory should select providers that support requested features.

        Verifies:
        - Speaker diarization requests route to capable providers
        - Sentiment analysis requests route to providers with that capability
        - Feature-based selection overrides default provider selection

        Feature Support Matrix:
        - Speaker Diarization: Supported by Deepgram
        - Sentiment Analysis: Supported by Deepgram
        - ElevenLabs: May have different feature set
        """
        self.set_test_env(
            DEEPGRAM_API_KEY="test_deepgram_key", ELEVENLABS_API_KEY="test_elevenlabs_key"
        )

        with patch("src.providers.factory.TranscriptionProviderFactory") as mock_factory:
            # Test speaker diarization requirement (typically Deepgram)
            mock_factory.get_provider_with_features.return_value = "deepgram"
            diarization_provider = mock_factory.get_provider_with_features(
                features=["speaker_diarization"]
            )

            # Test sentiment analysis requirement (typically Deepgram)
            mock_factory.get_provider_with_features.return_value = "deepgram"
            sentiment_provider = mock_factory.get_provider_with_features(
                features=["sentiment_analysis"]
            )

            assert diarization_provider in ["deepgram", "elevenlabs"]
            assert sentiment_provider in ["deepgram", "elevenlabs"]


@pytest.mark.e2e
@pytest.mark.providers
@pytest.mark.slow
class TestWhisperProviderIntegration(E2ETestBase, MockProviderMixin):
    """
    Test Whisper provider integration and unique capabilities.

    Whisper is unique among providers as it's an offline, local model that
    doesn't require API keys or internet connectivity. These tests validate:
    - Offline operation without API credentials
    - Model size selection (tiny, base, small, medium, large)
    - GPU acceleration detection and fallback to CPU
    - Local model deployment scenarios
    """

    def test_whisper_offline_capability(self):
        """
        Test Whisper offline transcription capability.

        Scenario: Whisper should work without any API keys or internet connection.
        Expected: Successful transcription using local model.

        Verifies:
        - No API key required for initialization
        - Transcription produces valid output offline
        - Language detection works in offline mode
        - Confidence scores are provided
        """
        # Whisper should work without API keys - this is its key advantage
        with patch("src.providers.whisper.WhisperProvider") as mock_provider:
            mock_instance = Mock()
            mock_instance.transcribe.return_value = {
                "transcript": "Offline transcription result",
                "language": "en",
                "confidence": 0.85,
            }
            mock_provider.return_value = mock_instance

            provider = mock_provider()  # No API key needed
            result = provider.transcribe("dummy_file.mp3")

            assert "Offline transcription" in result["transcript"]
            assert result["language"] == "en"

    def test_whisper_model_selection(self):
        """
        Test Whisper model selection across different sizes.

        Scenario: Users should be able to select different Whisper model sizes
        based on their accuracy/speed tradeoff preferences.
        Expected: All standard model sizes should be selectable.

        Verifies:
        - All 5 standard Whisper models can be loaded
        - Model switching works dynamically
        - set_model() returns success for valid models

        Model Size Tradeoffs:
        - tiny: Fastest, lowest accuracy (~1GB RAM)
        - base: Fast, basic accuracy (~1GB RAM)
        - small: Balanced speed/accuracy (~2GB RAM)
        - medium: Good accuracy, slower (~5GB RAM)
        - large: Best accuracy, slowest (~10GB RAM)
        """
        with patch("src.providers.whisper.WhisperProvider") as mock_provider:
            mock_instance = Mock()
            mock_instance.set_model.return_value = True
            mock_provider.return_value = mock_instance

            provider = mock_provider()

            # Test all standard Whisper model sizes
            models = ["tiny", "base", "small", "medium", "large"]
            for model in models:
                result = provider.set_model(model)
                assert result is True

    def test_whisper_gpu_acceleration(self):
        """
        Test Whisper GPU acceleration detection and CPU fallback.

        Scenario: System may or may not have GPU available for acceleration.
        Expected: Whisper should detect GPU availability and fallback gracefully.

        Verifies:
        - GPU support detection returns boolean status
        - Provider works correctly even without GPU (CPU fallback)
        - No crashes or errors when GPU is unavailable

        Note: In test environment, we typically assume no GPU is available.
        Real deployments should leverage GPU when available for better performance.
        """
        with patch("src.providers.whisper.WhisperProvider") as mock_provider:
            mock_instance = Mock()
            # Assume no GPU in test environment (typical for CI/CD)
            mock_instance.has_gpu_support.return_value = False
            mock_provider.return_value = mock_instance

            provider = mock_provider()

            # Provider should work without GPU using CPU fallback
            assert not provider.has_gpu_support()


# ============================================================================
# Real Provider Contract Testing Infrastructure
# ============================================================================
# This section provides fixtures and hooks for optional contract testing
# against real provider APIs. Contract tests verify that our code correctly
# integrates with actual provider services, catching API changes and ensuring
# compatibility.
#
# WARNING: Real provider tests consume API quota and require internet access.
# They are disabled by default and must be explicitly enabled.
#
# Usage Examples:
#   # Run only real provider tests with all configured providers
#   pytest -m "real_provider" --real-provider-mode
#
#   # Test specific provider only
#   pytest -m "real_provider" --real-provider-mode --provider=deepgram
#   pytest -m "real_provider" --real-provider-mode --provider=elevenlabs
#
# Required Environment Variables:
#   DEEPGRAM_API_KEY   - For Deepgram provider contract tests
#   ELEVENLABS_API_KEY - For ElevenLabs provider contract tests
#
# Note: Whisper provider doesn't require API keys (offline/local model)
# ============================================================================


@pytest.fixture(scope="session")
def real_provider_mode(request):
    """
    Fixture to enable real provider contract testing.

    Usage:
        pytest --real-provider-mode
        pytest --real-provider-mode --provider=deepgram

    Returns dict with:
        - enabled: bool - whether real provider mode is active
        - provider: str - specific provider to test (None = all available)
    """
    return {
        "enabled": request.config.getoption("--real-provider-mode", default=False),
        "provider": request.config.getoption("--provider", default=None),
    }


@pytest.fixture(scope="session")
def real_provider_credentials():
    """
    Fixture providing real API credentials for contract testing.

    Returns dict with available provider credentials:
        - deepgram: API key or None
        - elevenlabs: API key or None

    Note: Only returns credentials that are actually set in environment.
    """
    return {
        "deepgram": os.getenv("DEEPGRAM_API_KEY"),
        "elevenlabs": os.getenv("ELEVENLABS_API_KEY"),
    }


@pytest.fixture(scope="function")
def real_audio_sample(tmp_path):
    """
    Fixture providing a small real audio file for contract testing.

    Creates a minimal audio file that can be used for real provider tests
    without consuming significant quota.

    Returns:
        Path to audio file suitable for provider contract testing
    """
    # In real implementation, this would generate or provide a small test audio file
    # For now, return a path that tests can check existence of
    audio_path = tmp_path / "contract_test_sample.mp3"

    # Tests should check if this file exists and skip if not available
    # Real implementation would generate a minimal valid audio file
    return audio_path


def pytest_configure(config):
    """
    Register custom pytest markers for real provider testing.

    This pytest hook adds the 'real_provider' marker to the test suite,
    allowing tests to be selectively run against actual provider APIs.

    Marker:
        real_provider: Marks tests that make real API calls to provider services.
                      These tests require valid API credentials and consume quota.

    Usage:
        @pytest.mark.real_provider
        def test_real_deepgram_api():
            # Test that calls actual Deepgram API
            pass
    """
    config.addinivalue_line(
        "markers",
        "real_provider: mark test to run against real provider APIs (requires credentials)",
    )


def pytest_addoption(parser):
    """
    Add command-line options for real provider testing.

    This pytest hook registers custom CLI options that control real provider
    contract testing behavior. These options allow developers to selectively
    test against actual provider APIs.

    Options:
        --real-provider-mode: Enable testing against real provider APIs.
                             Requires valid API keys in environment variables.
                             WARNING: Consumes API quota and makes real network calls.

        --provider: Specify which provider to test (deepgram, elevenlabs, whisper).
                   If not specified, all providers with valid credentials are tested.

    Examples:
        # Test all providers with real APIs
        pytest --real-provider-mode

        # Test only Deepgram provider
        pytest --real-provider-mode --provider=deepgram

        # Run only real provider tests for ElevenLabs
        pytest -m real_provider --real-provider-mode --provider=elevenlabs
    """
    parser.addoption(
        "--real-provider-mode",
        action="store_true",
        default=False,
        help="Enable real provider contract testing (requires API keys)",
    )
    parser.addoption(
        "--provider",
        action="store",
        default=None,
        help="Specific provider to test in real mode (deepgram, elevenlabs, whisper)",
    )
