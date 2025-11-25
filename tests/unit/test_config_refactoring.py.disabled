"""Comprehensive tests for refactored configuration system.

This test module validates the new modular configuration architecture that replaces
the monolithic Config class. It ensures:

1. Backward compatibility - Legacy Config class interface remains functional
2. Core configuration modules - GlobalConfig, SecurityConfig, PerformanceConfig, UIConfig
3. Provider-specific configs - Deepgram, Whisper, ElevenLabs, Parakeet
4. Configuration validation - Multi-level validation system with auto-fix capabilities
5. Advanced features - Overlays, rate limiting, resource tracking, sanitization

The tests cover both functional correctness and integration between configuration
components, ensuring the refactored system maintains all original capabilities while
providing enhanced modularity and testability.
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from src.config import (
    Config,
    ConfigPriority,
    GlobalConfig,
    PerformanceConfig,
    UIConfig,
    ValidationLevel,
    create_config_validator,
    get_global_config,
    get_performance_config,
    get_security_config,
    get_ui_config,
)
from src.config.providers import DeepgramConfig, ElevenLabsConfig, ParakeetConfig, WhisperConfig


class TestBackwardCompatibility:
    """Test backward compatibility with existing Config class."""

    def test_config_class_exists(self):
        """Test that Config class still exists for backward compatibility.

        Ensures existing code using Config() continues to work after refactoring.
        The Config class now acts as a facade over the modular configuration system.
        """
        config = Config()
        assert config is not None

    def test_api_key_properties(self):
        """Test API key property access through backward-compatible interface.

        Verifies that legacy code can still access API keys via Config properties.
        API keys are mocked with provider-specific formats:
        - Deepgram: 40+ character alphanumeric string
        - ElevenLabs: 32+ character alphanumeric string
        - Gemini: Starts with "AIza" prefix, 39+ characters total
        """
        with patch.dict(
            os.environ,
            {
                # Mock API keys matching provider-specific format requirements
                "DEEPGRAM_API_KEY": "test_deepgram_key_1234567890abcdef1234567890abcdef12345678",
                "ELEVENLABS_API_KEY": "test_elevenlabs_key_1234567890ab",
                "GEMINI_API_KEY": "AIzaTestKey123456789012345678901234567",
            },
        ):
            config = Config()

            # Verify API keys are accessible without validation errors
            assert config.DEEPGRAM_API_KEY is not None
            assert config.ELEVENLABS_API_KEY is not None
            assert config.GEMINI_API_KEY is not None

    def test_provider_settings(self):
        """Test provider configuration properties maintain default values.

        Ensures backward compatibility for provider settings that existing code
        may depend on. Validates that sensible defaults exist even without
        explicit configuration.
        """
        config = Config()

        # Verify default provider configuration
        assert config.DEFAULT_TRANSCRIPTION_PROVIDER == "deepgram"
        assert "deepgram" in config.AVAILABLE_PROVIDERS
        assert config.DEFAULT_LANGUAGE == "en"
        assert config.MAX_FILE_SIZE > 0  # Must have a positive file size limit

    def test_performance_settings(self):
        """Test performance configuration properties for API resilience.

        Validates retry and circuit breaker settings that ensure reliable API
        communication. These settings are critical for handling transient failures
        and preventing cascading failures in production.
        """
        config = Config()

        # Retry configuration must allow at least one retry attempt
        assert config.MAX_API_RETRIES >= 1
        assert config.API_RETRY_DELAY > 0
        # Max delay must be >= initial delay for exponential backoff to work
        assert config.MAX_RETRY_DELAY >= config.API_RETRY_DELAY
        # Circuit breaker threshold must be positive to trigger after failures
        assert config.CIRCUIT_BREAKER_FAILURE_THRESHOLD > 0

    def test_class_methods(self):
        """Test backward compatible class methods for provider and file validation.

        Tests static/class methods that don't require Config instantiation.
        These methods are commonly used for pre-flight checks in client code.
        """
        # Test is_configured - validates provider setup
        with patch.dict(os.environ, {"DEEPGRAM_API_KEY": "test_key"}):
            # Invalid key format (too short) should return False
            assert Config.is_configured("deepgram") is False

        # Test validate_file_extension - ensures supported audio formats
        assert Config.validate_file_extension(Path("test.mp3")) is True  # Supported audio format
        assert Config.validate_file_extension(Path("test.exe")) is False  # Unsupported format

    def test_get_provider_config(self):
        """Test getting provider-specific configuration dictionary.

        Validates that provider configs contain all required operational parameters.
        This is used by provider clients to initialize with correct settings.
        Uses minimum valid API key length (40 chars) for Deepgram.
        """
        with patch.dict(os.environ, {"DEEPGRAM_API_KEY": "a" * 40}):
            config = Config.get_provider_config("deepgram")

            # Verify all essential provider settings are present
            assert "max_retries" in config
            assert "timeout" in config
            assert "max_file_size" in config


class TestGlobalConfig:
    """Test global configuration module."""

    def test_singleton_pattern(self):
        """Test singleton implementation ensures single configuration instance.

        GlobalConfig uses singleton pattern to maintain consistent configuration
        state across the application. Multiple calls to get_global_config() must
        return the same instance to prevent configuration drift.
        """
        config1 = get_global_config()
        config2 = get_global_config()
        assert config1 is config2  # Must be the exact same object

    def test_environment_loading(self):
        """Test environment variable loading."""
        with patch.dict(
            os.environ, {"APP_NAME": "test_app", "MAX_FILE_SIZE": "50000000", "LOG_LEVEL": "DEBUG"}
        ):
            config = GlobalConfig()
            assert config.app_name == "test_app"
            assert config.max_file_size == 50000000
            assert config.log_level == "DEBUG"

    def test_directory_creation(self):
        """Test that required directories are created."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(
                os.environ, {"DATA_DIR": f"{tmpdir}/data", "CACHE_DIR": f"{tmpdir}/cache"}
            ):
                GlobalConfig()
                assert Path(f"{tmpdir}/data").exists()
                assert Path(f"{tmpdir}/cache").exists()

    def test_config_overlay(self):
        """Test configuration overlay system with priority resolution.

        The overlay system allows configuration from multiple sources (defaults,
        files, CLI args) with automatic priority-based resolution. Higher priority
        sources override lower ones: CLI > FILE > DEFAULTS.
        """
        config = get_global_config()

        # Set overlay at different priorities
        config.set_overlay(ConfigPriority.DEFAULTS, {"test_key": "default"})
        config.set_overlay(ConfigPriority.FILE, {"test_key": "file"})
        config.set_overlay(ConfigPriority.CLI, {"test_key": "cli"})

        # CLI priority should override all others
        assert config.get_value("test_key") == "cli"

    def test_validation(self):
        """Test configuration validation."""
        config = get_global_config()

        # Should validate successfully with default values
        assert config.validate() is True

    def test_parse_helpers(self):
        """Test parsing helper methods."""
        config = get_global_config()

        assert config.parse_bool("true") is True
        assert config.parse_bool("false") is False
        assert config.parse_bool("1") is True
        assert config.parse_bool("0") is False

        assert config.parse_list("a,b,c") == ["a", "b", "c"]
        assert config.parse_list("") == []


