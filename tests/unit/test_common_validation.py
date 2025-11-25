"""Tests for common validation utilities."""

from pathlib import Path

import pytest

from src.utils.file_validation import (
    ConfigValidator,
    FileValidator,
    validate_file_path,
    validate_media_file,
    validate_output_path,
)


class TestFileValidatorBasicChecks:
    """Tests for FileValidator basic validation methods."""

    def test_check_file_existence_valid(self, tmp_path):
        """Test that existing file passes existence check."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        # Should not raise
        FileValidator._check_file_existence(test_file)

    def test_check_file_existence_missing(self, tmp_path):
        """Test that missing file raises FileNotFoundError."""
        test_file = tmp_path / "missing.txt"

        with pytest.raises(FileNotFoundError, match="File not found"):
            FileValidator._check_file_existence(test_file)

    def test_check_file_extension_valid(self, tmp_path):
        """Test that valid extension passes check."""
        test_file = tmp_path / "test.mp3"

        # Should not raise
        FileValidator._check_file_extension(test_file, {".mp3", ".wav"})

    def test_check_file_extension_invalid(self, tmp_path):
        """Test that invalid extension raises ValueError."""
        test_file = tmp_path / "test.xyz"

        with pytest.raises(ValueError, match="Unsupported file extension"):
            FileValidator._check_file_extension(test_file, {".mp3", ".wav"})

    def test_check_file_extension_case_insensitive(self, tmp_path):
        """Test that extension check is case-insensitive."""
        test_file = tmp_path / "test.MP3"

        # Should not raise (case-insensitive)
        FileValidator._check_file_extension(test_file, {".mp3", ".wav"})

    def test_check_file_size_valid(self, tmp_path):
        """Test that file within size limit passes check."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("small content")

        # Should not raise
        FileValidator._check_file_size(test_file, max_size=1024)

    def test_check_file_size_exceeds_limit(self, tmp_path):
        """Test that oversized file raises ValueError."""
        test_file = tmp_path / "test.txt"
        test_file.write_bytes(b"x" * 2000)

        with pytest.raises(ValueError, match="exceeds maximum"):
            FileValidator._check_file_size(test_file, max_size=1000)

    def test_check_file_type_valid(self, tmp_path):
        """Test that regular file passes type check."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        # Should not raise
        FileValidator._check_file_type(test_file)

    def test_check_file_type_directory(self, tmp_path):
        """Test that directory raises ValueError."""
        test_dir = tmp_path / "testdir"
        test_dir.mkdir()

        with pytest.raises(ValueError, match="not a file"):
            FileValidator._check_file_type(test_dir)

    def test_check_file_permissions_readable(self, tmp_path):
        """Test that readable file passes permission check."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        # Should not raise
        FileValidator._check_file_permissions(test_file)

    def test_check_file_permissions_unreadable(self, tmp_path):
        """Test that unreadable file raises PermissionError."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")
        test_file.chmod(0o000)

        try:
            with pytest.raises(PermissionError, match="Cannot read file"):
                FileValidator._check_file_permissions(test_file)
        finally:
            # Restore permissions for cleanup
            test_file.chmod(0o644)


class TestFileValidatorValidateFilePath:
    """Tests for FileValidator.validate_file_path method."""

    def test_validate_existing_file(self, tmp_path):
        """Test validation of existing file with default settings."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        # Should not raise
        FileValidator.validate_file_path(test_file)

    def test_validate_non_existing_file_must_exist(self, tmp_path):
        """Test that non-existing file raises error when must_exist=True."""
        test_file = tmp_path / "missing.txt"

        with pytest.raises(FileNotFoundError):
            FileValidator.validate_file_path(test_file, must_exist=True)

    def test_validate_non_existing_file_optional(self, tmp_path):
        """Test that non-existing file passes when must_exist=False."""
        test_file = tmp_path / "missing.txt"

        # Should not raise
        FileValidator.validate_file_path(test_file, must_exist=False)

    def test_validate_with_allowed_extensions(self, tmp_path):
        """Test validation with extension whitelist."""
        test_file = tmp_path / "test.mp3"
        test_file.write_text("content")

        # Should not raise
        FileValidator.validate_file_path(test_file, allowed_extensions={".mp3", ".wav"})

    def test_validate_with_disallowed_extension(self, tmp_path):
        """Test that disallowed extension raises ValueError."""
        test_file = tmp_path / "test.xyz"
        test_file.write_text("content")

        with pytest.raises(ValueError, match="Unsupported file extension"):
            FileValidator.validate_file_path(test_file, allowed_extensions={".mp3", ".wav"})

    def test_validate_with_max_size(self, tmp_path):
        """Test validation with file size limit."""
        test_file = tmp_path / "test.txt"
        test_file.write_bytes(b"x" * 500)

        # Should not raise
        FileValidator.validate_file_path(test_file, max_size=1000)

    def test_validate_exceeds_max_size(self, tmp_path):
        """Test that oversized file raises ValueError."""
        test_file = tmp_path / "test.txt"
        test_file.write_bytes(b"x" * 2000)

        with pytest.raises(ValueError, match="exceeds maximum"):
            FileValidator.validate_file_path(test_file, max_size=1000)

    def test_validate_size_check_skipped_when_not_exists(self, tmp_path):
        """Test that size check is skipped when file doesn't exist."""
        test_file = tmp_path / "missing.txt"

        # Should not raise (size check requires file to exist)
        FileValidator.validate_file_path(test_file, must_exist=False, max_size=100)

    def test_validate_directory_fails(self, tmp_path):
        """Test that directory path raises ValueError."""
        test_dir = tmp_path / "testdir"
        test_dir.mkdir()

        with pytest.raises(ValueError, match="not a file"):
            FileValidator.validate_file_path(test_dir)

    def test_validate_path_security_integration(self, tmp_path):
        """Test that path security validation is performed."""
        # Create a path with dangerous characters
        with pytest.raises(ValueError, match="Invalid characters"):
            FileValidator.validate_file_path(Path("/path/with;semicolon"), must_exist=False)

    def test_validate_string_path_converted(self, tmp_path):
        """Test that string paths are converted to Path objects."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        # Should accept string and convert to Path
        FileValidator.validate_file_path(str(test_file))


class TestFileValidatorValidateMediaFile:
    """Tests for FileValidator.validate_media_file method."""

    def test_validate_audio_file_mp3(self, tmp_path):
        """Test validation of MP3 audio file."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake_audio" * 100)

        # Should not raise
        FileValidator.validate_media_file(audio_file)

    def test_validate_audio_file_wav(self, tmp_path):
        """Test validation of WAV audio file."""
        audio_file = tmp_path / "test.wav"
        audio_file.write_bytes(b"fake_audio" * 100)

        # Should not raise
        FileValidator.validate_media_file(audio_file)

    def test_validate_video_file_mp4(self, tmp_path):
        """Test validation of MP4 video file."""
        video_file = tmp_path / "test.mp4"
        video_file.write_bytes(b"fake_video" * 100)

        # Should not raise
        FileValidator.validate_media_file(video_file)

    def test_validate_all_audio_extensions(self, tmp_path):
        """Test all supported audio extensions."""
        for ext in FileValidator.AUDIO_EXTENSIONS:
            audio_file = tmp_path / f"test{ext}"
            audio_file.write_bytes(b"fake_audio" * 100)

            # Should not raise for any audio extension
            FileValidator.validate_media_file(audio_file)
            audio_file.unlink()

    def test_validate_all_video_extensions(self, tmp_path):
        """Test all supported video extensions."""
        for ext in FileValidator.VIDEO_EXTENSIONS:
            video_file = tmp_path / f"test{ext}"
            video_file.write_bytes(b"fake_video" * 100)

            # Should not raise for any video extension
            FileValidator.validate_media_file(video_file)
            video_file.unlink()

    def test_validate_unsupported_extension(self, tmp_path):
        """Test that unsupported file extension raises ValueError."""
        invalid_file = tmp_path / "test.xyz"
        invalid_file.write_text("content")

        with pytest.raises(ValueError, match="Unsupported file extension"):
            FileValidator.validate_media_file(invalid_file)

    def test_validate_media_missing_file(self, tmp_path):
        """Test that missing media file raises FileNotFoundError."""
        missing_file = tmp_path / "missing.mp4"

        with pytest.raises(FileNotFoundError):
            FileValidator.validate_media_file(missing_file)

    def test_validate_media_with_custom_size(self, tmp_path):
        """Test validation with custom max size."""
        media_file = tmp_path / "test.mp4"
        media_file.write_bytes(b"x" * 500)

        # Should not raise
        FileValidator.validate_media_file(media_file, max_size=1000)

    def test_validate_media_exceeds_custom_size(self, tmp_path):
        """Test that media file exceeding custom size raises ValueError."""
        media_file = tmp_path / "test.mp4"
        media_file.write_bytes(b"x" * 2000)

        with pytest.raises(ValueError, match="exceeds maximum"):
            FileValidator.validate_media_file(media_file, max_size=1000)

    def test_validate_media_default_size_limit(self, tmp_path):
        """Test that default size limit (2GB) is applied."""
        media_file = tmp_path / "test.mp4"
        media_file.write_bytes(b"x" * 1000)

        # Should use DEFAULT_MAX_FILE_SIZE when max_size not specified
        FileValidator.validate_media_file(media_file)


