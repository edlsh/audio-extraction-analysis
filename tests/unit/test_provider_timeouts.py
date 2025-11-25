import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.providers.base import BaseTranscriptionProvider

pytestmark = [pytest.mark.unit, pytest.mark.fast, pytest.mark.mock]


class _SlowProvider(BaseTranscriptionProvider):
    async def _transcribe_impl(self, audio_file_path: Path, language: str = "en"):
        await asyncio.sleep(0.2)
        return None

    def validate_configuration(self) -> bool:
        return True

    def get_provider_name(self) -> str:
        return "slow"

    def get_supported_features(self) -> list[str]:
        return []

    async def health_check_async(self) -> dict:
        return {"healthy": True}


class _ImmediateProvider(BaseTranscriptionProvider):
    async def _transcribe_impl(self, audio_file_path: Path, language: str = "en"):
        return MagicMock()

    def validate_configuration(self) -> bool:
        return True

    def get_provider_name(self) -> str:
        return "immediate"

    def get_supported_features(self) -> list[str]:
        return ["basic_transcription"]

    async def health_check_async(self) -> dict:
        return {"healthy": True}


@pytest.mark.asyncio
async def test_transcribe_async_enforces_timeout() -> None:
    provider = _SlowProvider()
    provider.update_transcription_timeout(0.01)

    with pytest.raises(asyncio.TimeoutError):
        await provider.transcribe_async(Path("dummy"), timeout=0.01)


def test_transcribe_uses_shared_executor_in_running_loop(monkeypatch) -> None:
    provider = _ImmediateProvider()
    monkeypatch.setattr("src.providers.base.asyncio.get_running_loop", object)

    with patch.object(
        BaseTranscriptionProvider._SYNC_EXECUTOR,
        "submit",
        wraps=BaseTranscriptionProvider._SYNC_EXECUTOR.submit,
    ) as mock_submit:
        result = provider.transcribe(Path("dummy"))

    mock_submit.assert_called_once()
    assert result is not None


def test_transcribe_defers_coroutine_creation(monkeypatch) -> None:
    provider = _ImmediateProvider()

    # Simulate being inside an active event loop
    monkeypatch.setattr("src.providers.base.asyncio.get_running_loop", object)

    call_order: list[str] = []

    def fake_asyncio_run(coro):
        call_order.append("run")
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    monkeypatch.setattr("src.providers.base.asyncio.run", fake_asyncio_run)

    class DummyExecutor:
        def submit(self, fn):
            call_order.append("submit")

            class DummyFuture:
                def result(self, timeout=None):
                    call_order.append("result")
                    return fn()

            return DummyFuture()

    monkeypatch.setattr(BaseTranscriptionProvider, "_SYNC_EXECUTOR", DummyExecutor())

    result = provider.transcribe(Path("dummy"))

    assert result is not None
    assert call_order == ["submit", "result", "run"]
