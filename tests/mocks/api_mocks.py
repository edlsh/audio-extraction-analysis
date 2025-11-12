"""API mocking framework for testing without real API keys.

This module provides mock responses for external API providers:
- Deepgram transcription API
- ElevenLabs transcription API
- Standardized mock response patterns
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# Mock API responses based on real API documentation

DEEPGRAM_SUCCESS_RESPONSE = {
    "metadata": {
        "transaction_key": "test-transaction-123",
        "request_id": "test-request-456",
        "sha256": "test-sha256-hash",
        "created": "2025-01-27T00:00:00.000Z",
        "duration": 5.0,
        "channels": 1,
    },
    "results": {
        "channels": [
            {
                "alternatives": [
                    {
                        "transcript": "This is a test transcription from Deepgram.",
                        "confidence": 0.95,
                        "words": [
                            {"word": "This", "start": 0.0, "end": 0.2, "confidence": 0.98},
                            {"word": "is", "start": 0.2, "end": 0.3, "confidence": 0.97},
                            {"word": "a", "start": 0.3, "end": 0.4, "confidence": 0.96},
                            {"word": "test", "start": 0.4, "end": 0.7, "confidence": 0.95},
                            {"word": "transcription", "start": 0.7, "end": 1.5, "confidence": 0.94},
                            {"word": "from", "start": 1.5, "end": 1.7, "confidence": 0.93},
                            {"word": "Deepgram", "start": 1.7, "end": 2.2, "confidence": 0.92},
                        ],
                    }
                ]
            }
        ]
    },
}

DEEPGRAM_ERROR_401 = {
    "err_code": "INVALID_CREDENTIALS",
    "err_msg": "Invalid API credentials",
    "request_id": "test-request-error-401",
}

DEEPGRAM_ERROR_TIMEOUT = {
    "err_code": "TIMEOUT",
    "err_msg": "Request timed out",
    "request_id": "test-request-timeout",
}

ELEVENLABS_SUCCESS_RESPONSE = {
    "text": "This is a test transcription from ElevenLabs.",
    "confidence": 0.94,
    "language": "en",
    "duration_seconds": 5.0,
    "request_id": "test-elevenlabs-123",
}

ELEVENLABS_ERROR_500 = {
    "error": {"message": "Internal server error", "type": "server_error", "code": 500}
}


class MockAPIResponse:
    """Mock HTTP response object."""

    def __init__(self, json_data: dict[str, Any], status_code: int = 200):
        self.json_data = json_data
        self.status_code = status_code
        self.text = json.dumps(json_data)
        self.headers = {"Content-Type": "application/json"}

    def json(self) -> dict[str, Any]:
        """Return JSON data."""
        return self.json_data

    def raise_for_status(self):
        """Raise exception for error status codes."""
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}: {self.text}")


def get_mock_response(provider: str, scenario: str) -> MockAPIResponse:
    """Get mock API response for specified provider and scenario.

    Args:
        provider: Provider name ('deepgram' or 'elevenlabs')
        scenario: Response scenario ('success', 'error_401', 'error_500', etc.)

    Returns:
        MockAPIResponse object

    Raises:
        ValueError: If provider or scenario is unknown
    """
    if provider.lower() == "deepgram":
        if scenario == "success":
            return MockAPIResponse(DEEPGRAM_SUCCESS_RESPONSE, 200)
        elif scenario == "error_401":
            return MockAPIResponse(DEEPGRAM_ERROR_401, 401)
        elif scenario == "error_timeout":
            return MockAPIResponse(DEEPGRAM_ERROR_TIMEOUT, 408)
        else:
            raise ValueError(f"Unknown Deepgram scenario: {scenario}")

    elif provider.lower() == "elevenlabs":
        if scenario == "success":
            return MockAPIResponse(ELEVENLABS_SUCCESS_RESPONSE, 200)
        elif scenario == "error_500":
            return MockAPIResponse(ELEVENLABS_ERROR_500, 500)
        else:
            raise ValueError(f"Unknown ElevenLabs scenario: {scenario}")

    else:
        raise ValueError(f"Unknown provider: {provider}")


def load_mock_response_from_file(filepath: Path) -> dict[str, Any]:
    """Load mock response from JSON file.

    Args:
        filepath: Path to JSON file containing mock response

    Returns:
        Parsed JSON data
    """
    with filepath.open() as f:
        return json.load(f)


def save_mock_response_to_file(data: dict[str, Any], filepath: Path):
    """Save mock response to JSON file.

    Args:
        data: Response data to save
        filepath: Path where to save the file
    """
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with filepath.open("w") as f:
        json.dump(data, f, indent=2)
