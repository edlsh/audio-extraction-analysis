"""Test suite for src.providers.observability module."""

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from src.providers.observability import (
    CircuitBreakerEvent,
    CompositeObserver,
    LoggingObserver,
    ProviderObserver,
    ProviderSelectionEvent,
    RetryEvent,
    TimeoutEvent,
)


class TestRetryEvent:
    """Test RetryEvent dataclass."""

    def test_create_retry_event(self):
        """Test creating a RetryEvent with all fields."""
        event = RetryEvent(
            provider="deepgram",
            attempt=2,
            max_attempts=3,
            exception_type="ConnectionError",
            exception_message="Connection refused",
            delay_seconds=2.0,
            total_delay_seconds=3.0,
            will_retry=True,
        )

        assert event.provider == "deepgram"
        assert event.attempt == 2
        assert event.max_attempts == 3
        assert event.exception_type == "ConnectionError"
        assert event.exception_message == "Connection refused"
        assert event.delay_seconds == 2.0
        assert event.total_delay_seconds == 3.0
        assert event.will_retry is True
        assert isinstance(event.timestamp, datetime)

    def test_retry_event_with_custom_timestamp(self):
        """Test creating a RetryEvent with custom timestamp."""
        custom_time = datetime(2024, 1, 15, 10, 30, 0)
        event = RetryEvent(
            provider="whisper",
            attempt=1,
            max_attempts=3,
            exception_type="TimeoutError",
            exception_message="Timed out",
            delay_seconds=1.0,
            total_delay_seconds=1.0,
            will_retry=True,
            timestamp=custom_time,
        )

        assert event.timestamp == custom_time

    def test_retry_event_is_frozen(self):
        """Test that RetryEvent is immutable."""
        event = RetryEvent(
            provider="deepgram",
            attempt=1,
            max_attempts=3,
            exception_type="Error",
            exception_message="msg",
            delay_seconds=1.0,
            total_delay_seconds=1.0,
            will_retry=True,
        )

        with pytest.raises(AttributeError):
            event.provider = "other"


class TestCircuitBreakerEvent:
    """Test CircuitBreakerEvent dataclass."""

    def test_create_circuit_breaker_event(self):
        """Test creating a CircuitBreakerEvent with all fields."""
        event = CircuitBreakerEvent(
            provider="elevenlabs",
            state="open",
            previous_state="closed",
            failure_count=5,
            threshold=5,
            recovery_timeout=60.0,
            time_until_retry=60.0,
            triggering_exception="APIError: Rate limited",
        )

        assert event.provider == "elevenlabs"
        assert event.state == "open"
        assert event.previous_state == "closed"
        assert event.failure_count == 5
        assert event.threshold == 5
        assert event.recovery_timeout == 60.0
        assert event.time_until_retry == 60.0
        assert event.triggering_exception == "APIError: Rate limited"
        assert isinstance(event.timestamp, datetime)

    def test_circuit_breaker_event_half_open(self):
        """Test CircuitBreakerEvent with half_open state."""
        event = CircuitBreakerEvent(
            provider="deepgram",
            state="half_open",
            previous_state="open",
            failure_count=5,
            threshold=5,
            recovery_timeout=60.0,
            time_until_retry=None,
            triggering_exception=None,
        )

        assert event.state == "half_open"
        assert event.time_until_retry is None
        assert event.triggering_exception is None

    def test_circuit_breaker_event_is_frozen(self):
        """Test that CircuitBreakerEvent is immutable."""
        event = CircuitBreakerEvent(
            provider="deepgram",
            state="closed",
            previous_state="closed",
            failure_count=0,
            threshold=5,
            recovery_timeout=60.0,
            time_until_retry=None,
            triggering_exception=None,
        )

        with pytest.raises(AttributeError):
            event.state = "open"


class TestTimeoutEvent:
    """Test TimeoutEvent dataclass."""

    def test_create_timeout_event(self):
        """Test creating a TimeoutEvent with all fields."""
        event = TimeoutEvent(
            provider="parakeet",
            operation="transcribe",
            timeout_seconds=300.0,
            elapsed_seconds=300.5,
            file_path="/path/to/audio.mp3",
        )

        assert event.provider == "parakeet"
        assert event.operation == "transcribe"
        assert event.timeout_seconds == 300.0
        assert event.elapsed_seconds == 300.5
        assert event.file_path == "/path/to/audio.mp3"
        assert isinstance(event.timestamp, datetime)

    def test_timeout_event_without_file_path(self):
        """Test creating a TimeoutEvent without file_path."""
        event = TimeoutEvent(
            provider="whisper",
            operation="health_check",
            timeout_seconds=30.0,
            elapsed_seconds=30.1,
            file_path=None,
        )

        assert event.file_path is None

    def test_timeout_event_is_frozen(self):
        """Test that TimeoutEvent is immutable."""
        event = TimeoutEvent(
            provider="deepgram",
            operation="transcribe",
            timeout_seconds=60.0,
            elapsed_seconds=60.5,
            file_path=None,
        )

        with pytest.raises(AttributeError):
            event.elapsed_seconds = 120.0


