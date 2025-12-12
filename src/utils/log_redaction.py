"""Log redaction utilities for filtering sensitive data from log output.

This module provides filters and utilities to prevent accidental logging
of secrets like API keys, passwords, and other sensitive data.

Also provides URL sanitization to prevent leaking tokens/signatures in URLs.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

if TYPE_CHECKING:
    from collections.abc import Mapping

# Known secret environment variable patterns (case-insensitive matching on key names)
SECRET_ENV_PATTERNS = [
    r".*_API_KEY$",
    r".*_SECRET$",
    r".*_TOKEN$",
    r".*_PASSWORD$",
    r".*_CREDENTIALS?$",
    r"^API_KEY$",
    r"^SECRET$",
    r"^PASSWORD$",
    r"^TOKEN$",
    r"^DEEPGRAM_.*",
    r"^ELEVENLABS_.*",
    r"^GEMINI_.*",
    r"^OPENAI_.*",
    r"^ANTHROPIC_.*",
    r"^AWS_SECRET.*",
    r"^GITHUB_TOKEN$",
]

# Compiled patterns for efficiency
_SECRET_KEY_PATTERNS = [re.compile(p, re.IGNORECASE) for p in SECRET_ENV_PATTERNS]

# Value patterns that look like secrets (for redacting values in logs)
SECRET_VALUE_PATTERNS = [
    # API keys with known prefixes
    r"\b(sk-[a-zA-Z0-9]{20,})\b",  # OpenAI-style keys
    r"\b(dg-[a-zA-Z0-9]{20,})\b",  # Deepgram-style keys
    r"\b(el-[a-zA-Z0-9]{20,})\b",  # ElevenLabs-style keys
    # Generic long alphanumeric strings (potential keys)
    r"\b([a-zA-Z0-9]{32,})\b",
    # Bearer tokens
    r"(Bearer\s+[a-zA-Z0-9._-]+)",
    # Basic auth
    r"(Basic\s+[a-zA-Z0-9+/=]+)",
]

_SECRET_VALUE_PATTERNS = [re.compile(p) for p in SECRET_VALUE_PATTERNS]

# URL query parameter names that typically contain sensitive data
SENSITIVE_URL_PARAMS = {
    "token",
    "key",
    "api_key",
    "apikey",
    "api-key",
    "access_token",
    "accesstoken",
    "auth",
    "auth_token",
    "authorization",
    "sig",
    "signature",
    "secret",
    "password",
    "pwd",
    "credentials",
    "bearer",
    "jwt",
    "session",
    "session_id",
    "sessionid",
    "x-api-key",
    "x-auth-token",
}

REDACTED = "[REDACTED]"


def is_secret_key(key: str) -> bool:
    """Check if a key name matches known secret patterns.

    Args:
        key: Environment variable or config key name

    Returns:
        True if the key matches a secret pattern
    """
    return any(pattern.match(key) for pattern in _SECRET_KEY_PATTERNS)


def redact_secrets_from_dict(data: Mapping[str, Any], *, copy: bool = True) -> dict[str, Any]:
    """Redact secret values from a dictionary.

    Args:
        data: Dictionary that may contain secrets
        copy: If True, return a new dict; if False, mutate in place

    Returns:
        Dictionary with secret values replaced by [REDACTED]
    """
    result: dict[str, Any] = dict(data) if copy else dict(data)
    for key in list(result.keys()):
        if is_secret_key(key):
            result[key] = REDACTED
        elif isinstance(result[key], dict):
            result[key] = redact_secrets_from_dict(result[key], copy=copy)
    return result


def redact_secrets_from_string(text: str) -> str:
    """Redact potential secrets from a string.

    Scans for patterns that look like API keys, tokens, and other secrets.

    Args:
        text: String that may contain secrets

    Returns:
        String with potential secrets replaced by [REDACTED]
    """
    result = text
    for pattern in _SECRET_VALUE_PATTERNS:
        result = pattern.sub(REDACTED, result)
    return result


def sanitize_url(url: str, *, redact_query: bool = True, remove_fragment: bool = True) -> str:
    """Sanitize a URL by redacting sensitive query parameters and fragments.

    This function keeps the scheme, host, and path intact for debugging purposes,
    but redacts potentially sensitive query parameter values and removes fragments.

    Args:
        url: The URL to sanitize
        redact_query: If True, redact values of sensitive query params (default: True)
        remove_fragment: If True, remove the fragment/anchor (default: True)

    Returns:
        Sanitized URL safe for logging

    Example:
        >>> sanitize_url("https://api.example.com/v1/data?token=secret123&page=1")
        "https://api.example.com/v1/data?token=[REDACTED]&page=1"
    """
    if not url:
        return url

    try:
        parsed = urlparse(url)
    except Exception:
        # If URL parsing fails, return a minimal safe representation
        return "[INVALID_URL]"

    # Handle fragment
    fragment = "" if remove_fragment else parsed.fragment

    # Handle query parameters
    new_query = parsed.query
    if redact_query and parsed.query:
        try:
            # Parse query parameters
            params = parse_qs(parsed.query, keep_blank_values=True)
            redacted_params: dict[str, list[str]] = {}

            for key, values in params.items():
                # Check if this key is sensitive (case-insensitive)
                if key.lower() in SENSITIVE_URL_PARAMS:
                    redacted_params[key] = [REDACTED for _ in values]
                else:
                    redacted_params[key] = values

            # Rebuild query string
            # urlencode with doseq=True handles list values
            new_query = urlencode(redacted_params, doseq=True)
        except Exception:
            # If query parsing fails, redact the entire query
            new_query = REDACTED

    # Reconstruct the URL
    sanitized = urlunparse(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,  # URL params (rarely used, between path and query)
            new_query,
            fragment,
        )
    )

    return sanitized


def sanitize_url_for_display(url: str) -> str:
    """Create a minimal URL representation for user-facing display.

    This is more aggressive than sanitize_url - it removes the query string
    entirely and just shows scheme://host/path for cleaner output.

    Args:
        url: The URL to sanitize

    Returns:
        Minimal URL representation (scheme://host/path only)

    Example:
        >>> sanitize_url_for_display("https://api.example.com/v1/data?token=secret")
        "https://api.example.com/v1/data"
    """
    if not url:
        return url

    try:
        parsed = urlparse(url)
        # Return just scheme://host/path
        return urlunparse(
            (
                parsed.scheme,
                parsed.netloc,
                parsed.path,
                "",  # no params
                "",  # no query
                "",  # no fragment
            )
        )
    except Exception:
        return "[INVALID_URL]"


class LogRedactionFilter:
    """Loguru filter that redacts secrets from log messages and context.

    Usage with loguru:
        >>> from loguru import logger
        >>> from src.utils.log_redaction import LogRedactionFilter
        >>> logger.add(sys.stderr, filter=LogRedactionFilter())
    """

    def __call__(self, record: dict[str, Any]) -> bool:
        """Filter log record, redacting any secrets.

        Args:
            record: Loguru log record

        Returns:
            True (always passes through, but with redacted content)
        """
        # Redact the message
        if isinstance(record.get("message"), str):
            record["message"] = redact_secrets_from_string(record["message"])

        # Redact extra context
        if "extra" in record and isinstance(record["extra"], dict):
            record["extra"] = redact_secrets_from_dict(record["extra"], copy=False)

        return True


def create_safe_env_repr(env: Mapping[str, str] | None = None) -> dict[str, str]:
    """Create a safe representation of environment variables for logging.

    Args:
        env: Environment dict (defaults to os.environ)

    Returns:
        Dict with secret values redacted
    """
    import os

    if env is None:
        env = os.environ

    return redact_secrets_from_dict(dict(env))


__all__ = [
    "REDACTED",
    "SECRET_ENV_PATTERNS",
    "SENSITIVE_URL_PARAMS",
    "LogRedactionFilter",
    "create_safe_env_repr",
    "is_secret_key",
    "redact_secrets_from_dict",
    "redact_secrets_from_string",
    "sanitize_url",
    "sanitize_url_for_display",
]
