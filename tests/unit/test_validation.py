"""Tests for the validation module.

This module tests the FileValidator class and its methods for validating
audio/video files, extensions, and file sizes.
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from src.utils.file_validation import FileValidator


class TestFileValidator:
    """Test suite for FileValidator class."""

    def test_video_extensions_constant(self):
        """Test that VIDEO_EXTENSIONS contains expected video formats."""
        expected_extensions = {
            ".mp4",
            ".avi",
            ".mov",
            ".mkv",
            ".webm",
            ".flv",
            ".wmv",
            ".m4v",
            ".3gp",
        }
        assert FileValidator.VIDEO_EXTENSIONS == expected_extensions

    def test_audio_extensions_constant(self):
        """Test that AUDIO_EXTENSIONS contains expected audio formats."""
        expected_extensions = {".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a", ".wma"}
        assert FileValidator.AUDIO_EXTENSIONS == expected_extensions

    def test_validate_path_security_valid_path(self, tmp_path):
        """Test that valid paths pass security validation."""
        test_file = tmp_path / "valid_file.mp4"
        test_file.write_text("test content")

        # Should not raise any exception
        FileValidator.validate_path_security(test_file)

    def test_validate_path_security_delegates_to_sanitizer(self, tmp_path):
        """Test that validate_path_security delegates to PathSanitizer."""
        test_file = tmp_path / "test.mp4"

        with patch(
            "src.utils.file_validation.PathSanitizer.validate_path_security"
        ) as mock_validate:
            FileValidator.validate_path_security(test_file)
            mock_validate.assert_called_once_with(test_file)

    def test_validate_video_file_success(self, temp_video_file):
        """Test successful validation of a video file."""
        # Should not raise any exception
        FileValidator.validate_video_file(temp_video_file)

    def test_validate_video_file_nonexistent(self, tmp_path):
        """Test that validate_video_file raises FileNotFoundError for missing files."""
        nonexistent = tmp_path / "nonexistent.mp4"

        with pytest.raises(FileNotFoundError):
            FileValidator.validate_video_file(nonexistent)

    def test_validate_video_file_wrong_extension(self, tmp_path):
        """Test that validate_video_file rejects non-video extensions."""
        wrong_ext = tmp_path / "test.txt"
        wrong_ext.write_text("not a video")

        with pytest.raises(ValueError, match="Unsupported file extension"):
            FileValidator.validate_video_file(wrong_ext)

    def test_validate_video_file_with_max_size(self, temp_video_file):
        """Test validate_video_file with custom max size."""
        # Get actual file size
        actual_size = temp_video_file.stat().st_size

        # Should succeed with larger max_size
        FileValidator.validate_video_file(temp_video_file, max_file_size=actual_size + 1000)

        # Should fail with smaller max_size
        with pytest.raises(ValueError, match="exceeds maximum"):
            FileValidator.validate_video_file(temp_video_file, max_file_size=100)

    def test_validate_video_file_various_extensions(self, tmp_path):
        """Test that all valid video extensions are accepted."""
        for ext in [".mp4", ".avi", ".mov", ".mkv", ".webm"]:
            video_file = tmp_path / f"test{ext}"
            video_file.write_bytes(b"fake_video_data" * 100)

            # Should not raise
            FileValidator.validate_video_file(video_file)

    def test_validate_audio_file_success(self, temp_audio_file):
        """Test successful validation of an audio file."""
        # Should not raise any exception
        FileValidator.validate_audio_file(temp_audio_file)

    def test_validate_audio_file_nonexistent_must_exist_true(self, tmp_path):
        """Test that validate_audio_file raises FileNotFoundError when must_exist=True."""
        nonexistent = tmp_path / "nonexistent.mp3"

        with pytest.raises(FileNotFoundError):
            FileValidator.validate_audio_file(nonexistent, must_exist=True)

    def test_validate_audio_file_nonexistent_must_exist_false(self, tmp_path):
        """Test that validate_audio_file allows nonexistent files when must_exist=False."""
        nonexistent = tmp_path / "future_audio.mp3"

        # Should not raise
        FileValidator.validate_audio_file(nonexistent, must_exist=False)

    def test_validate_audio_file_wrong_extension(self, tmp_path):
        """Test that validate_audio_file rejects non-audio extensions."""
        wrong_ext = tmp_path / "test.txt"
        wrong_ext.write_text("not audio")

        with pytest.raises(ValueError, match="Unsupported file extension"):
            FileValidator.validate_audio_file(wrong_ext)

    def test_validate_audio_file_with_max_size(self, temp_audio_file):
        """Test validate_audio_file with custom max size."""
        actual_size = temp_audio_file.stat().st_size

        # Should succeed with larger max_size
        FileValidator.validate_audio_file(temp_audio_file, max_file_size=actual_size + 1000)

        # Should fail with smaller max_size
        with pytest.raises(ValueError, match="exceeds maximum"):
            FileValidator.validate_audio_file(temp_audio_file, max_file_size=100)

    def test_validate_audio_file_various_extensions(self, tmp_path):
        """Test that all valid audio extensions are accepted."""
        for ext in [".mp3", ".wav", ".flac", ".aac", ".ogg"]:
            audio_file = tmp_path / f"test{ext}"
            audio_file.write_bytes(b"fake_audio_data" * 100)

            # Should not raise
            FileValidator.validate_audio_file(audio_file)

    def test_is_valid_extension_video_files(self, tmp_path):
        """Test is_valid_extension with video files."""
        video_file = tmp_path / "test.mp4"
        assert FileValidator.is_valid_extension(video_file, FileValidator.VIDEO_EXTENSIONS)

        non_video = tmp_path / "test.txt"
        assert not FileValidator.is_valid_extension(non_video, FileValidator.VIDEO_EXTENSIONS)

    def test_is_valid_extension_audio_files(self, tmp_path):
        """Test is_valid_extension with audio files."""
        audio_file = tmp_path / "test.mp3"
        assert FileValidator.is_valid_extension(audio_file, FileValidator.AUDIO_EXTENSIONS)

        non_audio = tmp_path / "test.txt"
        assert not FileValidator.is_valid_extension(non_audio, FileValidator.AUDIO_EXTENSIONS)

    def test_is_valid_extension_case_insensitive(self, tmp_path):
        """Test that is_valid_extension is case-insensitive."""
        upper_ext = tmp_path / "test.MP4"
        assert FileValidator.is_valid_extension(upper_ext, FileValidator.VIDEO_EXTENSIONS)

        mixed_ext = tmp_path / "test.Mp3"
        assert FileValidator.is_valid_extension(mixed_ext, FileValidator.AUDIO_EXTENSIONS)

    def test_is_valid_extension_custom_set(self, tmp_path):
        """Test is_valid_extension with custom extension set."""
        custom_exts = {".custom", ".special"}

        valid_file = tmp_path / "file.custom"
        assert FileValidator.is_valid_extension(valid_file, custom_exts)

        invalid_file = tmp_path / "file.txt"
        assert not FileValidator.is_valid_extension(invalid_file, custom_exts)

    def test_get_file_size_mb_existing_file(self, temp_audio_file):
        """Test get_file_size_mb with an existing file."""
        size_mb = FileValidator.get_file_size_mb(temp_audio_file)

        # Should return a positive value
        assert size_mb > 0

        # Calculate expected size
        actual_bytes = temp_audio_file.stat().st_size
        expected_mb = actual_bytes / (1024 * 1024)

        assert abs(size_mb - expected_mb) < 0.001  # Allow small floating point difference

    def test_get_file_size_mb_nonexistent_file(self, tmp_path):
        """Test get_file_size_mb returns 0.0 for nonexistent files."""
        nonexistent = tmp_path / "nonexistent.mp3"
        size_mb = FileValidator.get_file_size_mb(nonexistent)

        assert size_mb == 0.0

    def test_get_file_size_mb_zero_byte_file(self, tmp_path):
        """Test get_file_size_mb with a zero-byte file."""
        empty_file = tmp_path / "empty.mp3"
        empty_file.write_bytes(b"")

        size_mb = FileValidator.get_file_size_mb(empty_file)
        assert size_mb == 0.0

    def test_get_file_size_mb_large_file(self, tmp_path):
        """Test get_file_size_mb with a larger file."""
        large_file = tmp_path / "large.mp4"
        # Create a ~5MB file
        large_file.write_bytes(b"x" * (5 * 1024 * 1024))

        size_mb = FileValidator.get_file_size_mb(large_file)
        assert 4.9 < size_mb < 5.1  # Should be approximately 5MB

    def test_get_file_size_mb_handles_permission_error(self, tmp_path):
        """Test that get_file_size_mb returns 0.0 on permission errors."""
        test_file = tmp_path / "test.mp3"
        test_file.write_bytes(b"test")

        with patch.object(Path, "stat") as mock_stat:
            mock_stat.side_effect = PermissionError("Access denied")
            size_mb = FileValidator.get_file_size_mb(test_file)
            assert size_mb == 0.0

    def test_get_file_size_mb_handles_os_error(self, tmp_path):
        """Test that get_file_size_mb returns 0.0 on OS errors."""
        test_file = tmp_path / "test.mp3"

        with patch.object(Path, "exists", return_value=True):
            with patch.object(Path, "stat") as mock_stat:
                mock_stat.side_effect = OSError("Disk error")
                size_mb = FileValidator.get_file_size_mb(test_file)
                assert size_mb == 0.0

    def test_validate_video_file_inherits_from_common(self):
        """Test that FileValidator properly inherits from CommonFileValidator."""
        # FileValidator should have methods from CommonFileValidator
        assert hasattr(FileValidator, "validate_file_path")
        assert hasattr(FileValidator, "validate_media_file")
        assert hasattr(FileValidator, "DEFAULT_MAX_FILE_SIZE")

    def test_default_max_file_size_constant(self):
        """Test that DEFAULT_MAX_FILE_SIZE is 2GB."""
        assert FileValidator.DEFAULT_MAX_FILE_SIZE == 2 * 1024 * 1024 * 1024

    def test_validate_video_file_uses_default_max_size(self, temp_video_file):
        """Test that validate_video_file uses default max size when not specified."""
        with patch.object(FileValidator, "validate_file_path") as mock_validate:
            FileValidator.validate_video_file(temp_video_file)

            # Check that validate_file_path was called with default max size
            call_kwargs = mock_validate.call_args[1]
            assert call_kwargs["max_size"] == FileValidator.DEFAULT_MAX_FILE_SIZE

    def test_validate_audio_file_uses_default_max_size(self, temp_audio_file):
        """Test that validate_audio_file uses default max size when not specified."""
        with patch.object(FileValidator, "validate_file_path") as mock_validate:
            FileValidator.validate_audio_file(temp_audio_file)

            # Check that validate_file_path was called with default max size
            call_kwargs = mock_validate.call_args[1]
            assert call_kwargs["max_size"] == FileValidator.DEFAULT_MAX_FILE_SIZE


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_validate_audio_file_boundary_max_size(self, tmp_path):
        """Test validate_audio_file at exact max size boundary."""
        audio_file = tmp_path / "exact_size.mp3"
        test_size = 1000
        audio_file.write_bytes(b"x" * test_size)

        # Should succeed at exact boundary
        FileValidator.validate_audio_file(audio_file, max_file_size=test_size)

        # Should fail at one byte over
        with pytest.raises(ValueError, match="exceeds maximum"):
            FileValidator.validate_audio_file(audio_file, max_file_size=test_size - 1)

    def test_is_valid_extension_empty_extension(self, tmp_path):
        """Test is_valid_extension with file that has no extension."""
        no_ext = tmp_path / "noextension"
        assert not FileValidator.is_valid_extension(no_ext, FileValidator.VIDEO_EXTENSIONS)
        assert not FileValidator.is_valid_extension(no_ext, FileValidator.AUDIO_EXTENSIONS)

    def test_is_valid_extension_dot_only(self, tmp_path):
        """Test is_valid_extension with filename ending in just a dot."""
        dot_only = tmp_path / "file."
        assert not FileValidator.is_valid_extension(dot_only, FileValidator.VIDEO_EXTENSIONS)

    def test_get_file_size_mb_symlink(self, tmp_path):
        """Test get_file_size_mb with symbolic links."""
        real_file = tmp_path / "real.mp3"
        real_file.write_bytes(b"x" * 1024 * 1024)  # 1MB

        symlink = tmp_path / "link.mp3"
        symlink.symlink_to(real_file)

        # Should follow symlink and get size
        size_mb = FileValidator.get_file_size_mb(symlink)
        assert 0.9 < size_mb < 1.1

    def test_validate_path_with_unicode_characters(self, tmp_path):
        """Test validation with Unicode characters in filename."""
        unicode_file = tmp_path / "test_文件.mp4"
        unicode_file.write_bytes(b"test")

        # Should handle Unicode filenames
        FileValidator.validate_video_file(unicode_file)

    def test_validate_path_with_spaces(self, tmp_path):
        """Test validation with spaces in filename."""
        spaced_file = tmp_path / "test file with spaces.mp3"
        spaced_file.write_bytes(b"test")

        # Should handle spaces in filenames
        FileValidator.validate_audio_file(spaced_file)
