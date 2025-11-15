"""Unit tests for TUI persistence module."""

import json
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, Mock, mock_open, patch

import pytest

from src.ui.tui import persistence
from src.ui.tui.persistence import (
    add_recent_file,
    clear_recent_files,
    default_settings,
    get_config_dir,
    load_recent_files,
    load_settings,
    save_recent_files,
    save_settings,
)


class TestGetConfigDir:
    """Test get_config_dir function."""

    @patch("src.ui.tui.persistence.PLATFORMDIRS_AVAILABLE", False)
    def test_no_platformdirs(self):
        """Test when platformdirs is not available."""
        result = get_config_dir()
        assert result is None

    @patch("src.ui.tui.persistence.PLATFORMDIRS_AVAILABLE", True)
    @patch("src.ui.tui.persistence.user_config_dir")
    def test_with_platformdirs(self, mock_user_config):
        """Test when platformdirs is available."""
        mock_dir = Path("/mock/config/dir")
        mock_user_config.return_value = str(mock_dir)

        with patch.object(Path, "mkdir") as mock_mkdir:
            result = get_config_dir()

        assert result == mock_dir
        mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)
        mock_user_config.assert_called_once_with(
            "audio-extraction-analysis",
            appauthor=False
        )


class TestDefaultSettings:
    """Test default_settings function."""

    def test_returns_complete_structure(self):
        """Test that default settings has all required keys."""
        settings = default_settings()

        # Check top-level keys
        assert "version" in settings
        assert "last_input_dir" in settings
        assert "last_output_dir" in settings
        assert "defaults" in settings
        assert "exports" in settings
        assert "ui" in settings

        # Check defaults structure
        assert settings["defaults"]["quality"] == "speech"
        assert settings["defaults"]["language"] == "en"
        assert settings["defaults"]["provider"] == "auto"
        assert settings["defaults"]["analysis_style"] == "concise"

        # Check exports structure
        assert settings["exports"]["markdown"] is True
        assert settings["exports"]["html"] is False

        # Check UI structure
        assert settings["ui"]["theme"] == "dark"
        assert settings["ui"]["verbose_logs"] is False
        assert settings["ui"]["log_panel_height"] == 10

    def test_returns_new_dict_each_time(self):
        """Test that each call returns a new dictionary."""
        settings1 = default_settings()
        settings2 = default_settings()

        # Should be equal but not the same object
        assert settings1 == settings2
        assert settings1 is not settings2


