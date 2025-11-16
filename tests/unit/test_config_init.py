"""Comprehensive test suite for src/config/__init__.py module.

This module tests the configuration system used throughout the audio extraction
and analysis application. The Config class provides centralized configuration
management with environment variable support, type parsing, and validation.

Test Coverage:
    - Helper functions (_parse_bool, _parse_list, _getenv)
    - Config initialization with defaults and environment variables
    - Type conversion (boolean, integer, float, list, Path)
    - Directory creation in __post_init__
    - Backward compatibility properties for legacy code
    - Class methods for provider validation and API key retrieval
    - Singleton pattern via get_config()
    - Edge cases and special scenarios

The tests use pytest with mocked environment variables to ensure isolation
and repeatability across different execution environments.
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from src.config import Config, _getenv, _parse_bool, _parse_list, get_config


class TestHelperFunctions:
    """Test helper functions for configuration parsing.

    These utility functions handle conversion of environment variable strings
    into typed Python values. They support multiple input formats and provide
    sensible defaults for edge cases.

    Functions tested:
        - _parse_bool: Converts various truthy/falsy strings to boolean
        - _parse_list: Parses comma-separated strings into lists
        - _getenv: Wrapper around os.getenv with default value support
    """

    # Tests for _parse_bool
    # =====================
    # _parse_bool handles environment variable conversion to boolean.
    # It supports multiple formats: native bool, strings ('true', 'yes', 'on', 'enabled'),
    # numeric values (1/0), and provides safe fallback to False for invalid inputs.

    def test_parse_bool_with_boolean_true(self):
        """Test _parse_bool passes through native boolean True unchanged."""
        assert _parse_bool(True) is True

    def test_parse_bool_with_boolean_false(self):
        """Test _parse_bool passes through native boolean False unchanged."""
        assert _parse_bool(False) is False

    def test_parse_bool_with_none(self):
        """Test _parse_bool treats None as falsy and returns False.

        This handles unset optional environment variables gracefully.
        """
        assert _parse_bool(None) is False

    def test_parse_bool_with_string_true(self):
        """Test _parse_bool recognizes 'true' in any case as True.

        Supports common boolean string representations from environment variables.
        """
        assert _parse_bool("true") is True
        assert _parse_bool("True") is True
        assert _parse_bool("TRUE") is True

    def test_parse_bool_with_string_false(self):
        """Test _parse_bool recognizes 'false' in any case as False.

        Explicitly handles string 'false' (not just invalid strings).
        """
        assert _parse_bool("false") is False
        assert _parse_bool("False") is False
        assert _parse_bool("FALSE") is False

    def test_parse_bool_with_string_numeric(self):
        """Test _parse_bool interprets numeric strings '1' and '0'.

        Common pattern in shell scripts and environment configurations.
        """
        assert _parse_bool("1") is True
        assert _parse_bool("0") is False

    def test_parse_bool_with_string_yes(self):
        """Test _parse_bool recognizes 'yes' as truthy in any case.

        Alternative to 'true', commonly used in configuration files.
        """
        assert _parse_bool("yes") is True
        assert _parse_bool("Yes") is True
        assert _parse_bool("YES") is True

    def test_parse_bool_with_string_on(self):
        """Test _parse_bool recognizes 'on' as truthy in any case.

        Common in toggle-style configurations (ON/OFF).
        """
        assert _parse_bool("on") is True
        assert _parse_bool("On") is True
        assert _parse_bool("ON") is True

    def test_parse_bool_with_string_enabled(self):
        """Test _parse_bool recognizes 'enabled' as truthy (case-insensitive).

        Semantic alternative to true/yes/on for feature flags.
        """
        assert _parse_bool("enabled") is True
        assert _parse_bool("Enabled") is True

    def test_parse_bool_with_invalid_string(self):
        """Test _parse_bool safely returns False for unrecognized strings.

        Includes explicit testing of common falsy strings like 'no', 'off', 'disabled'
        which are treated as invalid (only recognized truthy patterns return True).
        """
        assert _parse_bool("invalid") is False
        assert _parse_bool("no") is False
        assert _parse_bool("off") is False
        assert _parse_bool("disabled") is False

    def test_parse_bool_with_empty_string(self):
        """Test _parse_bool treats empty string as falsy.

        Handles edge case of empty environment variable (VAR="").
        """
        assert _parse_bool("") is False

    def test_parse_bool_with_numeric_values(self):
        """Test _parse_bool with native numeric types.

        Follows Python truthiness: 0 is False, any non-zero is True.
        """
        assert _parse_bool(1) is True
        assert _parse_bool(0) is False
        assert _parse_bool(42) is True  # Any non-zero number is truthy

    # Tests for _parse_list
    # ======================
    # _parse_list converts comma-separated strings into Python lists.
    # Supports custom delimiters, whitespace trimming, and handles various edge cases.

    def test_parse_list_with_list(self):
        """Test _parse_list passes through existing lists unchanged.

        If input is already a list, no parsing is needed.
        """
        input_list = ["a", "b", "c"]
        assert _parse_list(input_list) == input_list

    def test_parse_list_with_string(self):
        """Test _parse_list splits comma-separated string into list.

        Most common use case: parsing environment variable like "mp3,wav,flac".
        """
        assert _parse_list("a,b,c") == ["a", "b", "c"]

    def test_parse_list_with_string_spaces(self):
        """Test _parse_list strips leading/trailing whitespace from each item.

        Handles formatted strings like "item1, item2, item3" with spaces for readability.
        """
        assert _parse_list("a, b , c") == ["a", "b", "c"]
        assert _parse_list(" a , b , c ") == ["a", "b", "c"]

    def test_parse_list_with_none(self):
        """Test _parse_list converts None to empty list.

        Provides safe default for unset optional environment variables.
        """
        assert _parse_list(None) == []

    def test_parse_list_with_empty_string(self):
        """Test _parse_list converts empty string to empty list.

        Handles edge case of explicitly empty environment variable (VAR="").
        """
        assert _parse_list("") == []

    def test_parse_list_with_custom_delimiter(self):
        """Test _parse_list supports alternative delimiters beyond comma.

        Useful for pipe-delimited (|) or colon-delimited (:) configurations.
        """
        assert _parse_list("a|b|c", delimiter="|") == ["a", "b", "c"]
        assert _parse_list("a:b:c", delimiter=":") == ["a", "b", "c"]

    def test_parse_list_ignores_empty_items(self):
        """Test _parse_list filters out empty items from result.

        Handles trailing commas, leading commas, or consecutive delimiters gracefully.
        Prevents empty strings in the output list.
        """
        assert _parse_list("a,,b,,c") == ["a", "b", "c"]
        assert _parse_list(",a,b,c,") == ["a", "b", "c"]

    def test_parse_list_with_single_value(self):
        """Test _parse_list wraps single value string in a list.

        Ensures consistent list output even for single-item configurations.
        """
        assert _parse_list("single") == ["single"]

    def test_parse_list_with_non_string_non_list(self):
        """Test _parse_list wraps non-string, non-list values in a list.

        Provides fallback behavior for unexpected types (numbers, booleans, etc.).
        """
        assert _parse_list(42) == [42]
        assert _parse_list(True) == [True]

    # Tests for _getenv
    # ==================
    # _getenv is a thin wrapper around os.getenv providing consistent default behavior.

    def test_getenv_with_existing_variable(self):
        """Test _getenv retrieves existing environment variable value."""
        with patch.dict(os.environ, {"TEST_VAR": "test_value"}):
            assert _getenv("TEST_VAR") == "test_value"

    def test_getenv_with_missing_variable(self):
        """Test _getenv returns default value when variable doesn't exist.

        Allows callers to provide fallback values for optional configuration.
        """
        with patch.dict(os.environ, {}, clear=True):
            assert _getenv("MISSING_VAR", "default") == "default"

    def test_getenv_with_missing_variable_no_default(self):
        """Test _getenv returns empty string when no default provided.

        Differs from os.getenv which returns None - provides string type consistency.
        """
        with patch.dict(os.environ, {}, clear=True):
            assert _getenv("MISSING_VAR") == ""

    def test_getenv_with_empty_value(self):
        """Test _getenv preserves empty string environment variable value.

        Distinguishes between unset variable and explicitly empty (VAR="").
        """
        with patch.dict(os.environ, {"EMPTY_VAR": ""}):
            assert _getenv("EMPTY_VAR") == ""

    def test_getenv_case_sensitive(self):
        """Test _getenv respects case sensitivity in variable names.

        Environment variables are case-sensitive on Unix-like systems.
        TEST_VAR and test_var are different variables.
        """
        with patch.dict(os.environ, {"test_var": "lowercase"}):
            assert _getenv("TEST_VAR", "default") == "default"
            assert _getenv("test_var") == "lowercase"


class TestConfigInitialization:
    """Test Config class initialization and defaults.

    The Config class is a dataclass that loads configuration from environment
    variables with sensible defaults. This test class verifies:
    - Default values when no environment variables are set
    - Environment variable parsing and type conversion
    - Directory creation in __post_init__
    - Proper handling of various data types (bool, int, float, list, Path)
    - Special cases like NO_COLOR and API keys
    """

    def test_config_initialization_defaults(self):
        """Test Config initializes with all default values when no env vars set.

        This is a comprehensive test verifying ALL default values defined in the
        Config class. It ensures the application can run without any environment
        variables configured, which is critical for development and testing.
        """
        with patch.dict(os.environ, {}, clear=True):
            config = Config()

            # Application settings - basic metadata
            assert config.app_name == "audio-extraction-analysis"
            assert config.app_version == "2.0.0"
            assert config.environment == "production"

            # Paths - filesystem locations for data persistence
            assert config.data_dir == Path("./data")
            assert config.cache_dir == Path("./cache")
            assert config.temp_dir == Path("/tmp")

            # File handling - validation and limits
            assert config.max_file_size == 100000000  # 100MB default
            assert ".mp3" in config.allowed_extensions
            assert ".wav" in config.allowed_extensions

            # Logging - output configuration
            assert config.log_level == "INFO"
            assert config.log_to_console is True

            # Provider settings - transcription service configuration
            assert config.default_provider == "deepgram"
            assert "elevenlabs" in config.fallback_providers

            # Language settings - i18n support
            assert config.default_language == "en"
            assert "en" in config.supported_languages

            # Feature flags - runtime behavior toggles
            assert config.enable_caching is True
            assert config.enable_retries is True
            assert config.enable_health_checks is True
            assert config.enable_metrics is False  # Disabled by default for performance

    def test_config_initialization_with_environment_variables(self):
        """Test Config reads from environment variables."""
        with patch.dict(
            os.environ,
            {
                "APP_NAME": "custom_app",
                "APP_VERSION": "2.0.0",
                "ENVIRONMENT": "development",
                "LOG_LEVEL": "DEBUG",
                "MAX_FILE_SIZE": "50000000",
                "DEFAULT_LANGUAGE": "es",
            },
        ):
            config = Config()

            assert config.app_name == "custom_app"
            assert config.app_version == "2.0.0"
            assert config.environment == "development"
            assert config.log_level == "DEBUG"
            assert config.max_file_size == 50000000
            assert config.default_language == "es"

    def test_config_post_init_creates_directories(self):
        """Test __post_init__ creates required directories if they don't exist.

        The Config dataclass uses __post_init__ to automatically create data_dir
        and cache_dir when the Config instance is initialized. This ensures the
        application has necessary directories for operation without manual setup.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            # Use temporary paths that don't exist yet
            data_path = Path(tmpdir) / "data"
            cache_path = Path(tmpdir) / "cache"

            with patch.dict(
                os.environ,
                {
                    "DATA_DIR": str(data_path),
                    "CACHE_DIR": str(cache_path),
                },
            ):
                # Creating Config should automatically create the directories
                Config()

                # Verify directories were created
                assert data_path.exists()
                assert cache_path.exists()
                assert data_path.is_dir()
                assert cache_path.is_dir()

    def test_config_boolean_fields_parsing(self):
        """Test boolean fields are parsed correctly from environment."""
        with patch.dict(
            os.environ,
            {
                "LOG_TO_CONSOLE": "false",
                "ENABLE_CACHING": "0",
                "ENABLE_RETRIES": "off",
                "ENABLE_METRICS": "true",
            },
        ):
            config = Config()

            assert config.log_to_console is False
            assert config.enable_caching is False
            assert config.enable_retries is False
            assert config.enable_metrics is True

    def test_config_list_fields_parsing(self):
        """Test list fields are parsed correctly from environment."""
        with patch.dict(
            os.environ,
            {
                "ALLOWED_EXTENSIONS": ".mp3,.wav,.flac",
                "FALLBACK_PROVIDERS": "whisper,elevenlabs",
                "SUPPORTED_LANGUAGES": "en,es,fr",
            },
        ):
            config = Config()

            assert config.allowed_extensions == [".mp3", ".wav", ".flac"]
            assert config.fallback_providers == ["whisper", "elevenlabs"]
            assert config.supported_languages == ["en", "es", "fr"]

    def test_config_integer_fields_parsing(self):
        """Test integer fields are parsed correctly from environment."""
        with patch.dict(
            os.environ,
            {
                "MAX_FILE_SIZE": "123456",
                "MAX_WORKERS": "8",
                "MAX_API_RETRIES": "5",
                "BATCH_SIZE": "10",
            },
        ):
            config = Config()

            assert config.max_file_size == 123456
            assert config.max_workers == 8
            assert config.max_retries == 5
            assert config.batch_size == 10

    def test_config_float_fields_parsing(self):
        """Test float fields are parsed correctly from environment."""
        with patch.dict(
            os.environ,
            {
                "API_RETRY_DELAY": "2.5",
                "MAX_RETRY_DELAY": "120.0",
                "RETRY_EXPONENTIAL_BASE": "3.0",
            },
        ):
            config = Config()

            assert config.retry_delay == 2.5
            assert config.max_retry_delay == 120.0
            assert config.retry_exponential_base == 3.0

    def test_config_api_keys_optional(self):
        """Test API keys are optional and default to None."""
        with patch.dict(os.environ, {}, clear=True):
            config = Config()

            assert config.DEEPGRAM_API_KEY is None
            assert config.ELEVENLABS_API_KEY is None
            assert config.GEMINI_API_KEY is None
            assert config.OPENAI_API_KEY is None
            assert config.ANTHROPIC_API_KEY is None

    def test_config_api_keys_from_environment(self):
        """Test API keys are read from environment."""
        with patch.dict(
            os.environ,
            {
                "DEEPGRAM_API_KEY": "dg_key_123",
                "ELEVENLABS_API_KEY": "el_key_456",
                "GEMINI_API_KEY": "gem_key_789",
            },
        ):
            config = Config()

            assert config.DEEPGRAM_API_KEY == "dg_key_123"
            assert config.ELEVENLABS_API_KEY == "el_key_456"
            assert config.GEMINI_API_KEY == "gem_key_789"

    def test_config_no_color_special_handling(self):
        """Test NO_COLOR environment variable special handling per NO_COLOR spec.

        The NO_COLOR environment variable follows a special convention where
        the PRESENCE of the variable (regardless of value) indicates color
        should be disabled. This follows the informal NO_COLOR standard used
        by command-line tools: https://no-color.org/
        """
        # NO_COLOR set to any value - presence enables it
        with patch.dict(os.environ, {"NO_COLOR": "1"}):
            config = Config()
            assert config.no_color is True

        # NO_COLOR set to empty string - presence still matters, not the value
        with patch.dict(os.environ, {"NO_COLOR": ""}):
            config = Config()
            assert config.no_color is True

        # NO_COLOR not set - color output is allowed
        with patch.dict(os.environ, {}, clear=True):
            config = Config()
            assert config.no_color is False


