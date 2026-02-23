"""Unit tests for OpenTUI JSON-RPC backend."""

from __future__ import annotations

import pytest

from src.models.events import Event


@pytest.mark.unit
@pytest.mark.fast
def test_normalize_event_maps_url_stage_and_artifact_type() -> None:
    """URL stages and artifact payload keys should be normalized for frontend types."""
    from src.ui.opentui_backend import normalize_event_for_frontend

    event = Event(
        type="artifact",
        run_id="run-123",
        stage="url_download",
        data={"type": "audio", "path": "/tmp/example.mp3"},
    )

    normalized = normalize_event_for_frontend(event)

    assert normalized["stage"] == "download"
    assert isinstance(normalized["data"], dict)
    data = normalized["data"]
    assert data["kind"] == "audio"
    assert data["path"] == "/tmp/example.mp3"


@pytest.mark.unit
@pytest.mark.fast
@pytest.mark.asyncio
async def test_backend_handles_system_ping(tmp_path) -> None:
    """Backend should respond to system.ping via JSON-RPC."""
    from src.ui.opentui_backend import OpenTuiBackend

    backend = OpenTuiBackend(project_root=tmp_path)

    response = await backend.handle_request(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "system.ping",
            "params": {},
        }
    )

    assert response["jsonrpc"] == "2.0"
    assert response["id"] == 1
    assert response["result"] == {"pong": True}


@pytest.mark.unit
@pytest.mark.fast
@pytest.mark.asyncio
async def test_backend_providers_health_excludes_removed_provider(tmp_path) -> None:
    """Provider health should not expose removed providers like Parakeet."""
    from src.ui.opentui_backend import OpenTuiBackend

    backend = OpenTuiBackend(project_root=tmp_path)

    response = await backend.handle_request(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "providers.health",
            "params": {},
        }
    )

    providers = response["result"]["providers"]
    provider_names = {provider["name"] for provider in providers}

    assert {"deepgram", "elevenlabs", "whisper"}.issubset(provider_names)
    assert "parakeet" not in provider_names


@pytest.mark.unit
@pytest.mark.fast
@pytest.mark.asyncio
async def test_settings_get_redacts_api_keys(tmp_path, monkeypatch) -> None:
    """settings.get should never return raw API key material."""
    from src.ui.opentui_backend import OpenTuiBackend

    monkeypatch.setenv("GEMINI_API_KEY", "secret-value")

    backend = OpenTuiBackend(project_root=tmp_path)
    response = await backend.handle_request(
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "settings.get",
            "params": {},
        }
    )

    api_keys = response["result"]["settings"]["api_keys"]
    assert api_keys["gemini"] == "__configured__"