class TestSecurityConfig:
    """Test security configuration module."""

    def test_api_key_validation(self):
        """Test API key format validation for different providers.

        Each provider has specific API key format requirements for security:
        - Deepgram: Minimum 40 characters
        - ElevenLabs: Minimum 32 characters
        - Gemini: Must start with "AIza", minimum 39 characters total

        Validation prevents runtime errors from malformed keys and provides
        early feedback during configuration.
        """
        config = get_security_config()

        # Valid formats - meet minimum length and format requirements
        assert config.validate_api_key("deepgram", "a" * 40) is True
        assert config.validate_api_key("elevenlabs", "b" * 32) is True
        assert config.validate_api_key("gemini", "AIza" + "x" * 35) is True

        # Invalid formats - too short or wrong format
        assert config.validate_api_key("deepgram", "short") is False
        assert config.validate_api_key("elevenlabs", "wrong_length") is False

    def test_rate_limiting(self):
        """Test rate limiting functionality for API abuse prevention.

        Rate limiting protects against API abuse by tracking requests per identifier
        (user, IP, API key) within a time window. Once the limit is reached, further
        requests are blocked until the window resets.

        This test validates: allowing requests within limit, blocking after limit,
        and proper tracking per identifier.
        """
        config = get_security_config()
        config.enable_rate_limiting = True
        config.rate_limit_max_requests = 5  # Allow 5 requests
        config.rate_limit_window = 1  # Within 1 second window

        identifier = "test_user"

        # Should allow first 5 requests within the limit
        for _ in range(5):
            assert config.check_rate_limit(identifier) is True

        # 6th request should be blocked (check without incrementing counter)
        assert config.check_rate_limit(identifier, increment=False) is False

    def test_path_sanitization(self):
        """Test path sanitization prevents directory traversal attacks.

        Path sanitization is critical for preventing directory traversal and
        unauthorized file access. It validates and resolves paths while blocking
        dangerous patterns like "../" (parent directory access) and sensitive
        system directories.
        """
        config = get_security_config()
        config.enable_input_sanitization = True

        # Valid paths should be resolved to absolute canonical form
        valid_path = Path("/tmp/test.txt")
        assert config.sanitize_path(valid_path) == valid_path.resolve()

        # Should reject dangerous patterns that could access sensitive files
        config.blocked_path_patterns = ["../", "/etc/"]

        # Attempt to access /etc/passwd via traversal should raise ValueError
        with pytest.raises(ValueError):
            config.sanitize_path(Path("../etc/passwd"))

    def test_sensitive_data_handling(self):
        """Test sensitive data sanitization for logs and storage.

        Prevents accidental exposure of sensitive data in logs, error messages,
        and debug output. Uses two strategies:
        1. Sanitization - replaces sensitive parts with asterisks for logging
        2. Hashing - creates one-way hash for storage/comparison without exposing original

        Critical for compliance with security best practices and regulations.
        """
        config = get_security_config()

        # Test sanitization for logging - obscures sensitive content
        api_key = "secret_api_key_12345678"
        sanitized = config.sanitize_for_logging(api_key)
        assert "secret" not in sanitized  # Original value hidden
        assert "****" in sanitized  # Replaced with asterisks

        # Test hashing for secure storage/comparison
        data = "sensitive_data"
        hash1 = config.hash_sensitive_data(data)
        hash2 = config.hash_sensitive_data(data)
        assert hash1 == hash2  # Deterministic hashing for same input
        assert data not in hash1  # Original data not recoverable from hash