class TestConfigProperties:
    """Test Config backward compatibility properties.

    The Config class provides @property methods to maintain compatibility
    with legacy code that uses UPPERCASE naming conventions. These properties
    map to the modern lowercase attribute names.

    This ensures smooth migration from the old configuration system while
    maintaining a clean, modern API for new code.
    """

    def test_default_transcription_provider_property(self):
        """Test DEFAULT_TRANSCRIPTION_PROVIDER property."""
        with patch.dict(os.environ, {"DEFAULT_TRANSCRIPTION_PROVIDER": "whisper"}):
            config = Config()
            assert config.DEFAULT_TRANSCRIPTION_PROVIDER == "whisper"
            assert config.default_provider == "whisper"

    def test_available_providers_property(self):
        """Test AVAILABLE_PROVIDERS property."""
        config = Config()
        providers = config.AVAILABLE_PROVIDERS

        assert isinstance(providers, list)
        assert "deepgram" in providers
        assert "elevenlabs" in providers
        assert "whisper" in providers
        assert "parakeet" in providers
        assert "auto" in providers

    def test_default_language_property(self):
        """Test DEFAULT_LANGUAGE property."""
        with patch.dict(os.environ, {"DEFAULT_LANGUAGE": "fr"}):
            config = Config()
            assert config.DEFAULT_LANGUAGE == "fr"
            assert config.default_language == "fr"

    def test_max_file_size_property(self):
        """Test MAX_FILE_SIZE property."""
        with patch.dict(os.environ, {"MAX_FILE_SIZE": "50000000"}):
            config = Config()
            assert config.MAX_FILE_SIZE == 50000000
            assert config.max_file_size == 50000000

    def test_allowed_file_extensions_property(self):
        """Test ALLOWED_FILE_EXTENSIONS returns a set."""
        config = Config()
        extensions = config.ALLOWED_FILE_EXTENSIONS

        assert isinstance(extensions, set)
        assert ".mp3" in extensions
        assert ".wav" in extensions

    def test_retry_properties(self):
        """Test retry-related backward compatibility properties."""
        with patch.dict(
            os.environ,
            {
                "MAX_API_RETRIES": "5",
                "API_RETRY_DELAY": "2.0",
                "MAX_RETRY_DELAY": "120.0",
                "RETRY_EXPONENTIAL_BASE": "3.0",
                "RETRY_JITTER_ENABLED": "false",
            },
        ):
            config = Config()

            assert config.MAX_API_RETRIES == 5
            assert config.API_RETRY_DELAY == 2.0
            assert config.MAX_RETRY_DELAY == 120.0
            assert config.RETRY_EXPONENTIAL_BASE == 3.0
            assert config.RETRY_JITTER_ENABLED is False

    def test_circuit_breaker_properties(self):
        """Test circuit breaker backward compatibility properties."""
        with patch.dict(
            os.environ,
            {
                "CIRCUIT_BREAKER_FAILURE_THRESHOLD": "10",
                "CIRCUIT_BREAKER_RECOVERY_TIMEOUT": "120.0",
            },
        ):
            config = Config()

            assert config.CIRCUIT_BREAKER_FAILURE_THRESHOLD == 10
            assert config.CIRCUIT_BREAKER_RECOVERY_TIMEOUT == 120.0

    def test_health_check_properties(self):
        """Test health check backward compatibility properties."""
        with patch.dict(
            os.environ,
            {
                "ENABLE_HEALTH_CHECKS": "false",
                "CONNECT_TIMEOUT": "15",
            },
        ):
            config = Config()

            assert config.HEALTH_CHECK_ENABLED is False
            assert config.HEALTH_CHECK_TIMEOUT == 15.0

    def test_log_level_property(self):
        """Test LOG_LEVEL property."""
        with patch.dict(os.environ, {"LOG_LEVEL": "warning"}):
            config = Config()
            assert config.LOG_LEVEL == "WARNING"

    def test_markdown_default_template_property(self):
        """Test markdown_default_template property."""
        with patch.dict(os.environ, {"MARKDOWN_TEMPLATE": "custom"}):
            config = Config()
            assert config.markdown_default_template == "custom"


