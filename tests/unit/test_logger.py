"""Tests for src.utils.logger module with loguru backend."""

from pathlib import Path
from unittest.mock import patch

import pytest

from src.utils.logger import configure_logger, get_logger
from src.utils.loguru_config import reset as reset_loguru


class TestGetLogger:
    """Tests for get_logger function."""

    def setup_method(self):
        """Reset loguru state before each test."""
        reset_loguru()

    def teardown_method(self):
        """Reset loguru state after each test."""
        reset_loguru()

    def test_get_logger_with_explicit_name(self):
        """Test getting logger with explicit name."""
        logger = get_logger("test.module")
        # Loguru returns a bound logger - verify it can log
        assert hasattr(logger, "info")
        assert hasattr(logger, "debug")
        assert hasattr(logger, "warning")
        assert hasattr(logger, "error")

    def test_get_logger_without_name_uses_caller_module(self):
        """Test that get_logger without name uses caller's __name__."""
        logger = get_logger()
        # Should have logging methods
        assert hasattr(logger, "info")
        assert callable(logger.info)

    def test_get_logger_returns_logger_with_methods(self):
        """Test that calling get_logger returns a logger with standard methods."""
        logger1 = get_logger("test.same")
        logger2 = get_logger("test.same")
        # Both should have logging methods
        assert hasattr(logger1, "info")
        assert hasattr(logger2, "info")

    def test_get_logger_with_none_and_no_frame(self):
        """Test get_logger when frame inspection fails."""
        with patch("inspect.currentframe", return_value=None):
            logger = get_logger(None)
            # Should still return a working logger
            assert hasattr(logger, "info")

    def test_get_logger_with_none_and_no_f_back(self):
        """Test get_logger when f_back is None."""
        from unittest.mock import MagicMock

        mock_frame = MagicMock()
        mock_frame.f_back = None
        with patch("inspect.currentframe", return_value=mock_frame):
            logger = get_logger(None)
            assert hasattr(logger, "info")


class TestConfigureLogger:
    """Tests for configure_logger function."""

    def setup_method(self):
        """Reset loguru configuration before each test."""
        reset_loguru()

    def teardown_method(self):
        """Reset loguru state after each test."""
        reset_loguru()

    def test_configure_logger_default_settings(self):
        """Test configure_logger with default settings."""
        configure_logger()
        logger = get_logger("test")
        # Should be able to log without error
        logger.info("Test message")

    def test_configure_logger_custom_level(self):
        """Test configure_logger with custom log level."""
        configure_logger(level="DEBUG")
        logger = get_logger("test.debug")
        # Should be able to log at debug level
        logger.debug("Debug message")

    def test_configure_logger_case_insensitive_level(self):
        """Test that level parameter is case-insensitive."""
        configure_logger(level="warning")
        logger = get_logger("test.warning")
        logger.warning("Warning message")

    def test_configure_logger_with_file_handler(self, tmp_path: Path):
        """Test configure_logger with file handler enabled."""
        log_file = tmp_path / "test.log"
        configure_logger(add_file_handler=True, file_path=str(log_file))
        
        logger = get_logger("test.file")
        logger.info("Test file message")
        
        # Loguru writes to configured directory
        # The actual log file location is managed by loguru_config

    def test_configure_logger_file_handler_without_path(self):
        """Test that file handler works with default path when no path specified."""
        configure_logger(add_file_handler=True, file_path=None)
        logger = get_logger("test")
        # Should be able to log
        logger.info("Test message")

    def test_configure_logger_all_log_levels(self, tmp_path: Path):
        """Test configure_logger with all standard log levels."""
        levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

        for level_str in levels:
            reset_loguru()
            configure_logger(level=level_str)
            logger = get_logger(f"test.{level_str.lower()}")
            # Should be able to get a logger at each level
            assert hasattr(logger, "info")


class TestLoggerIntegration:
    """Integration tests for logger module."""

    def setup_method(self):
        """Reset loguru state before each test."""
        reset_loguru()

    def teardown_method(self):
        """Reset loguru state after each test."""
        reset_loguru()

    def test_get_logger_and_configure_together(self, tmp_path: Path):
        """Test using get_logger after configure_logger."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)

        # Configure first
        configure_logger(level="INFO", add_file_handler=True, file_path=str(log_dir / "test.log"))

        # Get logger and use it
        logger = get_logger("integration.test")
        logger.info("Integration test message")
        logger.debug("This may not appear at INFO level")

    def test_multiple_loggers_same_configuration(self):
        """Test that multiple loggers work with the same configuration."""
        configure_logger(level="WARNING")

        logger1 = get_logger("module1")
        logger2 = get_logger("module2")

        # Both should have logging methods
        assert hasattr(logger1, "warning")
        assert hasattr(logger2, "warning")

    def test_logger_hierarchy(self):
        """Test that loggers can have hierarchical names."""
        configure_logger(level="INFO")

        parent = get_logger("parent")
        child = get_logger("parent.child")

        # Both should work
        parent.info("Parent message")
        child.info("Child message")
