"""
Tests for file hash caching optimization.

This module tests the file hash cache that eliminates redundant I/O operations
by caching file hashes based on (path, mtime, size) metadata.
"""

from __future__ import annotations

import tempfile
import time
from pathlib import Path

import pytest

from src.cache.transcription_cache import CacheKey

# Apply markers to all tests in this module
pytestmark = [
    pytest.mark.unit,
    pytest.mark.fast,
]


class TestFileHashCache:
    """Test file hash caching functionality."""

    @pytest.fixture(autouse=True)
    def clear_hash_cache(self):
        """Clear hash cache before each test."""
        CacheKey.clear_hash_cache()
        yield
        CacheKey.clear_hash_cache()

    @pytest.fixture
    def temp_file(self) -> Path:
        """Create a temporary file for testing."""
        with tempfile.NamedTemporaryFile(mode="wb", delete=False) as f:
            f.write(b"Test content for hash caching" * 1000)
            temp_path = Path(f.name)

        yield temp_path

        # Cleanup
        temp_path.unlink(missing_ok=True)

    def test_hash_cache_hit_on_repeated_calls(self, temp_file: Path):
        """Test that repeated hash calls use cache instead of rehashing."""
        # First call should compute hash
        hash1 = CacheKey._hash_file(temp_file)

        # Second call should return cached hash
        hash2 = CacheKey._hash_file(temp_file)

        assert hash1 == hash2, "Hash should be consistent"

        # Verify cache contains entry
        import os

        stat = os.stat(temp_file)
        cache_key = (str(temp_file), stat.st_mtime, stat.st_size)
        assert cache_key in CacheKey._file_hash_cache, "Hash should be cached"

    def test_hash_cache_invalidation_on_content_change(self, temp_file: Path):
        """Test that cache is invalidated when file content changes."""
        # Get initial hash
        hash1 = CacheKey._hash_file(temp_file)

        # Modify file content
        time.sleep(0.01)  # Ensure mtime changes
        with open(temp_file, "ab") as f:
            f.write(b"Modified content")

        # Hash should be different after modification
        hash2 = CacheKey._hash_file(temp_file)

        assert hash1 != hash2, "Hash should change when content changes"

        # Both hashes should be in cache (different cache keys due to mtime/size change)
        assert len(CacheKey._file_hash_cache) >= 1, "Cache should contain entries"

    def test_hash_cache_invalidation_on_size_change(self, temp_file: Path):
        """Test that cache key changes when file size changes."""
        # Get initial hash
        hash1 = CacheKey._hash_file(temp_file)
        initial_size = temp_file.stat().st_size

        # Modify file size
        time.sleep(0.01)
        with open(temp_file, "ab") as f:
            f.write(b"X" * 100)

        new_size = temp_file.stat().st_size
        assert new_size != initial_size, "File size should have changed"

        # New hash should be computed due to size change
        hash2 = CacheKey._hash_file(temp_file)
        assert hash1 != hash2, "Hash should change when file size changes"

    def test_clear_hash_cache_specific_file(self, temp_file: Path):
        """Test clearing cache for a specific file."""
        # Hash the file to populate cache
        CacheKey._hash_file(temp_file)

        # Verify cache is populated
        assert len(CacheKey._file_hash_cache) > 0, "Cache should be populated"

        # Clear cache for this file
        cleared = CacheKey.clear_hash_cache(temp_file)

        assert cleared > 0, "Should clear at least one entry"
        assert len(CacheKey._file_hash_cache) == 0, "Cache should be empty after clearing"

    def test_clear_hash_cache_all_files(self, temp_file: Path):
        """Test clearing entire hash cache."""
        # Create multiple temp files and hash them
        temp_files = [temp_file]
        for _ in range(3):
            with tempfile.NamedTemporaryFile(mode="wb", delete=False) as f:
                f.write(b"Test content")
                temp_path = Path(f.name)
                temp_files.append(temp_path)
                CacheKey._hash_file(temp_path)

        # Verify cache is populated
        assert len(CacheKey._file_hash_cache) >= 3, "Cache should have multiple entries"

        # Clear all
        cleared = CacheKey.clear_hash_cache()

        assert cleared >= 3, "Should clear multiple entries"
        assert len(CacheKey._file_hash_cache) == 0, "Cache should be completely empty"

        # Cleanup extra files
        for path in temp_files[1:]:
            path.unlink(missing_ok=True)

    def test_hash_cache_performance_improvement(self, temp_file: Path):
        """Test that cache provides significant performance improvement."""
        import timeit

        # Clear cache first
        CacheKey.clear_hash_cache()

        # Time first hash (cache miss)
        start = timeit.default_timer()
        hash1 = CacheKey._hash_file(temp_file)
        time_uncached = timeit.default_timer() - start

        # Time second hash (cache hit)
        start = timeit.default_timer()
        hash2 = CacheKey._hash_file(temp_file)
        time_cached = timeit.default_timer() - start

        assert hash1 == hash2, "Hashes should match"

        # Cached should be significantly faster (at least 10x for even small files)
        speedup = time_uncached / time_cached if time_cached > 0 else float("inf")
        assert speedup > 10, f"Cache should provide >10x speedup, got {speedup:.1f}x"

    def test_hash_cache_with_cache_key_from_file(self, temp_file: Path):
        """Test that CacheKey.from_file() benefits from hash cache."""
        # Create cache keys multiple times
        key1 = CacheKey.from_file(temp_file, "test_provider", {"setting": "value"})
        key2 = CacheKey.from_file(temp_file, "test_provider", {"setting": "value"})
        key3 = CacheKey.from_file(temp_file, "other_provider", {"setting": "value"})

        # All should use the same cached file hash
        assert key1.file_hash == key2.file_hash == key3.file_hash, "File hash should be reused"

        # Hash cache should have exactly one entry for this file
        import os

        stat = os.stat(temp_file)
        cache_key = (str(temp_file), stat.st_mtime, stat.st_size)
        assert cache_key in CacheKey._file_hash_cache, "Hash should be cached"

    def test_hash_consistency_after_cache_clear(self, temp_file: Path):
        """Test that hash remains consistent after clearing and recomputing."""
        # Get hash
        hash1 = CacheKey._hash_file(temp_file)

        # Clear cache
        CacheKey.clear_hash_cache(temp_file)

        # Get hash again (should recompute)
        hash2 = CacheKey._hash_file(temp_file)

        assert hash1 == hash2, "Hash should be consistent even after cache clear"

    def test_multiple_files_different_cache_keys(self):
        """Test that different files have different cache keys."""
        # Create two different temp files
        with tempfile.NamedTemporaryFile(mode="wb", delete=False) as f1:
            f1.write(b"Content 1")
            file1 = Path(f1.name)

        with tempfile.NamedTemporaryFile(mode="wb", delete=False) as f2:
            f2.write(b"Content 2")
            file2 = Path(f2.name)

        try:
            # Hash both files
            hash1 = CacheKey._hash_file(file1)
            hash2 = CacheKey._hash_file(file2)

            # Hashes should be different
            assert hash1 != hash2, "Different files should have different hashes"

            # Cache should have two entries
            assert len(CacheKey._file_hash_cache) == 2, "Cache should have entries for both files"

        finally:
            file1.unlink(missing_ok=True)
            file2.unlink(missing_ok=True)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