class TestPerformanceConfig:
    """Test performance configuration module."""

    def test_performance_profiles(self):
        """Test predefined performance profiles."""
        with patch.dict(os.environ, {"PERFORMANCE_PROFILE": "high"}):
            config = PerformanceConfig()
            assert config.profile.name == "high"
            assert config.profile.max_workers > 4

    def test_retry_configuration(self):
        """Test retry settings."""
        config = get_performance_config()
        retry_config = config.get_retry_config()

        assert "max_attempts" in retry_config
        assert "initial_delay" in retry_config
        assert "exponential_base" in retry_config
        assert retry_config["max_attempts"] > 0

    def test_circuit_breaker_config(self):
        """Test circuit breaker configuration."""
        config = get_performance_config()
        cb_config = config.get_circuit_breaker_config()

        assert cb_config["enabled"] is True
        assert cb_config["failure_threshold"] > 0
        assert cb_config["recovery_timeout"] > 0

    def test_resource_tracking(self):
        """Test resource usage tracking and throttling decisions.

        Resource tracking monitors CPU and memory usage to prevent system overload.
        When usage exceeds configured limits, the system throttles operations to
        maintain stability. This is critical for production systems under load.

        Tests both tracking accuracy and throttling decision logic.
        """
        config = get_performance_config()

        # Update resource usage metrics
        config.update_resource_usage("cpu", 0.5)  # 50% CPU usage
        config.update_resource_usage("memory", 1024)  # 1024 MB memory

        # Verify tracking stores values correctly
        usage = config.get_resource_usage()
        assert usage["cpu"] == 0.5
        assert usage["memory"] == 1024

        # Test throttling decision when usage exceeds limit
        config.cpu_limit = 0.4  # Set limit to 40%
        assert config.should_throttle() is True  # Should throttle at 50% usage

    def test_optimal_batch_size(self):
        """Test dynamic batch size calculation based on resource availability.

        Batch processing performance depends on available resources. This method
        dynamically adjusts batch size based on current CPU/memory usage to
        optimize throughput while preventing overload.

        Under normal conditions, uses configured batch size. When throttling,
        reduces batch size to ease resource pressure.
        """
        config = get_performance_config()
        config.batch_size = 10

        # Normal conditions - use full configured batch size
        assert config.get_optimal_batch_size() == 10

        # Throttled conditions - reduce batch size to prevent overload
        config.cpu_limit = 0.1  # Very low limit (10%)
        config.update_resource_usage("cpu", 0.2)  # Usage at 20% (exceeds limit)
        assert config.get_optimal_batch_size() < 10  # Must reduce batch size


