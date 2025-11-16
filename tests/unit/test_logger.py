"""Tests for src.utils.logger module."""

import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.utils.logger import configure_logger, get_logger


class TestGetLogger:
    """Tests for get_logger function."""

    def test_get_logger_with_explicit_name(self):
        """Test getting logger with explicit name."""
        logger = get_logger("test.module")
        assert isinstance(logger, logging.Logger)
        assert logger.name == "test.module"

    def test_get_logger_without_name_uses_caller_module(self):
        """Test that get_logger without name uses caller's __name__."""
        logger = get_logger()
        assert isinstance(logger, logging.Logger)
        # Should use the test module's name or fallback
        assert logger.name in ["__main__", "test_logger", "audio_extraction_analysis"]

    def test_get_logger_returns_same_instance_for_same_name(self):
        """Test that calling get_logger with same name returns same instance."""
        logger1 = get_logger("test.same")
        logger2 = get_logger("test.same")
        assert logger1 is logger2

    def test_get_logger_with_none_and_no_frame(self):
        """Test get_logger when frame inspection fails."""
        with patch("inspect.currentframe", return_value=None):
            logger = get_logger(None)
            assert logger.name == "audio_extraction_analysis"

    def test_get_logger_with_none_and_no_f_back(self):
        """Test get_logger when f_back is None."""
        mock_frame = MagicMock()
        mock_frame.f_back = None
        with patch("inspect.currentframe", return_value=mock_frame):
            logger = get_logger(None)
            assert logger.name == "audio_extraction_analysis"

    def test_get_logger_with_none_and_missing_name(self):
        """Test get_logger when __name__ is not in globals."""
        mock_frame = MagicMock()
        mock_frame.f_back.f_globals = {}
        with patch("inspect.currentframe", return_value=mock_frame):
            logger = get_logger(None)
            assert logger.name == "audio_extraction_analysis"


