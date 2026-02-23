"""Unit tests for TranscriptionService runtime policy boundaries."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest

from src.exceptions import ProviderNotAvailableError, ProviderSelectionError
from src.models.transcription import TranscriptionResult
from src.services import transcription as transcription_module
from src.services.ffmpeg_core import MediaProbeResult
from src.services.transcription import TranscriptionService


@pytest.fixture
def sample_audio_path(tmp_path: Path) -> Path:
    """Create a tiny placeholder audio path for service-level tests."""
    path = tmp_path / "sample.mp3"
    path.write_bytes(b"ID3")
    return path


class TestTranscriptionServiceRuntimePolicy:
    """Boundary tests for selection context and ffprobe wrapper usage."""

    @pytest.mark.unit
    @pytest.mark.fast
    def test_prepare_transcription_raises_selection_error_by_default(
        self, monkeypatch: pytest.MonkeyPatch, sample_audio_path: Path
    ) -> None:
        """Normal runtime should map missing providers to ProviderSelectionError."""
        service = TranscriptionService()

        monkeypatch.setattr(
            transcription_module,
            "validate_audio_file_or_raise",
            lambda _path: sample_audio_path,
        )
        monkeypatch.setattr(
            service.factory,
            "auto_select_provider",
            Mock(side_effect=ValueError("no configured providers")),
        )

        with pytest.raises(ProviderSelectionError):
            service._prepare_transcription(sample_audio_path)

    @pytest.mark.unit
    @pytest.mark.fast
    def test_prepare_transcription_honors_explicit_test_runtime_flag(
        self, monkeypatch: pytest.MonkeyPatch, sample_audio_path: Path
    ) -> None:
        """Test runtime flag should map missing providers to ProviderNotAvailableError."""
        service = TranscriptionService(is_test_environment=True)

        monkeypatch.setattr(
            transcription_module,
            "validate_audio_file_or_raise",
            lambda _path: sample_audio_path,
        )
        monkeypatch.setattr(
            service.factory,
            "auto_select_provider",
            Mock(side_effect=ValueError("no configured providers")),
        )

        with pytest.raises(ProviderNotAvailableError):
            service._prepare_transcription(sample_audio_path)

    @pytest.mark.unit
    @pytest.mark.fast
    def test_prepare_transcription_uses_explicit_test_override_provider(
        self, monkeypatch: pytest.MonkeyPatch, sample_audio_path: Path
    ) -> None:
        """Selection override should come from constructor context, not ambient env vars."""
        service = TranscriptionService(test_override_provider="whisper")
        auto_select = Mock(return_value="whisper")

        monkeypatch.setattr(
            transcription_module,
            "validate_audio_file_or_raise",
            lambda _path: sample_audio_path,
        )
        monkeypatch.setattr(service.factory, "auto_select_provider", auto_select)
        monkeypatch.setattr(service.factory, "validate_provider_for_file", Mock(return_value=True))

        _, selected_provider = service._prepare_transcription(sample_audio_path)

        assert selected_provider == "whisper"
        auto_select.assert_called_once_with(
            audio_file_path=sample_audio_path,
            test_override="whisper",
            include_test_providers=False,
        )

    @pytest.mark.unit
    @pytest.mark.fast
    def test_prepare_transcription_passes_test_runtime_policy_to_auto_select(
        self, monkeypatch: pytest.MonkeyPatch, sample_audio_path: Path
    ) -> None:
        """Auto-selection should receive explicit runtime policy intent from service context."""
        service = TranscriptionService(
            test_override_provider="test",
            is_test_environment=True,
        )
        auto_select = Mock(return_value="test")

        monkeypatch.setattr(
            transcription_module,
            "validate_audio_file_or_raise",
            lambda _path: sample_audio_path,
        )
        monkeypatch.setattr(service.factory, "auto_select_provider", auto_select)
        monkeypatch.setattr(service.factory, "validate_provider_for_file", Mock(return_value=True))

        _, selected_provider = service._prepare_transcription(sample_audio_path)

        assert selected_provider == "test"
        auto_select.assert_called_once_with(
            audio_file_path=sample_audio_path,
            test_override="test",
            include_test_providers=True,
        )

    @pytest.mark.unit
    @pytest.mark.fast
    def test_create_provider_passes_test_runtime_policy_flag(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Provider creation should propagate explicit runtime policy to factory."""
        service = TranscriptionService(is_test_environment=True)
        create_provider = Mock(return_value=object())
        monkeypatch.setattr(service.factory, "create_provider", create_provider)

        service._create_provider("test")

        create_provider.assert_called_once_with("test", include_test_providers=True)

    @pytest.mark.unit
    @pytest.mark.fast
    def test_get_provider_key_from_name_includes_test_aliases_when_enabled(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Provider key mapping should request test aliases in explicit test runtime."""
        service = TranscriptionService(is_test_environment=True)
        get_available_providers = Mock(return_value=["deepgram", "test"])
        monkeypatch.setattr(service.factory, "get_available_providers", get_available_providers)

        provider_key = service._get_provider_key_from_name("test")

        assert provider_key == "test"
        get_available_providers.assert_called_once_with(include_test_providers=True)

    @pytest.mark.unit
    @pytest.mark.fast
    @pytest.mark.asyncio
    async def test_get_audio_duration_uses_probe_media_async(
        self, monkeypatch: pytest.MonkeyPatch, sample_audio_path: Path
    ) -> None:
        """Duration probing should route through shared ffmpeg_core wrapper."""
        service = TranscriptionService()
        probe_media_async = AsyncMock(
            return_value=MediaProbeResult(duration=12.5, size_bytes=64, size_mb=0.000061)
        )
        monkeypatch.setattr(transcription_module, "probe_media_async", probe_media_async)

        duration = await service._get_audio_duration(str(sample_audio_path))

        assert duration == 12.5
        probe_media_async.assert_awaited_once_with(
            sample_audio_path,
            timeout=transcription_module.Timeouts.FFMPEG_PROBE,
        )

    @pytest.mark.unit
    @pytest.mark.fast
    def test_get_provider_features_passes_test_runtime_policy_flag(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Feature lookup should propagate explicit test runtime policy to factory."""
        service = TranscriptionService(is_test_environment=True)
        provider = Mock()
        provider.get_supported_features.return_value = ["basic"]
        create_provider = Mock(return_value=provider)
        monkeypatch.setattr(service.factory, "create_provider", create_provider)

        features = service.get_provider_features("test")

        assert features == ["basic"]
        create_provider.assert_called_once_with("test", include_test_providers=True)

    @pytest.mark.unit
    @pytest.mark.fast
    def test_save_result_uses_runtime_policy_when_loading_provider(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Provider-specific save path should honor explicit test runtime policy."""
        service = TranscriptionService(is_test_environment=True)
        provider = Mock()
        provider.save_result_to_file = Mock()
        create_provider = Mock(return_value=provider)
        monkeypatch.setattr(service.factory, "create_provider", create_provider)

        result = TranscriptionResult(
            transcript="test transcript",
            duration=1.0,
            generated_at=datetime.utcnow(),
            audio_file="sample.mp3",
            provider_name="test",
        )
        output_path = tmp_path / "out.txt"

        service.save_transcription_result(result, output_path, provider_name="test")

        create_provider.assert_called_once_with("test", include_test_providers=True)
        provider.save_result_to_file.assert_called_once_with(result, output_path)
