"""Provider observability module for structured event logging.

This module provides a composable observer pattern for monitoring provider
lifecycle events including retries, circuit breaker state changes, timeouts,
and provider selection. Observers can be composed together for flexible
event handling.

Usage:
    from src.providers.observability import LoggingObserver, CompositeObserver

    observer = LoggingObserver()
    observer.on_retry(retry_event)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, Literal, Protocol

from src.utils.logger import get_logger

if TYPE_CHECKING:
    from collections.abc import Sequence

logger = get_logger(__name__)


# =============================================================================
# Event Dataclasses
# =============================================================================


@dataclass(frozen=True)
class RetryEvent:
    """Event emitted when a provider operation is retried.

    Attributes:
        provider: Name of the provider being retried
        attempt: Current attempt number (1-indexed)
        max_attempts: Maximum number of attempts configured
        exception_type: Type name of the exception that triggered retry
        exception_message: Exception message
        delay_seconds: Delay before this retry attempt
        total_delay_seconds: Total delay accumulated across all retries
        will_retry: Whether another retry will be attempted
        timestamp: UTC timestamp of the event
    """

    provider: str
    attempt: int
    max_attempts: int
    exception_type: str
    exception_message: str
    delay_seconds: float
    total_delay_seconds: float
    will_retry: bool
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass(frozen=True)
class CircuitBreakerEvent:
    """Event emitted when circuit breaker state changes.

    Attributes:
        provider: Name of the provider
        state: Current circuit breaker state
        previous_state: Previous circuit breaker state
        failure_count: Current failure count
        threshold: Failure threshold for opening circuit
        recovery_timeout: Time until circuit allows retry (seconds)
        time_until_retry: Seconds until next retry attempt (if open)
        triggering_exception: Exception that triggered state change (if any)
        timestamp: UTC timestamp of the event
    """

    provider: str
    state: Literal["closed", "open", "half_open"]
    previous_state: Literal["closed", "open", "half_open"]
    failure_count: int
    threshold: int
    recovery_timeout: float
    time_until_retry: float | None
    triggering_exception: str | None
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass(frozen=True)
class TimeoutEvent:
    """Event emitted when a provider operation times out.

    Attributes:
        provider: Name of the provider
        operation: Name of the operation that timed out
        timeout_seconds: Configured timeout duration
        elapsed_seconds: Actual elapsed time before timeout
        file_path: Path to file being processed (if applicable)
        timestamp: UTC timestamp of the event
    """

    provider: str
    operation: str
    timeout_seconds: float
    elapsed_seconds: float
    file_path: str | None
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass(frozen=True)
class ProviderSelectionEvent:
    """Event emitted when a provider is selected for transcription.

    Attributes:
        selected_provider: Name of the provider that was selected
        configured_providers: List of all configured provider names
        rejected_providers: List of (name, reason) tuples for rejected providers
        selection_criteria: Dictionary of criteria used for selection
        file_size_mb: Size of the file being processed (if known)
        timestamp: UTC timestamp of the event
    """

    selected_provider: str
    configured_providers: list[str]
    rejected_providers: list[tuple[str, str]]
    selection_criteria: dict[str, Any]
    file_size_mb: float | None
    timestamp: datetime = field(default_factory=datetime.utcnow)


# =============================================================================
# Observer Protocol
# =============================================================================


class ProviderObserver(Protocol):
    """Protocol for provider event observers.

    Implement this protocol to receive notifications about provider lifecycle
    events. All methods are optional - implementations may handle only the
    events they care about.
    """

    def on_retry(self, event: RetryEvent) -> None:
        """Handle a retry event.

        Args:
            event: The retry event details
        """
        ...

    def on_circuit_breaker(self, event: CircuitBreakerEvent) -> None:
        """Handle a circuit breaker state change event.

        Args:
            event: The circuit breaker event details
        """
        ...

    def on_timeout(self, event: TimeoutEvent) -> None:
        """Handle a timeout event.

        Args:
            event: The timeout event details
        """
        ...

    def on_provider_selected(self, event: ProviderSelectionEvent) -> None:
        """Handle a provider selection event.

        Args:
            event: The provider selection event details
        """
        ...


# =============================================================================
# Observer Implementations
# =============================================================================


class LoggingObserver:
    """Observer that logs provider events using structured loguru logging.

    Uses appropriate log levels based on event severity:
    - INFO: Provider selection, successful operations
    - WARNING: Retries, circuit breaker half-open
    - ERROR: Timeouts, circuit breaker open
    """

    def on_retry(self, event: RetryEvent) -> None:
        """Log retry events at WARNING level.

        Args:
            event: The retry event details
        """
        try:
            log_level = "warning" if event.will_retry else "error"
            getattr(logger, log_level)(
                "Provider retry attempt",
                provider=event.provider,
                attempt=event.attempt,
                max_attempts=event.max_attempts,
                exception_type=event.exception_type,
                exception_message=event.exception_message,
                delay_seconds=event.delay_seconds,
                total_delay_seconds=event.total_delay_seconds,
                will_retry=event.will_retry,
            )
        except Exception:
            # Never crash on logging failures
            pass

    def on_circuit_breaker(self, event: CircuitBreakerEvent) -> None:
        """Log circuit breaker events with appropriate severity.

        Args:
            event: The circuit breaker event details
        """
        try:
            # Determine log level based on state transition
            if event.state == "open":
                log_level = "error"
            elif event.state == "half_open":
                log_level = "warning"
            else:
                log_level = "info"

            getattr(logger, log_level)(
                "Circuit breaker state change",
                provider=event.provider,
                state=event.state,
                previous_state=event.previous_state,
                failure_count=event.failure_count,
                threshold=event.threshold,
                recovery_timeout=event.recovery_timeout,
                time_until_retry=event.time_until_retry,
                triggering_exception=event.triggering_exception,
            )
        except Exception:
            # Never crash on logging failures
            pass

    def on_timeout(self, event: TimeoutEvent) -> None:
        """Log timeout events at ERROR level.

        Args:
            event: The timeout event details
        """
        try:
            logger.error(
                "Provider operation timeout",
                provider=event.provider,
                operation=event.operation,
                timeout_seconds=event.timeout_seconds,
                elapsed_seconds=event.elapsed_seconds,
                file_path=event.file_path,
            )
        except Exception:
            # Never crash on logging failures
            pass

    def on_provider_selected(self, event: ProviderSelectionEvent) -> None:
        """Log provider selection events at INFO level.

        Args:
            event: The provider selection event details
        """
        try:
            logger.info(
                "Provider selected",
                selected_provider=event.selected_provider,
                configured_providers=event.configured_providers,
                rejected_providers=event.rejected_providers,
                selection_criteria=event.selection_criteria,
                file_size_mb=event.file_size_mb,
            )
        except Exception:
            # Never crash on logging failures
            pass


class CompositeObserver:
    """Observer that fans out events to multiple child observers.

    Handles individual observer failures gracefully - if one observer
    raises an exception, other observers still receive the event.

    Args:
        observers: Sequence of observers to notify
    """

    def __init__(self, observers: Sequence[ProviderObserver]) -> None:
        """Initialize with a list of child observers.

        Args:
            observers: Sequence of observers to forward events to
        """
        self._observers: list[ProviderObserver] = list(observers)

    def add_observer(self, observer: ProviderObserver) -> None:
        """Add an observer to the composite.

        Args:
            observer: Observer to add
        """
        self._observers.append(observer)

    def remove_observer(self, observer: ProviderObserver) -> None:
        """Remove an observer from the composite.

        Args:
            observer: Observer to remove

        Raises:
            ValueError: If observer is not in the list
        """
        self._observers.remove(observer)

    @property
    def observers(self) -> list[ProviderObserver]:
        """Get the list of observers (copy)."""
        return list(self._observers)

    def on_retry(self, event: RetryEvent) -> None:
        """Fan out retry event to all observers.

        Args:
            event: The retry event details
        """
        for observer in self._observers:
            try:
                observer.on_retry(event)
            except Exception as e:
                logger.debug(
                    "Observer failed to handle retry event",
                    observer_type=type(observer).__name__,
                    error=str(e),
                )

    def on_circuit_breaker(self, event: CircuitBreakerEvent) -> None:
        """Fan out circuit breaker event to all observers.

        Args:
            event: The circuit breaker event details
        """
        for observer in self._observers:
            try:
                observer.on_circuit_breaker(event)
            except Exception as e:
                logger.debug(
                    "Observer failed to handle circuit breaker event",
                    observer_type=type(observer).__name__,
                    error=str(e),
                )

    def on_timeout(self, event: TimeoutEvent) -> None:
        """Fan out timeout event to all observers.

        Args:
            event: The timeout event details
        """
        for observer in self._observers:
            try:
                observer.on_timeout(event)
            except Exception as e:
                logger.debug(
                    "Observer failed to handle timeout event",
                    observer_type=type(observer).__name__,
                    error=str(e),
                )

    def on_provider_selected(self, event: ProviderSelectionEvent) -> None:
        """Fan out provider selection event to all observers.

        Args:
            event: The provider selection event details
        """
        for observer in self._observers:
            try:
                observer.on_provider_selected(event)
            except Exception as e:
                logger.debug(
                    "Observer failed to handle provider selection event",
                    observer_type=type(observer).__name__,
                    error=str(e),
                )


__all__ = [
    "CircuitBreakerEvent",
    "CompositeObserver",
    "LoggingObserver",
    "ProviderObserver",
    "ProviderSelectionEvent",
    "RetryEvent",
    "TimeoutEvent",
]