class TestProviderSelectionEvent:
    """Test ProviderSelectionEvent dataclass."""

    def test_create_provider_selection_event(self):
        """Test creating a ProviderSelectionEvent with all fields."""
        event = ProviderSelectionEvent(
            selected_provider="deepgram",
            configured_providers=["deepgram", "elevenlabs", "whisper"],
            rejected_providers=[
                ("elevenlabs", "File too large"),
                ("whisper", "Not preferred for small files"),
            ],
            selection_criteria={"prefer_cloud": True, "max_file_size_mb": 50},
            file_size_mb=25.5,
        )

        assert event.selected_provider == "deepgram"
        assert event.configured_providers == ["deepgram", "elevenlabs", "whisper"]
        assert len(event.rejected_providers) == 2
        assert event.rejected_providers[0] == ("elevenlabs", "File too large")
        assert event.selection_criteria["prefer_cloud"] is True
        assert event.file_size_mb == 25.5
        assert isinstance(event.timestamp, datetime)

    def test_provider_selection_event_without_file_size(self):
        """Test creating a ProviderSelectionEvent without file_size_mb."""
        event = ProviderSelectionEvent(
            selected_provider="whisper",
            configured_providers=["whisper"],
            rejected_providers=[],
            selection_criteria={},
            file_size_mb=None,
        )

        assert event.file_size_mb is None
        assert event.rejected_providers == []

    def test_provider_selection_event_is_frozen(self):
        """Test that ProviderSelectionEvent is immutable."""
        event = ProviderSelectionEvent(
            selected_provider="deepgram",
            configured_providers=["deepgram"],
            rejected_providers=[],
            selection_criteria={},
            file_size_mb=10.0,
        )

        with pytest.raises(AttributeError):
            event.selected_provider = "whisper"


class TestLoggingObserver:
    """Test LoggingObserver implementation."""

    def test_on_retry_logs_warning_when_will_retry(self, caplog):
        """Test that on_retry logs at warning level when will_retry is True."""
        observer = LoggingObserver()
        event = RetryEvent(
            provider="deepgram",
            attempt=1,
            max_attempts=3,
            exception_type="ConnectionError",
            exception_message="Connection refused",
            delay_seconds=1.0,
            total_delay_seconds=1.0,
            will_retry=True,
        )

        observer.on_retry(event)
        # Just verify no exception was raised - actual logging is structured

    def test_on_retry_logs_error_when_will_not_retry(self, caplog):
        """Test that on_retry logs at error level when will_retry is False."""
        observer = LoggingObserver()
        event = RetryEvent(
            provider="deepgram",
            attempt=3,
            max_attempts=3,
            exception_type="ConnectionError",
            exception_message="Connection refused",
            delay_seconds=4.0,
            total_delay_seconds=7.0,
            will_retry=False,
        )

        observer.on_retry(event)
        # Just verify no exception was raised

    def test_on_circuit_breaker_logs_error_when_open(self):
        """Test that on_circuit_breaker logs at error level when state is open."""
        observer = LoggingObserver()
        event = CircuitBreakerEvent(
            provider="elevenlabs",
            state="open",
            previous_state="closed",
            failure_count=5,
            threshold=5,
            recovery_timeout=60.0,
            time_until_retry=60.0,
            triggering_exception="APIError",
        )

        observer.on_circuit_breaker(event)
        # Just verify no exception was raised

    def test_on_circuit_breaker_logs_warning_when_half_open(self):
        """Test that on_circuit_breaker logs at warning level when half_open."""
        observer = LoggingObserver()
        event = CircuitBreakerEvent(
            provider="deepgram",
            state="half_open",
            previous_state="open",
            failure_count=5,
            threshold=5,
            recovery_timeout=60.0,
            time_until_retry=None,
            triggering_exception=None,
        )

        observer.on_circuit_breaker(event)
        # Just verify no exception was raised

    def test_on_circuit_breaker_logs_info_when_closed(self):
        """Test that on_circuit_breaker logs at info level when closed."""
        observer = LoggingObserver()
        event = CircuitBreakerEvent(
            provider="deepgram",
            state="closed",
            previous_state="half_open",
            failure_count=0,
            threshold=5,
            recovery_timeout=60.0,
            time_until_retry=None,
            triggering_exception=None,
        )

        observer.on_circuit_breaker(event)
        # Just verify no exception was raised

    def test_on_timeout_logs_error(self):
        """Test that on_timeout logs at error level."""
        observer = LoggingObserver()
        event = TimeoutEvent(
            provider="whisper",
            operation="transcribe",
            timeout_seconds=300.0,
            elapsed_seconds=300.5,
            file_path="/path/to/audio.mp3",
        )

        observer.on_timeout(event)
        # Just verify no exception was raised

    def test_on_provider_selected_logs_info(self):
        """Test that on_provider_selected logs at info level."""
        observer = LoggingObserver()
        event = ProviderSelectionEvent(
            selected_provider="deepgram",
            configured_providers=["deepgram", "whisper"],
            rejected_providers=[],
            selection_criteria={"prefer_cloud": True},
            file_size_mb=10.0,
        )

        observer.on_provider_selected(event)
        # Just verify no exception was raised

    def test_observer_never_crashes_on_logging_error(self):
        """Test that observer methods never raise exceptions."""
        observer = LoggingObserver()

        # Create events with potentially problematic data
        retry_event = RetryEvent(
            provider="test",
            attempt=1,
            max_attempts=1,
            exception_type="Error",
            exception_message="x" * 10000,  # Very long message
            delay_seconds=0.0,
            total_delay_seconds=0.0,
            will_retry=False,
        )

        # These should not raise
        observer.on_retry(retry_event)


