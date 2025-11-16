from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.services.audio_extraction import AudioQuality
from src.services.url_ingestion import UrlIngestionError, UrlIngestionResult, UrlIngestionService
from tests.conftest_helpers import skip_without_ffmpeg

# Apply markers to all tests in this module
# These tests use URL ingestion which may trigger FFmpeg for conversion
pytestmark = [
    pytest.mark.unit,
    pytest.mark.ffmpeg,
    skip_without_ffmpeg(),
]


@pytest.fixture()
def download_dir(tmp_path: Path) -> Path:
    return tmp_path / "downloads"


def test_ingest_rejects_playlist(download_dir: Path) -> None:
    service = UrlIngestionService(download_dir)

    with pytest.raises(UrlIngestionError):
        service.ingest("https://www.youtube.com/playlist?list=123")


@patch("src.services.url_ingestion.YoutubeDL")
def test_ingest_returns_audio_when_bestaudio(mock_ydl: MagicMock, download_dir: Path) -> None:
    service = UrlIngestionService(download_dir, prefer_audio_only=True)

    audio_file = download_dir / "abc_title.m4a"

    # Ensure directory exists for our fake file
    audio_file.parent.mkdir(parents=True, exist_ok=True)
    audio_file.write_bytes(b"fake audio")

    instance = mock_ydl.return_value.__enter__.return_value
    instance.extract_info.return_value = {"id": "abc", "_filename": str(audio_file)}

    result = service.ingest("https://example.com/video")

    assert isinstance(result, UrlIngestionResult)
    assert result.audio_path == audio_file
    assert result.source_video_path is None


@patch("src.services.url_ingestion.YoutubeDL")
@patch("src.services.url_ingestion.AudioExtractor")
def test_ingest_extracts_audio_from_video(
    mock_extractor_cls: MagicMock,
    mock_ydl: MagicMock,
    download_dir: Path,
) -> None:
    service = UrlIngestionService(download_dir, prefer_audio_only=False, keep_video=False)

    video_file = download_dir / "abc_title.mp4"
    video_file.parent.mkdir(parents=True, exist_ok=True)
    video_file.write_bytes(b"fake video")

    instance = mock_ydl.return_value.__enter__.return_value
    instance.extract_info.return_value = {"id": "abc", "_filename": str(video_file)}

    extractor_instance = mock_extractor_cls.return_value
    extractor_instance.extract_audio.return_value = str(download_dir / "abc_title.mp3")

    result = service.ingest("https://example.com/video")

    assert isinstance(result, UrlIngestionResult)
    assert result.audio_path.suffix == ".mp3"
    # keep_video=False should delete video_file or at least not report it
    assert result.source_video_path is None


@patch("src.services.url_ingestion.YoutubeDL")
def test_ingest_raises_when_no_file_produced(mock_ydl: MagicMock, download_dir: Path) -> None:
    service = UrlIngestionService(download_dir)

    instance = mock_ydl.return_value.__enter__.return_value
    instance.extract_info.return_value = {}

    with pytest.raises(UrlIngestionError):
        service.ingest("https://example.com/video")
