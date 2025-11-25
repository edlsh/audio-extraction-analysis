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
        """Test that PrerecordedOptions object is created with correct settings."""
        language = "en-US"

        # Mock the deepgram module
        mock_deepgram = MagicMock()
        mock_options_class = MagicMock()
        mock_instance = MagicMock()
        mock_options_class.return_value = mock_instance
        mock_deepgram.PrerecordedOptions = mock_options_class

        with patch.dict("sys.modules", {"deepgram": mock_deepgram}):
            result = build_prerecorded_options(language)

            # Verify PrerecordedOptions was called with correct parameters
            mock_options_class.assert_called_once_with(
                model="nova-3",
                smart_format=True,
                utterances=True,
                punctuate=True,
                paragraphs=True,
                diarize=True,
                summarize="v2",
                topics=True,
                intents=True,
                sentiment=True,
                language=language,
                detect_language=True,
                alternatives=1,
            )

            # Verify the returned object is the mocked instance
            assert result is mock_instance

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
        mock_deepgram = MagicMock()
        mock_options_class = MagicMock()
        mock_instance = MagicMock()
        mock_options_class.return_value = mock_instance
        mock_deepgram.PrerecordedOptions = mock_options_class

        with patch.dict("sys.modules", {"deepgram": mock_deepgram}):
            result = build_prerecorded_options(language)

            # Verify language parameter was passed correctly
            call_kwargs = mock_options_class.call_args[1]
            assert call_kwargs["language"] == language
            assert result is mock_instance

    def test_build_prerecorded_options_all_boolean_flags_enabled(self) -> None:
        """Test that all boolean flags are set to True as expected."""
        mock_deepgram = MagicMock()
        mock_options_class = MagicMock()
        mock_deepgram.PrerecordedOptions = mock_options_class

        with patch.dict("sys.modules", {"deepgram": mock_deepgram}):
            build_prerecorded_options("en")

            call_kwargs = mock_options_class.call_args[1]
            assert call_kwargs["smart_format"] is True
            assert call_kwargs["utterances"] is True
            assert call_kwargs["punctuate"] is True
            assert call_kwargs["paragraphs"] is True
            assert call_kwargs["diarize"] is True
            assert call_kwargs["topics"] is True
            assert call_kwargs["intents"] is True
            assert call_kwargs["sentiment"] is True
            assert call_kwargs["detect_language"] is True

    def test_build_prerecorded_options_model_version(self) -> None:
        """Test that nova-3 model is specified."""
        mock_deepgram = MagicMock()
        mock_options_class = MagicMock()
        mock_deepgram.PrerecordedOptions = mock_options_class

        with patch.dict("sys.modules", {"deepgram": mock_deepgram}):
            build_prerecorded_options("en")

            call_kwargs = mock_options_class.call_args[1]
            assert call_kwargs["model"] == "nova-3"

    def test_build_prerecorded_options_summarize_version(self) -> None:
        """Test that summarize v2 is used."""
        mock_deepgram = MagicMock()
        mock_options_class = MagicMock()
        mock_deepgram.PrerecordedOptions = mock_options_class

        with patch.dict("sys.modules", {"deepgram": mock_deepgram}):
            build_prerecorded_options("en")

            call_kwargs = mock_options_class.call_args[1]
            assert call_kwargs["summarize"] == "v2"

    def test_build_prerecorded_options_alternatives_count(self) -> None:
        """Test that alternatives is set to 1."""
        mock_deepgram = MagicMock()
        mock_options_class = MagicMock()
        mock_deepgram.PrerecordedOptions = mock_options_class

        with patch.dict("sys.modules", {"deepgram": mock_deepgram}):
            build_prerecorded_options("en")

            call_kwargs = mock_options_class.call_args[1]
            assert call_kwargs["alternatives"] == 1

    def test_build_prerecorded_options_with_empty_string_language(self) -> None:
        """Test options building with empty language string (edge case)."""
        mock_deepgram = MagicMock()
        mock_options_class = MagicMock()
        mock_instance = MagicMock()
        mock_options_class.return_value = mock_instance
        mock_deepgram.PrerecordedOptions = mock_options_class

        with patch.dict("sys.modules", {"deepgram": mock_deepgram}):
            result = build_prerecorded_options("")

            call_kwargs = mock_options_class.call_args[1]
            assert call_kwargs["language"] == ""
            assert result is mock_instance

    def test_build_prerecorded_options_preserves_language_casing(self) -> None:
        """Test that language parameter is passed as-is without modification."""
        mock_deepgram = MagicMock()
        mock_options_class = MagicMock()
        mock_deepgram.PrerecordedOptions = mock_options_class

        with patch.dict("sys.modules", {"deepgram": mock_deepgram}):
            language = "EN-us"  # Mixed case
            build_prerecorded_options(language)

            call_kwargs = mock_options_class.call_args[1]
            assert call_kwargs["language"] == language

    def test_build_prerecorded_options_with_special_characters(self) -> None:
        """Test language code with special characters (edge case)."""
        mock_deepgram = MagicMock()
        mock_options_class = MagicMock()
        mock_instance = MagicMock()
        mock_options_class.return_value = mock_instance
        mock_deepgram.PrerecordedOptions = mock_options_class

        with patch.dict("sys.modules", {"deepgram": mock_deepgram}):
            language = "en-US_variant"
            result = build_prerecorded_options(language)

            call_kwargs = mock_options_class.call_args[1]
            assert call_kwargs["language"] == language
            assert result is mock_instance

    def test_build_prerecorded_options_with_numeric_language(self) -> None:
        """Test language parameter with numeric values (unusual but valid string)."""
        mock_deepgram = MagicMock()
        mock_options_class = MagicMock()
        mock_instance = MagicMock()
        mock_options_class.return_value = mock_instance
        mock_deepgram.PrerecordedOptions = mock_options_class

        with patch.dict("sys.modules", {"deepgram": mock_deepgram}):
            language = "lang-123"
            result = build_prerecorded_options(language)

            call_kwargs = mock_options_class.call_args[1]
            assert call_kwargs["language"] == language
            assert result is mock_instance

    def test_build_prerecorded_options_with_long_language_code(self) -> None:
        """Test language parameter with very long string."""
        mock_deepgram = MagicMock()
        mock_options_class = MagicMock()
        mock_instance = MagicMock()
        mock_options_class.return_value = mock_instance
        mock_deepgram.PrerecordedOptions = mock_options_class

        with patch.dict("sys.modules", {"deepgram": mock_deepgram}):
            language = "en-US-x-very-long-variant-name"
            result = build_prerecorded_options(language)

            call_kwargs = mock_options_class.call_args[1]
            assert call_kwargs["language"] == language
            assert result is mock_instance
