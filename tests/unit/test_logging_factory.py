"""Tests for src.utils.logging_factory module with loguru backend."""

from pathlib import Path

import pytest

from src.utils.logging_factory import LoggingFactory, get_logger
from src.utils.loguru_config import reset as reset_loguru


class TestLoggingFactoryInitialize:
    """Tests for LoggingFactory.initialize() method."""

    def setup_method(self):
        """Reset LoggingFactory and loguru state before each test."""
        LoggingFactory.reset()

    def teardown_method(self):
        """Reset state after each test."""
        LoggingFactory.reset()

    def test_initialize_default_settings(self, tmp_path):
        """Test initialize with default settings."""
        log_dir = tmp_path / "logs"

        LoggingFactory._log_dir = log_dir
        LoggingFactory.initialize(log_dir=log_dir)

        # Verify factory state
        assert LoggingFactory._initialized is True
        assert LoggingFactory._log_dir == log_dir
        assert log_dir.exists()

    def test_initialize_custom_log_dir(self, tmp_path):
        """Test initialize with custom log directory."""
        custom_dir = tmp_path / "custom_logs"
        LoggingFactory.initialize(log_dir=custom_dir)

        assert LoggingFactory._log_dir == custom_dir
        assert custom_dir.exists()

    def test_initialize_custom_level(self, tmp_path):
        """Test initialize with custom logging level."""
        log_dir = tmp_path / "logs"
        LoggingFactory.initialize(log_dir=log_dir, level="DEBUG")

        # Verify initialization completed
        assert LoggingFactory._initialized is True
        assert log_dir.exists()

    def test_initialize_idempotent(self, tmp_path):
        """Test that calling initialize multiple times is idempotent."""
        log_dir1 = tmp_path / "logs1"
        log_dir2 = tmp_path / "logs2"

        LoggingFactory.initialize(log_dir=log_dir1)

        # Second call should be ignored
        LoggingFactory.initialize(log_dir=log_dir2)

        # Should still use first log directory
        assert LoggingFactory._log_dir == log_dir1
        # Second directory should not be created
        assert not log_dir2.exists()

    def test_initialize_creates_missing_directory(self, tmp_path):
        """Test that initialize creates log directory if it doesn't exist."""
        log_dir = tmp_path / "nested" / "log" / "dir"
        assert not log_dir.exists()

        LoggingFactory.initialize(log_dir=log_dir)

        assert log_dir.exists()


class TestLoggingFactoryGetLogger:
    """Tests for LoggingFactory.get_logger() method."""

    def setup_method(self):
        """Reset LoggingFactory and loguru state before each test."""
        LoggingFactory.reset()

    def teardown_method(self):
        """Reset state after each test."""
        LoggingFactory.reset()

    def test_get_logger_auto_initializes(self, tmp_path):
        """Test that get_logger auto-initializes if not already done."""
        # Set log dir to temp path to avoid creating logs in project
        LoggingFactory._log_dir = tmp_path / "logs"

        assert LoggingFactory._initialized is False
        logger = LoggingFactory.get_logger("test.module")

        # Should auto-initialize
        assert LoggingFactory._initialized is True
        assert hasattr(logger, "info")

    def test_get_logger_returns_logger_instance(self, tmp_path):
        """Test that get_logger returns a logger instance with methods."""
        log_dir = tmp_path / "logs"
        LoggingFactory.initialize(log_dir=log_dir)

        logger = LoggingFactory.get_logger("test.module")

        assert hasattr(logger, "info")
        assert hasattr(logger, "debug")
        assert hasattr(logger, "warning")
        assert hasattr(logger, "error")

    def test_get_logger_can_log_messages(self, tmp_path):
        """Test that get_logger returns a logger that can log."""
        log_dir = tmp_path / "logs"
        LoggingFactory.initialize(log_dir=log_dir)

        logger1 = LoggingFactory.get_logger("test.same")
        logger2 = LoggingFactory.get_logger("test.same")

        # Both should be able to log
        logger1.info("Message 1")
        logger2.info("Message 2")

    def test_get_logger_different_names(self, tmp_path):
        """Test that get_logger works for different module names."""
        log_dir = tmp_path / "logs"
        LoggingFactory.initialize(log_dir=log_dir)

        logger1 = LoggingFactory.get_logger("test.module1")
        logger2 = LoggingFactory.get_logger("test.module2")

        # Both should have logging methods
        assert hasattr(logger1, "info")
        assert hasattr(logger2, "info")


