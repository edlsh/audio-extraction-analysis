"""
Base classes and utilities for end-to-end testing.

This module provides a comprehensive testing framework for end-to-end testing
of the audio extraction and analysis system. It includes:

- Base test classes with common setup/teardown functionality
- Test result and test file dataclasses for structured data
- Mixins for CLI testing, performance monitoring, security testing, and provider mocking
- Utilities for managing test environments, temporary files, and output validation

Typical usage:
    class MyE2ETest(E2ETestBase, CLITestMixin):
        def test_extraction(self):
            result = self.run_extract_command("input.mp4")
            assert result.success
"""

import os
import subprocess
import tempfile
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Union


@dataclass
class TestResult:
    """
    Encapsulates test execution results from CLI command execution.

    Attributes:
        success: True if the command executed successfully (exit code 0)
        output: Standard output (stdout) from the command
        error: Standard error (stderr) from the command
        duration: Execution time in seconds (as a float)
        exit_code: Process exit code (-1 for timeout/exception, 0 for success)
    """

    success: bool
    output: str
    error: str
    duration: float
    exit_code: int

    @property
    def failed(self) -> bool:
        """Convenience property to check if the test result indicates failure."""
        return not self.success


@dataclass
class TestFile:
    """
    Test media file specification for managing test assets.

    Attributes:
        name: Human-readable name identifier for the test file
        path: Full filesystem path to the test file
        duration: Optional duration of the media file in seconds
        size: Optional file size in bytes
        format: Optional media format (e.g., 'mp4', 'wav', 'mp3')
        description: Optional human-readable description of what the file tests
    """

    name: str
    path: Path
    duration: Optional[float] = None
    size: Optional[int] = None
    format: Optional[str] = None
    description: str = ""


class E2ETestBase:
    """
    Base class for end-to-end tests with common utilities.

    Provides standard setup/teardown functionality, temporary directory management,
    environment variable handling, and common test utilities. Integrates with
    TestDataManager for accessing shared test media files.

    Attributes created during setup:
        temp_dir: Temporary directory for test execution
        output_dir: Directory for test output files
        original_env: Backup of environment variables for restoration
        test_data_manager: Manager for accessing test data files
        test_files: Generated test file specifications
    """

    def setup_method(self):
        """
        Setup test environment before each test method.

        Creates temporary directories for test execution and output,
        backs up environment variables, and initializes test data manager
        with shared test files.
        """
        self.temp_dir = Path(tempfile.mkdtemp(prefix="e2e_test_"))
        self.output_dir = self.temp_dir / "output"
        self.output_dir.mkdir(exist_ok=True)

        # Store original environment
        self.original_env = dict(os.environ)

        # Ensure shared test data is available
        if not hasattr(self, "test_data_manager"):
            from .test_data_manager import TestDataManager

            self.test_data_manager = TestDataManager()
        if not hasattr(self, "test_files"):
            self.test_files = self.test_data_manager.generate_all_test_files()

    def teardown_method(self):
        """
        Cleanup after each test method.

        Restores original environment variables and removes all temporary
        files and directories created during the test.
        """
        # Restore original environment
        os.environ.clear()
        os.environ.update(self.original_env)

        # Cleanup temporary files
        self._cleanup_temp_files()

    def _cleanup_temp_files(self):
        """
        Remove temporary test files and directories.

        Recursively deletes the temporary directory created during setup,
        ignoring any errors that occur during deletion.
        """
        import shutil

        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def run_cli_command(
        self, command: List[str], timeout: int = 300, env_vars: Optional[Dict[str, str]] = None
    ) -> TestResult:
        """
        Execute CLI command and return results.

        Args:
            command: CLI command as list of strings
            timeout: Maximum execution time in seconds
            env_vars: Additional environment variables

        Returns:
            TestResult with execution details
        """
        start_time = time.time()

        # Prepare environment
        test_env = os.environ.copy()
        if env_vars:
            test_env.update(env_vars)

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=test_env,
                cwd=self.temp_dir,
            )

            duration = time.time() - start_time

            return TestResult(
                success=result.returncode == 0,
                output=result.stdout,
                error=result.stderr,
                duration=duration,
                exit_code=result.returncode,
            )

        except subprocess.TimeoutExpired:
            duration = time.time() - start_time
            return TestResult(
                success=False,
                output="",
                error=f"Command timed out after {timeout} seconds",
                duration=duration,
                exit_code=-1,
            )
        except Exception as e:
            duration = time.time() - start_time
            return TestResult(
                success=False, output="", error=str(e), duration=duration, exit_code=-1
            )

    def validate_output_files(self, expected_files: List[str]) -> Dict[str, bool]:
        """
        Validate that expected output files exist and are non-empty.

        Args:
            expected_files: List of expected output file names

        Returns:
            Dictionary mapping file names to existence status
        """
        results = {}
        for filename in expected_files:
            file_path = self.output_dir / filename
            exists = file_path.exists()
            non_empty = exists and file_path.stat().st_size > 0
            results[filename] = exists and non_empty
        return results

    def assert_files_exist(self, expected_files: List[str]):
        """
        Assert that all expected files exist and are non-empty.

        Args:
            expected_files: List of expected output file names

        Raises:
            AssertionError: If any file doesn't exist or is empty
        """
        validation_results = self.validate_output_files(expected_files)
        for filename, exists in validation_results.items():
            assert exists, f"Expected output file '{filename}' does not exist or is empty"

    def set_test_env(self, **env_vars):
        """
        Set environment variables for testing.

        Args:
            **env_vars: Keyword arguments where keys are environment variable
                names and values are their corresponding values
        """
        for key, value in env_vars.items():
            os.environ[key] = value

    def get_test_data_path(self) -> Path:
        """
        Get path to test data directory.

        Returns:
            Path object pointing to the test_data directory within tests/e2e/
        """
        return Path(__file__).parent / "test_data"

    @contextmanager
    def subTest(self, **_params):
        """
        Pytest compatibility shim for unittest-style subTest contexts.

        Provides a no-op context manager to support legacy tests that use
        unittest's subTest feature. Parameters are accepted but ignored.

        Args:
            **_params: Ignored parameters for compatibility

        Yields:
            None (no-op context)
        """
        yield


