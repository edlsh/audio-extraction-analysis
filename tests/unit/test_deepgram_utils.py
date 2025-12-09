"""Unit tests for Deepgram provider utilities.

Tests cover mimetype detection and options building with edge cases.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.providers.deepgram_utils import build_prerecorded_options, detect_mimetype


class TestDetectMimetype:
    """Test suite for mimetype detection."""

    @pytest.mark.parametrize(
        "extension,expected_mimetype",
        [
            (".mp3", "audio/mp3"),
            (".wav", "audio/wav"),
            (".m4a", "audio/mp4"),
            (".mp4", "audio/mp4"),
            (".aac", "audio/aac"),
            (".flac", "audio/flac"),
            (".ogg", "audio/ogg"),
            (".webm", "audio/webm"),
        ],
    )
    def test_detect_mimetype_known_formats(self, extension: str, expected_mimetype: str) -> None:
        """Test mimetype detection for all known audio formats."""
        path = Path(f"test_file{extension}")
        assert detect_mimetype(path) == expected_mimetype

    @pytest.mark.parametrize(
        "extension,expected_mimetype",
        [
            (".MP3", "audio/mp3"),
            (".WAV", "audio/wav"),
            (".M4A", "audio/mp4"),
            (".FLAC", "audio/flac"),
        ],
    )
    def test_detect_mimetype_uppercase_extensions(
        self, extension: str, expected_mimetype: str
    ) -> None:
        """Test that uppercase extensions are handled correctly."""
        path = Path(f"test_file{extension}")
        assert detect_mimetype(path) == expected_mimetype

    @pytest.mark.parametrize(
        "extension,expected_mimetype",
        [
            (".Mp3", "audio/mp3"),
            (".WaV", "audio/wav"),
            (".m4A", "audio/mp4"),
        ],
    )
    def test_detect_mimetype_mixed_case_extensions(
        self, extension: str, expected_mimetype: str
    ) -> None:
        """Test that mixed-case extensions are normalized."""
        path = Path(f"test_file{extension}")
        assert detect_mimetype(path) == expected_mimetype

    def test_detect_mimetype_unknown_extension(self) -> None:
        """Test that unknown extensions default to audio/mp3."""
        path = Path("test_file.xyz")
        assert detect_mimetype(path) == "audio/mp3"

    def test_detect_mimetype_no_extension(self) -> None:
        """Test file with no extension defaults to audio/mp3."""
        path = Path("test_file")
        assert detect_mimetype(path) == "audio/mp3"

    def test_detect_mimetype_multiple_dots(self) -> None:
        """Test file with multiple dots uses the last extension."""
        path = Path("test.file.name.mp3")
        assert detect_mimetype(path) == "audio/mp3"

    def test_detect_mimetype_hidden_file(self) -> None:
        """Test hidden file with valid extension."""
        path = Path(".hidden_audio.wav")
        assert detect_mimetype(path) == "audio/wav"

    def test_detect_mimetype_path_with_directories(self) -> None:
        """Test that directory paths don't affect mimetype detection."""
        path = Path("/some/long/path/to/audio.flac")
        assert detect_mimetype(path) == "audio/flac"

    def test_detect_mimetype_empty_suffix(self) -> None:
        """Test file ending with dot but no extension."""
        path = Path("test_file.")
        assert detect_mimetype(path) == "audio/mp3"

    def test_detect_mimetype_windows_path(self) -> None:
        """Test Windows-style path handling for cross-platform compatibility."""
        path = Path("C:\\Users\\Audio\\recording.wav")
        assert detect_mimetype(path) == "audio/wav"

    def test_detect_mimetype_complex_nested_path(self) -> None:
        """Test deeply nested path with multiple directory levels."""
        path = Path("/var/media/projects/2024/audio/final/master.flac")
        assert detect_mimetype(path) == "audio/flac"

    def test_detect_mimetype_backup_extension(self) -> None:
        """Test file with backup extension pattern (should default)."""
        path = Path("audio.mp3.bak")
        assert detect_mimetype(path) == "audio/mp3"

    def test_detect_mimetype_numeric_extension(self) -> None:
        """Test file with numeric extension defaults correctly."""
        path = Path("audio.123")
        assert detect_mimetype(path) == "audio/mp3"

    def test_detect_mimetype_very_long_extension(self) -> None:
        """Test file with unusually long extension defaults correctly."""
        path = Path("audio.thisisaverylongextension")
        assert detect_mimetype(path) == "audio/mp3"


