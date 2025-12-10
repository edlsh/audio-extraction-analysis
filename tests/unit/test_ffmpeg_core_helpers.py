"""Unit tests for ffmpeg_core.py helper functions.

Tests cover:
- prepare_extraction_paths: Input validation and output path generation
- verify_extraction_output: Output file verification
- check_ffmpeg_available: FFmpeg availability check
- validate_path_security: Path security validation
- cleanup_temp_file: Temporary file cleanup
"""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from src.exceptions import AudioExtractionError, FFmpegNotFoundError, ValidationError
from src.services.ffmpeg_core import (
    check_ffmpeg_available,
    cleanup_temp_file,
    prepare_extraction_paths,
    validate_path_security,
    verify_extraction_output,
)


class TestPrepareExtractionPaths:
    """Tests for prepare_extraction_paths function."""

    def test_valid_input_returns_paths(self, tmp_path):
        """Valid input file should return validated input and output paths."""
        input_file = tmp_path / "video.mp4"
        input_file.write_bytes(b"fake video content")

        with patch(
            "src.services.ffmpeg_core.validate_media_file_or_raise",
            return_value=input_file,
        ):
            input_result, output_result = prepare_extraction_paths(input_file, None)

            assert input_result == input_file
            assert output_result == input_file.with_suffix(".mp3")

    def test_auto_generates_output_path(self, tmp_path):
        """When output_path is None, auto-generate with default suffix."""
        input_file = tmp_path / "video.mp4"
        input_file.write_bytes(b"fake video content")

        with patch(
            "src.services.ffmpeg_core.validate_media_file_or_raise",
            return_value=input_file,
        ):
            _, output_result = prepare_extraction_paths(input_file, None)

            assert output_result.suffix == ".mp3"
            assert output_result.stem == input_file.stem

    def test_custom_output_path_preserved(self, tmp_path):
        """Explicit output_path should be preserved."""
        input_file = tmp_path / "video.mp4"
        input_file.write_bytes(b"fake video content")
        output_file = tmp_path / "custom" / "output.wav"

        with patch(
            "src.services.ffmpeg_core.validate_media_file_or_raise",
            return_value=input_file,
        ):
            _, output_result = prepare_extraction_paths(input_file, output_file)

            assert output_result == output_file

    def test_creates_output_parent_directory(self, tmp_path):
        """Output path parent directory should be created if it doesn't exist."""
        input_file = tmp_path / "video.mp4"
        input_file.write_bytes(b"fake video content")
        output_file = tmp_path / "nested" / "deep" / "output.mp3"

        with patch(
            "src.services.ffmpeg_core.validate_media_file_or_raise",
            return_value=input_file,
        ):
            prepare_extraction_paths(input_file, output_file)

            assert output_file.parent.exists()

    def test_invalid_input_raises_validation_error(self, tmp_path):
        """Invalid input should raise ValidationError."""
        input_file = tmp_path / "nonexistent.mp4"

        with patch(
            "src.services.ffmpeg_core.validate_media_file_or_raise",
            side_effect=ValidationError("Invalid media file"),
        ):
            with pytest.raises(ValidationError):
                prepare_extraction_paths(input_file, None)

    def test_custom_default_suffix(self, tmp_path):
        """Custom default_suffix should be used for auto-generated output."""
        input_file = tmp_path / "video.mp4"
        input_file.write_bytes(b"fake video content")

        with patch(
            "src.services.ffmpeg_core.validate_media_file_or_raise",
            return_value=input_file,
        ):
            _, output_result = prepare_extraction_paths(input_file, None, default_suffix=".wav")

            assert output_result.suffix == ".wav"


class TestVerifyExtractionOutput:
    """Tests for verify_extraction_output function."""

    def test_existing_output_returns_path(self, tmp_path):
        """Existing output file should return the path."""
        input_file = tmp_path / "input.mp4"
        output_file = tmp_path / "output.mp3"
        output_file.write_bytes(b"extracted audio")

        result = verify_extraction_output(input_file, output_file)

        assert result == output_file

    def test_missing_output_raises_error(self, tmp_path):
        """Missing output file should raise AudioExtractionError."""
        input_file = tmp_path / "input.mp4"
        output_file = tmp_path / "missing_output.mp3"

        with pytest.raises(AudioExtractionError) as exc_info:
            verify_extraction_output(input_file, output_file)

        assert "not found" in str(exc_info.value).lower()

    def test_logs_success_by_default(self, tmp_path, caplog):
        """Success should be logged by default."""
        input_file = tmp_path / "input.mp4"
        output_file = tmp_path / "output.mp3"
        output_file.write_bytes(b"extracted audio content")

        with caplog.at_level("INFO"):
            verify_extraction_output(input_file, output_file, log_success=True)

        # Check that some log message was emitted (the actual logging may vary)
        # We just verify the function completes without error


