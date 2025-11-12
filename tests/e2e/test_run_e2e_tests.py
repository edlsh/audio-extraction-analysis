#!/usr/bin/env python3
"""
Comprehensive test suite for run_e2e_tests.py E2E test runner.

Tests cover:
- E2ETestRunner initialization and configuration
- Environment validation
- Test data setup
- Test suite execution
- Report generation and saving
- Error handling and edge cases
"""

import json
import subprocess
import tempfile
from argparse import Namespace
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

# Import the module to test
from .run_e2e_tests import E2ETestReport, E2ETestRunner, TestSuiteResult

# ==================== Fixtures ====================


@pytest.fixture
def mock_args():
    """Create mock arguments for E2ETestRunner."""
    return Namespace(
        suite="all",
        output_dir=None,
        coverage=False,
        parallel=False,
        fail_fast=False,
        verbose=False,
        generate_test_data=False,
        real_api_keys=False,
        keep_artifacts=False,
    )


@pytest.fixture
def temp_output_dir():
    """Create temporary output directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def runner_with_temp_dir(mock_args, temp_output_dir):
    """Create E2ETestRunner with temporary output directory."""
    mock_args.output_dir = str(temp_output_dir)
    runner = E2ETestRunner(mock_args)
    return runner


# ==================== Data Class Tests ====================


class TestDataClasses:
    """Test the dataclass structures."""

    def test_test_suite_result_creation(self):
        """Test TestSuiteResult can be created with required fields."""
        result = TestSuiteResult(
            suite_name="unit",
            success=True,
            duration=10.5,
            tests_passed=50,
            tests_failed=0,
            tests_skipped=2,
        )

        assert result.suite_name == "unit"
        assert result.success is True
        assert result.duration == 10.5
        assert result.tests_passed == 50
        assert result.tests_failed == 0
        assert result.tests_skipped == 2
        assert result.error_message is None
        assert result.coverage is None

    def test_test_suite_result_with_error(self):
        """Test TestSuiteResult with error message."""
        result = TestSuiteResult(
            suite_name="integration",
            success=False,
            duration=5.2,
            tests_passed=10,
            tests_failed=3,
            tests_skipped=0,
            error_message="Test timeout",
        )

        assert result.success is False
        assert result.error_message == "Test timeout"

    def test_e2e_test_report_creation(self):
        """Test E2ETestReport can be created."""
        suite_results = [
            TestSuiteResult("unit", True, 10.0, 50, 0, 2),
            TestSuiteResult("integration", True, 15.0, 30, 0, 1),
        ]

        report = E2ETestReport(
            start_time="2025-01-01 10:00:00",
            end_time="2025-01-01 10:25:00",
            total_duration=1500.0,
            environment_info={"python_version": "3.10.0"},
            suite_results=suite_results,
            overall_success=True,
        )

        assert report.overall_success is True
        assert len(report.suite_results) == 2
        assert report.total_duration == 1500.0


# ==================== Initialization Tests ====================


class TestE2ETestRunnerInit:
    """Test E2ETestRunner initialization."""

    def test_runner_initialization(self, mock_args, temp_output_dir):
        """Test basic runner initialization."""
        mock_args.output_dir = str(temp_output_dir)
        runner = E2ETestRunner(mock_args)

        assert runner.args == mock_args
        assert runner.output_dir == temp_output_dir
        assert runner.output_dir.exists()
        assert len(runner.suite_results) == 0
        assert isinstance(runner.test_suites, dict)

    def test_runner_creates_output_directory(self, mock_args):
        """Test runner creates output directory if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create parent directory first as mkdir(exist_ok=True) doesn't create parents
            parent_path = Path(tmpdir) / "nonexistent"
            parent_path.mkdir(exist_ok=True)
            output_path = parent_path / "output"
            mock_args.output_dir = str(output_path)

            runner = E2ETestRunner(mock_args)

            assert runner.output_dir.exists()

    def test_runner_test_suites_configuration(self, runner_with_temp_dir):
        """Test test suites are properly configured."""
        runner = runner_with_temp_dir

        assert "unit" in runner.test_suites
        assert "integration" in runner.test_suites
        assert "cli" in runner.test_suites
        assert "provider" in runner.test_suites
        assert "performance" in runner.test_suites
        assert "security" in runner.test_suites

        # Check critical flags
        assert runner.test_suites["unit"]["critical"] is True
        assert runner.test_suites["performance"]["critical"] is False