class TestBuildPrerecordedOptions:
    """Test suite for building Deepgram prerecorded options."""

    def test_build_prerecorded_options_creates_correct_object(self) -> None:
        """Test that options dict is created with correct settings."""
        language = "en-US"

        result = build_prerecorded_options(language)

        # Verify dict was created with correct parameters
        assert result == {
            "model": "nova-3",
            "smart_format": True,
            "utterances": True,
            "punctuate": True,
            "paragraphs": True,
            "diarize": True,
            "summarize": "v2",
            "topics": True,
            "intents": True,
            "sentiment": True,
            "language": language,
            "detect_language": True,
            "alternatives": 1,
        }

    @pytest.mark.parametrize(
        "language",
        [
            "en-US",
            "es-ES",
            "fr-FR",
            "de-DE",
            "ja-JP",
            "zh-CN",
            "pt-BR",
            "ru-RU",
        ],
    )
    def test_build_prerecorded_options_with_different_languages(self, language: str) -> None:
        """Test that options are built correctly for various language codes."""
        result = build_prerecorded_options(language)

        # Verify language parameter was passed correctly
        assert result["language"] == language
        assert isinstance(result, dict)

    def test_build_prerecorded_options_all_boolean_flags_enabled(self) -> None:
        """Test that all boolean flags are set to True as expected."""
        result = build_prerecorded_options("en")

        boolean_flags = [
            "smart_format",
            "utterances",
            "punctuate",
            "paragraphs",
            "diarize",
            "topics",
            "intents",
            "sentiment",
            "detect_language",
        ]

        for flag in boolean_flags:
            assert result[flag] is True, f"Expected {flag} to be True"

    def test_build_prerecorded_options_model_version(self) -> None:
        """Test that nova-3 model is specified."""
        result = build_prerecorded_options("en")
        assert result["model"] == "nova-3"

    def test_build_prerecorded_options_summarize_version(self) -> None:
        """Test that summarize v2 is used."""
        result = build_prerecorded_options("en")
        assert result["summarize"] == "v2"

    def test_build_prerecorded_options_alternatives_count(self) -> None:
        """Test that alternatives is set to 1."""
        result = build_prerecorded_options("en")
        assert result["alternatives"] == 1

    def test_build_prerecorded_options_with_empty_string_language(self) -> None:
        """Test options building with empty language string (edge case)."""
        result = build_prerecorded_options("")
        assert result["language"] == ""
        assert isinstance(result, dict)

    def test_build_prerecorded_options_preserves_language_casing(self) -> None:
        """Test that language parameter is passed as-is without modification."""
        language = "EN-us"  # Mixed case
        result = build_prerecorded_options(language)
        assert result["language"] == language

    def test_build_prerecorded_options_with_special_characters(self) -> None:
        """Test language code with special characters (edge case)."""
        language = "zh-Hans-CN"  # Chinese Simplified
        result = build_prerecorded_options(language)
        assert result["language"] == language
        assert isinstance(result, dict)

    def test_build_prerecorded_options_with_numeric_language(self) -> None:
        """Test language parameter with numeric values (unusual but valid string)."""
        language = "lang-123"
        result = build_prerecorded_options(language)
        assert result["language"] == language

    def test_build_prerecorded_options_with_long_language_code(self) -> None:
        """Test language parameter with very long string."""
        language = "en-US-x-very-long-variant-name"
        result = build_prerecorded_options(language)
        assert result["language"] == language
        assert isinstance(result, dict)