class TestConfigClassMethods:
    """Test Config class methods for provider validation and API key retrieval.

    The Config class provides several @classmethod utilities:
    - is_configured(): Check if providers have required API keys
    - get_<provider>_api_key(): Retrieve API keys with validation
    - get_available_providers(): List configured providers
    - validate_file_extension(): Check file type support

    These methods support runtime provider availability checks and configuration
    validation without requiring a Config instance.
    """

    def test_is_configured_deepgram_with_key(self):
        """Test is_configured for deepgram with API key."""
        with patch.dict(os.environ, {"DEEPGRAM_API_KEY": "test_key"}):
            assert Config.is_configured("deepgram") is True

    def test_is_configured_deepgram_without_key(self):
        """Test is_configured for deepgram without API key."""
        with patch.dict(os.environ, {}, clear=True):
            assert Config.is_configured("deepgram") is False

    def test_is_configured_elevenlabs_with_key(self):
        """Test is_configured for elevenlabs with API key."""
        with patch.dict(os.environ, {"ELEVENLABS_API_KEY": "test_key"}):
            assert Config.is_configured("elevenlabs") is True

    def test_is_configured_elevenlabs_without_key(self):
        """Test is_configured for elevenlabs without API key."""
        with patch.dict(os.environ, {}, clear=True):
            assert Config.is_configured("elevenlabs") is False

    def test_is_configured_no_provider_with_deepgram(self):
        """Test is_configured with no provider but deepgram key present."""
        with patch.dict(os.environ, {"DEEPGRAM_API_KEY": "test_key"}):
            assert Config.is_configured() is True

    def test_is_configured_no_provider_with_elevenlabs(self):
        """Test is_configured with no provider but elevenlabs key present."""
        with patch.dict(os.environ, {"ELEVENLABS_API_KEY": "test_key"}):
            assert Config.is_configured() is True

    def test_is_configured_no_provider_no_keys(self):
        """Test is_configured with no provider and no keys."""
        with patch.dict(os.environ, {}, clear=True):
            assert Config.is_configured() is False

    def test_get_deepgram_api_key_success(self):
        """Test get_deepgram_api_key with valid key."""
        with patch.dict(os.environ, {"DEEPGRAM_API_KEY": "valid_key"}):
            key = Config.get_deepgram_api_key()
            assert key == "valid_key"

    def test_get_deepgram_api_key_missing(self):
        """Test get_deepgram_api_key raises ValueError when key is not configured.

        This test verifies proper error handling: the method should fail-fast
        with a clear error message rather than returning None or empty string.
        This helps catch configuration issues early in application startup.
        """
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError) as exc_info:
                Config.get_deepgram_api_key()

            # Verify the error message is informative
            assert "DEEPGRAM_API_KEY not configured" in str(exc_info.value)

    def test_get_elevenlabs_api_key_success(self):
        """Test get_elevenlabs_api_key with valid key."""
        with patch.dict(os.environ, {"ELEVENLABS_API_KEY": "valid_key"}):
            key = Config.get_elevenlabs_api_key()
            assert key == "valid_key"

    def test_get_elevenlabs_api_key_missing(self):
        """Test get_elevenlabs_api_key raises error when key missing."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError) as exc_info:
                Config.get_elevenlabs_api_key()

            assert "ELEVENLABS_API_KEY not configured" in str(exc_info.value)

    def test_get_gemini_api_key_success(self):
        """Test get_gemini_api_key with valid key."""
        with patch.dict(os.environ, {"GEMINI_API_KEY": "valid_key"}):
            key = Config.get_gemini_api_key()
            assert key == "valid_key"

    def test_get_gemini_api_key_missing(self):
        """Test get_gemini_api_key raises error when key missing."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError) as exc_info:
                Config.get_gemini_api_key()

            assert "GEMINI_API_KEY not configured" in str(exc_info.value)

    def test_get_available_providers_with_deepgram(self):
        """Test get_available_providers includes deepgram when key present."""
        with patch.dict(os.environ, {"DEEPGRAM_API_KEY": "test_key"}):
            providers = Config.get_available_providers()
            assert "deepgram" in providers

    def test_get_available_providers_with_elevenlabs(self):
        """Test get_available_providers includes elevenlabs when key present."""
        with patch.dict(os.environ, {"ELEVENLABS_API_KEY": "test_key"}):
            providers = Config.get_available_providers()
            assert "elevenlabs" in providers

    def test_get_available_providers_empty(self):
        """Test get_available_providers with no API keys."""
        with patch.dict(os.environ, {}, clear=True):
            providers = Config.get_available_providers()
            assert isinstance(providers, list)
            # May include whisper/parakeet if installed

    def test_validate_file_extension_valid(self):
        """Test validate_file_extension with valid extensions."""
        assert Config.validate_file_extension(Path("test.mp3")) is True
        assert Config.validate_file_extension(Path("test.wav")) is True
        assert Config.validate_file_extension(Path("test.m4a")) is True

    def test_validate_file_extension_invalid(self):
        """Test validate_file_extension with invalid extensions."""
        assert Config.validate_file_extension(Path("test.txt")) is False
        assert Config.validate_file_extension(Path("test.exe")) is False
        assert Config.validate_file_extension(Path("test.pdf")) is False

    def test_validate_file_extension_case_insensitive(self):
        """Test validate_file_extension is case-insensitive."""
        assert Config.validate_file_extension(Path("test.MP3")) is True
        assert Config.validate_file_extension(Path("test.WAV")) is True
        assert Config.validate_file_extension(Path("test.M4A")) is True


