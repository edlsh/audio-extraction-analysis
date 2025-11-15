#!/usr/bin/env python3
"""
Security test to verify the RCE vulnerability fix.

This test verifies that the cache system now uses safe JSON serialization
instead of unsafe pickle deserialization.
"""

import json
import tempfile
from datetime import datetime
from pathlib import Path

from src.cache.backends import DiskCache
from src.cache.transcription_cache import CacheEntry, CacheKey
from src.models.transcription import TranscriptionResult


def test_disk_cache_safe_serialization():
    """Test that DiskCache uses safe JSON serialization."""
    # Create a temporary directory for the test cache
    with tempfile.TemporaryDirectory() as temp_dir:
        cache_dir = Path(temp_dir)
        cache = DiskCache(cache_dir=cache_dir)

        # Create a test transcription result
        transcription = TranscriptionResult(
            transcript="Test transcript",
            duration=10.0,
            generated_at=datetime.now(),
            audio_file="test.mp3",
            provider_name="test_provider",
        )

        # Create a cache entry
        cache_key = CacheKey(
            file_hash="test_hash", provider="test_provider", settings_hash="test_settings"
        )

        entry = CacheEntry(key=cache_key, value=transcription, size=1024, ttl=3600)

        # Store in cache
        key_str = str(cache_key)
        success = cache.put(key_str, entry)
        assert success, "Failed to store entry in cache"

        # Retrieve from cache
        retrieved_entry = cache.get(key_str)
        assert retrieved_entry is not None, "Failed to retrieve entry from cache"
        assert isinstance(
            retrieved_entry.value, TranscriptionResult
        ), "Retrieved value is not TranscriptionResult"
        assert retrieved_entry.value.transcript == "Test transcript", "Transcript content mismatch"

        print("✓ DiskCache safe serialization test passed")


def test_no_pickle_imports():
    """Test that pickle is not imported in cache modules."""
    import src.cache.backends as backends_module
    import src.cache.transcription_cache as cache_module

    # Check that pickle is not in the module's globals
    assert "pickle" not in backends_module.__dict__, "pickle is still imported in backends module"
    assert "pickle" not in cache_module.__dict__, "pickle is still imported in cache module"

    print("✓ No pickle imports test passed")


def test_serialization_safety():
    """Test that serialization methods are safe and don't use pickle."""
    # Create test objects
    transcription = TranscriptionResult(
        transcript="Test transcript with special chars: <>\"'&",
        duration=10.5,
        generated_at=datetime.now(),
        audio_file="test file.mp3",
        provider_name="test_provider",
    )

    cache_key = CacheKey(file_hash="abc123", provider="test_provider", settings_hash="def456")

    entry = CacheEntry(key=cache_key, value=transcription, size=2048, ttl=7200)

    # Test round-trip serialization
    entry_dict = entry.to_dict()

    # Verify it's JSON serializable
    json_str = json.dumps(entry_dict)
    loaded_dict = json.loads(json_str)

    # Reconstruct from dict
    reconstructed_entry = CacheEntry.from_dict(loaded_dict)

    # Verify data integrity
    assert reconstructed_entry.key.file_hash == cache_key.file_hash
    assert reconstructed_entry.key.provider == cache_key.provider
    assert reconstructed_entry.key.settings_hash == cache_key.settings_hash
    assert isinstance(reconstructed_entry.value, TranscriptionResult)
    assert reconstructed_entry.value.transcript == transcription.transcript
    assert reconstructed_entry.value.duration == transcription.duration
    assert reconstructed_entry.size == entry.size
    assert reconstructed_entry.ttl == entry.ttl

    print("✓ Serialization safety test passed")


def test_in_memory_cache_safe_serialization():
    """Test that InMemoryCache uses safe JSON serialization."""
    from src.cache.backends import InMemoryCache

    cache = InMemoryCache(max_size_mb=10)

    # Create a test transcription result with complex nested data
    transcription = TranscriptionResult(
        transcript="Test with complex data",
        duration=15.0,
        generated_at=datetime.now(),
        audio_file="complex_test.mp3",
        provider_name="test_provider",
        summary="Test summary",
        metadata={"test_key": "test_value"},
    )

    cache_key = CacheKey(
        file_hash="memory_test_hash", provider="test_provider", settings_hash="memory_settings"
    )

    entry = CacheEntry(key=cache_key, value=transcription, size=2048, ttl=7200)

    key_str = str(cache_key)
    success = cache.put(key_str, entry)
    assert success, "Failed to store entry in InMemoryCache"

    # Retrieve and verify
    retrieved = cache.get(key_str)
    assert retrieved is not None, "Failed to retrieve from InMemoryCache"
    assert isinstance(retrieved.value, TranscriptionResult)
    assert retrieved.value.transcript == "Test with complex data"

    print("✓ InMemoryCache safe serialization test passed")


