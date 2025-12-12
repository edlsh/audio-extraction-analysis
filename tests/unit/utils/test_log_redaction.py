"""Tests for log redaction utilities."""

from __future__ import annotations

import pytest

from src.utils.log_redaction import (
    REDACTED,
    LogRedactionFilter,
    create_safe_env_repr,
    is_secret_key,
    redact_secrets_from_dict,
    redact_secrets_from_string,
)


class TestIsSecretKey:
    """Test secret key pattern matching."""

    @pytest.mark.parametrize(
        "key",
        [
            "API_KEY",
            "DEEPGRAM_API_KEY",
            "ELEVENLABS_API_KEY",
            "GEMINI_API_KEY",
            "OPENAI_API_KEY",
            "MY_SECRET",
            "AUTH_TOKEN",
            "DB_PASSWORD",
            "AWS_SECRET_ACCESS_KEY",
            "GITHUB_TOKEN",
        ],
    )
    def test_recognizes_secret_keys(self, key: str) -> None:
        """Known secret key patterns should be recognized."""
        assert is_secret_key(key), f"{key} should be recognized as secret"

    @pytest.mark.parametrize(
        "key",
        [
            "HOME",
            "PATH",
            "USER",
            "SHELL",
            "AUDIO_QUALITY",
            "LOG_LEVEL",
            "DEBUG",
            "OUTPUT_DIR",
        ],
    )
    def test_ignores_non_secret_keys(self, key: str) -> None:
        """Non-secret environment variables should not match."""
        assert not is_secret_key(key), f"{key} should not be recognized as secret"


class TestRedactSecretsFromDict:
    """Test dictionary redaction."""

    def test_redacts_api_key(self) -> None:
        """API keys should be redacted."""
        data = {"DEEPGRAM_API_KEY": "secret123", "DEBUG": "true"}
        result = redact_secrets_from_dict(data)
        assert result["DEEPGRAM_API_KEY"] == REDACTED
        assert result["DEBUG"] == "true"

    def test_redacts_nested_secrets(self) -> None:
        """Nested dictionaries should have secrets redacted."""
        data = {
            "config": {
                "API_KEY": "secret",
                "timeout": 30,
            }
        }
        result = redact_secrets_from_dict(data)
        assert result["config"]["API_KEY"] == REDACTED
        assert result["config"]["timeout"] == 30

    def test_preserves_original_when_copy_true(self) -> None:
        """Original dict should be unchanged when copy=True."""
        data = {"API_KEY": "secret"}
        result = redact_secrets_from_dict(data, copy=True)
        assert data["API_KEY"] == "secret"
        assert result["API_KEY"] == REDACTED


class TestRedactSecretsFromString:
    """Test string redaction."""

    def test_redacts_openai_style_key(self) -> None:
        """OpenAI-style sk-xxx keys should be redacted."""
        text = "Using key sk-abcdef1234567890abcdef1234567890"
        result = redact_secrets_from_string(text)
        assert "sk-" not in result
        assert REDACTED in result

    def test_redacts_long_alphanumeric(self) -> None:
        """Long alphanumeric strings (potential keys) should be redacted."""
        text = "Key: abcdef1234567890abcdef1234567890ab"
        result = redact_secrets_from_string(text)
        assert "abcdef" not in result

    def test_redacts_bearer_token(self) -> None:
        """Bearer tokens should be redacted."""
        text = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
        result = redact_secrets_from_string(text)
        assert "eyJ" not in result

    def test_preserves_short_strings(self) -> None:
        """Short strings should not be redacted."""
        text = "Processing file audio.mp3 with quality=high"
        result = redact_secrets_from_string(text)
        assert result == text


class TestLogRedactionFilter:
    """Test the loguru filter."""

    def test_redacts_message(self) -> None:
        """Filter should redact secrets from message."""
        record = {
            "message": "Using API key sk-test1234567890abcdef1234567890",
            "extra": {},
        }
        filter_fn = LogRedactionFilter()
        result = filter_fn(record)
        assert result is True
        assert "sk-test" not in record["message"]

    def test_redacts_extra_context(self) -> None:
        """Filter should redact secrets from extra context."""
        record = {
            "message": "Config loaded",
            "extra": {"API_KEY": "secret123"},
        }
        filter_fn = LogRedactionFilter()
        filter_fn(record)
        assert record["extra"]["API_KEY"] == REDACTED


class TestCreateSafeEnvRepr:
    """Test safe environment representation."""

    def test_redacts_env_secrets(self) -> None:
        """Secrets in environment should be redacted."""
        env = {
            "PATH": "/usr/bin",
            "DEEPGRAM_API_KEY": "secret123",
            "HOME": "/home/user",
        }
        result = create_safe_env_repr(env)
        assert result["PATH"] == "/usr/bin"
        assert result["HOME"] == "/home/user"
        assert result["DEEPGRAM_API_KEY"] == REDACTED


__all__ = [
    "TestCreateSafeEnvRepr",
    "TestIsSecretKey",
    "TestLogRedactionFilter",
    "TestRedactSecretsFromDict",
    "TestRedactSecretsFromString",
]
