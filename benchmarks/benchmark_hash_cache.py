"""
Shim module for backward compatibility with tests.
Re-exports the main benchmark functions from hash_cache_benchmark.py
"""

# Re-export all public functions from the actual implementation
from .hash_cache_benchmark import (
    create_test_file,
    benchmark_hash_performance,
    main,
)

__all__ = [
    "create_test_file",
    "benchmark_hash_performance",
    "main",
]