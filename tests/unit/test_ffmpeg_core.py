"""Unit tests for ffmpeg_core.py - FFmpeg command construction.

Tests cover:
- Base command construction
- All quality presets (SPEECH, STANDARD, HIGH, COMPRESSED)
- Two-step SPEECH pipeline (extract + normalize)
- Path handling with spaces and special characters
- Command injection prevention
- -y flag presence to prevent hangs
"""

from pathlib import Path

from src.services.ffmpeg_core import build_base_cmd, build_extract_commands


class TestBuildBaseCmd:
    """Tests for build_base_cmd - base ffmpeg command construction."""

    def test_base_cmd_structure(self):
        """Verify base command has correct structure with -y flag."""
        input_path = Path("/test/input.mp4")
        cmd = build_base_cmd(input_path)

        assert cmd[0] == "ffmpeg"
        assert "-i" in cmd
        assert "-y" in cmd
        assert str(input_path) in cmd

    def test_base_cmd_overwrite_flag(self):
        """Verify -y flag is present to prevent interactive prompts."""
        input_path = Path("/test/video.mp4")
        cmd = build_base_cmd(input_path)

        assert "-y" in cmd, "Missing -y flag - could cause hangs on file overwrites"

    def test_base_cmd_path_with_spaces(self):
        """Test path handling with spaces in filename."""
        input_path = Path("/test/my video file.mp4")
        cmd = build_base_cmd(input_path)

        # Path is converted to string, shell quoting is handled by subprocess
        assert str(input_path) in cmd
        assert "my video file.mp4" in str(input_path)

    def test_base_cmd_path_with_special_chars(self):
        """Test path handling with special characters."""
        input_path = Path("/test/file (1) [copy].mp4")
        cmd = build_base_cmd(input_path)

        assert str(input_path) in cmd
        assert "file (1) [copy].mp4" in str(input_path)