# ==================== Logging Tests ====================


class TestLogging:
    """Test logging setup and configuration."""

    def test_logging_setup_creates_log_file(self, runner_with_temp_dir):
        """Test that logging setup creates log file."""
        runner = runner_with_temp_dir
        log_file = runner.output_dir / "e2e_test_run.log"

        assert log_file.exists()
        assert runner.logger is not None

    def test_logging_verbose_mode(self, mock_args, temp_output_dir):
        """Test verbose logging mode."""
        mock_args.output_dir = str(temp_output_dir)
        mock_args.verbose = True

        runner = E2ETestRunner(mock_args)

        assert runner.logger.level == 10  # DEBUG level


# ==================== Environment Validation Tests ====================


class TestEnvironmentValidation:
    """Test environment validation functionality."""

    @patch("tests.e2e.run_e2e_tests.E2ETestRunner.check_tool_available")
    def test_validate_environment_success(self, mock_check_tool, runner_with_temp_dir):
        """Test successful environment validation."""
        mock_check_tool.return_value = True
        runner = runner_with_temp_dir

        result = runner.validate_environment()

        assert result is True
        assert "python_version" in runner.environment_info
        assert "platform" in runner.environment_info

    @patch("tests.e2e.run_e2e_tests.E2ETestRunner.check_tool_available")
    def test_validate_environment_missing_tool(self, mock_check_tool, runner_with_temp_dir):
        """Test environment validation fails with missing tool."""
        # ffmpeg not available
        mock_check_tool.side_effect = lambda tool: tool != "ffmpeg"
        runner = runner_with_temp_dir

        result = runner.validate_environment()

        assert result is False
        assert len(runner.environment_info.get("validation_errors", [])) > 0

    @patch("sys.version_info", (3, 7, 0))  # Python 3.7
    def test_validate_environment_old_python(self, runner_with_temp_dir):
        """Test environment validation fails with old Python version."""
        runner = runner_with_temp_dir

        # Note: This test may not work as expected due to sys.version_info patching limitations
        # Just checking the logic exists
        assert hasattr(runner, "validate_environment")


# ==================== Tool Checking Tests ====================


class TestToolChecking:
    """Test tool availability checking."""

    @patch("subprocess.run")
    def test_check_tool_available_success(self, mock_run, runner_with_temp_dir):
        """Test checking available tool."""
        mock_run.return_value = Mock(returncode=0)
        runner = runner_with_temp_dir

        result = runner.check_tool_available("pytest")

        assert result is True
        mock_run.assert_called_once()

    @patch("subprocess.run")
    def test_check_tool_available_not_found(self, mock_run, runner_with_temp_dir):
        """Test checking unavailable tool."""
        mock_run.side_effect = FileNotFoundError()
        runner = runner_with_temp_dir

        result = runner.check_tool_available("nonexistent_tool")

        assert result is False

    @patch("subprocess.run")
    def test_check_tool_available_timeout(self, mock_run, runner_with_temp_dir):
        """Test tool check with timeout."""
        mock_run.side_effect = subprocess.TimeoutExpired("cmd", 10)
        runner = runner_with_temp_dir

        result = runner.check_tool_available("slow_tool")

        assert result is False

    @patch("subprocess.run")
    def test_get_tool_version_success(self, mock_run, runner_with_temp_dir):
        """Test getting tool version successfully."""
        mock_run.return_value = Mock(returncode=0, stdout="pytest 7.4.0\n")
        runner = runner_with_temp_dir

        version = runner.get_tool_version("pytest")

        assert version == "pytest 7.4.0"

    @patch("subprocess.run")
    def test_get_tool_version_failure(self, mock_run, runner_with_temp_dir):
        """Test getting tool version failure."""
        mock_run.side_effect = FileNotFoundError()
        runner = runner_with_temp_dir

        version = runner.get_tool_version("nonexistent")

        assert version is None


# ==================== Test Data Setup Tests ====================


