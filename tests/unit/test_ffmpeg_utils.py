"""Unit tests for ffmpeg_utils.py - FFmpeg error handling decorators.

Tests cover:
- handle_ffmpeg_errors decorator (synchronous)
- handle_ffmpeg_errors_async decorator (asynchronous)
- All error types (CalledProcessError, TimeoutExpired, FileNotFoundError, etc.)
- Custom operation names in error messages
- Function metadata preservation
- Return value handling (None on error, actual value on success)
"""

import logging
import subprocess
from typing import Optional

import pytest

from src.utils.ffmpeg_utils import handle_ffmpeg_errors, handle_ffmpeg_errors_async


class TestHandleFfmpegErrorsDecorator:
    """Tests for handle_ffmpeg_errors - synchronous error handling decorator."""

    def test_successful_execution(self):
        """Test that decorator allows successful function execution."""

        @handle_ffmpeg_errors("Test operation")
        def successful_func(value: int) -> int:
            return value * 2

        result = successful_func(5)
        assert result == 10

    def test_called_process_error_returns_none(self):
        """Test CalledProcessError is caught and returns None."""

        @handle_ffmpeg_errors("FFmpeg extraction")
        def failing_func() -> Optional[str]:
            raise subprocess.CalledProcessError(1, ["ffmpeg"], stderr="FFmpeg error")

        result = failing_func()
        assert result is None

    def test_timeout_expired_returns_none(self):
        """Test TimeoutExpired is caught and returns None."""

        @handle_ffmpeg_errors("FFmpeg timeout test")
        def timeout_func() -> Optional[str]:
            raise subprocess.TimeoutExpired(["ffmpeg"], 30)

        result = timeout_func()
        assert result is None

    def test_file_not_found_returns_none(self):
        """Test FileNotFoundError is caught and returns None."""

        @handle_ffmpeg_errors("File operation")
        def file_not_found_func() -> Optional[str]:
            raise FileNotFoundError("Input file missing")

        result = file_not_found_func()
        assert result is None

    def test_permission_error_returns_none(self):
        """Test PermissionError is caught and returns None."""

        @handle_ffmpeg_errors("Permission test")
        def permission_func() -> Optional[str]:
            raise PermissionError("No write access")

        result = permission_func()
        assert result is None

    def test_os_error_returns_none(self):
        """Test OSError is caught and returns None."""

        @handle_ffmpeg_errors("OS operation")
        def os_error_func() -> Optional[str]:
            raise OSError("System error occurred")

        result = os_error_func()
        assert result is None

    def test_value_error_returns_none(self):
        """Test ValueError is caught and returns None."""

        @handle_ffmpeg_errors("Input validation")
        def value_error_func() -> Optional[str]:
            raise ValueError("Invalid input parameter")

        result = value_error_func()
        assert result is None

    def test_custom_operation_name(self):
        """Test that custom operation name is used in logging."""
        operation_name = "Custom audio extraction"

        @handle_ffmpeg_errors(operation_name)
        def custom_name_func() -> Optional[str]:
            raise ValueError("Test error")

        # Function should still return None despite the error
        result = custom_name_func()
        assert result is None

    def test_default_operation_name(self):
        """Test that default operation name is used when not specified."""

        @handle_ffmpeg_errors()
        def default_name_func() -> Optional[str]:
            raise ValueError("Test error")

        result = default_name_func()
        assert result is None

    def test_none_operation_name(self):
        """Test that None as operation name is handled gracefully."""

        @handle_ffmpeg_errors(None)
        def none_name_func() -> Optional[str]:
            raise ValueError("Test error")

        result = none_name_func()
        assert result is None

    def test_empty_operation_name(self):
        """Test that empty string as operation name is handled gracefully."""

        @handle_ffmpeg_errors("")
        def empty_name_func() -> Optional[str]:
            raise ValueError("Test error")

        result = empty_name_func()
        assert result is None

    def test_preserves_function_metadata(self):
        """Test that decorator preserves original function metadata."""

        @handle_ffmpeg_errors("Test")
        def documented_func() -> str:
            """This is a test function."""
            return "result"

        assert documented_func.__name__ == "documented_func"
        assert documented_func.__doc__ == "This is a test function."

    def test_handles_function_with_args(self):
        """Test decorator works with functions that have arguments."""

        @handle_ffmpeg_errors("Args test")
        def func_with_args(a: int, b: int, c: int = 10) -> int:
            return a + b + c

        result = func_with_args(5, 3)
        assert result == 18

        result_with_kwarg = func_with_args(5, 3, c=20)
        assert result_with_kwarg == 28

    def test_handles_function_with_kwargs(self):
        """Test decorator works with functions that use **kwargs."""

        @handle_ffmpeg_errors("Kwargs test")
        def func_with_kwargs(**kwargs) -> dict:
            return kwargs

        result = func_with_kwargs(key1="value1", key2="value2")
        assert result == {"key1": "value1", "key2": "value2"}

    def test_called_process_error_with_stderr(self):
        """Test CalledProcessError with stderr attribute is handled."""

        @handle_ffmpeg_errors("Stderr test")
        def func_with_stderr() -> Optional[str]:
            error = subprocess.CalledProcessError(1, ["ffmpeg"], stderr="Detailed error message")
            raise error

        result = func_with_stderr()
        assert result is None

    def test_called_process_error_without_stderr(self):
        """Test CalledProcessError without stderr attribute is handled."""

        @handle_ffmpeg_errors("No stderr test")
        def func_without_stderr() -> Optional[str]:
            error = subprocess.CalledProcessError(1, ["ffmpeg"])
            # Edge case: Ensure decorator handles CalledProcessError when stderr is missing
            # Some subprocess calls may not populate stderr, so we test this explicitly
            if hasattr(error, "stderr"):
                delattr(error, "stderr")
            raise error

        result = func_without_stderr()
        assert result is None

    def test_unhandled_exception_propagates(self):
        """Test that unhandled exceptions are not caught."""

        @handle_ffmpeg_errors("Exception test")
        def unhandled_exception_func() -> str:
            raise RuntimeError("Unhandled error")

        with pytest.raises(RuntimeError, match="Unhandled error"):
            unhandled_exception_func()

    def test_returns_none_type_hint(self):
        """Test decorator with Optional return type returns None on error."""

        @handle_ffmpeg_errors("Type hint test")
        def optional_return_func() -> Optional[str]:
            raise ValueError("Error")

        result = optional_return_func()
        assert result is None
        assert isinstance(result, type(None))

    def test_logs_error_messages(self, caplog):
        """Test that errors are logged with appropriate messages."""
        with caplog.at_level(logging.ERROR):

            @handle_ffmpeg_errors("Logging test")
            def logging_func() -> Optional[str]:
                raise FileNotFoundError("Test file missing")

            result = logging_func()

            assert result is None
            assert len(caplog.records) > 0
            assert "Logging test" in caplog.text
            assert "Test file missing" in caplog.text