class TestFileValidatorValidateOutputPath:
    """Tests for FileValidator.validate_output_path method."""

    def test_validate_new_output_path(self, tmp_path):
        """Test validation of new output path."""
        output_file = tmp_path / "output.txt"

        # Should not raise
        FileValidator.validate_output_path(output_file)

    def test_validate_existing_output_without_force(self, tmp_path):
        """Test that existing file raises FileExistsError without force."""
        output_file = tmp_path / "output.txt"
        output_file.write_text("existing")

        with pytest.raises(FileExistsError, match="already exists"):
            FileValidator.validate_output_path(output_file, force=False)

    def test_validate_existing_output_with_force(self, tmp_path):
        """Test that existing file is allowed with force=True."""
        output_file = tmp_path / "output.txt"
        output_file.write_text("existing")

        # Should not raise
        FileValidator.validate_output_path(output_file, force=True)

    def test_validate_creates_parent_directories(self, tmp_path):
        """Test that parent directories are created."""
        output_file = tmp_path / "level1" / "level2" / "output.txt"

        FileValidator.validate_output_path(output_file, create_parents=True)

        # Parent directories should exist
        assert output_file.parent.exists()
        assert output_file.parent.is_dir()

    def test_validate_without_creating_parents(self, tmp_path):
        """Test that missing parent raises error without create_parents."""
        output_file = tmp_path / "missing" / "output.txt"

        with pytest.raises(ValueError, match="does not exist"):
            FileValidator.validate_output_path(output_file, create_parents=False)

    def test_validate_parent_is_file(self, tmp_path):
        """Test that error is raised if parent is a file."""
        parent_file = tmp_path / "parent.txt"
        parent_file.write_text("content")
        output_file = parent_file / "output.txt"

        with pytest.raises(ValueError, match="not a directory"):
            FileValidator.validate_output_path(output_file, create_parents=False)

    def test_validate_write_permissions(self, tmp_path):
        """Test that write permissions are checked."""
        output_file = tmp_path / "output.txt"

        # Should not raise with writable directory
        FileValidator.validate_output_path(output_file)

        # Verify test file is cleaned up
        test_file = output_file.parent / f".write_test_{output_file.name}"
        assert not test_file.exists()

    def test_validate_no_write_permissions(self, tmp_path):
        """Test that permission error is raised for read-only directory."""
        read_only_dir = tmp_path / "readonly"
        read_only_dir.mkdir()
        read_only_dir.chmod(0o444)
        output_file = read_only_dir / "output.txt"

        try:
            # Permission error can occur either when checking if file exists
            # or when testing write permissions
            with pytest.raises(PermissionError):
                FileValidator.validate_output_path(output_file, create_parents=False)
        finally:
            # Restore permissions for cleanup
            read_only_dir.chmod(0o755)

    def test_validate_output_security_integration(self):
        """Test that path security validation is performed."""
        with pytest.raises(ValueError, match="Invalid characters"):
            FileValidator.validate_output_path(Path("/path/with|pipe"))

    def test_validate_string_path_converted(self, tmp_path):
        """Test that string paths are converted to Path objects."""
        output_file = str(tmp_path / "output.txt")

        # Should accept string and convert to Path
        FileValidator.validate_output_path(output_file)