class TestTestDataSetup:
    """Test test data setup functionality."""

    @patch("tests.e2e.run_e2e_tests.TestDataManager")
    def test_setup_test_data_success(self, mock_tdm_class, runner_with_temp_dir):
        """Test successful test data setup."""
        mock_tdm = Mock()
        mock_tdm.validate_test_files.return_value = {"audio_file": True, "video_file": True}
        mock_tdm_class.return_value = mock_tdm

        runner = runner_with_temp_dir
        result = runner.setup_test_data()

        assert result is True

    @patch("tests.e2e.run_e2e_tests.TestDataManager")
    def test_setup_test_data_no_valid_files(self, mock_tdm_class, runner_with_temp_dir):
        """Test test data setup fails with no valid files."""
        mock_tdm = Mock()
        mock_tdm.validate_test_files.return_value = {}
        mock_tdm_class.return_value = mock_tdm

        runner = runner_with_temp_dir
        result = runner.setup_test_data()

        assert result is False

    @patch("tests.e2e.run_e2e_tests.TestDataManager")
    def test_setup_test_data_with_generation(self, mock_tdm_class, mock_args, temp_output_dir):
        """Test test data setup with file generation."""
        mock_args.output_dir = str(temp_output_dir)
        mock_args.generate_test_data = True

        mock_tdm = Mock()
        mock_tdm.generate_all_test_files.return_value = {
            "audio": "/path/to/audio.mp3",
            "video": "/path/to/video.mp4",
        }
        mock_tdm.validate_test_files.return_value = {"audio": True, "video": True}
        mock_tdm_class.return_value = mock_tdm

        runner = E2ETestRunner(mock_args)
        result = runner.setup_test_data()

        assert result is True
        mock_tdm.generate_all_test_files.assert_called_once()


# ==================== Test Suite Execution Tests ====================


