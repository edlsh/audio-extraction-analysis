"""Tests for console UI components."""

import io
import json
import logging
import threading
from unittest.mock import Mock, patch

from src.ui.console import (
    ConsoleManager,
    FallbackProgressTracker,
    JsonProgressTracker,
    RichProgressTracker,
)


class TestConsoleManager:
    """Test console manager functionality."""

    def test_json_output_mode(self):
        """Test JSON output mode for stage events."""
        console_manager = ConsoleManager(json_output=True)

        captured = io.StringIO()
        with patch("sys.stderr", captured):
            console_manager.print_stage("Test Stage", "starting")

        output_line = captured.getvalue().strip()
        data = json.loads(output_line)
        assert data["stage"] == "Test Stage"
        assert data["status"] == "starting"

    def test_progress_context_fallback(self):
        """Test progress context in non-TTY environment falls back gracefully."""
        console_manager = ConsoleManager()
        console_manager.is_tty = False

        with console_manager.progress_context("Test Progress") as progress:
            assert hasattr(progress, "update")
            # Should not raise
            progress.update(50, 100)

    @patch("src.ui.console.sys.stderr.isatty")
    def test_tty_detection(self, mock_isatty):
        """Test TTY detection toggles modes."""
        mock_isatty.return_value = True
        cm = ConsoleManager()
        assert cm.is_tty is True

        mock_isatty.return_value = False
        cm = ConsoleManager()
        assert cm.is_tty is False

    def test_setup_logging_json_mode(self):
        """Test logging setup in JSON mode."""
        console_manager = ConsoleManager(json_output=True, verbose=True)
        logger = logging.getLogger("test_json_logger")
        logger.handlers.clear()

        console_manager.setup_logging(logger)

        assert len(logger.handlers) > 0
        assert logger.level == logging.DEBUG
        # Verify no duplicate handlers on second call
        console_manager.setup_logging(logger)
        assert len(logger.handlers) == 1

    def test_setup_logging_rich_mode(self):
        """Test logging setup with Rich handler."""
        console_manager = ConsoleManager(json_output=False, verbose=False)
        logger = logging.getLogger("test_rich_logger")
        logger.handlers.clear()

        console_manager.setup_logging(logger)

        assert len(logger.handlers) > 0
        assert logger.level == logging.INFO

    def test_print_summary_json_mode(self):
        """Test summary output in JSON mode."""
        console_manager = ConsoleManager(json_output=True)
        results = {
            "stage1": {"duration": 1.5, "status": "success"},
            "stage2": {"duration": 2.3, "status": "failed"},
        }

        captured = io.StringIO()
        with patch("sys.stdout", captured):
            console_manager.print_summary(results)

        output = captured.getvalue().strip()
        data = json.loads(output)
        assert data["type"] == "summary"
        assert "results" in data
        assert "stage1" in data["results"]

    def test_print_summary_plain_mode(self):
        """Test summary output in plain text mode."""
        console_manager = ConsoleManager(json_output=False)
        console_manager.console = None  # Force plain mode
        results = {
            "stage1": {"duration": 1.5, "status": "success"},
        }

        captured = io.StringIO()
        with patch("sys.stderr", captured):
            console_manager.print_summary(results)

        output = captured.getvalue()
        assert "Processing Summary" in output
        assert "stage1" in output

    def test_log_error_json_mode(self):
        """Test error logging in JSON mode."""
        console_manager = ConsoleManager(json_output=True)

        captured = io.StringIO()
        with patch("sys.stderr", captured):
            console_manager._log_error("Test error message")

        output = captured.getvalue().strip()
        data = json.loads(output)
        assert data["type"] == "error"
        assert "Test error message" in data["message"]

    def test_log_error_plain_mode(self):
        """Test error logging in plain mode."""
        console_manager = ConsoleManager(json_output=False)
        console_manager.console = None

        captured = io.StringIO()
        with patch("sys.stderr", captured):
            console_manager._log_error("Test error")

        output = captured.getvalue()
        assert "ERROR: Test error" in output

    def test_sanitize_string_field(self):
        """Test string field sanitization for security."""
        console_manager = ConsoleManager()

        # Test control character removal
        result = console_manager._sanitize_string_field("test\x00\x01string")
        assert "\x00" not in result
        assert "\x01" not in result

        # Test HTML escaping
        result = console_manager._sanitize_string_field("<script>alert('xss')</script>")
        assert "&lt;script&gt;" in result
        assert "<script>" not in result

        # Test length limiting
        long_string = "a" * 300
        result = console_manager._sanitize_string_field(long_string)
        assert len(result) <= 203  # 200 + "..."

        # Test newline conversion
        result = console_manager._sanitize_string_field("line1\nline2\rline3")
        assert "\n" not in result
        assert "\r" not in result

    def test_sanitize_numeric_field(self):
        """Test numeric field sanitization."""
        console_manager = ConsoleManager()

        # Test NaN handling
        result = console_manager._sanitize_numeric_field(float("nan"))
        assert result == 0.0

        # Test infinity handling
        result = console_manager._sanitize_numeric_field(float("inf"))
        assert result == 1e308

        # Test negative infinity
        result = console_manager._sanitize_numeric_field(float("-inf"))
        assert result == -1e308

        # Test normal numbers
        result = console_manager._sanitize_numeric_field(42.5)
        assert result == 42.5

    def test_sanitize_json_value_nested(self):
        """Test JSON value sanitization with nested structures."""
        console_manager = ConsoleManager()

        # Test nested dict
        nested = {
            "level1": {
                "level2": {"level3": "value"},
            }
        }
        result = console_manager._sanitize_json_value(nested)
        assert isinstance(result, dict)
        assert "level1" in result

        # Test max depth limiting
        console_manager._json_max_nesting_depth = 2
        deep_nested = {"a": {"b": {"c": {"d": "too deep"}}}}
        result = console_manager._sanitize_json_value(deep_nested)
        # Should be truncated at depth

        # Test list sanitization
        test_list = [1, 2, "test", {"key": "value"}]
        result = console_manager._sanitize_json_value(test_list)
        assert isinstance(result, list)
        assert len(result) == 4

        # Test None, bool, int, float
        assert console_manager._sanitize_json_value(None) is None
        assert console_manager._sanitize_json_value(True) is True
        assert console_manager._sanitize_json_value(False) is False
        assert console_manager._sanitize_json_value(42) == 42

    def test_sanitize_json_value_limits(self):
        """Test JSON value sanitization size limits."""
        console_manager = ConsoleManager()

        # Test large dict (should limit to 50 items)
        large_dict = {f"key{i}": f"value{i}" for i in range(100)}
        result = console_manager._sanitize_json_value(large_dict)
        assert len(result) <= 50

        # Test large list (should limit to 100 items)
        large_list = list(range(200))
        result = console_manager._sanitize_json_value(large_list)
        assert len(result) <= 100