def test_complex_transcription_serialization():
    """Test serialization of TranscriptionResult with all nested features."""
    from src.models.transcription import (
        TranscriptionChapter,
        TranscriptionSpeaker,
        TranscriptionUtterance,
    )

    # Create complex transcription with all features
    chapters = [
        TranscriptionChapter(
            start_time=0.0, end_time=5.0, topics=["introduction"], confidence_scores=[0.95]
        ),
        TranscriptionChapter(
            start_time=5.0, end_time=10.0, topics=["main topic"], confidence_scores=[0.92]
        ),
    ]

    speakers = [
        TranscriptionSpeaker(id=1, total_time=8.0, percentage=80.0),
        TranscriptionSpeaker(id=2, total_time=2.0, percentage=20.0),
    ]

    utterances = [
        TranscriptionUtterance(speaker=1, start=0.0, end=3.0, text="Hello"),
        TranscriptionUtterance(speaker=2, start=3.0, end=5.0, text="Hi there"),
    ]

    transcription = TranscriptionResult(
        transcript="Full transcript with all features",
        duration=10.0,
        generated_at=datetime.now(),
        audio_file="complex.mp3",
        provider_name="advanced_provider",
        summary="A comprehensive test",
        chapters=chapters,
        speakers=speakers,
        utterances=utterances,
        topics={"technology": 5, "science": 3},
        intents=["informative", "educational"],
        sentiment_distribution={"positive": 70, "neutral": 30},
        metadata={"quality": "high", "language": "en"},
    )

    cache_key = CacheKey(
        file_hash="complex_hash", provider="advanced_provider", settings_hash="complex_settings"
    )

    entry = CacheEntry(
        key=cache_key,
        value=transcription,
        size=4096,
        ttl=3600,
        metadata={"cached_by": "test", "priority": "high"},
    )

    # Test round-trip serialization
    entry_dict = entry.to_dict()

    # Verify JSON serializability
    json_str = json.dumps(entry_dict)
    loaded_dict = json.loads(json_str)

    # Reconstruct
    reconstructed = CacheEntry.from_dict(loaded_dict)

    # Verify all nested data preserved
    assert isinstance(reconstructed.value, TranscriptionResult)
    assert len(reconstructed.value.chapters) == 2
    assert len(reconstructed.value.speakers) == 2
    assert len(reconstructed.value.utterances) == 2
    assert reconstructed.value.topics == {"technology": 5, "science": 3}
    assert reconstructed.value.intents == ["informative", "educational"]
    assert reconstructed.value.sentiment_distribution == {"positive": 70, "neutral": 30}
    assert reconstructed.metadata == {"cached_by": "test", "priority": "high"}

    print("✓ Complex transcription serialization test passed")


def test_corrupted_cache_handling():
    """Test that corrupted cache data is handled safely without code execution."""
    with tempfile.TemporaryDirectory() as temp_dir:
        cache_dir = Path(temp_dir)
        cache = DiskCache(cache_dir=cache_dir)

        # Create a valid entry first
        transcription = TranscriptionResult(
            transcript="Valid entry",
            duration=5.0,
            generated_at=datetime.now(),
            audio_file="test.mp3",
            provider_name="test_provider",
        )

        cache_key = CacheKey(
            file_hash="corruption_test", provider="test_provider", settings_hash="test_settings"
        )

        entry = CacheEntry(key=cache_key, value=transcription, size=1024, ttl=3600)

        key_str = str(cache_key)
        cache.put(key_str, entry)

        # Now corrupt the cache data by inserting invalid JSON
        import sqlite3

        conn = sqlite3.connect(str(cache.db_path))
        cursor = conn.cursor()

        # Insert corrupted data that's not valid JSON
        corrupted_data = b"not valid json {malicious code}"
        cursor.execute(
            "UPDATE cache_entries SET value = ? WHERE key = ?", (corrupted_data, key_str)
        )
        conn.commit()
        conn.close()

        # Try to retrieve - should return None and clean up corrupted entry
        retrieved = cache.get(key_str)
        assert retrieved is None, "Corrupted entry should return None"

        # Verify corrupted entry was deleted
        assert not cache.exists(key_str), "Corrupted entry should be deleted"

        print("✓ Corrupted cache handling test passed")