class TestUIConfig:
    """Test UI configuration module."""

    def test_output_formats(self):
        """Test output format configuration."""
        with patch.dict(os.environ, {"OUTPUT_FORMAT": "json"}):
            config = UIConfig()
            assert config.output_format.value == "json"

    def test_color_detection(self):
        """Test color output detection for terminal compatibility.

        Respects the NO_COLOR environment variable standard (https://no-color.org)
        which allows users to disable colored output globally. This is important
        for accessibility, logging to files, and CI/CD environments.

        Also supports force_color override for debugging and development.
        """
        config = get_ui_config()

        # Test NO_COLOR standard - must disable colors when set
        with patch.dict(os.environ, {"NO_COLOR": "1"}):
            assert config.should_use_color() is False

        # Test force color override - explicitly enables colors
        config.force_color = True
        assert config.should_use_color() is True

    def test_progress_configuration(self):
        """Test progress bar configuration."""
        config = get_ui_config()
        progress_config = config.get_progress_config()

        assert "style" in progress_config
        assert "width" in progress_config
        assert "refresh_rate" in progress_config
        assert progress_config["width"] > 0

    def test_format_output(self):
        """Test output formatting."""
        config = get_ui_config()

        data = {"key": "value", "number": 42}

        # Test JSON formatting
        from src.config.ui import OutputFormat

        json_output = config.format_output(data, OutputFormat.JSON)
        assert '"key"' in json_output
        assert '"value"' in json_output