class CLITestMixin:
    """
    Mixin providing CLI-specific test utilities for audio processing commands.

    Provides convenient wrapper methods for running extract, transcribe, and
    process commands with common parameter configurations.
    """

    def run_extract_command(
        self,
        input_file: Union[str, Path],
        quality: str = "high",
        output_file: Optional[Union[str, Path]] = None,
        additional_args: Optional[List[str]] = None,
    ) -> TestResult:
        """
        Run audio extraction command.

        Args:
            input_file: Path to input media file
            quality: Extraction quality level (default: "high")
            output_file: Optional output file path
            additional_args: Optional list of additional CLI arguments

        Returns:
            TestResult containing command execution results
        """
        cmd = ["audio-extraction-analysis", "extract", str(input_file), "--quality", quality]

        if output_file:
            cmd.extend(["--output", str(output_file)])

        if additional_args:
            cmd.extend(additional_args)

        return self.run_cli_command(cmd)

    def run_transcribe_command(
        self,
        input_file: Union[str, Path],
        provider: str = "auto",
        language: str = "en",
        output_file: Optional[Union[str, Path]] = None,
        additional_args: Optional[List[str]] = None,
    ) -> TestResult:
        """
        Run transcription command.

        Args:
            input_file: Path to input audio file
            provider: Transcription provider to use (default: "auto")
            language: Language code for transcription (default: "en")
            output_file: Optional output file path for transcription
            additional_args: Optional list of additional CLI arguments

        Returns:
            TestResult containing command execution results
        """
        cmd = [
            "audio-extraction-analysis",
            "transcribe",
            str(input_file),
            "--provider",
            provider,
            "--language",
            language,
        ]

        if output_file:
            cmd.extend(["--output", str(output_file)])

        if additional_args:
            cmd.extend(additional_args)

        return self.run_cli_command(cmd)

    def run_process_command(
        self,
        input_file: Union[str, Path],
        output_dir: Optional[Union[str, Path]] = None,
        provider: str = "auto",
        quality: str = "high",
        additional_args: Optional[List[str]] = None,
    ) -> TestResult:
        """
        Run full processing pipeline command (extraction + transcription).

        Args:
            input_file: Path to input media file
            output_dir: Optional directory for output files
            provider: Transcription provider to use (default: "auto")
            quality: Extraction quality level (default: "high")
            additional_args: Optional list of additional CLI arguments

        Returns:
            TestResult containing command execution results
        """
        cmd = [
            "audio-extraction-analysis",
            "process",
            str(input_file),
            "--provider",
            provider,
            "--quality",
            quality,
        ]

        if output_dir:
            cmd.extend(["--output-dir", str(output_dir)])

        if additional_args:
            cmd.extend(additional_args)

        return self.run_cli_command(cmd)


