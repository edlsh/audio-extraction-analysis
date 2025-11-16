#!/usr/bin/env python3
"""
Comprehensive E2E Test Runner for audio-extraction-analysis.

This script orchestrates the complete end-to-end testing suite including:
- Environment setup and validation
- Test data preparation
- Test execution with different suites
- Result reporting and analysis
- Cleanup operations
"""

import argparse
import json
import logging
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

from .test_data_manager import TestDataManager


@dataclass
class TestSuiteResult:
    """Results from a test suite execution."""

    suite_name: str
    success: bool
    duration: float
    tests_passed: int
    tests_failed: int
    tests_skipped: int
    error_message: str | None = None
    coverage: float | None = None


@dataclass
class E2ETestReport:
    """Complete E2E test execution report."""

    start_time: str
    end_time: str
    total_duration: float
    environment_info: dict
    suite_results: list[TestSuiteResult]
    overall_success: bool
    coverage_report: dict | None = None


class E2ETestRunner:
    """Main E2E test runner class."""

    def __init__(self, args: argparse.Namespace):
        """Initialize test runner with configuration."""
        self.args = args
        self.start_time = time.time()
        self.project_root = Path(__file__).parent.parent.parent
        self.test_dir = self.project_root / "tests" / "e2e"
        self.output_dir = (
            Path(args.output_dir) if args.output_dir else self.project_root / "test_results"
        )
        self.output_dir.mkdir(exist_ok=True)

        # Setup logging
        self.setup_logging()

        # Test suites configuration
        self.test_suites = {
            "unit": {
                "path": "tests/unit",
                "description": "Unit tests for individual components",
                "timeout": 300,
                "critical": True,
            },
            "integration": {
                "path": "tests/integration",
                "description": "Integration tests for service interactions",
                "timeout": 600,
                "critical": True,
            },
            "cli": {
                "path": "tests/e2e/test_cli_integration.py",
                "description": "CLI command integration tests",
                "timeout": 900,
                "critical": True,
            },
            "provider": {
                "path": "tests/e2e/test_provider_integration.py",
                "description": "Provider factory and integration tests",
                "timeout": 600,
                "critical": True,
            },
            "performance": {
                "path": "tests/e2e/test_performance.py",
                "description": "Performance and load testing",
                "timeout": 1800,
                "critical": False,
            },
            "security": {
                "path": "tests/e2e/test_security.py",
                "description": "Security and vulnerability testing",
                "timeout": 600,
                "critical": True,
            },
        }

        # Results storage
        self.suite_results: list[TestSuiteResult] = []
        self.environment_info = {}

    def setup_logging(self):
        """Setup logging configuration."""
        log_level = logging.DEBUG if self.args.verbose else logging.INFO

        # Create formatters
        detailed_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        simple_formatter = logging.Formatter("%(levelname)s: %(message)s")

        # Setup logger
        self.logger = logging.getLogger("e2e_test_runner")
        self.logger.setLevel(log_level)

        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(log_level)
        console_handler.setFormatter(
            simple_formatter if not self.args.verbose else detailed_formatter
        )
        self.logger.addHandler(console_handler)

        # File handler
        log_file = self.output_dir / "e2e_test_run.log"
        file_handler = logging.FileHandler(log_file, mode="w")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(detailed_formatter)
        self.logger.addHandler(file_handler)

        self.logger.info(f"E2E Test Runner started - Log file: {log_file}")

    def validate_environment(self) -> bool:
        """Validate test environment and dependencies."""
        self.logger.info("Validating test environment...")

        validation_errors = []

        # Check Python version
        python_version = sys.version_info
        if python_version < (3, 8):
            validation_errors.append(
                f"Python 3.8+ required, found {python_version.major}.{python_version.minor}"
            )

        # Check required tools
        required_tools = ["ffmpeg", "pytest"]
        for tool in required_tools:
            if not self.check_tool_available(tool):
                validation_errors.append(f"Required tool not found: {tool}")

        # Check project structure
        required_paths = [
            self.project_root / "src",
            self.project_root / "tests",
            self.project_root / "pyproject.toml",
        ]

        for path in required_paths:
            if not path.exists():
                validation_errors.append(f"Required path not found: {path}")

        # Check test dependencies
        try:
            import psutil
            import pytest
        except ImportError as e:
            validation_errors.append(f"Required Python package not found: {e}")

        # Store environment info
        self.environment_info = {
            "python_version": f"{python_version.major}.{python_version.minor}.{python_version.micro}",
            "platform": sys.platform,
            "working_directory": str(Path.cwd()),
            "project_root": str(self.project_root),
            "ffmpeg_available": self.check_tool_available("ffmpeg"),
            "pytest_version": self.get_tool_version("pytest"),
            "validation_errors": validation_errors,
        }

        if validation_errors:
            self.logger.error("Environment validation failed:")
            for error in validation_errors:
                self.logger.error(f"  - {error}")
            return False

        self.logger.info("Environment validation passed")
        return True

    def check_tool_available(self, tool: str) -> bool:
        """Check if a command-line tool is available."""
        try:
            result = subprocess.run([tool, "--version"], capture_output=True, text=True, timeout=10)
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def get_tool_version(self, tool: str) -> str | None:
        """Get version of a command-line tool."""
        try:
            result = subprocess.run([tool, "--version"], capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                return result.stdout.strip().split("\n")[0]
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        return None

    def setup_test_data(self) -> bool:
        """Setup test data and media files."""
        self.logger.info("Setting up test data...")

        try:
            test_data_manager = TestDataManager()

            if self.args.generate_test_data:
                self.logger.info("Generating test media files...")
                generated_files = test_data_manager.generate_all_test_files(force_regenerate=True)

                if generated_files:
                    self.logger.info(f"Generated {len(generated_files)} test files")
                    for file_type, file_path in generated_files.items():
                        self.logger.debug(f"  {file_type}: {file_path}")
                else:
                    self.logger.warning("No test files were generated")

            # Validate test files
            validation_results = test_data_manager.validate_test_files()
            valid_files = [k for k, v in validation_results.items() if v]
            invalid_files = [k for k, v in validation_results.items() if not v]

            self.logger.info(
                f"Test data validation: {len(valid_files)} valid, {len(invalid_files)} invalid"
            )

            if invalid_files:
                self.logger.warning(f"Invalid test files: {invalid_files}")

            # At least some test files should be available
            if len(valid_files) == 0:
                self.logger.error("No valid test files available")
                return False

            return True

        except Exception as e:
            self.logger.error(f"Test data setup failed: {e}")
            return False

    def run_test_suite(self, suite_name: str, suite_config: dict) -> TestSuiteResult:
        """Run a specific test suite."""
        self.logger.info(f"Running {suite_name} test suite: {suite_config['description']}")

        start_time = time.time()

        # Prepare pytest command
        pytest_args = [
            "python",
            "-m",
            "pytest",
            suite_config["path"],
            "-v",
            "--tb=short",
            f"--timeout={suite_config['timeout']}",
            "--json-report",
            f"--json-report-file={self.output_dir / f'{suite_name}_report.json'}",
        ]

        # Add coverage if requested
        if self.args.coverage:
            pytest_args.extend(
                [
                    "--cov=src",
                    f"--cov-report=html:{self.output_dir / (suite_name + '_coverage')!s}",
                    f"--cov-report=json:{self.output_dir / (suite_name + '_coverage.json')!s}",
                ]
            )

        # Add parallel execution if requested
        if self.args.parallel and suite_name in ["unit", "integration"]:
            pytest_args.extend(["-n", "auto"])

        # Set environment variables for testing
        test_env = os.environ.copy()
        test_env.update(
            {
                "PYTHONPATH": str(self.project_root),
                "TEST_MODE": "true",
                "LOG_LEVEL": "DEBUG" if self.args.verbose else "INFO",
            }
        )

        # Add mock API keys for testing
        if not self.args.real_api_keys:
            test_env.update(
                {
                    "DEEPGRAM_API_KEY": "test_deepgram_key_for_mocking",
                    "ELEVENLABS_API_KEY": "test_elevenlabs_key_for_mocking",
                }
            )

        try:
            # Run pytest
            self.logger.debug(f"Executing: {' '.join(pytest_args)}")

            result = subprocess.run(
                pytest_args,
                capture_output=True,
                text=True,
                cwd=self.project_root,
                env=test_env,
                timeout=suite_config["timeout"] + 60,  # Extra buffer
            )

            duration = time.time() - start_time

            # Parse results from JSON report
            report_file = self.output_dir / f"{suite_name}_report.json"
            test_stats = self.parse_pytest_json_report(report_file)

            # Determine success
            success = result.returncode == 0

            suite_result = TestSuiteResult(
                suite_name=suite_name,
                success=success,
                duration=duration,
                tests_passed=test_stats.get("passed", 0),
                tests_failed=test_stats.get("failed", 0),
                tests_skipped=test_stats.get("skipped", 0),
                error_message=result.stderr if not success else None,
            )

            # Log results
            if success:
                self.logger.info(
                    f"✅ {suite_name}: {test_stats.get('passed', 0)} passed, "
                    f"{test_stats.get('skipped', 0)} skipped in {duration:.1f}s"
                )
            else:
                self.logger.error(
                    f"❌ {suite_name}: {test_stats.get('failed', 0)} failed, "
                    f"{test_stats.get('passed', 0)} passed in {duration:.1f}s"
                )
                if self.args.verbose and result.stderr:
                    self.logger.error(f"Error output: {result.stderr}")

            return suite_result

        except subprocess.TimeoutExpired:
            duration = time.time() - start_time
            self.logger.error(f"❌ {suite_name}: Timed out after {duration:.1f}s")

            return TestSuiteResult(
                suite_name=suite_name,
                success=False,
                duration=duration,
                tests_passed=0,
                tests_failed=1,
                tests_skipped=0,
                error_message=f"Test suite timed out after {duration:.1f}s",
            )

        except Exception as e:
            duration = time.time() - start_time
            self.logger.error(f"❌ {suite_name}: Execution failed: {e}")

            return TestSuiteResult(
                suite_name=suite_name,
                success=False,
                duration=duration,
                tests_passed=0,
                tests_failed=1,
                tests_skipped=0,
                error_message=str(e),
            )

    def parse_pytest_json_report(self, report_file: Path) -> dict:
        """Parse pytest JSON report file."""
        if not report_file.exists():
            return {"passed": 0, "failed": 0, "skipped": 0}

        try:
            with open(report_file) as f:
                report_data = json.load(f)

            summary = report_data.get("summary", {})
            return {
                "passed": summary.get("passed", 0),
                "failed": summary.get("failed", 0),
                "skipped": summary.get("skipped", 0),
                "error": summary.get("error", 0),
            }
        except (json.JSONDecodeError, KeyError) as e:
            self.logger.warning(f"Failed to parse pytest report {report_file}: {e}")
            return {"passed": 0, "failed": 0, "skipped": 0}

    def run_all_suites(self) -> bool:
        """Run all configured test suites."""
        self.logger.info("Starting comprehensive E2E test execution...")

        # Determine which suites to run
        if self.args.suite == "all":
            suites_to_run = self.test_suites.items()
        else:
            if self.args.suite not in self.test_suites:
                self.logger.error(f"Unknown test suite: {self.args.suite}")
                return False
            suites_to_run = [(self.args.suite, self.test_suites[self.args.suite])]

        # Run suites
        overall_success = True
        critical_failure = False

        for suite_name, suite_config in suites_to_run:
            if self.args.fail_fast and critical_failure:
                self.logger.info(f"Skipping {suite_name} due to previous critical failure")
                continue

            result = self.run_test_suite(suite_name, suite_config)
            self.suite_results.append(result)

            if not result.success:
                overall_success = False
                if suite_config.get("critical", False):
                    critical_failure = True
                    if self.args.fail_fast:
                        self.logger.error(
                            f"Critical test suite {suite_name} failed, stopping execution"
                        )
                        break

        return overall_success

    def generate_report(self) -> E2ETestReport:
        """Generate comprehensive test report."""
        end_time = time.time()
        total_duration = end_time - self.start_time

        # Calculate overall success
        overall_success = all(result.success for result in self.suite_results)

        # Create report
        report = E2ETestReport(
            start_time=time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.start_time)),
            end_time=time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(end_time)),
            total_duration=total_duration,
            environment_info=self.environment_info,
            suite_results=self.suite_results,
            overall_success=overall_success,
        )

        return report

    def save_report(self, report: E2ETestReport):
        """Save test report to files."""
        # JSON report
        json_report_file = self.output_dir / "e2e_test_report.json"
        with open(json_report_file, "w") as f:
            json.dump(
                {
                    "start_time": report.start_time,
                    "end_time": report.end_time,
                    "total_duration": report.total_duration,
                    "environment_info": report.environment_info,
                    "overall_success": report.overall_success,
                    "suite_results": [
                        {
                            "suite_name": r.suite_name,
                            "success": r.success,
                            "duration": r.duration,
                            "tests_passed": r.tests_passed,
                            "tests_failed": r.tests_failed,
                            "tests_skipped": r.tests_skipped,
                            "error_message": r.error_message,
                        }
                        for r in report.suite_results
                    ],
                },
                f,
                indent=2,
            )

        # Human-readable report
        text_report_file = self.output_dir / "e2e_test_report.txt"
        with open(text_report_file, "w") as f:
            f.write("=" * 80 + "\n")
            f.write("AUDIO-EXTRACTION-ANALYSIS E2E TEST REPORT\n")
            f.write("=" * 80 + "\n\n")

            f.write(f"Execution Time: {report.start_time} - {report.end_time}\n")
            f.write(f"Total Duration: {report.total_duration:.1f} seconds\n")
            f.write(f"Overall Result: {'✅ PASSED' if report.overall_success else '❌ FAILED'}\n\n")

            f.write("ENVIRONMENT INFO:\n")
            f.write("-" * 40 + "\n")
            for key, value in report.environment_info.items():
                if key != "validation_errors":
                    f.write(f"{key}: {value}\n")
            f.write("\n")

            f.write("TEST SUITE RESULTS:\n")
            f.write("-" * 40 + "\n")

            total_passed = sum(r.tests_passed for r in report.suite_results)
            total_failed = sum(r.tests_failed for r in report.suite_results)
            total_skipped = sum(r.tests_skipped for r in report.suite_results)

            f.write(f"Total Tests: {total_passed + total_failed + total_skipped}\n")
            f.write(f"Passed: {total_passed}\n")
            f.write(f"Failed: {total_failed}\n")
            f.write(f"Skipped: {total_skipped}\n\n")

            for result in report.suite_results:
                status = "✅ PASSED" if result.success else "❌ FAILED"
                f.write(f"{result.suite_name}: {status}\n")
                f.write(f"  Duration: {result.duration:.1f}s\n")
                f.write(
                    f"  Tests: {result.tests_passed} passed, {result.tests_failed} failed, {result.tests_skipped} skipped\n"
                )
                if result.error_message:
                    f.write(f"  Error: {result.error_message}\n")
                f.write("\n")

        self.logger.info("Reports saved to:")
        self.logger.info(f"  JSON: {json_report_file}")
        self.logger.info(f"  Text: {text_report_file}")

    def cleanup(self):
        """Cleanup test artifacts and temporary files."""
        if not self.args.keep_artifacts:
            self.logger.info("Cleaning up test artifacts...")

            # Clean up test data if requested
            if hasattr(self, "test_data_manager"):
                self.test_data_manager.cleanup_test_files(keep_generated=True)

            # Clean up pytest cache
            pytest_cache = self.project_root / ".pytest_cache"
            if pytest_cache.exists():
                import shutil

                shutil.rmtree(pytest_cache, ignore_errors=True)
        else:
            self.logger.info("Keeping test artifacts as requested")

    def run(self) -> bool:
        """Main execution method."""
        try:
            # Validate environment
            if not self.validate_environment():
                return False

            # Setup test data
            if not self.setup_test_data():
                return False

            # Run test suites
            success = self.run_all_suites()

            # Generate and save report
            report = self.generate_report()
            self.save_report(report)

            # Print summary
            self.print_summary(report)

            return success

        except KeyboardInterrupt:
            self.logger.warning("Test execution interrupted by user")
            return False
        except Exception as e:
            self.logger.error(f"Test execution failed: {e}")
            if self.args.verbose:
                import traceback

                self.logger.error(traceback.format_exc())
            return False
        finally:
            self.cleanup()

    def print_summary(self, report: E2ETestReport):
        """Print execution summary."""
        print("\n" + "=" * 80)
        print("E2E TEST EXECUTION SUMMARY")
        print("=" * 80)

        print(f"Duration: {report.total_duration:.1f} seconds")
        print(f"Result: {'✅ PASSED' if report.overall_success else '❌ FAILED'}")

        total_tests = sum(
            r.tests_passed + r.tests_failed + r.tests_skipped for r in report.suite_results
        )
        total_passed = sum(r.tests_passed for r in report.suite_results)
        sum(r.tests_failed for r in report.suite_results)

        if total_tests > 0:
            pass_rate = total_passed / total_tests * 100
            print(f"Tests: {total_passed}/{total_tests} passed ({pass_rate:.1f}%)")
        else:
            print(f"Tests: {total_passed}/{total_tests} passed (N/A)")

        print("\nSuite Results:")
        for result in report.suite_results:
            status = "✅" if result.success else "❌"
            print(
                f"  {status} {result.suite_name}: {result.tests_passed}P {result.tests_failed}F {result.tests_skipped}S ({result.duration:.1f}s)"
            )

        print(f"\nDetailed reports: {self.output_dir}")
        print("=" * 80)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Comprehensive E2E Test Runner for audio-extraction-analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --suite all --coverage            # Run all tests with coverage
  %(prog)s --suite unit --fail-fast          # Run only unit tests, stop on first failure
  %(prog)s --suite performance --verbose     # Run performance tests with verbose output
  %(prog)s --generate-test-data              # Generate fresh test data
        """,
    )

    parser.add_argument(
        "--suite",
        choices=["all", "unit", "integration", "cli", "provider", "performance", "security"],
        default="all",
        help="Test suite to run (default: all)",
    )

    parser.add_argument(
        "--output-dir", help="Output directory for test results (default: ./test_results)"
    )

    parser.add_argument("--coverage", action="store_true", help="Generate code coverage reports")

    parser.add_argument(
        "--parallel", action="store_true", help="Run tests in parallel where possible"
    )

    parser.add_argument(
        "--fail-fast", action="store_true", help="Stop on first critical test failure"
    )

    parser.add_argument("--verbose", action="store_true", help="Verbose output and logging")

    parser.add_argument(
        "--generate-test-data", action="store_true", help="Generate fresh test media files"
    )

    parser.add_argument(
        "--real-api-keys",
        action="store_true",
        help="Use real API keys instead of mocked services (requires valid keys in environment)",
    )

    parser.add_argument(
        "--keep-artifacts", action="store_true", help="Keep test artifacts and temporary files"
    )

    args = parser.parse_args()

    # Create and run test runner
    runner = E2ETestRunner(args)
    success = runner.run()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
