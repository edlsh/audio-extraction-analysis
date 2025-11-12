#!/usr/bin/env python3
"""Automated comprehensive test runner for audio-extraction-analysis pipeline.

This script provides end-to-end testing for the audio extraction and analysis pipeline,
covering multiple test categories:
- Core functionality (extraction, transcription, processing)
- Provider integration (Deepgram, fallback mechanisms)
- Security (path traversal, command injection prevention)
- Error handling (missing files, invalid arguments, permission errors)
- CLI arguments (help, version, quality presets, output formats)
- Performance (caching behavior, timing characteristics)
- Output formats (JSON, Markdown export with various templates)

The test runner uses REAL media files from data/input directory rather than synthetic
test data to ensure authentic validation. All tests run in isolated temporary directories
to prevent pollution of the project workspace.

Environment Requirements:
- DEEPGRAM_API_KEY must be set in .env for provider tests
- FFmpeg must be installed for audio extraction
- Real audio/video files must exist in data/input/

Usage:
    python scripts/run_comprehensive_tests.py [options]

    Options:
        --test-data-dir PATH  Directory with test files (default: ./test_data)
        --json-report PATH    JSON report output path (default: test_report.json)
        --markdown-report PATH Markdown report path (default: test_report.md)
        --verbose            Enable verbose logging
        --debug              Enable pipeline debug dumps

Exit Codes:
    0 - All tests passed
    1 - One or more tests failed
    130 - Interrupted by user (Ctrl+C)
"""

import json
import logging
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Load .env from project root so subprocesses inherit API keys even when cwd is test_data_dir
# This ensures that DEEPGRAM_API_KEY and other secrets are available to subprocess
# commands executed from different working directories during tests
try:
    from dotenv import load_dotenv  # type: ignore

    _root_env = Path(__file__).parent.parent / ".env"
    if _root_env.exists():
        load_dotenv(_root_env)
        logger.info(f"Loaded environment from {_root_env}")
except Exception as e:
    logger.info(f"dotenv not available or failed to load .env: {e}")


