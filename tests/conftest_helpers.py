"""
Test configuration helpers for conditional test execution.

Provides utilities for skipping tests based on available dependencies,
environment variables, and system requirements.
"""

from __future__ import annotations

import os
import shutil
from functools import lru_cache
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from typing import Callable


# ============================================================================
# Dependency Detection
# ============================================================================


@lru_cache(maxsize=None)
def has_ffmpeg() -> bool:
    """Check if FFmpeg is installed and available."""
    return shutil.which("ffmpeg") is not None


@lru_cache(maxsize=None)
def has_parakeet() -> bool:
    """Check if Parakeet/NeMo dependencies are available."""
    try:
        import nemo.collections.asr as nemo_asr  # noqa: F401

        return True
    except ImportError:
        return False


@lru_cache(maxsize=None)
def has_whisper() -> bool:
    """Check if Whisper dependencies are available."""
    try:
        import whisper  # noqa: F401

        return True
    except ImportError:
        return False


@lru_cache(maxsize=None)
def has_redis() -> bool:
    """Check if Redis is available and connectable."""
    try:
        import redis

        client = redis.Redis(host="localhost", port=6379, socket_connect_timeout=1)
        client.ping()
        return True
    except (ImportError, Exception):
        return False


@lru_cache(maxsize=None)
def has_network() -> bool:
    """Check if network connectivity is available."""
    import socket

    try:
        # Try to connect to a reliable host
        socket.create_connection(("8.8.8.8", 53), timeout=2)
        return True
    except OSError:
        return False


@lru_cache(maxsize=None)
def has_api_key(provider: str) -> bool:
    """Check if API key is available for a provider."""
    key_map = {
        "deepgram": "DEEPGRAM_API_KEY",
        "elevenlabs": "ELEVENLABS_API_KEY",
    }
    env_var = key_map.get(provider.lower())
    if not env_var:
        return False

    key = os.environ.get(env_var, "")
    # Check if it's not a dummy/test key
    return bool(key) and key not in ("dummy_test_key", "test", "mock")


# ============================================================================
# Skip Decorators
# ============================================================================


def skip_without_ffmpeg() -> Callable:
    """Skip test if FFmpeg is not installed."""
    return pytest.mark.skipif(
        not has_ffmpeg(), reason="FFmpeg not installed (required for this test)"
    )


def skip_without_parakeet() -> Callable:
    """Skip test if Parakeet dependencies are not available."""
    return pytest.mark.skipif(
        not has_parakeet(),
        reason="Parakeet/NeMo not installed (optional dependency)",
    )


def skip_without_whisper() -> Callable:
    """Skip test if Whisper dependencies are not available."""
    return pytest.mark.skipif(
        not has_whisper(), reason="Whisper not installed (optional dependency)"
    )


def skip_without_redis() -> Callable:
    """Skip test if Redis is not available."""
    return pytest.mark.skipif(
        not has_redis(), reason="Redis not available (required for this test)"
    )


def skip_without_network() -> Callable:
    """Skip test if network is not available."""
    return pytest.mark.skipif(
        not has_network(), reason="Network not available (required for this test)"
    )


def skip_without_api_key(provider: str) -> Callable:
    """Skip test if API key is not available for provider."""
    return pytest.mark.skipif(
        not has_api_key(provider),
        reason=f"{provider} API key not available (set in environment)",
    )


# ============================================================================
# Environment Checks
# ============================================================================


def is_ci() -> bool:
    """Check if running in CI environment."""
    return os.environ.get("CI", "").lower() in ("true", "1", "yes")


def is_mock_mode() -> bool:
    """Check if running in mock/test mode."""
    return os.environ.get("AUDIO_TEST_MODE", "").lower() in ("true", "1", "yes")


def skip_in_ci() -> Callable:
    """Skip test if running in CI environment."""
    return pytest.mark.skipif(is_ci(), reason="Skipped in CI (resource intensive)")


# ============================================================================
# Fixtures for Conditional Dependencies
# ============================================================================


@pytest.fixture
def require_ffmpeg() -> None:
    """Fixture that requires FFmpeg to be installed."""
    if not has_ffmpeg():
        pytest.skip("FFmpeg not installed")


@pytest.fixture
def require_parakeet() -> None:
    """Fixture that requires Parakeet dependencies."""
    if not has_parakeet():
        pytest.skip("Parakeet/NeMo not installed")


@pytest.fixture
def require_network() -> None:
    """Fixture that requires network connectivity."""
    if not has_network():
        pytest.skip("Network not available")


@pytest.fixture
def require_deepgram_key() -> str:
    """Fixture that requires Deepgram API key."""
    if not has_api_key("deepgram"):
        pytest.skip("Deepgram API key not available")
    return os.environ["DEEPGRAM_API_KEY"]


@pytest.fixture
def require_elevenlabs_key() -> str:
    """Fixture that requires ElevenLabs API key."""
    if not has_api_key("elevenlabs"):
        pytest.skip("ElevenLabs API key not available")
    return os.environ["ELEVENLABS_API_KEY"]