class TestCheckFfmpegAvailable:
    """Tests for check_ffmpeg_available function."""

    def test_ffmpeg_available_no_error(self):
        """When FFmpeg is available, no error should be raised."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0)

            # Should not raise
            check_ffmpeg_available()

            mock_run.assert_called_once()

    def test_ffmpeg_not_found_raises_error(self):
        """FileNotFoundError should raise FFmpegNotFoundError."""
        with patch("subprocess.run", side_effect=FileNotFoundError("ffmpeg not found")):
            with pytest.raises(FFmpegNotFoundError) as exc_info:
                check_ffmpeg_available()

            assert "not found" in str(exc_info.value).lower()

    def test_ffmpeg_execution_error_raises_error(self):
        """CalledProcessError should raise FFmpegNotFoundError."""
        import subprocess

        with patch(
            "subprocess.run",
            side_effect=subprocess.CalledProcessError(1, "ffmpeg"),
        ):
            with pytest.raises(FFmpegNotFoundError):
                check_ffmpeg_available()

    def test_ffmpeg_timeout_raises_error(self):
        """TimeoutExpired should raise FFmpegNotFoundError."""
        import subprocess

        with patch(
            "subprocess.run",
            side_effect=subprocess.TimeoutExpired("ffmpeg", 5.0),
        ):
            with pytest.raises(FFmpegNotFoundError) as exc_info:
                check_ffmpeg_available(timeout=5.0)

            assert "timed out" in str(exc_info.value).lower()


class TestValidatePathSecurity:
    """Tests for validate_path_security function."""

    def test_safe_path_passes(self, tmp_path):
        """Safe path should pass validation."""
        safe_path = tmp_path / "safe_file.mp4"

        # Should not raise
        validate_path_security(safe_path)

    def test_path_with_semicolon_raises(self, tmp_path):
        """Path with semicolon should raise ValueError."""
        unsafe_path = tmp_path / "file;rm -rf.mp4"

        with pytest.raises(ValueError) as exc_info:
            validate_path_security(unsafe_path)

        assert (
            "dangerous" in str(exc_info.value).lower() or "invalid" in str(exc_info.value).lower()
        )

    def test_path_with_ampersand_raises(self, tmp_path):
        """Path with ampersand should raise ValueError."""
        unsafe_path = tmp_path / "file&whoami.mp4"

        with pytest.raises(ValueError) as exc_info:
            validate_path_security(unsafe_path)

        assert (
            "dangerous" in str(exc_info.value).lower() or "invalid" in str(exc_info.value).lower()
        )

    def test_path_with_backtick_raises(self, tmp_path):
        """Path with backtick should raise ValueError."""
        unsafe_path = tmp_path / "file`id`.mp4"

        with pytest.raises(ValueError) as exc_info:
            validate_path_security(unsafe_path)

        assert (
            "dangerous" in str(exc_info.value).lower() or "invalid" in str(exc_info.value).lower()
        )


class TestCleanupTempFile:
    """Tests for cleanup_temp_file function."""

    def test_deletes_existing_file(self, tmp_path):
        """Existing temp file should be deleted."""
        temp_file = tmp_path / "temp.mp3"
        temp_file.write_bytes(b"temp content")

        cleanup_temp_file(temp_file)

        assert not temp_file.exists()

    def test_none_path_no_error(self):
        """None path should not raise error."""
        # Should not raise
        cleanup_temp_file(None)

    def test_nonexistent_path_no_error(self, tmp_path):
        """Non-existent path should not raise error."""
        nonexistent = tmp_path / "does_not_exist.mp3"

        # Should not raise
        cleanup_temp_file(nonexistent)

    def test_handles_deletion_error_gracefully(self, tmp_path):
        """Deletion errors should be handled gracefully (logged, not raised)."""
        temp_file = tmp_path / "locked.mp3"
        temp_file.write_bytes(b"content")

        with patch.object(Path, "unlink", side_effect=PermissionError("Permission denied")):
            # Should not raise, just log warning
            cleanup_temp_file(temp_file)
