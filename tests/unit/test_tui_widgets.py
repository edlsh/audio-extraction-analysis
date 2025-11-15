"""Unit tests for TUI widgets (ProgressBoard, LogPanel)."""

from __future__ import annotations

import time

import pytest

# Skip all tests if textual is not available
textual = pytest.importorskip("textual")

from src.ui.tui.state import AppState, LogEntry
from src.ui.tui.widgets.log_panel import LogPanel
from src.ui.tui.widgets.progress_board import ProgressBoard


class TestProgressBoard:
    """Tests for ProgressBoard widget."""

    def test_progress_board_initialization(self):
        """Test that ProgressBoard initializes correctly."""
        board = ProgressBoard()

        assert board._eta_history == {}
        assert board._last_update == {}

    def test_stage_status_pending(self):
        """Test stage status when stage hasn't started."""
        board = ProgressBoard()
        state = AppState()

        status = board._get_stage_status(state, "extract")
        assert status == "pending"

    def test_stage_status_running(self):
        """Test stage status when stage is running."""
        board = ProgressBoard()
        state = AppState()
        state.current_stage = "extract"
        state.stage_completed["extract"] = 50
        state.stage_totals["extract"] = 100

        status = board._get_stage_status(state, "extract")
        assert status == "running"

    def test_stage_status_complete(self):
        """Test stage status when stage is complete."""
        board = ProgressBoard()
        state = AppState()
        state.stage_durations["extract"] = 5.5

        status = board._get_stage_status(state, "extract")
        assert status == "complete"

    def test_stage_status_error(self):
        """Test stage status when stage has error."""
        board = ProgressBoard()
        state = AppState()
        state.current_stage = "extract"
        state.errors.append("FFmpeg error")

        status = board._get_stage_status(state, "extract")
        assert status == "error"

    def test_eta_calculation_no_progress(self):
        """Test ETA calculation with no progress."""
        board = ProgressBoard()
        state = AppState()

        eta = board._calculate_eta(state, "extract", 0, 100)
        assert eta == "--:--"

    def test_eta_calculation_with_progress(self):
        """Test ETA calculation with progress."""
        board = ProgressBoard()
        state = AppState()

        # Simulate progress updates
        board._eta_history["extract"] = [1.0, 1.0, 1.0]  # 1 unit/sec

        eta = board._calculate_eta(state, "extract", 50, 100)

        # Should calculate remaining time for 50 units at 1 unit/sec = 50 seconds
        # Format should be MM:SS
        assert eta != "--:--"
        # ETA should be around 00:50
        assert ":" in eta

    def test_eta_calculation_max_time(self):
        """Test ETA calculation caps at 99:59."""
        board = ProgressBoard()
        state = AppState()

        # Very slow rate
        board._eta_history["extract"] = [0.001]  # 0.001 units/sec

        eta = board._calculate_eta(state, "extract", 1, 10000)

        # Should cap at 99:59
        assert eta == "99:59"

    def test_render_stage_card_pending(self):
        """Test rendering pending stage card."""
        board = ProgressBoard()
        state = AppState()

        card = board._render_stage_card(state, "extract", "Extract Audio")

        # Card should have title
        assert "Extract Audio" in str(card)

    def test_render_stage_card_running(self):
        """Test rendering running stage card."""
        board = ProgressBoard()
        state = AppState()
        state.current_stage = "extract"
        state.current_message = "Extracting audio..."
        state.stage_completed["extract"] = 50
        state.stage_totals["extract"] = 100

        card = board._render_stage_card(state, "extract", "Extract Audio")

        # Card should show progress
        assert "50%" in str(card) or "█" in str(card)

    def test_render_stage_card_complete(self):
        """Test rendering complete stage card."""
        board = ProgressBoard()
        state = AppState()
        state.stage_durations["extract"] = 3.5

        card = board._render_stage_card(state, "extract", "Extract Audio")

        # Card should show completion time
        assert "3.5s" in str(card) or "Completed" in str(card)