class TestConfigValidatorPositiveNumber:
    """Tests for ConfigValidator.validate_positive_number method."""

    def test_validate_positive_integer(self):
        """Test validation of positive integer."""
        # Should not raise
        ConfigValidator.validate_positive_number(5, "test_param")

    def test_validate_positive_float(self):
        """Test validation of positive float."""
        # Should not raise
        ConfigValidator.validate_positive_number(3.14, "test_param")

    def test_validate_zero_fails(self):
        """Test that zero raises ValueError."""
        with pytest.raises(ValueError, match="must be positive"):
            ConfigValidator.validate_positive_number(0, "test_param")

    def test_validate_negative_fails(self):
        """Test that negative number raises ValueError."""
        with pytest.raises(ValueError, match="must be positive"):
            ConfigValidator.validate_positive_number(-5, "test_param")

    def test_validate_negative_float_fails(self):
        """Test that negative float raises ValueError."""
        with pytest.raises(ValueError, match="must be positive"):
            ConfigValidator.validate_positive_number(-0.1, "test_param")

    def test_validate_small_positive(self):
        """Test validation of very small positive number."""
        # Should not raise
        ConfigValidator.validate_positive_number(0.0001, "test_param")

    def test_error_message_includes_name(self):
        """Test that error message includes parameter name."""
        with pytest.raises(ValueError, match="my_param must be positive"):
            ConfigValidator.validate_positive_number(-1, "my_param")


