"""
End-to-end test framework for audio-extraction-analysis.

This module provides comprehensive E2E testing capabilities including:
- CLI command integration tests
- Provider factory validation
- Performance and load testing
- Security testing
- Test data management
"""

from .base import (
    CLITestMixin,
    E2ETestBase,
    MockProviderMixin,
    PerformanceTestMixin,
    SecurityTestMixin,
    TestFile,
    TestResult,
)

__all__ = [
    # Test mixins
    "CLITestMixin",
    # Base classes
    "E2ETestBase",
    "MockProviderMixin",
    "PerformanceTestMixin",
    "SecurityTestMixin",
    # Data classes
    "TestFile",
    "TestResult",
]