class PerformanceTestMixin:
    """
    Mixin providing performance testing utilities.

    Includes tools for measuring execution time, asserting performance targets,
    and monitoring memory usage during test execution.
    """

    def measure_execution_time(self, func, *args, **kwargs) -> tuple:
        """
        Measure function execution time.

        Args:
            func: Callable to execute and measure
            *args: Positional arguments to pass to func
            **kwargs: Keyword arguments to pass to func

        Returns:
            Tuple of (function_result, duration_in_seconds)
        """
        start_time = time.time()
        result = func(*args, **kwargs)
        duration = time.time() - start_time
        return result, duration

    def assert_performance_target(self, duration: float, target: float, operation: str):
        """
        Assert that operation meets performance target.

        Args:
            duration: Actual execution duration in seconds
            target: Target maximum duration in seconds
            operation: Human-readable description of the operation

        Raises:
            AssertionError: If duration exceeds target
        """
        assert duration <= target, f"{operation} took {duration:.2f}s, expected <= {target}s"

    def monitor_memory_usage(self):
        """
        Context manager for monitoring memory usage during test execution.

        Returns:
            MemoryMonitor instance that tracks peak memory usage

        Example:
            with self.monitor_memory_usage() as monitor:
                # Run memory-intensive operation
                monitor.update_peak()
                memory_mb = monitor.get_memory_usage_mb()
        """
        import os

        import psutil

        class MemoryMonitor:
            """
            Tracks memory usage of the current process.

            Attributes:
                process: psutil.Process instance for current process
                peak_memory: Peak memory usage in bytes
                initial_memory: Initial memory usage in bytes at context entry
            """

            def __init__(self):
                self.process = psutil.Process(os.getpid())
                self.peak_memory = 0
                self.initial_memory = 0

            def __enter__(self):
                self.initial_memory = self.process.memory_info().rss
                return self

            def __exit__(self, exc_type, exc_val, exc_tb):
                pass

            def update_peak(self):
                """Update peak memory usage with current reading."""
                current_memory = self.process.memory_info().rss
                self.peak_memory = max(self.peak_memory, current_memory)

            def get_memory_usage_mb(self):
                """
                Get memory usage delta in megabytes.

                Returns:
                    Memory increase from initial to peak in MB
                """
                return (self.peak_memory - self.initial_memory) / 1024 / 1024

        return MemoryMonitor()


class SecurityTestMixin:
    """
    Mixin providing security testing utilities.

    Includes tools for testing path traversal, command injection, input sanitization,
    and output validation against common security vulnerabilities.
    """

    def create_malicious_filename(self, attack_type: str) -> str:
        """
        Create potentially malicious filenames for security testing.

        Args:
            attack_type: Type of security test (one of: "path_traversal",
                "command_injection", "unicode", "spaces", "special_chars", "long_name")

        Returns:
            Filename string designed to test the specified vulnerability
        """
        attacks = {
            "path_traversal": "../../../etc/passwd",
            "command_injection": "file.mp4; rm -rf /",
            "unicode": "test_unicode_名前.mp4",
            "spaces": "test file with spaces.mp4",
            "special_chars": "test@#$%^&*()file.mp4",
            "long_name": "a" * 300 + ".mp4",
        }
        return attacks.get(attack_type, "safe_test.mp4")

    def validate_output_sanitization(self, output: str) -> Dict[str, bool]:
        """
        Validate that output is properly sanitized against common vulnerabilities.

        Checks for control characters, script injection, API key leakage,
        and reasonable output length.

        Args:
            output: String output to validate

        Returns:
            Dictionary mapping check names to pass/fail status:
            - no_control_chars: No dangerous control characters present
            - no_script_tags: No HTML script tags detected
            - no_api_keys: No potential API key patterns found
            - reasonable_length: Output length under 1MB
        """
        checks = {
            "no_control_chars": not any(ord(c) < 32 for c in output if c not in "\n\r\t"),
            "no_script_tags": "<script>" not in output.lower(),
            "no_api_keys": not self._contains_api_key_pattern(output),
            "reasonable_length": len(output) < 1000000,  # 1MB max
        }
        return checks

    def _contains_api_key_pattern(self, text: str) -> bool:
        """
        Check if text contains potential API key patterns.

        Searches for common API key formats including long alphanumeric strings,
        OpenAI-style keys, and base64-encoded secrets.

        Args:
            text: Text to scan for API key patterns

        Returns:
            True if potential API key pattern detected, False otherwise
        """
        import re

        # Common API key patterns
        patterns = [
            r"[A-Za-z0-9]{32,}",  # Long alphanumeric strings
            r"sk-[A-Za-z0-9]{48}",  # OpenAI-style keys
            r"[A-Za-z0-9+/]{40,}={0,2}",  # Base64-encoded keys
        ]

        for pattern in patterns:
            if re.search(pattern, text):
                return True
        return False


class MockProviderMixin:
    """
    Mixin for mocking transcription provider responses during testing.

    Provides standardized mock responses for successful transcriptions and
    various failure scenarios to test error handling without requiring
    actual API calls.
    """

    def mock_successful_transcription(self):
        """
        Mock a successful transcription response.

        Returns:
            Dictionary containing mock transcription data with transcript text,
            speaker diarization, duration, and confidence score
        """
        return {
            "transcript": "This is a test transcription.",
            "speakers": [
                {"speaker": 0, "text": "Hello, this is speaker one."},
                {"speaker": 1, "text": "And this is speaker two responding."},
            ],
            "duration": 30.0,
            "confidence": 0.95,
        }

    def mock_provider_failure(self, error_type: str = "api_error"):
        """
        Mock various provider failure scenarios.

        Args:
            error_type: Type of failure to simulate (one of: "api_error",
                "auth_error", "file_too_large", "unsupported_format", "rate_limit")

        Returns:
            Dictionary containing error message for the specified failure type
        """
        errors = {
            "api_error": "API service temporarily unavailable",
            "auth_error": "Invalid API key",
            "file_too_large": "File exceeds maximum size limit",
            "unsupported_format": "Audio format not supported",
            "rate_limit": "Rate limit exceeded",
        }
        return {"error": errors.get(error_type, "Unknown error")}