class TestConfigValidatorRange:
    """Tests for ConfigValidator.validate_range method."""

    def test_validate_value_in_range(self):
        """Test validation of value within range."""
        # Should not raise
        ConfigValidator.validate_range(5, min_val=0, max_val=10)

    def test_validate_value_at_min_boundary(self):
        """Test that value at minimum boundary is accepted."""
        # Should not raise (inclusive)
        ConfigValidator.validate_range(0, min_val=0, max_val=10)

    def test_validate_value_at_max_boundary(self):
        """Test that value at maximum boundary is accepted."""
        # Should not raise (inclusive)
        ConfigValidator.validate_range(10, min_val=0, max_val=10)

    def test_validate_value_below_min(self):
        """Test that value below minimum raises ValueError."""
        with pytest.raises(ValueError, match="must be at least 0"):
            ConfigValidator.validate_range(-1, min_val=0, max_val=10)

    def test_validate_value_above_max(self):
        """Test that value above maximum raises ValueError."""
        with pytest.raises(ValueError, match="must be at most 10"):
            ConfigValidator.validate_range(11, min_val=0, max_val=10)

    def test_validate_only_min_specified(self):
        """Test validation with only minimum bound."""
        # Should not raise
        ConfigValidator.validate_range(100, min_val=0)

        # Should raise
        with pytest.raises(ValueError, match="must be at least 0"):
            ConfigValidator.validate_range(-1, min_val=0)

    def test_validate_only_max_specified(self):
        """Test validation with only maximum bound."""
        # Should not raise
        ConfigValidator.validate_range(-100, max_val=0)

        # Should raise
        with pytest.raises(ValueError, match="must be at most 0"):
            ConfigValidator.validate_range(1, max_val=0)

    def test_validate_no_bounds_specified(self):
        """Test validation with no bounds (should always pass)."""
        # Should not raise for any value
        ConfigValidator.validate_range(999999)
        ConfigValidator.validate_range(-999999)

    def test_validate_float_values(self):
        """Test validation with float values."""
        # Should not raise
        ConfigValidator.validate_range(3.14, min_val=0.0, max_val=10.0)

        # Should raise
        with pytest.raises(ValueError):
            ConfigValidator.validate_range(10.1, min_val=0.0, max_val=10.0)

    def test_error_message_includes_custom_name(self):
        """Test that error message includes custom parameter name."""
        with pytest.raises(ValueError, match="custom_param must be at least 5"):
            ConfigValidator.validate_range(3, min_val=5, name="custom_param")


