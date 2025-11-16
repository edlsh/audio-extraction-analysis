"""Test suite for retry utilities.

Tests the retry decorators and utility functions in src.utils.retry module,
covering:
- Network error retry with exponential backoff and jitter
- Rate limit retry with awareness of Retry-After headers
- Transient vs permanent error distinction
- FFmpeg operation retry (minimal)
- Custom retry decorator factory
- Retry attempt logging
"""

from __future__ import annotations

import pytest
from unittest.mock import Mock, patch
from pathlib import Path

from src.utils.retry import (
    retry_on_network_error,
    retry_on_rate_limit,
    retry_on_transient_error,
    retry_ffmpeg_operation,
    create_custom_retry,
    log_retry_attempt,
    PERMANENT_EXCEPTIONS,
)
from src.exceptions import (
    ProviderTimeoutError,
    ProviderRateLimitError,
    ProviderAuthenticationError,
    ValidationError,
    FFmpegExecutionError,
    AudioFileCorruptedError,
)


class TestRetryOnNetworkError:
    """Test retry_on_network_error decorator."""

    def test_succeeds_on_first_attempt(self):
        """Test that successful calls don't trigger retries."""
        call_count = 0

        @retry_on_network_error(max_attempts=3)
        def successful_call():
            nonlocal call_count
            call_count += 1
            return "success"

        result = successful_call()

        assert result == "success"
        assert call_count == 1

    def test_retries_on_network_error(self):
        """Test that ProviderTimeoutError triggers retries."""
        call_count = 0

        @retry_on_network_error(max_attempts=3)
        def failing_call():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ProviderTimeoutError("Connection failed")
            return "success"

        result = failing_call()

        assert result == "success"
        assert call_count == 3

    def test_gives_up_after_max_attempts(self):
        """Test that retry gives up after max attempts."""
        call_count = 0

        @retry_on_network_error(max_attempts=3)
        def always_fails():
            nonlocal call_count
            call_count += 1
            raise ProviderTimeoutError("Permanent network failure")

        with pytest.raises(ProviderTimeoutError):
            always_fails()

        assert call_count == 3

    def test_does_not_retry_permanent_errors(self):
        """Test that permanent errors are not retried."""
        call_count = 0

        @retry_on_network_error(max_attempts=3)
        def fails_with_auth_error():
            nonlocal call_count
            call_count += 1
            raise ProviderAuthenticationError("Invalid credentials")

        with pytest.raises(ProviderAuthenticationError):
            fails_with_auth_error()

        # Should only be called once (no retries)
        assert call_count == 1

    def test_custom_exceptions(self):
        """Test retry with custom exception types."""
        call_count = 0

        @retry_on_network_error(max_attempts=3, exceptions=(TimeoutError, ConnectionError))
        def fails_with_timeout():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise TimeoutError("Request timed out")
            return "success"

        result = fails_with_timeout()

        assert result == "success"
        assert call_count == 2


class TestRetryOnRateLimit:
    """Test retry_on_rate_limit decorator."""

    def test_succeeds_without_rate_limit(self):
        """Test successful calls without rate limiting."""
        call_count = 0

        @retry_on_rate_limit(max_attempts=5)
        def successful_call():
            nonlocal call_count
            call_count += 1
            return "success"

        result = successful_call()

        assert result == "success"
        assert call_count == 1

    def test_retries_on_rate_limit(self):
        """Test retry behavior when rate limited."""
        call_count = 0

        @retry_on_rate_limit(max_attempts=5)
        def rate_limited_call():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ProviderRateLimitError("Rate limit exceeded")
            return "success"

        result = rate_limited_call()

        assert result == "success"
        assert call_count == 3

    def test_gives_up_after_max_attempts(self):
        """Test that retry gives up after max attempts."""
        call_count = 0

        @retry_on_rate_limit(max_attempts=3)
        def always_rate_limited():
            nonlocal call_count
            call_count += 1
            raise ProviderRateLimitError("Persistent rate limit")

        with pytest.raises(ProviderRateLimitError):
            always_rate_limited()

        assert call_count == 3