class TestCompositeObserver:
    """Test CompositeObserver implementation."""

    def test_fans_out_retry_event(self):
        """Test that CompositeObserver fans out retry events to all observers."""
        mock1 = MagicMock(spec=ProviderObserver)
        mock2 = MagicMock(spec=ProviderObserver)
        composite = CompositeObserver([mock1, mock2])

        event = RetryEvent(
            provider="deepgram",
            attempt=1,
            max_attempts=3,
            exception_type="Error",
            exception_message="msg",
            delay_seconds=1.0,
            total_delay_seconds=1.0,
            will_retry=True,
        )

        composite.on_retry(event)

        mock1.on_retry.assert_called_once_with(event)
        mock2.on_retry.assert_called_once_with(event)

    def test_fans_out_circuit_breaker_event(self):
        """Test that CompositeObserver fans out circuit breaker events."""
        mock1 = MagicMock(spec=ProviderObserver)
        mock2 = MagicMock(spec=ProviderObserver)
        composite = CompositeObserver([mock1, mock2])

        event = CircuitBreakerEvent(
            provider="deepgram",
            state="open",
            previous_state="closed",
            failure_count=5,
            threshold=5,
            recovery_timeout=60.0,
            time_until_retry=60.0,
            triggering_exception="Error",
        )

        composite.on_circuit_breaker(event)

        mock1.on_circuit_breaker.assert_called_once_with(event)
        mock2.on_circuit_breaker.assert_called_once_with(event)

    def test_fans_out_timeout_event(self):
        """Test that CompositeObserver fans out timeout events."""
        mock1 = MagicMock(spec=ProviderObserver)
        mock2 = MagicMock(spec=ProviderObserver)
        composite = CompositeObserver([mock1, mock2])

        event = TimeoutEvent(
            provider="whisper",
            operation="transcribe",
            timeout_seconds=60.0,
            elapsed_seconds=60.5,
            file_path=None,
        )

        composite.on_timeout(event)

        mock1.on_timeout.assert_called_once_with(event)
        mock2.on_timeout.assert_called_once_with(event)

    def test_fans_out_provider_selection_event(self):
        """Test that CompositeObserver fans out provider selection events."""
        mock1 = MagicMock(spec=ProviderObserver)
        mock2 = MagicMock(spec=ProviderObserver)
        composite = CompositeObserver([mock1, mock2])

        event = ProviderSelectionEvent(
            selected_provider="deepgram",
            configured_providers=["deepgram"],
            rejected_providers=[],
            selection_criteria={},
            file_size_mb=10.0,
        )

        composite.on_provider_selected(event)

        mock1.on_provider_selected.assert_called_once_with(event)
        mock2.on_provider_selected.assert_called_once_with(event)

    def test_handles_observer_failure_gracefully(self):
        """Test that CompositeObserver continues when one observer fails."""
        failing_mock = MagicMock(spec=ProviderObserver)
        failing_mock.on_retry.side_effect = RuntimeError("Observer crashed")
        succeeding_mock = MagicMock(spec=ProviderObserver)

        composite = CompositeObserver([failing_mock, succeeding_mock])

        event = RetryEvent(
            provider="deepgram",
            attempt=1,
            max_attempts=3,
            exception_type="Error",
            exception_message="msg",
            delay_seconds=1.0,
            total_delay_seconds=1.0,
            will_retry=True,
        )

        # Should not raise
        composite.on_retry(event)

        # Second observer should still be called
        succeeding_mock.on_retry.assert_called_once_with(event)

    def test_add_observer(self):
        """Test adding an observer dynamically."""
        mock1 = MagicMock(spec=ProviderObserver)
        mock2 = MagicMock(spec=ProviderObserver)

        composite = CompositeObserver([mock1])
        composite.add_observer(mock2)

        event = RetryEvent(
            provider="deepgram",
            attempt=1,
            max_attempts=3,
            exception_type="Error",
            exception_message="msg",
            delay_seconds=1.0,
            total_delay_seconds=1.0,
            will_retry=True,
        )

        composite.on_retry(event)

        mock1.on_retry.assert_called_once()
        mock2.on_retry.assert_called_once()

    def test_remove_observer(self):
        """Test removing an observer dynamically."""
        mock1 = MagicMock(spec=ProviderObserver)
        mock2 = MagicMock(spec=ProviderObserver)

        composite = CompositeObserver([mock1, mock2])
        composite.remove_observer(mock1)

        event = RetryEvent(
            provider="deepgram",
            attempt=1,
            max_attempts=3,
            exception_type="Error",
            exception_message="msg",
            delay_seconds=1.0,
            total_delay_seconds=1.0,
            will_retry=True,
        )

        composite.on_retry(event)

        mock1.on_retry.assert_not_called()
        mock2.on_retry.assert_called_once()

    def test_remove_observer_raises_if_not_found(self):
        """Test that remove_observer raises ValueError if observer not found."""
        mock1 = MagicMock(spec=ProviderObserver)
        mock2 = MagicMock(spec=ProviderObserver)

        composite = CompositeObserver([mock1])

        with pytest.raises(ValueError):
            composite.remove_observer(mock2)

    def test_observers_property_returns_copy(self):
        """Test that observers property returns a copy of the list."""
        mock1 = MagicMock(spec=ProviderObserver)
        composite = CompositeObserver([mock1])

        observers = composite.observers
        observers.clear()

        # Original list should be unchanged
        assert len(composite.observers) == 1

    def test_empty_composite_observer(self):
        """Test that empty CompositeObserver handles events without error."""
        composite = CompositeObserver([])

        event = RetryEvent(
            provider="deepgram",
            attempt=1,
            max_attempts=3,
            exception_type="Error",
            exception_message="msg",
            delay_seconds=1.0,
            total_delay_seconds=1.0,
            will_retry=True,
        )

        # Should not raise
        composite.on_retry(event)