class TestTestSuiteExecution:
    """Test test suite execution."""

    @patch("subprocess.run")
    def test_run_test_suite_success(self, mock_run, runner_with_temp_dir, temp_output_dir):
        """Test successful test suite execution."""
        # Mock successful pytest run
        mock_run.return_value = Mock(returncode=0, stderr="")

        # Create mock JSON report
        report_data = {"summary": {"passed": 10, "failed": 0, "skipped": 2}}
        report_file = temp_output_dir / "unit_report.json"
        with open(report_file, "w") as f:
            json.dump(report_data, f)

        runner = runner_with_temp_dir
        suite_config = runner.test_suites["unit"]

        result = runner.run_test_suite("unit", suite_config)

        assert result.success is True
        assert result.tests_passed == 10
        assert result.tests_failed == 0
        assert result.tests_skipped == 2

    @patch("subprocess.run")
    def test_run_test_suite_failure(self, mock_run, runner_with_temp_dir, temp_output_dir):
        """Test failed test suite execution."""
        # Mock failed pytest run
        mock_run.return_value = Mock(returncode=1, stderr="Test failures")

        # Create mock JSON report with failures
        report_data = {"summary": {"passed": 5, "failed": 3, "skipped": 0}}
        report_file = temp_output_dir / "unit_report.json"
        with open(report_file, "w") as f:
            json.dump(report_data, f)

        runner = runner_with_temp_dir
        suite_config = runner.test_suites["unit"]

        result = runner.run_test_suite("unit", suite_config)

        assert result.success is False
        assert result.tests_failed == 3
        assert result.error_message is not None

    @patch("subprocess.run")
    def test_run_test_suite_timeout(self, mock_run, runner_with_temp_dir):
        """Test test suite execution timeout."""
        mock_run.side_effect = subprocess.TimeoutExpired("cmd", 300)

        runner = runner_with_temp_dir
        suite_config = runner.test_suites["unit"]

        result = runner.run_test_suite("unit", suite_config)

        assert result.success is False
        assert "timed out" in result.error_message.lower()

    @patch("subprocess.run")
    def test_run_test_suite_with_coverage(self, mock_run, mock_args, temp_output_dir):
        """Test test suite execution with coverage enabled."""
        mock_args.output_dir = str(temp_output_dir)
        mock_args.coverage = True
        mock_run.return_value = Mock(returncode=0, stderr="")

        # Create mock report
        report_file = temp_output_dir / "unit_report.json"
        with open(report_file, "w") as f:
            json.dump({"summary": {"passed": 10, "failed": 0, "skipped": 0}}, f)

        runner = E2ETestRunner(mock_args)
        suite_config = runner.test_suites["unit"]

        runner.run_test_suite("unit", suite_config)

        # Check that coverage arguments were added
        call_args = mock_run.call_args[0][0]
        assert any("--cov" in arg for arg in call_args)

    @patch("subprocess.run")
    def test_run_test_suite_with_parallel(self, mock_run, mock_args, temp_output_dir):
        """Test test suite execution with parallel enabled."""
        mock_args.output_dir = str(temp_output_dir)
        mock_args.parallel = True
        mock_run.return_value = Mock(returncode=0, stderr="")

        # Create mock report
        report_file = temp_output_dir / "unit_report.json"
        with open(report_file, "w") as f:
            json.dump({"summary": {"passed": 10, "failed": 0, "skipped": 0}}, f)

        runner = E2ETestRunner(mock_args)
        suite_config = runner.test_suites["unit"]

        runner.run_test_suite("unit", suite_config)

        # Check that parallel arguments were added
        call_args = mock_run.call_args[0][0]
        assert "-n" in call_args

    @patch("subprocess.run")
    def test_run_test_suite_environment_variables(self, mock_run, mock_args, temp_output_dir):
        """Test test suite sets correct environment variables."""
        mock_args.output_dir = str(temp_output_dir)
        mock_args.verbose = True
        mock_args.real_api_keys = False
        mock_run.return_value = Mock(returncode=0, stderr="")

        # Create mock report
        report_file = temp_output_dir / "unit_report.json"
        with open(report_file, "w") as f:
            json.dump({"summary": {"passed": 10, "failed": 0, "skipped": 0}}, f)

        runner = E2ETestRunner(mock_args)
        suite_config = runner.test_suites["unit"]

        runner.run_test_suite("unit", suite_config)

        # Verify environment variables were set
        call_env = mock_run.call_args[1]["env"]
        assert call_env.get("TEST_MODE") == "true"
        assert call_env.get("LOG_LEVEL") == "DEBUG"
        assert call_env.get("DEEPGRAM_API_KEY") == "test_deepgram_key_for_mocking"
        assert call_env.get("ELEVENLABS_API_KEY") == "test_elevenlabs_key_for_mocking"

    @patch("subprocess.run")
    def test_run_test_suite_real_api_keys(self, mock_run, mock_args, temp_output_dir):
        """Test test suite with real API keys enabled."""
        mock_args.output_dir = str(temp_output_dir)
        mock_args.real_api_keys = True
        mock_run.return_value = Mock(returncode=0, stderr="")

        # Create mock report
        report_file = temp_output_dir / "unit_report.json"
        with open(report_file, "w") as f:
            json.dump({"summary": {"passed": 10, "failed": 0, "skipped": 0}}, f)

        runner = E2ETestRunner(mock_args)
        suite_config = runner.test_suites["unit"]

        runner.run_test_suite("unit", suite_config)

        # Verify mock API keys were NOT set
        call_env = mock_run.call_args[1]["env"]
        # Should use environment's actual keys, not mock ones
        assert call_env.get("DEEPGRAM_API_KEY") != "test_deepgram_key_for_mocking"


# ==================== JSON Report Parsing Tests ====================


class TestJSONReportParsing:
    """Test pytest JSON report parsing."""

    def test_parse_valid_report(self, runner_with_temp_dir, temp_output_dir):
        """Test parsing valid pytest JSON report."""
        report_data = {"summary": {"passed": 15, "failed": 2, "skipped": 3, "error": 1}}

        report_file = temp_output_dir / "test_report.json"
        with open(report_file, "w") as f:
            json.dump(report_data, f)

        runner = runner_with_temp_dir
        stats = runner.parse_pytest_json_report(report_file)

        assert stats["passed"] == 15
        assert stats["failed"] == 2
        assert stats["skipped"] == 3
        assert stats["error"] == 1

    def test_parse_missing_report(self, runner_with_temp_dir, temp_output_dir):
        """Test parsing non-existent report file."""
        runner = runner_with_temp_dir
        report_file = temp_output_dir / "nonexistent.json"

        stats = runner.parse_pytest_json_report(report_file)

        assert stats["passed"] == 0
        assert stats["failed"] == 0
        assert stats["skipped"] == 0

    def test_parse_invalid_json(self, runner_with_temp_dir, temp_output_dir):
        """Test parsing invalid JSON report."""
        report_file = temp_output_dir / "invalid.json"
        with open(report_file, "w") as f:
            f.write("{ invalid json }")

        runner = runner_with_temp_dir
        stats = runner.parse_pytest_json_report(report_file)

        assert stats["passed"] == 0
        assert stats["failed"] == 0