class TestRetryOnTransientError:
    """Test retry_on_transient_error decorator."""

    def test_retries_transient_errors(self):
        """Test retry on transient errors (ProviderTimeoutError, ProviderRateLimitError)."""
        call_count = 0

        @retry_on_transient_error(max_attempts=3)
        def transient_failure():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ProviderTimeoutError("Temporary network issue")
            return "success"

        result = transient_failure()

        assert result == "success"
        assert call_count == 2

    def test_does_not_retry_permanent_errors(self):
        """Test that permanent errors fail immediately."""
        call_count = 0

        @retry_on_transient_error(max_attempts=3)
        def permanent_failure():
            nonlocal call_count
            call_count += 1
            raise ProviderAuthenticationError("Invalid API key")

        with pytest.raises(ProviderAuthenticationError):
            permanent_failure()

        # Should only be called once (no retries for permanent errors)
        assert call_count == 1

    def test_custom_transient_exceptions(self):
        """Test retry with custom transient exception types."""
        call_count = 0

        @retry_on_transient_error(max_attempts=3, exceptions=(TimeoutError, IOError))
        def custom_transient():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise TimeoutError("Temporary timeout")
            return "success"

        result = custom_transient()

        assert result == "success"
        assert call_count == 2

    def test_validates_permanent_exception_list(self):
        """Test that all permanent exceptions are not retried."""
        for exc_type in PERMANENT_EXCEPTIONS:
            call_count = 0

            @retry_on_transient_error(max_attempts=3)
            def fails_with_permanent():
                nonlocal call_count
                call_count += 1
                raise exc_type("Permanent error")

            with pytest.raises(exc_type):
                fails_with_permanent()

            assert call_count == 1, f"{exc_type.__name__} should not be retried"


class TestRetryFFmpegOperation:
    """Test retry_ffmpeg_operation decorator."""

    def test_succeeds_on_first_attempt(self):
        """Test successful FFmpeg operation without retry."""
        call_count = 0

        @retry_ffmpeg_operation(max_attempts=2)
        def successful_ffmpeg():
            nonlocal call_count
            call_count += 1
            return Path("/tmp/output.mp3")

        result = successful_ffmpeg()

        assert result == Path("/tmp/output.mp3")
        assert call_count == 1

    def test_retries_on_execution_error(self):
        """Test retry on FFmpegExecutionError (transient I/O issue)."""
        call_count = 0

        @retry_ffmpeg_operation(max_attempts=2)
        def transient_ffmpeg_error():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise FFmpegExecutionError("Temporary I/O error")
            return Path("/tmp/output.mp3")

        result = transient_ffmpeg_error()

        assert result == Path("/tmp/output.mp3")
        assert call_count == 2

    def test_does_not_retry_corrupted_file(self):
        """Test that corrupted file errors are not retried."""
        call_count = 0

        @retry_ffmpeg_operation(max_attempts=2)
        def corrupted_file():
            nonlocal call_count
            call_count += 1
            raise AudioFileCorruptedError("Input file is corrupted")

        with pytest.raises(AudioFileCorruptedError):
            corrupted_file()

        # Should only be called once (no retry for corrupted files)
        assert call_count == 1

    def test_minimal_retry_count(self):
        """Test that FFmpeg retry is minimal (max 2 attempts by default)."""
        call_count = 0

        @retry_ffmpeg_operation()  # Uses default max_attempts=2
        def always_fails():
            nonlocal call_count
            call_count += 1
            raise FFmpegExecutionError("Persistent FFmpeg error")

        with pytest.raises(FFmpegExecutionError):
            always_fails()

        assert call_count == 2  # Default is 2 attempts


class TestCreateCustomRetry:
    """Test create_custom_retry factory function."""

    def test_custom_retry_with_specific_exceptions(self):
        """Test custom retry with specific exception types."""
        call_count = 0

        custom_retry = create_custom_retry(
            exceptions=(ValueError, TypeError),
            max_attempts=3,
            initial_wait=0.1,
            max_wait=1.0,
        )

        @custom_retry
        def custom_failure():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("Temporary value error")
            return "success"

        result = custom_failure()

        assert result == "success"
        assert call_count == 2

    def test_custom_retry_excludes_exceptions(self):
        """Test custom retry with excluded exceptions."""
        call_count = 0

        custom_retry = create_custom_retry(
            exceptions=(Exception,),  # Retry all exceptions
            max_attempts=3,
            exclude_exceptions=(ValidationError, ProviderAuthenticationError),
        )

        @custom_retry
        def excluded_failure():
            nonlocal call_count
            call_count += 1
            raise ValidationError("Validation failed")

        with pytest.raises(ValidationError):
            excluded_failure()

        # Should only be called once (excluded from retry)
        assert call_count == 1

    def test_custom_retry_without_jitter(self):
        """Test custom retry without jitter (deterministic backoff)."""
        call_count = 0

        custom_retry = create_custom_retry(
            exceptions=(RuntimeError,),
            max_attempts=3,
            initial_wait=0.1,
            max_wait=1.0,
            use_jitter=False,  # Deterministic backoff
        )

        @custom_retry
        def no_jitter_failure():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise RuntimeError("Temporary error")
            return "success"

        result = no_jitter_failure()

        assert result == "success"
        assert call_count == 2

    def test_custom_retry_max_attempts(self):
        """Test custom retry respects max_attempts."""
        call_count = 0

        custom_retry = create_custom_retry(
            exceptions=(RuntimeError,),
            max_attempts=5,
            initial_wait=0.1,
        )

        @custom_retry
        def always_fails():
            nonlocal call_count
            call_count += 1
            raise RuntimeError("Persistent error")

        with pytest.raises(RuntimeError):
            always_fails()

        assert call_count == 5