class TestConfigValidatorEnum:
    """Tests for ConfigValidator.validate_enum method."""

    def test_validate_value_in_set(self):
        """Test validation of value in allowed set."""
        allowed = {"option1", "option2", "option3"}

        # Should not raise
        ConfigValidator.validate_enum("option1", allowed)

    def test_validate_value_not_in_set(self):
        """Test that value not in set raises ValueError."""
        allowed = {"option1", "option2", "option3"}

        with pytest.raises(ValueError, match="must be one of"):
            ConfigValidator.validate_enum("invalid", allowed)

    def test_validate_case_sensitive(self):
        """Test that validation is case-sensitive."""
        allowed = {"option1", "option2"}

        # Should raise (case matters)
        with pytest.raises(ValueError, match="must be one of"):
            ConfigValidator.validate_enum("OPTION1", allowed)

    def test_validate_empty_allowed_set(self):
        """Test validation with empty allowed set."""
        with pytest.raises(ValueError, match="must be one of"):
            ConfigValidator.validate_enum("anything", set())

    def test_validate_single_allowed_value(self):
        """Test validation with single allowed value."""
        allowed = {"only_option"}

        # Should not raise
        ConfigValidator.validate_enum("only_option", allowed)

        # Should raise
        with pytest.raises(ValueError):
            ConfigValidator.validate_enum("other", allowed)

    def test_error_message_includes_allowed_values(self):
        """Test that error message shows allowed values."""
        allowed = {"a", "b", "c"}

        with pytest.raises(ValueError, match=r"\['a', 'b', 'c'\]"):
            ConfigValidator.validate_enum("d", allowed)

    def test_error_message_includes_custom_name(self):
        """Test that error message includes custom parameter name."""
        allowed = {"valid"}

        with pytest.raises(ValueError, match="custom_param must be one of"):
            ConfigValidator.validate_enum("invalid", allowed, name="custom_param")

    def test_error_message_shows_received_value(self):
        """Test that error message shows the received value."""
        allowed = {"valid"}

        with pytest.raises(ValueError, match="got 'invalid'"):
            ConfigValidator.validate_enum("invalid", allowed)