class TestLoadSettings:
    """Test load_settings function."""

    @patch("src.ui.tui.persistence.get_config_dir")
    def test_no_config_dir(self, mock_get_config):
        """Test when config directory is not available."""
        mock_get_config.return_value = None

        result = load_settings()

        assert result == default_settings()

    @patch("src.ui.tui.persistence.get_config_dir")
    def test_settings_file_not_exists(self, mock_get_config):
        """Test when settings file doesn't exist."""
        mock_dir = Path("/mock/config")
        mock_get_config.return_value = mock_dir

        with patch.object(Path, "exists", return_value=False):
            result = load_settings()

        assert result == default_settings()

    @patch("src.ui.tui.persistence.get_config_dir")
    def test_load_valid_settings(self, mock_get_config):
        """Test loading valid settings file."""
        mock_dir = Path("/mock/config")
        mock_get_config.return_value = mock_dir

        custom_settings = {
            "defaults": {"quality": "high"},
            "ui": {"theme": "light"}
        }

        with patch.object(Path, "exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=json.dumps(custom_settings))):
                result = load_settings()

        # Should merge with defaults
        assert result["defaults"]["quality"] == "high"
        assert result["defaults"]["language"] == "en"  # From defaults
        assert result["ui"]["theme"] == "light"
        assert result["version"] == "1.0"  # From defaults

    @patch("src.ui.tui.persistence.get_config_dir")
    @patch("src.ui.tui.persistence.logger")
    def test_load_corrupted_json(self, mock_logger, mock_get_config):
        """Test loading corrupted JSON file."""
        mock_dir = Path("/mock/config")
        mock_get_config.return_value = mock_dir
        mock_settings_file = mock_dir / "tui_settings.json"

        with patch.object(Path, "exists", return_value=True):
            with patch("builtins.open", mock_open(read_data="invalid json {")):
                with patch.object(Path, "rename") as mock_rename:
                    result = load_settings()

        # Should return defaults
        assert result == default_settings()

        # Should log error
        mock_logger.error.assert_called_once()

        # Should attempt backup
        backup_path = mock_settings_file.with_suffix(".json.bak")
        mock_rename.assert_called_once_with(backup_path)

    @patch("src.ui.tui.persistence.get_config_dir")
    @patch("src.ui.tui.persistence.logger")
    def test_load_file_permission_error(self, mock_logger, mock_get_config):
        """Test loading with file permission error."""
        mock_dir = Path("/mock/config")
        mock_get_config.return_value = mock_dir

        with patch.object(Path, "exists", return_value=True):
            with patch("builtins.open", side_effect=PermissionError("Access denied")):
                result = load_settings()

        # Should return defaults
        assert result == default_settings()

        # Should log error
        mock_logger.error.assert_called_once()


class TestSaveSettings:
    """Test save_settings function."""

    @patch("src.ui.tui.persistence.get_config_dir")
    def test_no_config_dir(self, mock_get_config):
        """Test when config directory is not available."""
        mock_get_config.return_value = None

        result = save_settings({"test": "data"})

        assert result is False

    @patch("src.ui.tui.persistence.get_config_dir")
    def test_save_success(self, mock_get_config):
        """Test successful settings save."""
        mock_dir = Path("/mock/config")
        mock_get_config.return_value = mock_dir

        settings = {"test": "data", "nested": {"key": "value"}}

        with patch("builtins.open", mock_open()) as mock_file:
            result = save_settings(settings)

        assert result is True

        # Verify file was written
        mock_file.assert_called_once_with(
            mock_dir / "tui_settings.json",
            "w",
            encoding="utf-8"
        )

        # Verify JSON was dumped correctly
        handle = mock_file()
        written_content = "".join(
            call.args[0] for call in handle.write.call_args_list
        )
        parsed = json.loads(written_content)
        assert parsed == settings

    @patch("src.ui.tui.persistence.get_config_dir")
    @patch("src.ui.tui.persistence.logger")
    def test_save_permission_error(self, mock_logger, mock_get_config):
        """Test save with permission error."""
        mock_dir = Path("/mock/config")
        mock_get_config.return_value = mock_dir

        with patch("builtins.open", side_effect=PermissionError("Access denied")):
            result = save_settings({"test": "data"})

        assert result is False
        mock_logger.error.assert_called_once()


class TestLoadRecentFiles:
    """Test load_recent_files function."""

    @patch("src.ui.tui.persistence.get_config_dir")
    def test_no_config_dir(self, mock_get_config):
        """Test when config directory is not available."""
        mock_get_config.return_value = None

        result = load_recent_files()

        assert result == []

    @patch("src.ui.tui.persistence.get_config_dir")
    def test_recent_file_not_exists(self, mock_get_config):
        """Test when recent files file doesn't exist."""
        mock_dir = Path("/mock/config")
        mock_get_config.return_value = mock_dir

        with patch.object(Path, "exists", return_value=False):
            result = load_recent_files()

        assert result == []

    @patch("src.ui.tui.persistence.get_config_dir")
    def test_load_valid_recent_files(self, mock_get_config):
        """Test loading valid recent files."""
        mock_dir = Path("/mock/config")
        mock_get_config.return_value = mock_dir

        recent_files = [
            {"path": "/test/file1.mp3", "last_used": "2024-01-01", "size_mb": 10.5},
            {"path": "/test/file2.wav", "last_used": "2024-01-02", "size_mb": 25.2},
        ]

        with patch.object(Path, "exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=json.dumps(recent_files))):
                result = load_recent_files()

        assert result == recent_files

    @patch("src.ui.tui.persistence.get_config_dir")
    def test_load_recent_files_max_entries(self, mock_get_config):
        """Test loading with max entries limit."""
        mock_dir = Path("/mock/config")
        mock_get_config.return_value = mock_dir

        # Create 30 files
        recent_files = [
            {"path": f"/test/file{i}.mp3", "last_used": f"2024-01-{i:02d}", "size_mb": i}
            for i in range(1, 31)
        ]

        with patch.object(Path, "exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=json.dumps(recent_files))):
                result = load_recent_files(max_entries=10)

        # Should return only first 10
        assert len(result) == 10
        assert result == recent_files[:10]

    @patch("src.ui.tui.persistence.get_config_dir")
    @patch("src.ui.tui.persistence.logger")
    def test_load_corrupted_recent_files(self, mock_logger, mock_get_config):
        """Test loading corrupted recent files."""
        mock_dir = Path("/mock/config")
        mock_get_config.return_value = mock_dir

        with patch.object(Path, "exists", return_value=True):
            with patch("builtins.open", mock_open(read_data="invalid json [")):
                result = load_recent_files()

        assert result == []
        mock_logger.error.assert_called_once()


class TestSaveRecentFiles:
    """Test save_recent_files function."""

    @patch("src.ui.tui.persistence.get_config_dir")
    def test_no_config_dir(self, mock_get_config):
        """Test when config directory is not available."""
        mock_get_config.return_value = None

        result = save_recent_files([{"path": "/test/file.mp3"}])

        assert result is False

    @patch("src.ui.tui.persistence.get_config_dir")
    def test_save_success(self, mock_get_config):
        """Test successful recent files save."""
        mock_dir = Path("/mock/config")
        mock_get_config.return_value = mock_dir

        recent_files = [
            {"path": "/test/file1.mp3", "last_used": "2024-01-01", "size_mb": 10.5}
        ]

        with patch("builtins.open", mock_open()) as mock_file:
            result = save_recent_files(recent_files)

        assert result is True

        # Verify file was written
        mock_file.assert_called_once_with(
            mock_dir / "recent_files.json",
            "w",
            encoding="utf-8"
        )


class TestAddRecentFile:
    """Test add_recent_file function."""

    @patch("src.ui.tui.persistence.load_recent_files")
    @patch("src.ui.tui.persistence.save_recent_files")
    def test_add_new_file(self, mock_save, mock_load):
        """Test adding a new file to recent list."""
        mock_load.return_value = []
        mock_save.return_value = True

        test_file = Path("/test/new.mp3")
        with patch.object(Path, "exists", return_value=True):
            with patch.object(Path, "stat") as mock_stat:
                mock_stat.return_value = Mock(st_size=10 * 1024 * 1024)  # 10MB

                result = add_recent_file(test_file)

        assert result is True

        # Verify save was called with new file
        saved_files = mock_save.call_args[0][0]
        assert len(saved_files) == 1
        assert saved_files[0]["path"] == str(test_file.resolve())
        assert saved_files[0]["size_mb"] == 10.0

    @patch("src.ui.tui.persistence.load_recent_files")
    @patch("src.ui.tui.persistence.save_recent_files")
    def test_add_duplicate_file(self, mock_save, mock_load):
        """Test adding a file that already exists in recent list."""
        existing_file = "/test/existing.mp3"
        mock_load.return_value = [
            {"path": existing_file, "last_used": "2024-01-01", "size_mb": 5.0},
            {"path": "/test/other.mp3", "last_used": "2024-01-02", "size_mb": 8.0},
        ]
        mock_save.return_value = True

        test_file = Path(existing_file)
        with patch.object(Path, "exists", return_value=True):
            with patch.object(Path, "stat") as mock_stat:
                mock_stat.return_value = Mock(st_size=5 * 1024 * 1024)

                result = add_recent_file(test_file)

        assert result is True

        # Verify duplicate was moved to front, not added twice
        saved_files = mock_save.call_args[0][0]
        assert len(saved_files) == 2
        assert saved_files[0]["path"] == str(test_file.resolve())
        assert saved_files[1]["path"] == "/test/other.mp3"

    @patch("src.ui.tui.persistence.load_recent_files")
    @patch("src.ui.tui.persistence.save_recent_files")
    def test_add_file_max_entries(self, mock_save, mock_load):
        """Test that adding a file respects max entries limit."""
        # Create 20 existing files
        existing_files = [
            {"path": f"/test/file{i}.mp3", "last_used": f"2024-01-{i:02d}", "size_mb": i}
            for i in range(1, 21)
        ]
        mock_load.return_value = existing_files
        mock_save.return_value = True

        test_file = Path("/test/new.mp3")
        with patch.object(Path, "exists", return_value=True):
            with patch.object(Path, "stat") as mock_stat:
                mock_stat.return_value = Mock(st_size=100 * 1024 * 1024)

                result = add_recent_file(test_file)

        assert result is True

        # Verify only 20 files saved (new one + 19 old)
        saved_files = mock_save.call_args[0][0]
        assert len(saved_files) == 20
        assert saved_files[0]["path"] == str(test_file.resolve())

    def test_add_nonexistent_file(self):
        """Test adding a file that doesn't exist."""
        test_file = Path("/test/missing.mp3")

        with patch.object(Path, "exists", return_value=False):
            result = add_recent_file(test_file)

        assert result is False


class TestClearRecentFiles:
    """Test clear_recent_files function."""

    @patch("src.ui.tui.persistence.get_config_dir")
    def test_no_config_dir(self, mock_get_config):
        """Test when config directory is not available."""
        mock_get_config.return_value = None

        result = clear_recent_files()

        assert result is False

    @patch("src.ui.tui.persistence.get_config_dir")
    def test_clear_success(self, mock_get_config):
        """Test successful clear of recent files."""
        mock_dir = Path("/mock/config")
        mock_get_config.return_value = mock_dir

        with patch("builtins.open", mock_open()) as mock_file:
            result = clear_recent_files()

        assert result is True

        # Verify empty list was saved
        mock_file.assert_called_once()
        handle = mock_file()
        written_content = "".join(
            call.args[0] for call in handle.write.call_args_list
        )
        assert json.loads(written_content) == []

    @patch("src.ui.tui.persistence.get_config_dir")
    @patch("src.ui.tui.persistence.logger")
    def test_clear_permission_error(self, mock_logger, mock_get_config):
        """Test clear with permission error."""
        mock_dir = Path("/mock/config")
        mock_get_config.return_value = mock_dir

        with patch("builtins.open", side_effect=PermissionError("Access denied")):
            result = clear_recent_files()

        assert result is False
        mock_logger.error.assert_called_once()


class TestPersistenceIntegration:
    """Integration tests for persistence module."""

    def test_settings_round_trip(self):
        """Test saving and loading settings."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Mock config dir to use temp directory
            with patch("src.ui.tui.persistence.get_config_dir", return_value=Path(temp_dir)):
                # Save settings
                test_settings = default_settings()
                test_settings["defaults"]["quality"] = "high"
                test_settings["ui"]["theme"] = "light"

                save_result = save_settings(test_settings)
                assert save_result is True

                # Load settings back
                loaded = load_settings()
                assert loaded["defaults"]["quality"] == "high"
                assert loaded["ui"]["theme"] == "light"

    def test_recent_files_round_trip(self):
        """Test saving and loading recent files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Mock config dir to use temp directory
            with patch("src.ui.tui.persistence.get_config_dir", return_value=Path(temp_dir)):
                # Add some files
                test_file1 = Path(temp_dir) / "test1.mp3"
                test_file2 = Path(temp_dir) / "test2.wav"

                # Create actual files for stat to work
                test_file1.write_text("dummy")
                test_file2.write_text("dummy")

                add_recent_file(test_file1)
                add_recent_file(test_file2)

                # Load them back
                recent = load_recent_files()
                assert len(recent) == 2
                # Most recent first
                assert recent[0]["path"] == str(test_file2.resolve())
                assert recent[1]["path"] == str(test_file1.resolve())

                # Clear and verify
                clear_result = clear_recent_files()
                assert clear_result is True

                recent = load_recent_files()
                assert len(recent) == 0