class TestLogRetryAttempt:
    """Test log_retry_attempt utility function."""

    @patch("src.utils.retry_tenacity.logger")
    def test_logs_retry_attempt(self, mock_logger):
        """Test that retry attempts are logged correctly."""
        from tenacity import RetryCallState
        from unittest.mock import MagicMock

        # Create a mock retry state
        retry_state = MagicMock(spec=RetryCallState)
        retry_state.attempt_number = 2
        retry_state.seconds_since_start = 1.5

        # Create mock outcome with exception
        outcome = MagicMock()
        outcome.exception.return_value = ProviderTimeoutError("Connection failed")
        retry_state.outcome = outcome

        # Call the logging function
        log_retry_attempt(retry_state)

        # Verify logging was called
        mock_logger.warning.assert_called_once()
        call_args = mock_logger.warning.call_args[0][0]
        assert "Retry attempt 2" in call_args
        assert "1.50s" in call_args
        assert "ProviderTimeoutError" in call_args


class TestRetryIntegration:
    """Integration tests for retry decorators."""

    def test_async_function_retry(self):
        """Test retry decorator works with async functions."""
        import asyncio

        call_count = 0

        @retry_on_network_error(max_attempts=3)
        async def async_network_call():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ProviderTimeoutError("Async network error")
            return "async success"

        # Run async function
        result = asyncio.run(async_network_call())

        assert result == "async success"
        assert call_count == 2

    def test_retry_preserves_return_type(self):
        """Test that retry decorator preserves return type."""

        @retry_on_network_error(max_attempts=3)
        def returns_dict() -> dict[str, str]:
            return {"status": "ok", "data": "test"}

        result = returns_dict()

        assert isinstance(result, dict)
        assert result["status"] == "ok"
        assert result["data"] == "test"

    def test_retry_preserves_exceptions(self):
        """Test that final exception is preserved after all retries."""

        @retry_on_network_error(max_attempts=3)
        def always_fails():
            raise ProviderTimeoutError("Final error message")

        with pytest.raises(ProviderTimeoutError) as exc_info:
            always_fails()

        assert "Final error message" in str(exc_info.value)


# === Parameterized Tests ===


@pytest.mark.parametrize(
    "max_attempts,expected_calls",
    [
        (1, 1),
        (2, 2),
        (3, 3),
        (5, 5),
    ],
)
def test_retry_attempt_counts(max_attempts, expected_calls):
    """Test that retry respects max_attempts parameter."""
    call_count = 0

    @retry_on_network_error(max_attempts=max_attempts)
    def failing_call():
        nonlocal call_count
        call_count += 1
        raise ProviderTimeoutError("Test error")

    with pytest.raises(ProviderTimeoutError):
        failing_call()

    assert call_count == expected_calls


@pytest.mark.parametrize(
    "exception_type",
    [
        ProviderAuthenticationError,
        ValidationError,
        ValueError,
        FileNotFoundError,
        PermissionError,
    ],
)
def test_permanent_exceptions_not_retried(exception_type):
    """Test that all permanent exception types are not retried."""
    call_count = 0

    @retry_on_transient_error(max_attempts=3)
    def fails_permanently():
        nonlocal call_count
        call_count += 1
        raise exception_type("Permanent error")

    with pytest.raises(exception_type):
        fails_permanently()

    assert call_count == 1  # No retries for permanent errors