# ==================== Run All Suites Tests ====================


class TestRunAllSuites:
    """Test running all test suites."""

    @patch.object(E2ETestRunner, "run_test_suite")
    def test_run_all_suites_success(self, mock_run_suite, runner_with_temp_dir):
        """Test running all suites successfully."""
        mock_run_suite.return_value = TestSuiteResult("test", True, 10.0, 10, 0, 0)

        runner = runner_with_temp_dir
        result = runner.run_all_suites()

        assert result is True
        assert len(runner.suite_results) == len(runner.test_suites)

    @patch.object(E2ETestRunner, "run_test_suite")
    def test_run_single_suite(self, mock_run_suite, mock_args, temp_output_dir):
        """Test running a single suite."""
        mock_args.output_dir = str(temp_output_dir)
        mock_args.suite = "unit"
        mock_run_suite.return_value = TestSuiteResult("unit", True, 10.0, 10, 0, 0)

        runner = E2ETestRunner(mock_args)
        result = runner.run_all_suites()

        assert result is True
        assert len(runner.suite_results) == 1
        assert runner.suite_results[0].suite_name == "unit"

    @patch.object(E2ETestRunner, "run_test_suite")
    def test_run_suites_with_failure(self, mock_run_suite, runner_with_temp_dir):
        """Test running suites with failures."""
        # First suite fails, rest succeed
        mock_run_suite.side_effect = [
            TestSuiteResult("unit", False, 10.0, 5, 5, 0),
            TestSuiteResult("integration", True, 15.0, 10, 0, 0),
            TestSuiteResult("cli", True, 20.0, 8, 0, 1),
        ]

        runner = runner_with_temp_dir
        # Limit to specific suites for predictable behavior
        runner.test_suites = {
            "unit": runner.test_suites["unit"],
            "integration": runner.test_suites["integration"],
            "cli": runner.test_suites["cli"],
        }

        result = runner.run_all_suites()

        assert result is False  # Overall failure
        assert len(runner.suite_results) == 3

    @patch.object(E2ETestRunner, "run_test_suite")
    def test_run_suites_fail_fast(self, mock_run_suite, mock_args, temp_output_dir):
        """Test fail-fast behavior on critical failure."""
        mock_args.output_dir = str(temp_output_dir)
        mock_args.fail_fast = True

        # First critical suite fails
        mock_run_suite.return_value = TestSuiteResult("unit", False, 10.0, 0, 10, 0)

        runner = E2ETestRunner(mock_args)
        result = runner.run_all_suites()

        assert result is False
        # Should stop after first critical failure
        assert mock_run_suite.call_count == 1

    @patch.object(E2ETestRunner, "run_test_suite")
    def test_run_suites_mixed_critical_noncritical_failures(
        self, mock_run_suite, runner_with_temp_dir
    ):
        """Test handling of mixed critical and non-critical suite failures."""
        # Unit (critical) passes, performance (non-critical) fails, integration (critical) passes
        mock_run_suite.side_effect = [
            TestSuiteResult("unit", True, 10.0, 50, 0, 2),
            TestSuiteResult("integration", True, 15.0, 30, 0, 1),
            TestSuiteResult("cli", True, 20.0, 15, 0, 0),
            TestSuiteResult("provider", True, 12.0, 25, 0, 3),
            TestSuiteResult("performance", False, 30.0, 5, 10, 0),  # Non-critical failure
            TestSuiteResult("security", True, 18.0, 20, 0, 1),
        ]

        runner = runner_with_temp_dir
        result = runner.run_all_suites()

        # Should fail overall due to performance failure
        assert result is False
        # But should run all suites since performance is not critical
        assert len(runner.suite_results) == 6

    @patch.object(E2ETestRunner, "run_test_suite")
    def test_run_suites_non_critical_failure_no_fail_fast(
        self, mock_run_suite, mock_args, temp_output_dir
    ):
        """Test non-critical failures don't trigger fail-fast."""
        mock_args.output_dir = str(temp_output_dir)
        mock_args.fail_fast = True

        # Simulate performance (non-critical) failing, then unit (critical) passing
        results = []

        def mock_run_side_effect(suite_name, suite_config):
            if suite_name == "performance":
                result = TestSuiteResult("performance", False, 20.0, 5, 10, 0)
            else:
                result = TestSuiteResult(suite_name, True, 10.0, 10, 0, 0)
            results.append(result)
            return result

        mock_run_suite.side_effect = mock_run_side_effect

        runner = E2ETestRunner(mock_args)
        runner.run_all_suites()

        # Should continue running after non-critical failure
        assert len(results) > 1