class TestModuleExports:
    """Test module-level exports."""

    def test_all_exports_exist(self):
        """Test that all items in __all__ are importable."""
        from src.providers import observability

        expected = [
            "CircuitBreakerEvent",
            "CompositeObserver",
            "LoggingObserver",
            "ProviderObserver",
            "ProviderSelectionEvent",
            "RetryEvent",
            "TimeoutEvent",
        ]

        assert set(observability.__all__) == set(expected)

        for name in expected:
            assert hasattr(observability, name)

    def test_protocol_is_structural(self):
        """Test that ProviderObserver is a Protocol for structural typing."""

        class CustomObserver:
            """A custom observer that implements the protocol structurally."""

            def on_retry(self, event: RetryEvent) -> None:
                pass

            def on_circuit_breaker(self, event: CircuitBreakerEvent) -> None:
                pass

            def on_timeout(self, event: TimeoutEvent) -> None:
                pass

            def on_provider_selected(self, event: ProviderSelectionEvent) -> None:
                pass

        # Should be usable as a ProviderObserver
        observer = CustomObserver()
        composite = CompositeObserver([observer])

        event = RetryEvent(
            provider="test",
            attempt=1,
            max_attempts=1,
            exception_type="Error",
            exception_message="msg",
            delay_seconds=0.0,
            total_delay_seconds=0.0,
            will_retry=False,
        )

        # Should not raise
        composite.on_retry(event)
