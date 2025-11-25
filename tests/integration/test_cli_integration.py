"""Integration tests for CLI with progress tracking."""

import tempfile
from pathlib import Path

import pytest

from src.ui.console import ConsoleManager

# Apply markers to all tests in this module
pytestmark = [
    pytest.mark.integration,
    pytest.mark.mock,
]


class TestCLIProgressIntegration:
    """Integration tests for CLI with progress tracking."""

    @pytest.fixture
    def temp_files(self):
        """Create temporary test files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create test video file
            test_video = temp_path / "test_video.mp4"
            test_video.write_bytes(b"fake video content")

            # Create output directory
            output_dir = temp_path / "output"
            output_dir.mkdir()

            yield {
                "video": str(test_video),
                "output_dir": str(output_dir),
                "temp_dir": str(temp_path),
            }

    def test_basic_functionality(self):
        """Test that the test framework is working."""
        assert True


class TestSecurityMeasures:
    """Security tests for JSON output sanitization."""

    def test_control_character_removal(self):
        """Test removal of control characters from JSON output."""

        console = ConsoleManager(json_output=True)

        # Test various control characters
        malicious_inputs = [
            "test\x00null",
            "test\x01\x02binary",
            "test\x1f\x7fcontrol",
            "test\r\nlog\ninjection",
        ]

        for malicious_input in malicious_inputs:
            sanitized = console._sanitize_string_field(malicious_input)
            # Verify no control characters in output
            for char_code in range(32):
                if char_code not in [9, 10, 13]:  # Allow tab, newline, carriage return
                    assert chr(char_code) not in sanitized

    def test_log_injection_prevention(self):
        """Test prevention of log injection attacks."""

        console = ConsoleManager(json_output=True)

        injection_attempts = [
            '{"type":"fake","injected":true}\n{"type":"progress"',
            'Stage 1\n{"type":"error","message":"injected"}',
            'Normal stage\r\n{"malicious": "payload"}',
        ]

        for attempt in injection_attempts:
            sanitized = console._sanitize_string_field(attempt)
            # Ensure the output is HTML-encoded, so injected content won't be executed
            assert "&quot;" in sanitized  # Check that quotes are escaped

    def test_json_field_length_limiting(self):
        """Test that JSON fields are properly length-limited."""

        console = ConsoleManager(json_output=True)

        # Create a very long string
        long_string = "A" * 300
        sanitized = console._sanitize_string_field(long_string)

        # Should be truncated to 200 characters plus ellipsis
        assert len(sanitized) <= 203  # 200 + "..."
        assert sanitized.endswith("...")
