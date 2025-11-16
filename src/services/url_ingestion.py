from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from yt_dlp import YoutubeDL

from src.services.audio_extraction import AudioExtractor, AudioQuality
from src.utils.paths import ensure_subpath

logger = logging.getLogger(__name__)
logger = logging.getLogger(__name__)


@dataclass
class UrlIngestionResult:
    audio_path: Path
    source_video_path: Path | None


class UrlIngestionError(Exception):
    """Raised when URL ingestion fails."""


class UrlIngestionService:
    """Service responsible for downloading a single video URL and returning an audio file.

    This uses yt-dlp under the hood and falls back to AudioExtractor when the
    downloaded file is video-only.
    """

    def __init__(
        self,
        download_dir: Path,
        *,
        prefer_audio_only: bool = True,
        keep_video: bool = False,
    ) -> None:
        self._download_dir = download_dir
        self._prefer_audio_only = prefer_audio_only
        self._keep_video = keep_video
        self._extractor = AudioExtractor()

    def ingest(
        self, url: str, *, quality: AudioQuality = AudioQuality.SPEECH
    ) -> UrlIngestionResult:
        """Download `url` and return a local audio path.

        Raises UrlIngestionError on failure.
        """
        if "playlist" in url:
            raise UrlIngestionError(
                "Playlist URLs are not supported; please provide a single video URL."
            )

        safe_dir = ensure_subpath(self._download_dir.parent, self._download_dir)
        safe_dir.mkdir(parents=True, exist_ok=True)

        ydl_opts = {
            "outtmpl": str(safe_dir / "%(id)s_%(title)s.%(ext)s"),
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
        }

        if self._prefer_audio_only:
            ydl_opts["format"] = "bestaudio/best"
        else:
            ydl_opts["format"] = "bestvideo+bestaudio/best"

        downloaded_path: Path | None = None

        def _hook(d: dict) -> None:  # pragma: no cover - thin progress hook
            if d.get("status") == "finished":
                filename = d.get("filename")
                if filename:
                    nonlocal downloaded_path
                    downloaded_path = Path(filename)

        ydl_opts["progress_hooks"] = [_hook]

        try:
            with YoutubeDL(ydl_opts) as ydl:
                result = ydl.extract_info(url, download=True)
        except Exception as exc:
            logger.exception("URL ingestion failed for %s", url)
            raise UrlIngestionError(f"Failed to download URL: {url}") from exc

        if not downloaded_path:
            # Fallback: try to infer from result
            filename = result.get("_filename") if isinstance(result, dict) else None
            if filename:
                downloaded_path = Path(filename)

        if not downloaded_path or not downloaded_path.exists():
            raise UrlIngestionError("yt-dlp did not produce a downloadable file.")

        ext = downloaded_path.suffix.lower()
        audio_exts = {".mp3", ".m4a", ".aac", ".flac", ".wav", ".ogg", ".opus"}

        if ext in audio_exts:
            return UrlIngestionResult(audio_path=downloaded_path, source_video_path=None)

        # Video file: extract audio using existing extractor
        try:
            audio_path = self._extractor.extract_audio(
                input_path=downloaded_path,
                output_path=None,
                quality=quality,
            )
        except Exception as exc:
            logger.exception("Audio extraction from downloaded video failed: %s", downloaded_path)
            raise UrlIngestionError("Failed to extract audio from downloaded video.") from exc

        if audio_path is None:
            raise UrlIngestionError("Audio extraction returned no path.")

        source_video_path: Path | None = downloaded_path if self._keep_video else None
        if not self._keep_video:
            try:
                downloaded_path.unlink(missing_ok=True)
            except OSError:
                logger.warning("Failed to remove downloaded video: %s", downloaded_path)

        return UrlIngestionResult(audio_path=Path(audio_path), source_video_path=source_video_path)