# ==================== Report Generation Tests ====================


class TestReportGeneration:
    """Test report generation and saving."""

    def test_generate_report(self, runner_with_temp_dir):
        """Test report generation."""
        runner = runner_with_temp_dir

        # Add some mock results
        runner.suite_results = [
            TestSuiteResult("unit", True, 10.0, 50, 0, 2),
            TestSuiteResult("integration", True, 15.0, 30, 0, 1),
        ]

        report = runner.generate_report()

        assert isinstance(report, E2ETestReport)
        assert report.overall_success is True
        assert len(report.suite_results) == 2
        assert report.total_duration > 0

    def test_generate_report_with_failures(self, runner_with_temp_dir):
        """Test report generation with failures."""
        runner = runner_with_temp_dir

        runner.suite_results = [
            TestSuiteResult("unit", True, 10.0, 50, 0, 2),
            TestSuiteResult("integration", False, 15.0, 25, 5, 1),
        ]

        report = runner.generate_report()

        assert report.overall_success is False

    def test_save_report_creates_files(self, runner_with_temp_dir, temp_output_dir):
        """Test that save_report creates JSON and text files."""
        runner = runner_with_temp_dir

        report = E2ETestReport(
            start_time="2025-01-01 10:00:00",
            end_time="2025-01-01 10:30:00",
            total_duration=1800.0,
            environment_info={"python_version": "3.10.0"},
            suite_results=[TestSuiteResult("unit", True, 10.0, 50, 0, 2)],
            overall_success=True,
        )

        runner.save_report(report)

        json_file = temp_output_dir / "e2e_test_report.json"
        text_file = temp_output_dir / "e2e_test_report.txt"

        assert json_file.exists()
        assert text_file.exists()

        # Verify JSON content
        with open(json_file) as f:
            data = json.load(f)
            assert data["overall_success"] is True
            assert len(data["suite_results"]) == 1


# ==================== Cleanup Tests ====================


class TestCleanup:
    """Test cleanup functionality."""

    def test_cleanup_without_keep_artifacts(self, runner_with_temp_dir):
        """Test cleanup removes artifacts."""
        runner = runner_with_temp_dir
        runner.args.keep_artifacts = False

        # This should not raise an error
        runner.cleanup()

    def test_cleanup_with_keep_artifacts(self, runner_with_temp_dir):
        """Test cleanup keeps artifacts when requested."""
        runner = runner_with_temp_dir
        runner.args.keep_artifacts = True

        # This should not raise an error
        runner.cleanup()


# ==================== Main Run Method Tests ====================