class TestBuildExtractCommands:
    """Tests for build_extract_commands - quality-specific command generation."""

    def test_high_quality_single_command(self):
        """Test HIGH quality preset returns single 320k bitrate command."""
        input_path = Path("/test/input.mp4")
        output_path = Path("/test/output.mp3")

        commands, temp_path = build_extract_commands(input_path, output_path, "high")

        assert len(commands) == 1, "HIGH preset should use single-step extraction"
        assert temp_path is None, "HIGH preset should not use temp file"

        cmd = commands[0]
        assert "ffmpeg" in cmd
        assert "-y" in cmd
        assert "-b:a" in cmd
        assert "320k" in cmd
        assert "-map" in cmd
        assert "a" in cmd
        assert str(output_path) in cmd

    def test_standard_quality_single_command(self):
        """Test STANDARD quality preset returns single best-quality command."""
        input_path = Path("/test/input.mp4")
        output_path = Path("/test/output.mp3")

        commands, temp_path = build_extract_commands(input_path, output_path, "standard")

        assert len(commands) == 1, "STANDARD preset should use single-step extraction"
        assert temp_path is None, "STANDARD preset should not use temp file"

        cmd = commands[0]
        assert "ffmpeg" in cmd
        assert "-y" in cmd
        assert "-q:a" in cmd
        assert "0" in cmd
        assert "-map" in cmd
        assert "a" in cmd
        assert str(output_path) in cmd

    def test_compressed_quality_single_command(self):
        """Test COMPRESSED quality preset returns single 128k bitrate command."""
        input_path = Path("/test/input.mp4")
        output_path = Path("/test/output.mp3")

        commands, temp_path = build_extract_commands(input_path, output_path, "compressed")

        assert len(commands) == 1, "COMPRESSED preset should use single-step extraction"
        assert temp_path is None, "COMPRESSED preset should not use temp file"

        cmd = commands[0]
        assert "ffmpeg" in cmd
        assert "-y" in cmd
        assert "-b:a" in cmd
        assert "128k" in cmd
        assert "-map" in cmd
        assert "a" in cmd
        assert str(output_path) in cmd

    def test_speech_quality_two_step_pipeline(self):
        """Test SPEECH quality preset returns two-step extract + normalize pipeline."""
        input_path = Path("/test/input.mp4")
        output_path = Path("/test/output.mp3")

        commands, temp_path = build_extract_commands(input_path, output_path, "speech")

        assert len(commands) == 2, "SPEECH preset should use two-step pipeline"
        assert temp_path is not None, "SPEECH preset should use temp file"
        assert temp_path.suffix == ".mp3"
        assert ".temp." in str(temp_path)

        # Verify extraction command (step 1)
        extract_cmd = commands[0]
        assert "ffmpeg" in extract_cmd
        assert "-y" in extract_cmd
        assert "-q:a" in extract_cmd
        assert "0" in extract_cmd
        assert "-map" in extract_cmd
        assert "a" in extract_cmd
        assert str(temp_path) in extract_cmd

        # Verify normalization command (step 2)
        normalize_cmd = commands[1]
        normalize_str = " ".join(normalize_cmd)
        assert "ffmpeg" in normalize_cmd
        assert "-y" in normalize_cmd
        assert "-ac" in normalize_cmd
        assert "1" in normalize_cmd  # mono conversion
        assert "-af" in normalize_cmd
        assert "loudnorm" in normalize_str
        assert "I=-16" in normalize_str
        assert "TP=-1.5" in normalize_str
        assert "LRA=11" in normalize_str
        assert str(output_path) in normalize_cmd

    def test_default_quality_is_speech(self):
        """Test that unrecognized quality defaults to SPEECH behavior."""
        input_path = Path("/test/input.mp4")
        output_path = Path("/test/output.mp3")

        # Test with various invalid quality strings
        for invalid_quality in ["unknown", "UNKNOWN", "", "ultra", None]:
            commands, temp_path = build_extract_commands(input_path, output_path, invalid_quality)

            assert (
                len(commands) == 2
            ), f"Quality '{invalid_quality}' should default to SPEECH (two-step)"
            assert (
                temp_path is not None
            ), f"Quality '{invalid_quality}' should use temp file like SPEECH"

    def test_speech_temp_path_naming(self):
        """Verify SPEECH preset creates correctly named temp file."""
        input_path = Path("/test/input.mp4")
        output_path = Path("/test/audio/final.mp3")

        _commands, temp_path = build_extract_commands(input_path, output_path, "speech")

        assert temp_path.parent == output_path.parent
        assert temp_path.name == "final.temp.mp3"
        assert temp_path != output_path

    def test_all_commands_have_overwrite_flag(self):
        """Verify all quality presets include -y flag to prevent hangs."""
        input_path = Path("/test/input.mp4")
        output_path = Path("/test/output.mp3")

        for quality in ["high", "standard", "compressed", "speech"]:
            commands, _ = build_extract_commands(input_path, output_path, quality)

            for cmd in commands:
                assert (
                    "-y" in cmd
                ), f"Missing -y flag in {quality} preset - could hang on overwrites"

    def test_path_with_spaces_in_commands(self):
        """Test that paths with spaces are properly handled in commands."""
        input_path = Path("/test/my video file.mp4")
        output_path = Path("/test/my audio file.mp3")

        # Test with all quality presets
        for quality in ["high", "standard", "compressed", "speech"]:
            commands, _temp_path = build_extract_commands(input_path, output_path, quality)

            # Verify input path in first command
            assert str(input_path) in " ".join(commands[0])

            # Verify output path in final command
            final_cmd = commands[-1]
            if quality == "speech":
                # For speech, output_path is in normalize command
                assert str(output_path) in " ".join(final_cmd)
            else:
                assert str(output_path) in " ".join(final_cmd)

    def test_path_with_special_chars_in_commands(self):
        """Test command injection prevention with special characters."""
        # Potential command injection characters
        input_path = Path("/test/file;rm -rf.mp4")
        output_path = Path("/test/output$(whoami).mp3")

        commands, _ = build_extract_commands(input_path, output_path, "standard")

        # Paths should be treated as single string arguments
        # subprocess.run with list args prevents shell injection
        assert str(input_path) in commands[0]
        assert str(output_path) in commands[0]

        # Command structure should still be intact
        assert "ffmpeg" in commands[0]
        assert "-i" in commands[0]

    def test_quality_case_sensitivity(self):
        """Test that quality presets are case-sensitive."""
        input_path = Path("/test/input.mp4")
        output_path = Path("/test/output.mp3")

        # Uppercase should default to SPEECH (two-step)
        commands_upper, _temp_upper = build_extract_commands(input_path, output_path, "HIGH")
        assert len(commands_upper) == 2, "Uppercase 'HIGH' should default to SPEECH"

        # Lowercase should use specific preset (single-step)
        commands_lower, _temp_lower = build_extract_commands(input_path, output_path, "high")
        assert len(commands_lower) == 1, "Lowercase 'high' should use HIGH preset"

    def test_audio_map_parameter_in_all_presets(self):
        """Verify all presets use -map a to extract audio stream."""
        input_path = Path("/test/input.mp4")
        output_path = Path("/test/output.mp3")

        for quality in ["high", "standard", "compressed", "speech"]:
            commands, _ = build_extract_commands(input_path, output_path, quality)

            # First command (extraction) should always have -map a
            first_cmd = commands[0]
            assert "-map" in first_cmd
            assert "a" in first_cmd

    def test_speech_normalization_parameters(self):
        """Verify SPEECH preset normalization has correct loudness parameters."""
        input_path = Path("/test/input.mp4")
        output_path = Path("/test/output.mp3")

        commands, _ = build_extract_commands(input_path, output_path, "speech")
        normalize_cmd = commands[1]

        # Check loudnorm filter parameters
        af_filter = None
        for i, arg in enumerate(normalize_cmd):
            if arg == "-af" and i + 1 < len(normalize_cmd):
                af_filter = normalize_cmd[i + 1]
                break

        assert af_filter is not None, "-af parameter not found in normalize command"
        assert "loudnorm" in af_filter
        assert "I=-16" in af_filter  # Integrated loudness target
        assert "TP=-1.5" in af_filter  # True peak
        assert "LRA=11" in af_filter  # Loudness range

    def test_speech_mono_conversion(self):
        """Verify SPEECH preset converts to mono (single channel)."""
        input_path = Path("/test/input.mp4")
        output_path = Path("/test/output.mp3")

        commands, _ = build_extract_commands(input_path, output_path, "speech")
        normalize_cmd = commands[1]

        assert "-ac" in normalize_cmd
        # Find the value after -ac
        ac_idx = normalize_cmd.index("-ac")
        assert ac_idx + 1 < len(normalize_cmd)
        assert normalize_cmd[ac_idx + 1] == "1"