class TestHandleFfmpegErrorsAsyncDecorator:
    """Tests for handle_ffmpeg_errors_async - asynchronous error handling decorator."""

    @pytest.mark.asyncio
    async def test_successful_async_execution(self):
        """Test that decorator allows successful async function execution."""

        @handle_ffmpeg_errors_async("Async test operation")
        async def successful_async_func(value: int) -> int:
            return value * 3

        result = await successful_async_func(5)
        assert result == 15

    @pytest.mark.asyncio
    async def test_async_called_process_error_returns_none(self):
        """Test async CalledProcessError is caught and returns None."""

        @handle_ffmpeg_errors_async("Async FFmpeg extraction")
        async def failing_async_func() -> Optional[str]:
            raise subprocess.CalledProcessError(1, ["ffmpeg"], stderr="Async error")

        result = await failing_async_func()
        assert result is None

    @pytest.mark.asyncio
    async def test_async_timeout_expired_returns_none(self):
        """Test async TimeoutExpired is caught and returns None."""

        @handle_ffmpeg_errors_async("Async timeout test")
        async def timeout_async_func() -> Optional[str]:
            raise subprocess.TimeoutExpired(["ffmpeg"], 60)

        result = await timeout_async_func()
        assert result is None

    @pytest.mark.asyncio
    async def test_async_file_not_found_returns_none(self):
        """Test async FileNotFoundError is caught and returns None."""

        @handle_ffmpeg_errors_async("Async file operation")
        async def file_not_found_async_func() -> Optional[str]:
            raise FileNotFoundError("Async input file missing")

        result = await file_not_found_async_func()
        assert result is None

    @pytest.mark.asyncio
    async def test_async_permission_error_returns_none(self):
        """Test async PermissionError is caught and returns None."""

        @handle_ffmpeg_errors_async("Async permission test")
        async def permission_async_func() -> Optional[str]:
            raise PermissionError("Async no write access")

        result = await permission_async_func()
        assert result is None

    @pytest.mark.asyncio
    async def test_async_os_error_returns_none(self):
        """Test async OSError is caught and returns None."""

        @handle_ffmpeg_errors_async("Async OS operation")
        async def os_error_async_func() -> Optional[str]:
            raise OSError("Async system error")

        result = await os_error_async_func()
        assert result is None

    @pytest.mark.asyncio
    async def test_async_value_error_returns_none(self):
        """Test async ValueError is caught and returns None."""

        @handle_ffmpeg_errors_async("Async input validation")
        async def value_error_async_func() -> Optional[str]:
            raise ValueError("Async invalid input")

        result = await value_error_async_func()
        assert result is None

    @pytest.mark.asyncio
    async def test_async_custom_operation_name(self):
        """Test that custom operation name is used in async logging."""
        operation_name = "Custom async audio extraction"

        @handle_ffmpeg_errors_async(operation_name)
        async def custom_name_async_func() -> Optional[str]:
            raise ValueError("Async test error")

        result = await custom_name_async_func()
        assert result is None

    @pytest.mark.asyncio
    async def test_async_default_operation_name(self):
        """Test that default operation name is used in async when not specified."""

        @handle_ffmpeg_errors_async()
        async def default_name_async_func() -> Optional[str]:
            raise ValueError("Async test error")

        result = await default_name_async_func()
        assert result is None

    @pytest.mark.asyncio
    async def test_async_none_operation_name(self):
        """Test that None as operation name is handled gracefully in async."""

        @handle_ffmpeg_errors_async(None)
        async def none_name_async_func() -> Optional[str]:
            raise ValueError("Async test error")

        result = await none_name_async_func()
        assert result is None

    @pytest.mark.asyncio
    async def test_async_empty_operation_name(self):
        """Test that empty string as operation name is handled gracefully in async."""

        @handle_ffmpeg_errors_async("")
        async def empty_name_async_func() -> Optional[str]:
            raise ValueError("Async test error")

        result = await empty_name_async_func()
        assert result is None

    @pytest.mark.asyncio
    async def test_async_preserves_function_metadata(self):
        """Test that async decorator preserves original function metadata."""

        @handle_ffmpeg_errors_async("Async test")
        async def documented_async_func() -> str:
            """This is an async test function."""
            return "async result"

        assert documented_async_func.__name__ == "documented_async_func"
        assert documented_async_func.__doc__ == "This is an async test function."

    @pytest.mark.asyncio
    async def test_async_handles_function_with_args(self):
        """Test async decorator works with functions that have arguments."""

        @handle_ffmpeg_errors_async("Async args test")
        async def async_func_with_args(a: int, b: int, c: int = 10) -> int:
            return a + b + c

        result = await async_func_with_args(5, 3)
        assert result == 18

        result_with_kwarg = await async_func_with_args(5, 3, c=20)
        assert result_with_kwarg == 28

    @pytest.mark.asyncio
    async def test_async_handles_function_with_kwargs(self):
        """Test async decorator works with functions that use **kwargs."""

        @handle_ffmpeg_errors_async("Async kwargs test")
        async def async_func_with_kwargs(**kwargs) -> dict:
            return kwargs

        result = await async_func_with_kwargs(key1="value1", key2="value2")
        assert result == {"key1": "value1", "key2": "value2"}

    @pytest.mark.asyncio
    async def test_async_unhandled_exception_propagates(self):
        """Test that unhandled exceptions are not caught in async."""

        @handle_ffmpeg_errors_async("Async exception test")
        async def unhandled_async_exception_func() -> str:
            raise RuntimeError("Async unhandled error")

        with pytest.raises(RuntimeError, match="Async unhandled error"):
            await unhandled_async_exception_func()

    @pytest.mark.asyncio
    async def test_async_logs_error_messages(self, caplog):
        """Test that async errors are logged with appropriate messages."""
        with caplog.at_level(logging.ERROR):

            @handle_ffmpeg_errors_async("Async logging test")
            async def logging_async_func() -> Optional[str]:
                raise FileNotFoundError("Async test file missing")

            result = await logging_async_func()

            assert result is None
            assert len(caplog.records) > 0
            assert "Async logging test" in caplog.text
            assert "Async test file missing" in caplog.text


class TestDecoratorComparison:
    """Tests comparing sync and async decorator behavior."""

    @pytest.mark.asyncio
    async def test_sync_and_async_handle_same_errors(self):
        """Test that both decorators handle the same error types."""

        @handle_ffmpeg_errors("Sync comparison")
        def sync_func() -> Optional[str]:
            raise ValueError("Sync error")

        @handle_ffmpeg_errors_async("Async comparison")
        async def async_func() -> Optional[str]:
            raise ValueError("Async error")

        # Both should return None
        sync_result = sync_func()
        assert sync_result is None

        # Test async with consistent pytest.mark.asyncio pattern
        async_result = await async_func()
        assert async_result is None

    def test_both_decorators_preserve_metadata(self):
        """Test that both decorators preserve function metadata."""

        @handle_ffmpeg_errors("Sync metadata")
        def sync_func() -> str:
            """Sync docstring."""
            return "sync"

        @handle_ffmpeg_errors_async("Async metadata")
        async def async_func() -> str:
            """Async docstring."""
            return "async"

        assert sync_func.__name__ == "sync_func"
        assert sync_func.__doc__ == "Sync docstring."

        assert async_func.__name__ == "async_func"
        assert async_func.__doc__ == "Async docstring."