class TestConfigureLogger:
    """Tests for configure_logger function."""

    def setup_method(self):
        """Reset logging configuration before each test."""
        # Remove all handlers from root logger
        root = logging.getLogger()
        for handler in root.handlers[:]:
            handler.close()
            root.removeHandler(handler)
        # Reset level
        root.setLevel(logging.WARNING)
        # Clear the internal flag that prevents basicConfig from running
        # This is necessary because basicConfig only configures once per process
        if hasattr(logging, "_handlerList"):
            logging._handlerList[:] = []

    def test_configure_logger_default_settings(self):
        """Test configure_logger with default settings."""
        # Clear root handlers to ensure clean state
        root = logging.getLogger()
        root.handlers.clear()

        configure_logger()
        assert root.level == logging.INFO
        assert len(root.handlers) > 0

    def test_configure_logger_custom_level(self):
        """Test configure_logger with custom log level."""
        root = logging.getLogger()
        root.handlers.clear()

        configure_logger(level="DEBUG")
        assert root.level == logging.DEBUG

    def test_configure_logger_case_insensitive_level(self):
        """Test that level parameter is case-insensitive."""
        root = logging.getLogger()
        root.handlers.clear()

        configure_logger(level="warning")
        assert root.level == logging.WARNING

    def test_configure_logger_custom_format(self):
        """Test configure_logger with custom format string."""
        custom_format = "%(levelname)s: %(message)s"
        configure_logger(format_string=custom_format)
        root = logging.getLogger()
        assert len(root.handlers) > 0
        # At least one handler should have the custom format
        # (Note: basicConfig may create a StreamHandler)

    def test_configure_logger_with_file_handler(self, tmp_path: Path):
        """Test configure_logger with file handler enabled."""
        root = logging.getLogger()
        root.handlers.clear()

        log_file = tmp_path / "test.log"
        configure_logger(add_file_handler=True, file_path=str(log_file))

        file_handlers = [h for h in root.handlers if isinstance(h, logging.FileHandler)]
        assert len(file_handlers) > 0

        # Test that logging to file works
        test_logger = logging.getLogger("test.file")
        test_logger.info("Test message")

        # Flush and close handlers to ensure content is written
        for handler in root.handlers:
            handler.flush()

        assert log_file.exists()
        content = log_file.read_text()
        assert "Test message" in content

    def test_configure_logger_file_handler_without_path(self):
        """Test that file handler is not added without file_path."""
        len(logging.getLogger().handlers)
        configure_logger(add_file_handler=True, file_path=None)

        root = logging.getLogger()
        file_handlers = [h for h in root.handlers if isinstance(h, logging.FileHandler)]
        # Should not add file handler if path is None
        assert len(file_handlers) == 0

    def test_configure_logger_all_log_levels(self):
        """Test configure_logger with all standard log levels."""
        levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        expected = [logging.DEBUG, logging.INFO, logging.WARNING, logging.ERROR, logging.CRITICAL]

        for level_str, level_const in zip(levels, expected, strict=False):
            # Reset logger for each iteration
            root = logging.getLogger()
            root.handlers.clear()
            root.setLevel(logging.WARNING)

            configure_logger(level=level_str)
            assert root.level == level_const

    def test_configure_logger_invalid_level_raises(self):
        """Test that invalid log level raises AttributeError."""
        with pytest.raises(AttributeError):
            configure_logger(level="INVALID_LEVEL")

    def test_configure_logger_with_custom_format_and_file(self, tmp_path: Path):
        """Test configure_logger with both custom format and file handler."""
        root = logging.getLogger()
        root.handlers.clear()

        log_file = tmp_path / "formatted.log"
        custom_format = "%(levelname)s - %(message)s"

        configure_logger(
            level="DEBUG",
            format_string=custom_format,
            add_file_handler=True,
            file_path=str(log_file),
        )

        test_logger = logging.getLogger("test.formatted")
        test_logger.debug("Debug message")

        # Flush handlers to ensure content is written
        for handler in root.handlers:
            handler.flush()

        assert log_file.exists()
        content = log_file.read_text()
        assert "DEBUG - Debug message" in content

    def test_configure_logger_file_handler_raises_without_directory(self, tmp_path: Path):
        """Test that file handler raises error if parent directory doesn't exist."""
        nested_log = tmp_path / "nested" / "dir" / "test.log"

        # FileHandler doesn't auto-create parent directories
        # This should raise FileNotFoundError
        with pytest.raises(FileNotFoundError):
            configure_logger(add_file_handler=True, file_path=str(nested_log))


class TestLoggerIntegration:
    """Integration tests for logger module."""

    def test_get_logger_and_configure_together(self, tmp_path: Path):
        """Test using get_logger after configure_logger."""
        # Clear handlers first
        root = logging.getLogger()
        root.handlers.clear()

        log_file = tmp_path / "integration.log"

        # Configure first
        configure_logger(level="INFO", add_file_handler=True, file_path=str(log_file))

        # Get logger and use it
        logger = get_logger("integration.test")
        logger.info("Integration test message")
        logger.debug("This should not appear")  # Level is INFO

        # Flush handlers
        for handler in root.handlers:
            handler.flush()

        assert log_file.exists()
        content = log_file.read_text()
        assert "Integration test message" in content
        assert "This should not appear" not in content

    def test_multiple_loggers_same_configuration(self):
        """Test that multiple loggers share the same root configuration."""
        root = logging.getLogger()
        root.handlers.clear()

        configure_logger(level="WARNING")

        logger1 = get_logger("module1")
        logger2 = get_logger("module2")

        # Both should respect the root configuration
        assert logger1.getEffectiveLevel() == logging.WARNING
        assert logger2.getEffectiveLevel() == logging.WARNING

    def test_logger_hierarchy(self):
        """Test that logger hierarchy works correctly."""
        root = logging.getLogger()
        root.handlers.clear()

        configure_logger(level="INFO")

        parent = get_logger("parent")
        child = get_logger("parent.child")

        assert child.parent == parent