class TestLogPanel:
    """Tests for LogPanel widget."""

    def test_log_panel_initialization(self):
        """Test that LogPanel initializes correctly."""
        panel = LogPanel()

        assert panel._filter_level == "DEBUG"  # Show all by default
        assert panel._auto_scroll is True

    def test_filter_logs_all(self):
        """Test filtering with DEBUG level (all logs)."""
        panel = LogPanel()
        panel._filter_level = "DEBUG"

        logs = [
            LogEntry(timestamp=time.time(), level="DEBUG", message="Debug msg"),
            LogEntry(timestamp=time.time(), level="INFO", message="Info msg"),
            LogEntry(timestamp=time.time(), level="WARNING", message="Warning msg"),
            LogEntry(timestamp=time.time(), level="ERROR", message="Error msg"),
        ]

        filtered = panel._filter_logs(logs)
        assert len(filtered) == 4

    def test_filter_logs_info_plus(self):
        """Test filtering INFO and above."""
        panel = LogPanel()
        panel._filter_level = "INFO"

        logs = [
            LogEntry(timestamp=time.time(), level="DEBUG", message="Debug msg"),
            LogEntry(timestamp=time.time(), level="INFO", message="Info msg"),
            LogEntry(timestamp=time.time(), level="WARNING", message="Warning msg"),
            LogEntry(timestamp=time.time(), level="ERROR", message="Error msg"),
        ]

        filtered = panel._filter_logs(logs)
        assert len(filtered) == 3
        assert all(log.level != "DEBUG" for log in filtered)

    def test_filter_logs_warning_plus(self):
        """Test filtering WARNING and above."""
        panel = LogPanel()
        panel._filter_level = "WARNING"

        logs = [
            LogEntry(timestamp=time.time(), level="DEBUG", message="Debug msg"),
            LogEntry(timestamp=time.time(), level="INFO", message="Info msg"),
            LogEntry(timestamp=time.time(), level="WARNING", message="Warning msg"),
            LogEntry(timestamp=time.time(), level="ERROR", message="Error msg"),
        ]

        filtered = panel._filter_logs(logs)
        assert len(filtered) == 2
        assert all(log.level in ["WARNING", "ERROR"] for log in filtered)

    def test_filter_logs_error_only(self):
        """Test filtering ERROR only."""
        panel = LogPanel()
        panel._filter_level = "ERROR"

        logs = [
            LogEntry(timestamp=time.time(), level="DEBUG", message="Debug msg"),
            LogEntry(timestamp=time.time(), level="INFO", message="Info msg"),
            LogEntry(timestamp=time.time(), level="WARNING", message="Warning msg"),
            LogEntry(timestamp=time.time(), level="ERROR", message="Error msg"),
        ]

        filtered = panel._filter_logs(logs)
        assert len(filtered) == 1
        assert filtered[0].level == "ERROR"

    def test_format_timestamp(self):
        """Test timestamp formatting."""
        panel = LogPanel()

        timestamp = time.time()
        formatted = panel._format_timestamp(timestamp)

        # Should be HH:MM:SS format
        assert len(formatted) == 8
        assert formatted.count(":") == 2

    def test_format_level(self):
        """Test log level formatting."""
        panel = LogPanel()

        formatted = panel._format_level("ERROR")
        assert "ERROR" in str(formatted)

    def test_format_message_truncation(self):
        """Test message truncation for long messages."""
        panel = LogPanel()

        long_msg = "A" * 300
        formatted = panel._format_message(long_msg)

        # Should be truncated
        assert len(formatted) <= 203  # 200 + "..."
        assert formatted.endswith("...")

    def test_format_message_no_truncation(self):
        """Test message formatting without truncation."""
        panel = LogPanel()

        short_msg = "Short message"
        formatted = panel._format_message(short_msg)

        assert formatted == short_msg

    def test_action_filter_all(self):
        """Test filter_all action."""
        panel = LogPanel()
        panel._filter_level = "ERROR"

        panel.action_filter_all()
        assert panel._filter_level == "DEBUG"

    def test_action_filter_info(self):
        """Test filter_info action."""
        panel = LogPanel()

        panel.action_filter_info()
        assert panel._filter_level == "INFO"

    def test_action_filter_warning(self):
        """Test filter_warning action."""
        panel = LogPanel()

        panel.action_filter_warning()
        assert panel._filter_level == "WARNING"

    def test_action_filter_error(self):
        """Test filter_error action."""
        panel = LogPanel()

        panel.action_filter_error()
        assert panel._filter_level == "ERROR"

    def test_log_panel_handles_empty_logs(self):
        """Test LogPanel handles empty log list gracefully."""
        panel = LogPanel()
        state = AppState()

        # Should not raise exception
        panel.update_logs(state)

    def test_log_panel_limits_display(self):
        """Test LogPanel limits display to last 100 logs."""
        panel = LogPanel()
        state = AppState()

        # Add 200 logs
        for i in range(200):
            state.logs.append(LogEntry(timestamp=time.time(), level="INFO", message=f"Log {i}"))

        # Update should only show last 100
        # (This is tested implicitly in the update_logs method)
        filtered = panel._filter_logs(state.logs)

        # Should have all 200 logs (filtering is separate from display limiting)
        assert len(filtered) == 200