class TestConvenienceFunctions:
    """Tests for backward compatibility convenience functions."""

    def test_validate_file_path_function(self, tmp_path):
        """Test validate_file_path convenience function."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        # Should delegate to FileValidator.validate_file_path
        validate_file_path(test_file)

    def test_validate_file_path_function_with_args(self, tmp_path):
        """Test that convenience function passes arguments correctly."""
        test_file = tmp_path / "test.mp3"
        test_file.write_text("content")

        # Should pass kwargs to FileValidator
        validate_file_path(test_file, allowed_extensions={".mp3"})

    def test_validate_media_file_function(self, tmp_path):
        """Test validate_media_file convenience function."""
        media_file = tmp_path / "test.mp4"
        media_file.write_bytes(b"fake_video" * 100)

        # Should delegate to FileValidator.validate_media_file
        validate_media_file(media_file)

    def test_validate_media_file_function_with_args(self, tmp_path):
        """Test that media convenience function passes arguments."""
        media_file = tmp_path / "test.mp4"
        media_file.write_bytes(b"x" * 500)

        # Should pass kwargs to FileValidator
        validate_media_file(media_file, max_size=1000)

    def test_validate_output_path_function(self, tmp_path):
        """Test validate_output_path convenience function."""
        output_file = tmp_path / "output.txt"

        # Should delegate to FileValidator.validate_output_path
        validate_output_path(output_file)

    def test_validate_output_path_function_with_args(self, tmp_path):
        """Test that output convenience function passes arguments."""
        output_file = tmp_path / "output.txt"
        output_file.write_text("existing")

        # Should pass kwargs to FileValidator
        validate_output_path(output_file, force=True)


class TestFileValidatorConstants:
    """Tests for FileValidator class constants."""

    def test_audio_extensions_defined(self):
        """Test that audio extensions are properly defined."""
        assert len(FileValidator.AUDIO_EXTENSIONS) > 0
        assert ".mp3" in FileValidator.AUDIO_EXTENSIONS
        assert ".wav" in FileValidator.AUDIO_EXTENSIONS
        assert ".flac" in FileValidator.AUDIO_EXTENSIONS

    def test_video_extensions_defined(self):
        """Test that video extensions are properly defined."""
        assert len(FileValidator.VIDEO_EXTENSIONS) > 0
        assert ".mp4" in FileValidator.VIDEO_EXTENSIONS
        assert ".avi" in FileValidator.VIDEO_EXTENSIONS
        assert ".mkv" in FileValidator.VIDEO_EXTENSIONS

    def test_media_extensions_is_union(self):
        """Test that MEDIA_EXTENSIONS is union of audio and video."""
        assert FileValidator.MEDIA_EXTENSIONS == (
            FileValidator.AUDIO_EXTENSIONS | FileValidator.VIDEO_EXTENSIONS
        )

    def test_default_max_file_size(self):
        """Test that default max file size is 2GB."""
        expected_size = 2 * 1024 * 1024 * 1024  # 2GB
        assert FileValidator.DEFAULT_MAX_FILE_SIZE == expected_size

    def test_all_extensions_lowercase(self):
        """Test that all extensions are lowercase with dot."""
        for ext in FileValidator.MEDIA_EXTENSIONS:
            assert ext.startswith(".")
            assert ext == ext.lower()


class TestEdgeCases:
    """Tests for edge cases and special scenarios."""

    def test_validate_symlink_file(self, tmp_path):
        """Test validation of symlink to file."""
        target = tmp_path / "target.txt"
        target.write_text("content")
        link = tmp_path / "link.txt"
        link.symlink_to(target)

        # Should follow symlink and validate
        FileValidator.validate_file_path(link)

    def test_validate_very_long_filename(self, tmp_path):
        """Test validation with very long filename."""
        # Create file with long name
        long_name = "a" * 200 + ".mp3"
        audio_file = tmp_path / long_name
        audio_file.write_bytes(b"audio")

        # Should handle long filenames
        FileValidator.validate_media_file(audio_file)

    def test_validate_unicode_filename(self, tmp_path):
        """Test validation with unicode characters in filename."""
        unicode_file = tmp_path / "тест_файл.mp3"
        unicode_file.write_bytes(b"audio")

        # Should handle unicode
        FileValidator.validate_media_file(unicode_file)

    def test_validate_file_with_no_extension(self, tmp_path):
        """Test validation of file with no extension."""
        no_ext_file = tmp_path / "noextension"
        no_ext_file.write_text("content")

        # Should fail for media validation (requires extension)
        with pytest.raises(ValueError, match="Unsupported file extension"):
            FileValidator.validate_media_file(no_ext_file)

    def test_validate_hidden_file(self, tmp_path):
        """Test validation of hidden file (starting with dot)."""
        hidden_file = tmp_path / ".hidden.mp3"
        hidden_file.write_bytes(b"audio")

        # Should validate hidden files normally
        FileValidator.validate_media_file(hidden_file)

    def test_validate_with_multiple_dots(self, tmp_path):
        """Test validation of filename with multiple dots."""
        multi_dot = tmp_path / "file.name.with.dots.mp3"
        multi_dot.write_bytes(b"audio")

        # Should use last extension
        FileValidator.validate_media_file(multi_dot)

    def test_config_validate_with_infinity(self):
        """Test range validation with infinity values."""
        import math

        # Should handle infinity
        ConfigValidator.validate_range(100, max_val=math.inf)
        ConfigValidator.validate_range(-100, min_val=-math.inf)

    def test_config_validate_with_nan(self):
        """Test that NaN values pass through range validation (quirk of NaN comparisons)."""
        import math

        # NaN comparisons always return False, including NaN < min and NaN > max
        # This means NaN values will pass range validation (Python quirk)
        # This test documents this behavior rather than enforcing it
        ConfigValidator.validate_range(math.nan, min_val=0, max_val=10)

        # This is expected behavior - if you need to reject NaN,
        # you should check for it explicitly before calling validate_range