class TestJsonProgressTracker:
    """Test JSON progress tracker."""

    def test_json_progress_update(self):
        """Test JSON progress updates."""
        tracker = JsonProgressTracker("Test Task")

        captured = io.StringIO()
        with patch("sys.stderr", captured):
            tracker.update(50, 100)

        output = captured.getvalue().strip()
        data = json.loads(output)
        assert data["type"] == "progress"
        assert data["completed"] == 50
        assert data["total"] == 100
        assert data["percentage"] == 50.0

    def test_json_progress_description_update(self):
        """Test JSON progress with description update."""
        tracker = JsonProgressTracker("Initial")

        captured = io.StringIO()
        with patch("sys.stderr", captured):
            tracker.update(25, 100, description="Updated Task")

        output = captured.getvalue().strip()
        data = json.loads(output)
        assert "Updated Task" in data["stage"]

    def test_json_progress_sanitization(self):
        """Test JSON progress tracker sanitizes values."""
        tracker = JsonProgressTracker("Test")

        captured = io.StringIO()
        with patch("sys.stderr", captured):
            # Test clamping of values
            tracker.update(150, 100)  # completed > total

        output = captured.getvalue().strip()
        data = json.loads(output)
        assert data["completed"] <= data["total"]

    def test_json_progress_thread_safety(self):
        """Test JSON progress tracker thread safety."""
        tracker = JsonProgressTracker("Concurrent Test")
        results = []

        def update_task(value):
            captured = io.StringIO()
            with patch("sys.stderr", captured):
                tracker.update(value, 100)
            results.append(captured.getvalue())

        threads = [threading.Thread(target=update_task, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(results) == 5


class TestFallbackProgressTracker:
    """Test fallback progress tracker."""

    def test_fallback_progress_update(self):
        """Test fallback progress updates at 10% intervals."""
        tracker = FallbackProgressTracker("Fallback Task")

        captured = io.StringIO()
        with patch("sys.stderr", captured):
            tracker.update(5, 100)  # 5% - no output
            tracker.update(15, 100)  # 15% - should output
            tracker.update(18, 100)  # 18% - no output (less than 10% from last)
            tracker.update(25, 100)  # 25% - should output

        output = captured.getvalue()
        # Should have 2 progress messages (15% and 25%)
        lines = [line for line in output.strip().split("\n") if line]
        assert len(lines) == 2

    def test_fallback_description_override(self):
        """Test fallback tracker with description override."""
        tracker = FallbackProgressTracker("Original")

        captured = io.StringIO()
        with patch("sys.stderr", captured):
            tracker.update(50, 100, description="Override")

        output = captured.getvalue()
        assert "Override" in output

    def test_fallback_thread_safety(self):
        """Test fallback tracker thread safety."""
        tracker = FallbackProgressTracker("Thread Test")

        def update_task(value):
            tracker.update(value, 100)

        threads = [threading.Thread(target=update_task, args=(i * 15,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should complete without errors


class TestRichProgressTracker:
    """Test Rich progress tracker."""

    def test_rich_progress_update(self):
        """Test Rich progress tracker updates."""
        mock_progress = Mock()
        task_id = "test_task"

        tracker = RichProgressTracker(mock_progress, task_id)
        tracker.update(50, 100)

        mock_progress.update.assert_called_with(task_id, completed=50, total=100)

    def test_rich_progress_throttling(self):
        """Test Rich progress tracker throttles updates."""
        mock_progress = Mock()
        task_id = "test_task"

        tracker = RichProgressTracker(mock_progress, task_id)

        # First update at 15% should go through (>10% change from 0)
        tracker.update(15, 100)
        assert mock_progress.update.call_count == 1

        # Small increment (less than 10% change from 15%) should be throttled
        tracker.update(18, 100)
        assert mock_progress.update.call_count == 1  # Still 1, throttled

        # Large increment (>10% change from 15%) should go through
        tracker.update(30, 100)
        assert mock_progress.update.call_count == 2

    def test_rich_progress_description_update(self):
        """Test Rich progress tracker with description."""
        mock_progress = Mock()
        task_id = "test_task"

        tracker = RichProgressTracker(mock_progress, task_id)
        tracker.update(50, 100, description="New Description")

        mock_progress.update.assert_called_with(
            task_id, completed=50, total=100, description="New Description"
        )

    def test_rich_progress_thread_safety(self):
        """Test Rich progress tracker thread safety."""
        mock_progress = Mock()
        task_id = "test_task"

        tracker = RichProgressTracker(mock_progress, task_id)

        def update_task(value):
            tracker.update(value, 100)

        threads = [threading.Thread(target=update_task, args=(i * 15,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should complete without errors, with some number of calls
        assert mock_progress.update.call_count > 0