def test_cache_metadata_serialization():
    """Test that cache entry metadata is safely serialized."""
    cache_key = CacheKey(
        file_hash="metadata_test", provider="test_provider", settings_hash="metadata_settings"
    )

    transcription = TranscriptionResult(
        transcript="Test metadata",
        duration=5.0,
        generated_at=datetime.now(),
        audio_file="metadata.mp3",
        provider_name="test_provider",
    )

    # Create entry with complex metadata
    metadata = {
        "source": "api",
        "version": "2.0",
        "tags": ["important", "verified"],
        "nested": {"level1": {"level2": "value"}},
        "numbers": [1, 2, 3, 4, 5],
    }

    entry = CacheEntry(key=cache_key, value=transcription, size=1024, ttl=3600, metadata=metadata)

    # Test serialization
    entry_dict = entry.to_dict()
    json_str = json.dumps(entry_dict)
    loaded_dict = json.loads(json_str)

    # Reconstruct
    reconstructed = CacheEntry.from_dict(loaded_dict)

    # Verify metadata preserved
    assert reconstructed.metadata == metadata
    assert reconstructed.metadata["nested"]["level1"]["level2"] == "value"
    assert reconstructed.metadata["tags"] == ["important", "verified"]

    print("✓ Cache metadata serialization test passed")


def test_no_code_execution_in_deserialization():
    """Test that deserialization does not execute arbitrary code."""
    # This test ensures that even if malicious data is in the cache,
    # it cannot execute code during deserialization

    malicious_payloads = [
        b'{"__import__": "os", "system": "rm -rf /"}',  # Command injection attempt
        b'{"eval": "print(\'hacked\')"}',  # Eval attempt
        b'{"exec": "import os; os.system(\'ls\')"}',  # Exec attempt
    ]

    for payload in malicious_payloads:
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_dir = Path(temp_dir)
            cache = DiskCache(cache_dir=cache_dir)

            # Manually insert malicious payload into database
            import sqlite3

            conn = sqlite3.connect(str(cache.db_path))
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO cache_entries
                (key, value, size, created_at, accessed_at, access_count, ttl, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "malicious_key",
                    payload,
                    len(payload),
                    datetime.now().timestamp(),
                    datetime.now().timestamp(),
                    0,
                    3600,
                    json.dumps({}),
                ),
            )
            conn.commit()
            conn.close()

            # Try to retrieve - should safely fail without executing code
            result = cache.get("malicious_key")

            # Should return None (corrupted data) or fail safely
            assert result is None, "Malicious payload should not deserialize"

    print("✓ No code execution in deserialization test passed")


def test_special_characters_in_cache():
    """Test that special characters in data don't break JSON serialization."""
    special_chars_text = """
    Test with special characters: <>'"&
    Unicode: 你好世界 🎉
    Control chars: \n\r\t
    Quotes: "double" and 'single'
    Backslashes: \\path\\to\\file
    JSON special: {key: "value"}
    """

    transcription = TranscriptionResult(
        transcript=special_chars_text,
        duration=10.0,
        generated_at=datetime.now(),
        audio_file="special_chars_file.mp3",
        provider_name="test_provider",
    )

    cache_key = CacheKey(
        file_hash="special_hash", provider="test_provider", settings_hash="special_settings"
    )

    entry = CacheEntry(key=cache_key, value=transcription, size=2048, ttl=3600)

    # Test serialization with special characters
    entry_dict = entry.to_dict()
    json_str = json.dumps(entry_dict)
    loaded_dict = json.loads(json_str)

    # Reconstruct
    reconstructed = CacheEntry.from_dict(loaded_dict)

    # Verify special characters preserved
    assert reconstructed.value.transcript == special_chars_text

    print("✓ Special characters in cache test passed")


if __name__ == "__main__":
    print("Running security fix verification tests...")
    print("=" * 50)

    try:
        test_no_pickle_imports()
        test_serialization_safety()
        test_disk_cache_safe_serialization()
        test_in_memory_cache_safe_serialization()
        test_complex_transcription_serialization()
        test_corrupted_cache_handling()
        test_cache_metadata_serialization()
        test_no_code_execution_in_deserialization()
        test_special_characters_in_cache()

        print("=" * 50)
        print("🎉 All security fix tests passed!")
        print("✅ RCE vulnerability has been successfully fixed")
        print("✅ Cache system now uses safe JSON serialization")
        print("✅ All edge cases and security scenarios covered")

    except Exception as e:
        print("=" * 50)
        print(f"❌ Test failed: {e}")
        print("⚠ RCE vulnerability fix needs attention")
        raise