class TestLoggingFactorySetLevel:
    """Tests for LoggingFactory.set_level() method."""

    def setup_method(self):
        """Reset LoggingFactory and loguru state before each test."""
        LoggingFactory.reset()

    def teardown_method(self):
        """Reset state after each test."""
        LoggingFactory.reset()

    def test_set_level_accepts_string(self, tmp_path):
        """Test that set_level accepts string level names."""
        log_dir = tmp_path / "logs"
        LoggingFactory.initialize(log_dir=log_dir)

        logger_name = "test.logger"
        LoggingFactory.get_logger(logger_name)

        # Should not raise
        LoggingFactory.set_level(logger_name, "DEBUG")
        LoggingFactory.set_level(logger_name, "ERROR")

    def test_set_level_accepts_int(self, tmp_path):
        """Test that set_level accepts integer level values."""
        import logging

        log_dir = tmp_path / "logs"
        LoggingFactory.initialize(log_dir=log_dir)

        logger_name = "test.logger"
        LoggingFactory.get_logger(logger_name)

        # Should not raise
        LoggingFactory.set_level(logger_name, logging.DEBUG)
        LoggingFactory.set_level(logger_name, logging.ERROR)


class TestLoggingFactoryConfigureVerbose:
    """Tests for LoggingFactory.configure_verbose() method."""

    def setup_method(self):
        """Reset LoggingFactory and loguru state before each test."""
        LoggingFactory.reset()

    def teardown_method(self):
        """Reset state after each test."""
        LoggingFactory.reset()

    def test_configure_verbose_true(self, tmp_path):
        """Test that configure_verbose(True) enables DEBUG level."""
        log_dir = tmp_path / "logs"
        LoggingFactory._log_dir = log_dir
        LoggingFactory.initialize(log_dir=log_dir)

        LoggingFactory.configure_verbose(verbose=True)

        # Should be able to get a logger and log
        logger = LoggingFactory.get_logger("verbose.test")
        logger.debug("Debug message should appear")

    def test_configure_verbose_false(self, tmp_path):
        """Test that configure_verbose(False) sets INFO level."""
        log_dir = tmp_path / "logs"
        LoggingFactory._log_dir = log_dir
        LoggingFactory.initialize(log_dir=log_dir, level="DEBUG")

        LoggingFactory.configure_verbose(verbose=False)

        # Should be able to log
        logger = LoggingFactory.get_logger("verbose.test")
        logger.info("Info message")

    def test_configure_verbose_default_is_false(self, tmp_path):
        """Test that configure_verbose() with no argument defaults to False."""
        log_dir = tmp_path / "logs"
        LoggingFactory._log_dir = log_dir
        LoggingFactory.initialize(log_dir=log_dir, level="DEBUG")

        LoggingFactory.configure_verbose()

        # Should not raise
        logger = LoggingFactory.get_logger("test")
        logger.info("Info message")


class TestBackwardCompatibility:
    """Tests for backward compatibility functions."""

    def setup_method(self):
        """Reset LoggingFactory and loguru state before each test."""
        LoggingFactory.reset()

    def teardown_method(self):
        """Reset state after each test."""
        LoggingFactory.reset()

    def test_standalone_get_logger_function(self, tmp_path):
        """Test that standalone get_logger function works."""
        LoggingFactory._log_dir = tmp_path / "logs"

        logger = get_logger("test.standalone")

        assert hasattr(logger, "info")

    def test_standalone_function_works(self, tmp_path):
        """Test that standalone function returns working logger."""
        LoggingFactory._log_dir = tmp_path / "logs"

        factory_logger = LoggingFactory.get_logger("test.module")
        standalone_logger = get_logger("test.module")

        # Both should have logging methods
        assert hasattr(factory_logger, "info")
        assert hasattr(standalone_logger, "info")


class TestLoggingFactoryIntegration:
    """Integration tests for LoggingFactory."""

    def setup_method(self):
        """Reset LoggingFactory and loguru state before each test."""
        LoggingFactory.reset()

    def teardown_method(self):
        """Reset state after each test."""
        LoggingFactory.reset()

    def test_full_workflow(self, tmp_path):
        """Test complete workflow: initialize, get logger, log message."""
        log_dir = tmp_path / "logs"
        LoggingFactory.initialize(log_dir=log_dir, level="INFO")

        # Verify initialization
        assert LoggingFactory._initialized is True

        # Get logger and use it
        logger = LoggingFactory.get_logger("integration.test")
        logger.info("Integration test message")
        logger.debug("Debug message")

        # Get same logger again
        logger2 = LoggingFactory.get_logger("integration.test")
        assert hasattr(logger2, "info")

    def test_verbose_mode_workflow(self, tmp_path):
        """Test workflow with verbose mode changes."""
        log_dir = tmp_path / "logs"
        LoggingFactory.initialize(log_dir=log_dir, level="INFO")

        logger = LoggingFactory.get_logger("verbose.test")

        # Enable verbose mode
        LoggingFactory.configure_verbose(verbose=True)
        logger.debug("Debug message should appear now")

        # Disable verbose mode
        LoggingFactory.configure_verbose(verbose=False)
        logger.info("Info message")

    def test_multiple_modules_logging(self, tmp_path):
        """Test that multiple modules can log independently."""
        log_dir = tmp_path / "logs"
        LoggingFactory.initialize(log_dir=log_dir, level="INFO")

        # Get loggers for different modules
        logger1 = LoggingFactory.get_logger("module1")
        logger2 = LoggingFactory.get_logger("module2")

        # Both should be able to log
        logger1.info("Message from module1")
        logger2.info("Message from module2")