class TestProviderConfigs:
    """Test provider-specific configurations."""

    def test_deepgram_config(self):
        """Test Deepgram provider configuration and transcription options.

        Deepgram is a speech-to-text API provider. Configuration includes:
        - API key validation (minimum 40 characters)
        - Model selection (e.g., nova-2, enhanced, base)
        - Language specification for transcription

        The configuration generates transcription options used by the Deepgram client.
        """
        with patch.dict(
            os.environ,
            {"DEEPGRAM_API_KEY": "a" * 40, "DEEPGRAM_MODEL": "nova-2", "DEEPGRAM_LANGUAGE": "en"},
        ):
            config = DeepgramConfig()

            # Verify configuration loaded from environment
            assert config.model.value == "nova-2"
            assert config.language == "en"

            # Test transcription options passed to Deepgram API
            options = config.get_transcription_options()
            assert options["model"] == "nova-2"
            assert options["language"] == "en"

    def test_whisper_config(self):
        """Test Whisper (OpenAI) local transcription configuration.

        Whisper is OpenAI's open-source speech recognition model that runs locally.
        Configuration includes:
        - Model size (tiny, base, small, medium, large) - affects accuracy vs speed
        - Device selection (cpu, cuda, mps) - GPU acceleration when available
        - Memory estimation - helps determine if model fits in available RAM

        Local execution means no API costs but requires sufficient local resources.
        """
        with patch.dict(os.environ, {"WHISPER_MODEL": "base", "WHISPER_DEVICE": "cpu"}):
            config = WhisperConfig()

            # Verify model and device configuration
            assert config.model.value == "base"
            assert config.device.value == "cpu"

            # Test memory estimation for resource planning
            memory = config.estimate_memory_usage()
            assert memory > 0  # Must return positive memory requirement

    def test_elevenlabs_config(self):
        """Test ElevenLabs text-to-speech provider configuration.

        ElevenLabs provides high-quality AI voice synthesis. Configuration includes:
        - API key validation (minimum 32 characters)
        - Model selection (e.g., eleven_multilingual_v2 for multi-language support)
        - Voice settings (stability, similarity, style parameters)

        The configuration generates TTS options for voice synthesis API calls.
        """
        with patch.dict(
            os.environ,
            {"ELEVENLABS_API_KEY": "b" * 32, "ELEVENLABS_MODEL": "eleven_multilingual_v2"},
        ):
            config = ElevenLabsConfig()

            # Verify model configuration
            assert config.model.value == "eleven_multilingual_v2"

            # Test TTS options passed to ElevenLabs API
            options = config.get_tts_options()
            assert "model_id" in options
            assert "voice_settings" in options  # Voice quality parameters

    def test_parakeet_config(self):
        """Test Parakeet (NVIDIA NeMo) local transcription configuration.

        Parakeet is NVIDIA's neural speech recognition framework (NeMo).
        Configuration includes:
        - Model selection (e.g., conformer_ctc models with various sizes)
        - Batch size for efficient GPU utilization
        - Model-specific parameters for inference

        Like Whisper, runs locally but optimized for NVIDIA GPUs. Offers good
        accuracy with efficient batch processing capabilities.
        """
        with patch.dict(
            os.environ,
            {"PARAKEET_MODEL": "stt_en_conformer_ctc_large", "PARAKEET_BATCH_SIZE": "16"},
        ):
            config = ParakeetConfig()

            # Verify model and batch configuration
            assert config.model.value == "stt_en_conformer_ctc_large"
            assert config.batch_size == 16

            # Test model configuration for NeMo framework
            model_config = config.get_model_config()
            assert model_config["model_name"] == "stt_en_conformer_ctc_large"
            assert model_config["batch_size"] == 16


class TestConfigurationValidation:
    """Test configuration validation system."""

    def test_validator_creation(self):
        """Test validator creation with different levels."""
        validator_strict = create_config_validator(ValidationLevel.STRICT)
        validator_normal = create_config_validator(ValidationLevel.NORMAL)
        validator_lenient = create_config_validator(ValidationLevel.LENIENT)

        assert validator_strict.level == ValidationLevel.STRICT
        assert validator_normal.level == ValidationLevel.NORMAL
        assert validator_lenient.level == ValidationLevel.LENIENT

    def test_validation_rules(self):
        """Test validation rule application at different strictness levels.

        The validation system checks configuration values against defined rules:
        - Type checking (string, int, float, etc.)
        - Range validation (min/max values for ports, timeouts, etc.)
        - Format validation (API keys, file paths, URLs)

        Invalid configurations generate errors that help users fix issues quickly.
        """
        validator = create_config_validator(ValidationLevel.NORMAL)

        # Test with valid configuration
        config = {
            "api_key": "test_key_with_sufficient_length_12345",
            "timeout": 30,
            "port": 8080,
            "file_path": "/tmp/test.txt",
        }

        # Should pass all validation rules
        assert validator.validate(config) is True

        # Test with invalid values that violate constraints
        invalid_config = {
            "port": 70000,  # Out of valid port range (1-65535)
            "timeout": -1,  # Negative timeout is invalid
        }

        assert validator.validate(invalid_config) is False
        assert len(validator.errors) > 0  # Should report specific errors

    def test_auto_fix(self):
        """Test automatic value correction in non-strict validation modes.

        In NORMAL and LENIENT modes, the validator can automatically correct
        out-of-range values to sensible defaults rather than failing validation.
        This provides better user experience while maintaining system stability.

        Auto-fixes generate warnings so users are aware of the adjustments made.
        STRICT mode never auto-fixes - it fails validation instead.
        """
        validator = create_config_validator(ValidationLevel.NORMAL)

        config = {"timeout": 5000}  # Exceeds maximum allowed timeout

        # Validator should auto-fix the value in NORMAL mode
        validator.validate(config)

        # Should generate warning about the auto-correction
        assert len(validator.warnings) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