class PipelineTestRunner:
    """Comprehensive test runner for the audio extraction and analysis pipeline.

    This class orchestrates execution of all test suites, manages temporary test environments,
    collects results, and generates detailed reports. Tests are executed sequentially with
    proper setup/teardown to ensure isolation and reproducibility.

    Test Execution Flow:
        1. Initialize temporary workspace and locate real test media files
        2. Run core functionality tests (extraction, transcription, processing)
        3. Run provider integration tests (Deepgram, fallback behavior)
        4. Run security tests (injection/traversal prevention)
        5. Run error handling tests (missing files, invalid inputs)
        6. Run CLI argument tests (help, version, presets)
        7. Run performance tests (caching, timing)
        8. Run output format tests (JSON, Markdown exports)
        9. Generate comprehensive reports (JSON and Markdown)
        10. Cleanup temporary files and directories

    Attributes:
        results (List[Dict]): Accumulated test results from all suites
        start_time (float): Unix timestamp when test execution began
        extracted_audio (Optional[Path]): Path to audio extracted from video (used in later tests)
        test_data_dir (Path): Directory containing real media files for testing
        temp_dir (Path): Isolated temporary directory for test outputs
    """

    def __init__(self, test_data_dir: Optional[Path] = None):
        """Initialize test runner with temporary workspace and test data discovery.

        Creates an isolated temporary directory for test outputs and identifies real media
        files in data/input. The test_data_dir parameter is currently ignored; the runner
        always uses data/input from the project root to ensure testing with real media.

        Args:
            test_data_dir: [DEPRECATED] Ignored. Runner always uses data/input directory.

        Side Effects:
            - Creates temporary directory with prefix 'pipeline_test_'
            - Logs initialization details to INFO level
            - Sets up results collection list
        """
        self.results = []
        self.start_time = time.time()
        self.extracted_audio: Optional[Path] = None
        # Force usage of real data under data/input
        project_root = Path(__file__).parent.parent
        repo_input = project_root / "data" / "input"
        self.test_data_dir = repo_input
        self.temp_dir = Path(tempfile.mkdtemp(prefix="pipeline_test_"))
        logger.info(f"Test runner initialized. Temp dir: {self.temp_dir}")
        logger.info(f"Test data directory: {self.test_data_dir}")

    def setup_test_files(self) -> tuple[Optional[Path], Optional[Path]]:
        """Select real media files from data/input directory for testing.

        Discovers existing audio and video files in the data/input directory without creating
        any synthetic test data. This ensures tests run against real-world media formats and
        edge cases. The method prefers the first file found for each media type.

        Supported Formats:
            Audio: .mp3, .wav, .m4a, .flac, .ogg, .aac
            Video: .mp4, .webm, .mkv, .mov, .avi

        Returns:
            tuple[Optional[Path], Optional[Path]]: (video_path, audio_path)
                video_path: Absolute path to first video file found, or None
                audio_path: Absolute path to first audio file found, or None

        Logs:
            - ERROR if data/input directory doesn't exist
            - ERROR if no media files found (prompts user to add real files)
            - INFO with discovered file paths when successful
        """
        if not self.test_data_dir.exists():
            logger.error(f"Real data directory not found: {self.test_data_dir}")
            return None, None
        media = [p for p in self.test_data_dir.iterdir() if p.is_file()]
        audio_exts = {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".aac"}
        video_exts = {".mp4", ".webm", ".mkv", ".mov", ".avi"}
        audio = next((p.resolve() for p in media if p.suffix.lower() in audio_exts), None)
        video = next((p.resolve() for p in media if p.suffix.lower() in video_exts), None)
        if not audio and not video:
            logger.error(
                f"No media files found in {self.test_data_dir}. Place real files there and re-run."
            )
        else:
            logger.info(f"Using real data: audio={audio}, video={video}")
        return video, audio

    def run_test(
        self,
        name: str,
        command: str,
        expected_exit_code: int = 0,
        timeout: int = 60,
        env_vars: Optional[Dict] = None,
    ) -> Dict:
        """Execute a single test case with comprehensive result tracking.

        Runs the specified command in a subprocess with the given environment and timeout,
        capturing stdout/stderr and recording execution metrics. Tests are executed from the
        test_data_dir working directory to ensure relative paths work correctly.

        Args:
            name: Human-readable test name for reporting and logging
            command: Shell command to execute (executed with shell=True)
            expected_exit_code: Expected exit code (0 for success, 1+ for expected failures)
            timeout: Maximum execution time in seconds (default: 60)
            env_vars: Additional environment variables to merge with current environment

        Returns:
            Dict: Test result with the following structure:
                On Success:
                    - name (str): Test name
                    - command (str): Executed command
                    - success (bool): True if exit code matched expected
                    - exit_code (int): Actual exit code
                    - expected_exit_code (int): Expected exit code
                    - stdout (str): Last 4000 chars of stdout (truncated for diagnostics)
                    - stderr (str): Last 4000 chars of stderr (truncated for diagnostics)
                    - duration (float): Execution time in seconds
                    - timestamp (str): ISO format timestamp

                On Timeout:
                    - name, command, success (False), error, duration, timestamp

                On Exception:
                    - name, command, success (False), error, duration, timestamp

        Side Effects:
            - Logs test start, success/failure to INFO/ERROR level
            - Executes command from test_data_dir as working directory
            - Inherits and potentially modifies environment variables
        """
        logger.info(f"Running test: {name}")

        # Prepare environment
        env = os.environ.copy()
        if env_vars:
            env.update(env_vars)

        test_start = time.time()

        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env,
                cwd=str(self.test_data_dir),
            )

            success = result.returncode == expected_exit_code
            test_duration = time.time() - test_start

            # Build test result with truncated output for manageable report sizes
            # Last 4000 chars typically contain the most relevant error/success info
            test_result = {
                "name": name,
                "command": command,
                "success": success,
                "exit_code": result.returncode,
                "expected_exit_code": expected_exit_code,
                "stdout": result.stdout[-4000:],  # Tail to keep report size reasonable
                "stderr": result.stderr[-4000:],  # Most relevant errors appear at end
                "duration": test_duration,
                "timestamp": datetime.now().isoformat(),
            }

            if success:
                logger.info(f"✓ {name} passed ({test_duration:.2f}s)")
            else:
                logger.error(
                    f"✗ {name} failed (exit code: {result.returncode}, expected: {expected_exit_code})"
                )

            return test_result

        except subprocess.TimeoutExpired:
            logger.error(f"✗ {name} timed out after {timeout}s")
            return {
                "name": name,
                "command": command,
                "success": False,
                "error": f"Timeout exceeded ({timeout}s)",
                "duration": timeout,
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            logger.error(f"✗ {name} failed with exception: {e}")
            return {
                "name": name,
                "command": command,
                "success": False,
                "error": str(e),
                "duration": time.time() - test_start,
                "timestamp": datetime.now().isoformat(),
            }

    def run_core_functionality_tests(self):
        """Test core pipeline functionality with real media files.

        Validates the primary features of the audio extraction and analysis pipeline:
        1. Audio extraction from video files (FFmpeg integration)
        2. Complete processing pipeline (extract + transcribe + analyze)
        3. Analysis style variations (concise vs. full)

        The extracted audio from video tests is cached in self.extracted_audio for reuse
        in subsequent test suites to avoid redundant extraction operations.

        Tests Execute:
            - Audio extraction from video → MP3 output
            - Full pipeline with Deepgram provider (requires DEEPGRAM_API_KEY)
            - Concise analysis style processing
            - Full analysis style processing

        Dependencies:
            - FFmpeg for audio extraction
            - DEEPGRAM_API_KEY in environment for transcription
            - Real video file in data/input directory

        Side Effects:
            - Populates self.extracted_audio with extracted audio path
            - Appends test results to self.results
            - May attach pipeline_debug.json content to failed test results
        """
        logger.info("\n=== CORE FUNCTIONALITY TESTS ===")

        test_video, test_audio = self.setup_test_files()
        output_dir = self.temp_dir / "output"

        # Test 1: Extract audio from video (if available) and cache for later tests
        # The extracted audio path is saved in self.extracted_audio for reuse in
        # provider/performance/output tests to avoid redundant extraction
        if test_video:
            extracted = self.temp_dir / "extracted.mp3"
            r = self.run_test(
                "Audio extraction from video",
                f'audio-extraction-analysis extract "{test_video}" -o {extracted}',
                0,
                timeout=300,
            )
            self.results.append(r)
            if r.get("success"):
                self.extracted_audio = extracted

            # 2) Run process pipeline with explicit provider=deepgram to use .env
            # Test 2: Run complete processing pipeline with different analysis styles
            # Each test uses explicit --provider deepgram to ensure API key from .env is used
            for name, cmd, outdir in [
                (
                    "Complete processing pipeline",
                    f'audio-extraction-analysis process "{test_video}" --provider deepgram --output-dir {output_dir}',
                    output_dir,
                ),
                (
                    "Concise analysis style",
                    f'audio-extraction-analysis process "{test_video}" --provider deepgram --analysis-style concise --output-dir {output_dir}/concise',
                    output_dir / "concise",
                ),
                (
                    "Full analysis style",
                    f'audio-extraction-analysis process "{test_video}" --provider deepgram --analysis-style full --output-dir {output_dir}/full',
                    output_dir / "full",
                ),
            ]:
                res = self.run_test(name, cmd, 0, timeout=600)
                # If test failed and pipeline debug dump exists, attach it to stderr for diagnostics
                # This helps troubleshoot pipeline failures without needing to inspect temp directories
                try:
                    dbg = Path(outdir) / "pipeline_debug.json"
                    if not res.get("success") and dbg.exists():
                        with open(dbg, encoding="utf-8") as f:
                            snippet = f.read()[-4000:]
                        res["stderr"] = (res.get("stderr") or "") + f"\n[PIPELINE_DEBUG]\n{snippet}"
                except Exception:
                    pass
                self.results.append(res)

        # 3) Direct audio transcription if real audio exists
        if test_audio:
            self.results.append(
                self.run_test(
                    "Audio transcription with deepgram",
                    f"audio-extraction-analysis transcribe {test_audio} --provider deepgram -o {self.temp_dir}/transcript.txt",
                    0,
                    timeout=600,
                )
            )

    def run_provider_tests(self):
        """Test transcription provider integration and fallback mechanisms.

        Validates that the pipeline correctly integrates with third-party transcription
        providers and handles missing API credentials gracefully. Tests provider-specific
        behavior and the auto-fallback mechanism when API keys are unavailable.

        Tests Execute:
            - Deepgram provider with valid API key (expects success)
            - Auto provider fallback with no API keys (expects failure with exit code 1)

        The fallback test intentionally removes API keys from the environment to verify
        that the pipeline fails gracefully rather than hanging or crashing.

        Dependencies:
            - DEEPGRAM_API_KEY in environment for Deepgram test
            - Audio file from setup_test_files() or self.extracted_audio

        Side Effects:
            - Appends test results to self.results
            - Temporarily modifies environment variables for fallback test
        """
        logger.info("\n=== PROVIDER TESTS ===")

        # Prefer real audio; fall back to extracted audio from video
        _, real_audio = self.setup_test_files()
        test_audio = real_audio or self.extracted_audio
        if not test_audio:
            logger.info("Skipping provider tests (no audio available)")
            return

        # Test deepgram explicitly (uses key from .env)
        result = self.run_test(
            "Provider: deepgram",
            f"audio-extraction-analysis transcribe {test_audio} --provider deepgram -o {self.temp_dir}/deepgram_transcript.txt",
            0,
            timeout=600,
        )
        self.results.append(result)

        # Test fallback behavior
        result = self.run_test(
            "Provider fallback (no API keys)",
            f"audio-extraction-analysis transcribe {test_audio} --provider auto",
            1,
            env_vars={"DEEPGRAM_API_KEY": "", "ELEVENLABS_API_KEY": ""},
        )
        self.results.append(result)

    def run_security_tests(self):
        """Test security hardening against common attack vectors.

        Validates that the pipeline properly sanitizes and validates file paths and arguments
        to prevent security vulnerabilities. All tests expect failure (exit code 1) to confirm
        malicious inputs are rejected.

        Threat Model Coverage:
            - Path Traversal: Attempts to access files outside allowed directories
              using relative paths (../) and absolute paths to sensitive locations
            - Command Injection: Attempts to inject shell commands through semicolons,
              backticks, and other shell metacharacters in file arguments

        Tests Execute:
            - Path traversal with ../ sequences
            - Path traversal with absolute paths to /etc/passwd
            - Command injection via semicolon command separator
            - Command injection via backtick command substitution

        All tests MUST fail (exit code 1) to pass the security validation.

        Side Effects:
            - Appends test results to self.results
            - Each test expects and validates failure conditions
        """
        logger.info("\n=== SECURITY TESTS ===")

        security_tests = [
            # Path traversal attempts
            (
                "Path traversal prevention (../)",
                "audio-extraction-analysis process '../../../etc/passwd' --output-dir ./output",
                1,  # Should fail
            ),
            (
                "Path traversal prevention (absolute)",
                "audio-extraction-analysis extract test.mp4 --output /etc/passwd",
                1,  # Should fail
            ),
            # Command injection attempts
            (
                "Command injection prevention (semicolon)",
                "audio-extraction-analysis process 'test.mp4; echo HACKED' --output-dir ./output",
                1,  # Should fail
            ),
            (
                "Command injection prevention (backticks)",
                "audio-extraction-analysis process 'test.mp4`rm -rf /`' --output-dir ./output",
                1,  # Should fail
            ),
            # Invalid inputs (avoid null byte which raises before CLI)
        ]

        for test_case in security_tests:
            result = self.run_test(*test_case)
            self.results.append(result)

    def run_error_handling_tests(self):
        """Test error handling and recovery across various failure scenarios.

        Validates that the pipeline gracefully handles invalid inputs, missing files,
        and permission errors with appropriate error messages and exit codes. Tests
        ensure the application fails safely without crashes or undefined behavior.

        Error Scenarios Tested:
            - File System Errors:
                * Nonexistent input files (exit code 1)
                * Empty input files (exit code 1)
                * Read-only output directories (exit code 1)

            - Argument Validation Errors:
                * Invalid provider names (argparse error, exit code 2)
                * Invalid quality presets (argparse error, exit code 2)

        Creates a temporary empty file (empty.mp4) in temp_dir for testing, ensuring
        the real data/input directory remains unmodified.

        Side Effects:
            - Creates empty.mp4 in temp_dir for empty file testing
            - Appends test results to self.results
            - All tests expect and validate specific failure exit codes
        """
        logger.info("\n=== ERROR HANDLING TESTS ===")

        error_tests = [
            # Missing files
            ("Nonexistent input file", "audio-extraction-analysis process nonexistent_file.mp4", 1),
            (
                "Empty input file",
                f"audio-extraction-analysis process {self.test_data_dir}/empty.mp4",
                1,
            ),
            # Invalid arguments
            (
                "Invalid provider name",
                "audio-extraction-analysis transcribe test.mp3 --provider invalid_provider",
                2,  # argparse error
            ),
            (
                "Invalid quality preset",
                "audio-extraction-analysis extract test.mp4 --quality ultra_max",
                2,  # argparse error
            ),
            # Permission errors (if possible to test)
            (
                "Read-only output directory",
                "audio-extraction-analysis process test.mp4 --output-dir /dev/null",
                1,
            ),
        ]

        # Create empty file for testing in temp (do not modify data/input)
        empty_file = (self.temp_dir / "empty.mp4").resolve()
        empty_file.touch()

        for test_case in error_tests:
            result = self.run_test(*test_case)
            self.results.append(result)

    def run_cli_argument_tests(self):
        """Test CLI argument parsing, help messages, and version information.

        Validates that the CLI interface provides proper help documentation and version
        information. Currently limited to non-executing tests (help, version) to avoid
        requiring synthetic test files.

        The method contains commented-out tests for complex argument combinations and
        quality presets that would require real media files. These are disabled with
        an early return to prevent test failures when media files are unavailable.

        Tests Execute:
            - Main help message (--help)
            - Subcommand help messages (extract, transcribe, process)
            - Version information (--version)

        Commented Tests (Disabled):
            - Complex argument combinations (all features together)
            - Quality presets (compressed, speech, standard, high)
            These tests are preserved for future use when test file handling is improved.

        Side Effects:
            - Appends test results to self.results
            - Returns early to skip media-dependent tests
        """
        logger.info("\n=== CLI ARGUMENT TESTS ===")
        # Only run help/version tests to avoid dependency on synthetic test files
        basic_cli = [
            ("Main help", "audio-extraction-analysis --help", 0),
            ("Extract subcommand help", "audio-extraction-analysis extract --help", 0),
            ("Transcribe subcommand help", "audio-extraction-analysis transcribe --help", 0),
            ("Process subcommand help", "audio-extraction-analysis process --help", 0),
            ("Version information", "audio-extraction-analysis --version", 0),
        ]
        for tc in basic_cli:
            self.results.append(self.run_test(*tc))
        return

        test_video = self.test_data_dir / "test.mp4"
        (self.test_data_dir / "test.mp3").resolve()

        cli_tests = [
            # Help commands
            ("Main help", "audio-extraction-analysis --help", 0),
            ("Extract subcommand help", "audio-extraction-analysis extract --help", 0),
            ("Transcribe subcommand help", "audio-extraction-analysis transcribe --help", 0),
            ("Process subcommand help", "audio-extraction-analysis process --help", 0),
            # Version
            ("Version information", "audio-extraction-analysis --version", 0),
            # Complex argument combinations
            (
                "Maximum verbosity with all features",
                f"audio-extraction-analysis process {test_video} --verbose --json-output --quality high --provider auto --language en --analysis-style full --export-markdown --md-template detailed --md-confidence --output-dir {self.temp_dir}/full_test",
                0,
            ),
            # Quality presets
            (
                "Quality preset: compressed",
                f"audio-extraction-analysis extract {test_video} --quality compressed -o {self.temp_dir}/compressed.mp3",
                0,
            ),
            (
                "Quality preset: speech",
                f"audio-extraction-analysis extract {test_video} --quality speech -o {self.temp_dir}/speech.mp3",
                0,
            ),
            (
                "Quality preset: standard",
                f"audio-extraction-analysis extract {test_video} --quality standard -o {self.temp_dir}/standard.mp3",
                0,
            ),
            (
                "Quality preset: high",
                f"audio-extraction-analysis extract {test_video} --quality high -o {self.temp_dir}/high.mp3",
                0,
            ),
        ]

        for test_case in cli_tests:
            result = self.run_test(*test_case)
            self.results.append(result)

    def run_performance_tests(self):
        """Test performance characteristics and caching behavior.

        Validates that the pipeline's caching mechanism improves performance on repeated
        operations. Measures execution time for identical transcription requests to
        determine cache effectiveness.

        Test Strategy:
            1. Run transcription with no cache (cold start)
            2. Run identical transcription (warm cache)
            3. Compare execution times to calculate cache speedup

        Expected Behavior:
            If caching is implemented, the second run should be significantly faster.
            The speedup ratio is logged for performance analysis.

        Dependencies:
            - Audio file from setup_test_files() or self.extracted_audio
            - DEEPGRAM_API_KEY for transcription provider

        Side Effects:
            - Appends test results to self.results
            - Logs cache speedup metrics when both tests succeed
            - Skips tests if no audio file is available
        """
        logger.info("\n=== PERFORMANCE TESTS ===")

        # Prefer real audio; fall back to extracted audio
        _, real_audio = self.setup_test_files()
        test_audio = real_audio or self.extracted_audio
        if not test_audio:
            logger.info("Skipping performance tests (no audio available)")
            return

        # Test caching behavior
        cache_test_results = []

        # First run (no cache)
        result1 = self.run_test(
            "First transcription (no cache)",
            f"audio-extraction-analysis transcribe {test_audio} --provider deepgram",
            0,
            timeout=600,
        )
        cache_test_results.append(result1)
        self.results.append(result1)

        # Second run (should use cache if implemented)
        result2 = self.run_test(
            "Second transcription (with cache)",
            f"audio-extraction-analysis transcribe {test_audio} --provider deepgram",
            0,
            timeout=600,
        )
        cache_test_results.append(result2)
        self.results.append(result2)

        # Compare timing
        if len(cache_test_results) == 2 and all(r.get("success") for r in cache_test_results):
            first_time = cache_test_results[0]["duration"]
            second_time = cache_test_results[1]["duration"]

            cache_speedup = first_time / second_time if second_time > 0 else 0
            logger.info(
                f"Cache speedup: {cache_speedup:.2f}x (first: {first_time:.2f}s, second: {second_time:.2f}s)"
            )

    def run_output_format_tests(self):
        """Test various output formats and export options.

        Validates that the pipeline can generate outputs in multiple formats with
        different configuration options. Tests both inline format flags and dedicated
        export commands.

        Output Formats Tested:
            - JSON output mode (--json-output flag for structured data)
            - Markdown export with default template
            - Markdown export with detailed template
            - Markdown export without timestamps

        The markdown export tests verify template customization and optional features
        like timestamp inclusion/exclusion.

        Dependencies:
            - Audio file from setup_test_files() or self.extracted_audio
            - DEEPGRAM_API_KEY for transcription provider

        Side Effects:
            - Creates markdown output directories in temp_dir
            - Appends test results to self.results
            - Skips tests if no audio file is available
        """
        logger.info("\n=== OUTPUT FORMAT TESTS ===")

        # Prefer real audio; fall back to extracted audio
        _, real_audio = self.setup_test_files()
        test_audio = real_audio or self.extracted_audio
        if not test_audio:
            logger.info("Skipping output format tests (no audio available)")
            return

        format_tests = [
            # JSON output
            (
                "JSON output mode",
                f"audio-extraction-analysis --json-output transcribe {test_audio} --provider deepgram",
                0,
            ),
            # Markdown export
            (
                "Markdown export with defaults",
                f"audio-extraction-analysis export-markdown {test_audio} --output-dir {self.temp_dir}/markdown",
                0,
            ),
            (
                "Markdown export with detailed template",
                f"audio-extraction-analysis export-markdown {test_audio} --output-dir {self.temp_dir}/markdown_detailed --template detailed",
                0,
            ),
            (
                "Markdown export without timestamps",
                f"audio-extraction-analysis export-markdown {test_audio} --output-dir {self.temp_dir}/markdown_no_ts --no-timestamps",
                0,
            ),
        ]

        for test_case in format_tests:
            result = self.run_test(*test_case)
            self.results.append(result)

    def run_all_tests(self):
        """Execute all test suites in sequence with proper setup and teardown.

        Orchestrates the complete test execution workflow, running all test suites
        in a defined order that ensures dependencies are satisfied (e.g., core tests
        run first to extract audio for later tests).

        Execution Order:
            1. Core functionality tests (extraction, transcription, processing)
            2. Provider integration tests (Deepgram, fallbacks)
            3. Security tests (injection/traversal prevention)
            4. Error handling tests (invalid inputs, missing files)
            5. CLI argument tests (help, version, presets)
            6. Performance tests (caching, timing)
            7. Output format tests (JSON, Markdown)

        The execution order ensures:
            - Audio extraction happens first (creates self.extracted_audio)
            - Provider tests can use extracted audio as fallback
            - Performance tests measure real-world usage patterns
            - Cleanup happens even if tests fail (via finally block)

        Side Effects:
            - Populates self.results with all test outcomes
            - Creates temporary files and directories
            - Logs progress to INFO level
            - Calls cleanup() in finally block to ensure temp directory removal
        """
        logger.info("Starting comprehensive test suite...")
        logger.info(f"Test data directory: {self.test_data_dir}")
        logger.info(f"Temporary directory: {self.temp_dir}")

        try:
            # Setup
            self.setup_test_files()

            # Run test suites
            self.run_core_functionality_tests()
            self.run_provider_tests()
            self.run_security_tests()
            self.run_error_handling_tests()
            self.run_cli_argument_tests()
            self.run_performance_tests()
            self.run_output_format_tests()

        except Exception as e:
            logger.error(f"Test suite failed: {e}")

        finally:
            # Cleanup
            self.cleanup()

    def cleanup(self):
        """Clean up temporary files and directories created during testing.

        Removes the temporary directory tree created in __init__, including all
        extracted audio, output files, and test artifacts. Called automatically
        by run_all_tests() in the finally block to ensure cleanup even on failure.

        Side Effects:
            - Recursively deletes self.temp_dir and all contents
            - Logs cleanup success or failure warnings
            - Gracefully handles cases where temp_dir doesn't exist or can't be removed
        """
        try:
            import shutil

            if self.temp_dir.exists():
                shutil.rmtree(self.temp_dir)
                logger.info(f"Cleaned up temp directory: {self.temp_dir}")
        except Exception as e:
            logger.warning(f"Failed to clean up temp directory: {e}")

    def generate_report(self, output_file: str = "test_report.json"):
        """Generate comprehensive test report in JSON format.

        Creates a detailed JSON report containing test metadata, summary statistics,
        and complete test results. The report includes both successes and failures
        with full diagnostic information.

        Report Structure:
            - metadata: Timestamp, duration, Python version, platform, directories
            - summary: Total tests, passed, failed, success rate, duration
            - failures: Array of failed test results with error details
            - successes: Array of passed test results
            - all_results: Complete list of all test results in execution order

        Also prints a formatted summary to console showing:
            - Test counts (total, passed, failed)
            - Success rate percentage
            - Detailed failure information if any tests failed

        Args:
            output_file: Path to output JSON report (default: test_report.json)

        Returns:
            dict: The generated report structure

        Side Effects:
            - Writes JSON report to output_file
            - Prints formatted summary to stdout
            - Uses test data from self.results
        """
        total = len(self.results)
        passed = sum(1 for r in self.results if r.get("success", False))
        failed = total - passed

        duration = time.time() - self.start_time

        report = {
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "duration_seconds": duration,
                "python_version": sys.version,
                "platform": sys.platform,
                "test_data_dir": str(self.test_data_dir),
                "temp_dir": str(self.temp_dir),
            },
            "summary": {
                "total": total,
                "passed": passed,
                "failed": failed,
                "success_rate": f"{(passed/total)*100:.1f}%" if total > 0 else "0%",
                "duration": f"{duration:.2f}s",
            },
            "failures": [r for r in self.results if not r.get("success", False)],
            "successes": [r for r in self.results if r.get("success", False)],
            "all_results": self.results,
        }

        # Save JSON report
        with open(output_file, "w") as f:
            json.dump(report, f, indent=2)

        # Print summary
        print(f"\n{'='*60}")
        print("TEST EXECUTION SUMMARY")
        print(f"{'='*60}")
        print(f"Total Tests:    {total}")
        print(f"Passed:         {passed} ✓")
        print(f"Failed:         {failed} ✗")
        print(f"Success Rate:   {report['summary']['success_rate']}")
        print(f"Duration:       {report['summary']['duration']}")
        print(f"Report saved:   {output_file}")

        if failed > 0:
            print(f"\n{'='*60}")
            print(f"FAILED TESTS ({failed})")
            print(f"{'='*60}")
            for failure in report["failures"]:
                error_msg = failure.get(
                    "error",
                    f"Exit code: {failure.get('exit_code')} (expected: {failure.get('expected_exit_code')})",
                )
                print(f"✗ {failure['name']}")
                print(f"  Command: {failure['command']}")
                print(f"  Error: {error_msg}")
                if failure.get("stderr"):
                    print(f"  Stderr: {failure['stderr'][:200]}...")
                print()

        print(f"{'='*60}\n")

        return report

    def generate_markdown_report(self, output_file: str = "test_report.md"):
        """Generate a human-readable markdown version of the test report.

        Creates a formatted Markdown document suitable for documentation, GitHub issues,
        or project wikis. Tests are automatically categorized by type for easy navigation.

        Report Sections:
            - Header: Date, duration, platform, Python version
            - Summary Table: Total tests, passed, failed, success rate
            - Category Sections: Results grouped by test type (Core, Provider, Security, etc.)
            - Failed Tests Detail: Full error messages and stderr for failures
            - Recommendations: Actionable next steps based on results

        Test Categorization:
            Tests are automatically categorized based on keywords in test names:
            - Core Functionality: extraction, pipeline, processing
            - Provider Tests: provider, API integrations
            - Security Tests: security, traversal, injection
            - Error Handling: error, nonexistent, invalid
            - CLI Arguments: help, version, quality
            - Performance: cache, performance
            - Output Formats: json, markdown

        Args:
            output_file: Path to output markdown report (default: test_report.md)

        Side Effects:
            - Writes formatted markdown to output_file
            - Logs report save location to INFO level
            - Includes recommendations section with troubleshooting steps
        """
        total = len(self.results)
        passed = sum(1 for r in self.results if r.get("success", False))
        failed = total - passed
        duration = time.time() - self.start_time

        with open(output_file, "w") as f:
            f.write("# Audio-Extraction-Analysis Pipeline Test Report\n\n")
            f.write(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"**Duration:** {duration:.2f} seconds\n")
            f.write(f"**Platform:** {sys.platform}\n")
            f.write(f"**Python:** {sys.version.split()[0]}\n\n")

            f.write("## Summary\n\n")
            f.write("| Metric | Value |\n")
            f.write("|--------|-------|\n")
            f.write(f"| Total Tests | {total} |\n")
            f.write(f"| Passed | {passed} ✓ |\n")
            f.write(f"| Failed | {failed} ✗ |\n")
            f.write(f"| Success Rate | {(passed/total)*100:.1f}% |\n\n")

            # Group results by category based on test name keywords
            # This automatic categorization helps readers navigate the report by topic
            categories = {
                "Core Functionality": [],
                "Provider Tests": [],
                "Security Tests": [],
                "Error Handling": [],
                "CLI Arguments": [],
                "Performance": [],
                "Output Formats": [],
            }

            # Categorize each test result based on keywords in test name
            for result in self.results:
                name = result.get("name", "")
                if (
                    "extraction" in name.lower()
                    or "pipeline" in name.lower()
                    or "processing" in name.lower()
                ):
                    categories["Core Functionality"].append(result)
                elif "provider" in name.lower():
                    categories["Provider Tests"].append(result)
                elif (
                    "security" in name.lower()
                    or "traversal" in name.lower()
                    or "injection" in name.lower()
                ):
                    categories["Security Tests"].append(result)
                elif (
                    "error" in name.lower()
                    or "nonexistent" in name.lower()
                    or "invalid" in name.lower()
                ):
                    categories["Error Handling"].append(result)
                elif (
                    "help" in name.lower() or "version" in name.lower() or "quality" in name.lower()
                ):
                    categories["CLI Arguments"].append(result)
                elif "cache" in name.lower() or "performance" in name.lower():
                    categories["Performance"].append(result)
                elif "json" in name.lower() or "markdown" in name.lower():
                    categories["Output Formats"].append(result)
                else:
                    categories["Core Functionality"].append(result)

            # Write results by category
            for category, tests in categories.items():
                if tests:
                    f.write(f"## {category}\n\n")
                    f.write("| Test | Status | Duration |\n")
                    f.write("|------|--------|----------|\n")

                    for test in tests:
                        status = "✓ Pass" if test.get("success") else "✗ Fail"
                        duration = test.get("duration", 0)
                        name = test.get("name", "Unknown")
                        f.write(f"| {name} | {status} | {duration:.2f}s |\n")
                    f.write("\n")

            # Write failures detail if any
            if failed > 0:
                f.write("## Failed Tests Detail\n\n")
                for failure in [r for r in self.results if not r.get("success", False)]:
                    f.write(f"### {failure.get('name', 'Unknown')}\n\n")
                    f.write(f"**Command:** `{failure.get('command', 'N/A')}`\n\n")
                    error = failure.get(
                        "error",
                        f"Exit code: {failure.get('exit_code')} (expected: {failure.get('expected_exit_code')})",
                    )
                    f.write(f"**Error:** {error}\n\n")
                    if failure.get("stderr"):
                        f.write(f"**Stderr:**\n```\n{failure['stderr'][:500]}\n```\n\n")

            f.write("## Recommendations\n\n")
            if failed == 0:
                f.write(
                    "✅ All tests passed! The pipeline appears to be functioning correctly.\n\n"
                )
            else:
                f.write("⚠️ Some tests failed. Review the failures above and:\n\n")
                f.write("1. Check if required API keys are configured\n")
                f.write("2. Ensure all dependencies are installed\n")
                f.write("3. Verify file permissions and paths\n")
                f.write("4. Review error messages for specific issues\n\n")

        logger.info(f"Markdown report saved to: {output_file}")