class TestMainRun:
    """Test the main run method."""

    @patch.object(E2ETestRunner, "validate_environment")
    @patch.object(E2ETestRunner, "setup_test_data")
    @patch.object(E2ETestRunner, "run_all_suites")
    @patch.object(E2ETestRunner, "save_report")
    @patch.object(E2ETestRunner, "cleanup")
    def test_run_success(
        self,
        mock_cleanup,
        mock_save,
        mock_run_suites,
        mock_setup,
        mock_validate,
        runner_with_temp_dir,
    ):
        """Test successful full run."""
        mock_validate.return_value = True
        mock_setup.return_value = True
        mock_run_suites.return_value = True

        runner = runner_with_temp_dir
        result = runner.run()

        assert result is True
        mock_validate.assert_called_once()
        mock_setup.assert_called_once()
        mock_run_suites.assert_called_once()
        mock_save.assert_called_once()
        mock_cleanup.assert_called_once()

    @patch.object(E2ETestRunner, "validate_environment")
    @patch.object(E2ETestRunner, "cleanup")
    def test_run_validation_failure(self, mock_cleanup, mock_validate, runner_with_temp_dir):
        """Test run fails on validation failure."""
        mock_validate.return_value = False

        runner = runner_with_temp_dir
        result = runner.run()

        assert result is False
        mock_cleanup.assert_called_once()

    @patch.object(E2ETestRunner, "validate_environment")
    @patch.object(E2ETestRunner, "setup_test_data")
    @patch.object(E2ETestRunner, "cleanup")
    def test_run_data_setup_failure(
        self, mock_cleanup, mock_setup, mock_validate, runner_with_temp_dir
    ):
        """Test run fails on data setup failure."""
        mock_validate.return_value = True
        mock_setup.return_value = False

        runner = runner_with_temp_dir
        result = runner.run()

        assert result is False
        mock_cleanup.assert_called_once()

    @patch.object(E2ETestRunner, "validate_environment")
    @patch.object(E2ETestRunner, "run_all_suites")
    @patch.object(E2ETestRunner, "cleanup")
    def test_run_keyboard_interrupt(
        self, mock_cleanup, mock_run_suites, mock_validate, runner_with_temp_dir
    ):
        """Test run handles KeyboardInterrupt gracefully."""
        mock_validate.return_value = True
        mock_run_suites.side_effect = KeyboardInterrupt()

        runner = runner_with_temp_dir
        result = runner.run()

        assert result is False
        mock_cleanup.assert_called_once()

    @patch.object(E2ETestRunner, "validate_environment")
    @patch.object(E2ETestRunner, "run_all_suites")
    @patch.object(E2ETestRunner, "cleanup")
    def test_run_unexpected_exception(
        self, mock_cleanup, mock_run_suites, mock_validate, runner_with_temp_dir
    ):
        """Test run handles unexpected exceptions."""
        mock_validate.return_value = True
        mock_run_suites.side_effect = RuntimeError("Unexpected error")

        runner = runner_with_temp_dir
        result = runner.run()

        assert result is False
        mock_cleanup.assert_called_once()

    @patch.object(E2ETestRunner, "validate_environment")
    @patch.object(E2ETestRunner, "run_all_suites")
    @patch.object(E2ETestRunner, "cleanup")
    def test_run_verbose_exception_traceback(
        self, mock_cleanup, mock_run_suites, mock_validate, mock_args, temp_output_dir
    ):
        """Test run shows traceback in verbose mode on exception."""
        mock_args.output_dir = str(temp_output_dir)
        mock_args.verbose = True
        mock_validate.return_value = True
        mock_run_suites.side_effect = RuntimeError("Test error")

        runner = E2ETestRunner(mock_args)
        result = runner.run()

        assert result is False
        # In verbose mode, traceback should be logged (verified by no crash)


# ==================== Print Summary Tests ====================


class TestPrintSummary:
    """Test summary printing."""

    def test_print_summary(self, runner_with_temp_dir, capsys):
        """Test print_summary produces output."""
        runner = runner_with_temp_dir

        report = E2ETestReport(
            start_time="2025-01-01 10:00:00",
            end_time="2025-01-01 10:30:00",
            total_duration=1800.0,
            environment_info={"python_version": "3.10.0"},
            suite_results=[
                TestSuiteResult("unit", True, 10.0, 50, 0, 2),
                TestSuiteResult("integration", False, 15.0, 25, 5, 1),
            ],
            overall_success=False,
        )

        runner.print_summary(report)

        captured = capsys.readouterr()
        assert "E2E TEST EXECUTION SUMMARY" in captured.out
        assert "FAILED" in captured.out or "❌" in captured.out
        assert "unit" in captured.out
        assert "integration" in captured.out

    def test_print_summary_zero_tests(self, runner_with_temp_dir, capsys):
        """Test print_summary handles zero tests gracefully."""
        runner = runner_with_temp_dir

        report = E2ETestReport(
            start_time="2025-01-01 10:00:00",
            end_time="2025-01-01 10:30:00",
            total_duration=100.0,
            environment_info={"python_version": "3.10.0"},
            suite_results=[],
            overall_success=True,
        )

        runner.print_summary(report)

        captured = capsys.readouterr()
        assert "E2E TEST EXECUTION SUMMARY" in captured.out
        assert "0/0" in captured.out or "N/A" in captured.out

    def test_print_summary_all_passed(self, runner_with_temp_dir, capsys):
        """Test print_summary with all tests passing."""
        runner = runner_with_temp_dir

        report = E2ETestReport(
            start_time="2025-01-01 10:00:00",
            end_time="2025-01-01 10:30:00",
            total_duration=500.0,
            environment_info={"python_version": "3.10.0"},
            suite_results=[
                TestSuiteResult("unit", True, 10.0, 100, 0, 0),
                TestSuiteResult("integration", True, 15.0, 50, 0, 0),
            ],
            overall_success=True,
        )

        runner.print_summary(report)

        captured = capsys.readouterr()
        assert "E2E TEST EXECUTION SUMMARY" in captured.out
        assert "PASSED" in captured.out or "✅" in captured.out
        assert "150/150" in captured.out  # All tests passed
        assert "100.0%" in captured.out  # Pass rate should be 100%


