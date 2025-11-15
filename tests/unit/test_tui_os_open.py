"""Tests for cross-platform file/folder opener."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from src.ui.tui.services.os_open import open_path


class TestOsOpen:
    """Tests for open_path utility."""

    def test_open_path_nonexistent_returns_false(self):
        """Test opening nonexistent path returns False."""
        result = open_path(Path("/nonexistent/path/to/file"))
        assert result is False

    def test_open_path_macos(self, tmp_path):
        """Test macOS path opening."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        with patch("platform.system", return_value="Darwin"):
            with patch("subprocess.run") as mock_run:
                result = open_path(test_file)

                assert result is True
                mock_run.assert_called_once_with(["open", str(test_file)], check=True)

    def test_open_path_windows(self, tmp_path):
        """Test Windows path opening."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        with patch("platform.system", return_value="Windows"):
            with patch("subprocess.run") as mock_run:
                result = open_path(test_file)

                assert result is True
                mock_run.assert_called_once_with(
                    ["cmd", "/c", "start", "", str(test_file)], check=True
                )

    def test_open_path_linux(self, tmp_path):
        """Test Linux path opening."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        with patch("platform.system", return_value="Linux"):
            with patch("subprocess.run") as mock_run:
                result = open_path(test_file)

                assert result is True
                mock_run.assert_called_once_with(["xdg-open", str(test_file)], check=True)

    def test_open_path_unsupported_platform(self, tmp_path):
        """Test unsupported platform returns False."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        with patch("platform.system", return_value="UnknownOS"):
            result = open_path(test_file)

            assert result is False

    def test_open_path_subprocess_error(self, tmp_path):
        """Test subprocess error returns False."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        with patch("platform.system", return_value="Darwin"):
            with patch("subprocess.run") as mock_run:
                mock_run.side_effect = subprocess.CalledProcessError(1, "open")

                result = open_path(test_file)

                assert result is False

    def test_open_path_command_not_found(self, tmp_path):
        """Test command not found returns False."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        with patch("platform.system", return_value="Linux"):
            with patch("subprocess.run") as mock_run:
                mock_run.side_effect = FileNotFoundError("xdg-open not found")

                result = open_path(test_file)

                assert result is False

    def test_open_folder(self, tmp_path):
        """Test opening a folder (not just files)."""
        test_dir = tmp_path / "test_folder"
        test_dir.mkdir()

        with patch("platform.system", return_value="Darwin"):
            with patch("subprocess.run") as mock_run:
                result = open_path(test_dir)

                assert result is True
                mock_run.assert_called_once_with(["open", str(test_dir)], check=True)

    @pytest.mark.parametrize(
        "system,expected_cmd",
        [
            ("Darwin", ["open", "/path/to/file"]),
            ("Windows", ["cmd", "/c", "start", "", "/path/to/file"]),
            ("Linux", ["xdg-open", "/path/to/file"]),
        ],
    )
    def test_open_path_platform_commands(self, tmp_path, system, expected_cmd):
        """Test correct commands are used for each platform."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        # Update expected_cmd with actual path
        expected_cmd[-1] = str(test_file)

        with patch("platform.system", return_value=system):
            with patch("subprocess.run") as mock_run:
                open_path(test_file)

                mock_run.assert_called_with(expected_cmd, check=True)
