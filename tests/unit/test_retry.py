"""Tests for retry utilities."""

from __future__ import annotations

import pytest

from src.utils.retry import (
    RetryConfig,
    RetryExhaustedError,
    calculate_delay,
    is_retriable_exception,
    retry_async,
    retry_sync,
)


class TestRetryConfig:
    """Test RetryConfig dataclass."""

    def test_default_values(self):
        config = RetryConfig()
        assert config.max_attempts == 3
        assert config.base_delay == 1.0
        assert config.max_delay == 60.0
        assert config.jitter is True

    def test_custom_values(self):
        config = RetryConfig(max_attempts=5, base_delay=2.0, max_delay=120.0, jitter=False)
        assert config.max_attempts == 5
        assert config.base_delay == 2.0
        assert config.max_delay == 120.0
        assert config.jitter is False

    def test_validation_max_attempts(self):
        with pytest.raises(ValueError, match="max_attempts must be at least 1"):
            RetryConfig(max_attempts=0)

    def test_validation_max_delay(self):
        with pytest.raises(ValueError, match="max_delay must be >= base_delay"):
            RetryConfig(base_delay=10.0, max_delay=5.0)


class TestCalculateDelay:
    """Test delay calculation with exponential backoff."""

    def test_first_attempt_no_delay(self):
        delay = calculate_delay(0, 1.0, 60.0, 2.0, jitter=False)
        assert delay == 0.0

    def test_exponential_backoff(self):
        delay1 = calculate_delay(1, 1.0, 60.0, 2.0, jitter=False)
        delay2 = calculate_delay(2, 1.0, 60.0, 2.0, jitter=False)
        assert delay1 == 1.0
        assert delay2 == 2.0

    def test_respects_max_delay(self):
        delay = calculate_delay(10, 1.0, 5.0, 2.0, jitter=False)
        assert delay <= 5.0


class TestIsRetriableException:
    """Test exception classification."""

    def test_connection_error_is_retriable(self):
        assert is_retriable_exception(ConnectionError(), (ConnectionError, TimeoutError))

    def test_timeout_error_is_retriable(self):
        assert is_retriable_exception(TimeoutError(), (ConnectionError, TimeoutError))

    def test_value_error_not_retriable(self):
        assert not is_retriable_exception(ValueError(), (ConnectionError, TimeoutError))


class TestRetrySyncDecorator:
    """Test synchronous retry decorator."""

    def test_succeeds_without_retry(self):
        call_count = 0

        @retry_sync(max_attempts=3)
        def succeeds():
            nonlocal call_count
            call_count += 1
            return "ok"

        result = succeeds()
        assert result == "ok"
        assert call_count == 1

    def test_retries_on_error(self):
        call_count = 0

        @retry_sync(max_attempts=3, base_delay=0.01, retriable_exceptions=(ValueError,))
        def fails_twice():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("fail")
            return "ok"

        result = fails_twice()
        assert result == "ok"
        assert call_count == 3

    def test_exhausts_retries(self):
        @retry_sync(max_attempts=2, base_delay=0.01, retriable_exceptions=(ValueError,))
        def always_fails():
            raise ValueError("always fails")

        with pytest.raises(RetryExhaustedError):
            always_fails()


class TestRetryAsyncDecorator:
    """Test asynchronous retry decorator."""

    @pytest.mark.asyncio
    async def test_succeeds_without_retry(self):
        call_count = 0

        @retry_async(max_attempts=3)
        async def succeeds():
            nonlocal call_count
            call_count += 1
            return "ok"

        result = await succeeds()
        assert result == "ok"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retries_on_error(self):
        call_count = 0

        @retry_async(max_attempts=3, base_delay=0.01, retriable_exceptions=(ValueError,))
        async def fails_twice():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("fail")
            return "ok"

        result = await fails_twice()
        assert result == "ok"
        assert call_count == 3