def main():
    """Main entry point for the comprehensive test runner CLI.

    Parses command-line arguments, configures logging, creates the test runner,
    executes all test suites, and generates reports. Exits with appropriate
    status codes for CI/CD integration.

    Command-Line Arguments:
        --test-data-dir PATH: Directory containing test files (deprecated, always uses data/input)
        --json-report PATH: JSON report output path (default: test_report.json)
        --markdown-report PATH: Markdown report output path (default: test_report.md)
        --verbose: Enable verbose/debug logging
        --debug: Enable pipeline debug dumps (sets AUDIO_PIPELINE_DEBUG=1)

    Exit Codes:
        0: All tests passed successfully
        1: One or more tests failed
        130: User interrupted with Ctrl+C

    The function handles KeyboardInterrupt gracefully and ensures cleanup occurs
    even on unexpected exceptions.
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="Comprehensive test runner for audio-extraction-analysis pipeline"
    )
    parser.add_argument(
        "--test-data-dir",
        type=Path,
        default=Path("./test_data"),
        help="Directory containing test files",
    )
    parser.add_argument(
        "--json-report", default="test_report.json", help="Path for JSON report output"
    )
    parser.add_argument(
        "--markdown-report", default="test_report.md", help="Path for Markdown report output"
    )
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    parser.add_argument(
        "--debug", action="store_true", help="Enable pipeline debug dumps (AUDIO_PIPELINE_DEBUG=1)"
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Create and run test suite
    runner = PipelineTestRunner(test_data_dir=args.test_data_dir)
    if args.debug:
        os.environ["AUDIO_PIPELINE_DEBUG"] = "1"

    try:
        runner.run_all_tests()

        # Generate reports
        report = runner.generate_report(args.json_report)
        runner.generate_markdown_report(args.markdown_report)

        # Exit with appropriate code
        failed = report["summary"]["failed"]
        sys.exit(0 if failed == 0 else 1)

    except KeyboardInterrupt:
        logger.warning("\nTest execution interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Test runner failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