class TestGetConfigSingleton:
    """Test get_config singleton pattern.

    The get_config() function implements the singleton pattern to ensure only
    one Config instance exists throughout the application lifecycle. This:
    - Prevents redundant environment variable parsing
    - Ensures consistent configuration across modules
    - Avoids race conditions in multi-threaded scenarios

    The singleton is stored in module-level _config_instance variable.
    """

    def test_get_config_returns_config_instance(self):
        """Test get_config returns a Config instance."""
        config = get_config()
        assert isinstance(config, Config)

    def test_get_config_returns_same_instance(self):
        """Test get_config returns the same instance (singleton)."""
        config1 = get_config()
        config2 = get_config()
        assert config1 is config2

    def test_get_config_singleton_maintains_state(self):
        """Test singleton maintains state across calls.

        This verifies that modifications to the Config instance persist
        across multiple get_config() calls, proving it's truly a singleton.
        """
        # Reset singleton to ensure clean test state
        import src.config

        src.config._config_instance = None

        # First call creates instance and modify it
        config1 = get_config()
        config1.app_name = "modified_name"

        # Second call should return same instance with modified state intact
        config2 = get_config()
        assert config2.app_name == "modified_name"
        assert config1 is config2  # Verify they're the exact same object


class TestConfigEdgeCases:
    """Test edge cases and special scenarios.

    This class tests boundary conditions, unusual inputs, and provider-specific
    configurations that may not be covered in standard initialization tests:
    - Empty string environment variables
    - Path object handling
    - Optional configuration fields (log_file)
    - Provider-specific settings (Deepgram, Whisper)
    - Log level case normalization
    - Timeout configurations
    """

    def test_config_with_empty_string_values(self):
        """Test Config handles empty string environment variables.

        Note: Some fields like LOG_LEVEL have validation that rejects empty strings.
        This test verifies that fields without validation accept empty strings.
        """
        with patch.dict(
            os.environ,
            {
                "APP_NAME": "",
                "DEFAULT_LANGUAGE": "",
            },
        ):
            config = Config()

            assert config.app_name == ""
            # LOG_LEVEL has validation and won't accept empty string
            assert config.default_language == ""

    def test_config_path_objects(self):
        """Test Config creates Path objects correctly."""
        config = Config()

        assert isinstance(config.data_dir, Path)
        assert isinstance(config.cache_dir, Path)
        assert isinstance(config.temp_dir, Path)

    def test_config_log_file_optional(self):
        """Test log_file is optional and defaults to None."""
        with patch.dict(os.environ, {}, clear=True):
            config = Config()
            assert config.log_file is None

        with patch.dict(os.environ, {"LOG_FILE": ""}):
            config = Config()
            assert config.log_file is None

        with patch.dict(os.environ, {"LOG_FILE": "/var/log/app.log"}):
            config = Config()
            assert config.log_file == "/var/log/app.log"

    def test_config_provider_settings_deepgram(self):
        """Test Deepgram-specific settings."""
        with patch.dict(
            os.environ,
            {
                "DEEPGRAM_MODEL": "nova-3",
                "DEEPGRAM_LANGUAGE": "es",
                "DEEPGRAM_TIMEOUT": "300",
                "DEEPGRAM_PUNCTUATE": "false",
                "DEEPGRAM_DIARIZE": "true",
            },
        ):
            config = Config()

            assert config.DEEPGRAM_MODEL == "nova-3"
            assert config.DEEPGRAM_LANGUAGE == "es"
            assert config.DEEPGRAM_TIMEOUT == 300
            assert config.DEEPGRAM_PUNCTUATE is False
            assert config.DEEPGRAM_DIARIZE is True

    def test_config_provider_settings_whisper(self):
        """Test Whisper-specific settings."""
        with patch.dict(
            os.environ,
            {
                "WHISPER_MODEL": "large",
                "WHISPER_DEVICE": "cuda",
                "WHISPER_COMPUTE_TYPE": "float16",
            },
        ):
            config = Config()

            assert config.WHISPER_MODEL == "large"
            assert config.WHISPER_DEVICE == "cuda"
            assert config.WHISPER_COMPUTE_TYPE == "float16"

    def test_config_log_level_uppercase_conversion(self):
        """Test log level is automatically normalized to uppercase.

        Python's logging module expects uppercase level names (DEBUG, INFO, WARNING,
        ERROR, CRITICAL). This test verifies that user input is normalized regardless
        of case, preventing runtime errors from misconfigured log levels.
        """
        # Lowercase input normalized to uppercase
        with patch.dict(os.environ, {"LOG_LEVEL": "debug"}):
            config = Config()
            assert config.log_level == "DEBUG"

        # Mixed case input normalized to uppercase
        with patch.dict(os.environ, {"LOG_LEVEL": "WaRnInG"}):
            config = Config()
            assert config.log_level == "WARNING"

    def test_config_all_timeouts(self):
        """Test all timeout settings."""
        with patch.dict(
            os.environ,
            {
                "GLOBAL_TIMEOUT": "1200",
                "CONNECT_TIMEOUT": "20",
                "READ_TIMEOUT": "60",
                "WRITE_TIMEOUT": "60",
                "REQUEST_TIMEOUT": "45",
            },
        ):
            config = Config()

            assert config.global_timeout == 1200
            assert config.connect_timeout == 20
            assert config.read_timeout == 60
            assert config.write_timeout == 60
            assert config.request_timeout == 45


class TestConfigExports:
    """Test module exports and public API.

    Verifies that the src.config module exposes the correct public interface
    through __all__ and that all exported symbols are importable and functional.

    The module's public API consists of:
    - Config: The main configuration dataclass
    - get_config: Singleton accessor function
    """

    def test_module_all_exports(self):
        """Test __all__ contains expected public exports.

        The module exposes Config and get_config as the primary public API.
        Additional utility functions like _reset_config may also be exported
        for testing purposes.
        """
        from src.config import __all__

        # Core public API
        assert "Config" in __all__
        assert "get_config" in __all__

        # Allow for additional testing utilities
        assert len(__all__) >= 2

    def test_module_imports(self):
        """Test all expected imports work."""
        from src.config import Config, get_config

        assert Config is not None
        assert get_config is not None
        assert callable(get_config)


if __name__ == "__main__":
    # Allow running this test file directly for quick iteration during development
    # Usage: python -m pytest tests/unit/test_config_init.py -v
    # Or simply: python tests/unit/test_config_init.py
    pytest.main([__file__, "-v"])