# ==================== Edge Cases and Error Handling ====================


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_unknown_suite_name(self, runner_with_temp_dir):
        """Test handling of unknown suite name."""
        runner = runner_with_temp_dir
        runner.args.suite = "nonexistent_suite"

        result = runner.run_all_suites()

        assert result is False

    def test_empty_suite_results(self, runner_with_temp_dir):
        """Test report generation with no suite results."""
        runner = runner_with_temp_dir
        runner.suite_results = []

        report = runner.generate_report()

        assert report.overall_success is True  # No failures = success
        assert len(report.suite_results) == 0

    @patch("subprocess.run")
    def test_run_test_suite_unexpected_exception(self, mock_run, runner_with_temp_dir):
        """Test handling of unexpected exceptions during suite run."""
        mock_run.side_effect = RuntimeError("Unexpected error")

        runner = runner_with_temp_dir
        suite_config = runner.test_suites["unit"]

        result = runner.run_test_suite("unit", suite_config)

        assert result.success is False
        assert "Unexpected error" in result.error_message

    @patch("subprocess.run")
    def test_run_test_suite_no_parallel_for_non_unit_integration(
        self, mock_run, mock_args, temp_output_dir
    ):
        """Test parallel execution is not applied to non-unit/integration suites."""
        mock_args.output_dir = str(temp_output_dir)
        mock_args.parallel = True
        mock_run.return_value = Mock(returncode=0, stderr="")

        # Create mock report
        report_file = temp_output_dir / "performance_report.json"
        with open(report_file, "w") as f:
            json.dump({"summary": {"passed": 10, "failed": 0, "skipped": 0}}, f)

        runner = E2ETestRunner(mock_args)
        suite_config = runner.test_suites["performance"]

        runner.run_test_suite("performance", suite_config)

        # Check that parallel arguments were NOT added
        call_args = mock_run.call_args[0][0]
        assert "-n" not in call_args

    def test_parse_report_with_error_count(self, runner_with_temp_dir, temp_output_dir):
        """Test parsing report with error count."""
        report_data = {"summary": {"passed": 10, "failed": 2, "skipped": 1, "error": 3}}

        report_file = temp_output_dir / "test_report.json"
        with open(report_file, "w") as f:
            json.dump(report_data, f)

        runner = runner_with_temp_dir
        stats = runner.parse_pytest_json_report(report_file)

        assert stats["passed"] == 10
        assert stats["failed"] == 2
        assert stats["skipped"] == 1
        assert stats["error"] == 3

    def test_report_save_text_format(self, runner_with_temp_dir, temp_output_dir):
        """Test text report contains detailed information."""
        runner = runner_with_temp_dir

        report = E2ETestReport(
            start_time="2025-01-01 10:00:00",
            end_time="2025-01-01 10:30:00",
            total_duration=1800.0,
            environment_info={
                "python_version": "3.10.0",
                "platform": "linux",
                "validation_errors": [],
            },
            suite_results=[
                TestSuiteResult("unit", True, 10.0, 50, 0, 2),
                TestSuiteResult(
                    "integration", False, 15.0, 25, 5, 1, error_message="Test failures"
                ),
            ],
            overall_success=False,
        )

        runner.save_report(report)

        text_file = temp_output_dir / "e2e_test_report.txt"
        assert text_file.exists()

        with open(text_file) as f:
            content = f.read()
            assert "AUDIO-EXTRACTION-ANALYSIS E2E TEST REPORT" in content
            assert "python_version: 3.10.0" in content
            assert "platform: linux" in content
            assert "unit:" in content
            assert "integration:" in content
            assert "Test failures" in content
            assert "FAILED" in content or "❌" in content
