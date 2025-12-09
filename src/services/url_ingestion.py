from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import ParseResult, urlparse

from yt_dlp import YoutubeDL

from src.utils.logger import get_logger

from ..exceptions import (
    AudioAnalysisError,
    AudioExtractionError,
    UnsupportedUrlError,
    UrlDownloadError,
    UrlIngestionError,
)
from ..utils.paths import ensure_subpath
from ..utils.sanitization import PathSanitizer
from .audio_extraction import AudioExtractor, AudioQuality

logger = get_logger(__name__)


@dataclass
class UrlIngestionResult:
    audio_path: Path
    source_video_path: Path | None


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
        parsed = urlparse(url)
        self._validate_url(parsed, raw_url=url)
        self._reject_playlist(url)

        safe_dir = self._prepare_download_dir()
        downloaded_path = self._download_media(url, safe_dir)

        return self._process_downloaded_file(downloaded_path, safe_dir, url, quality)

    def _reject_playlist(self, url: str) -> None:
        """Reject playlist URLs."""
        if "playlist" in url:
            raise UnsupportedUrlError(
                "Playlist URLs are not supported; please provide a single video URL.",
                context={"url": url, "reason": "playlist"},
            )

    def _prepare_download_dir(self) -> Path:
        """Prepare and return the safe download directory."""
        safe_dir = ensure_subpath(self._download_dir.parent, self._download_dir)
        safe_dir.mkdir(parents=True, exist_ok=True)
        return safe_dir

    def _build_ydl_opts(self, safe_dir: Path) -> dict:
        """Build yt-dlp options dict."""
        output_template = safe_dir / "%(id)s.%(ext)s"
        opts = {
            "outtmpl": str(output_template),
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "restrictfilenames": True,
            "paths": {"home": str(safe_dir)},
            "format": "bestaudio/best" if self._prefer_audio_only else "bestvideo+bestaudio/best",
        }
        return opts

    def _download_media(self, url: str, safe_dir: Path) -> Path:
        """Download media and return path to downloaded file."""
        ydl_opts = self._build_ydl_opts(safe_dir)
        downloaded_path: Path | None = None

        def _hook(d: dict[str, object]) -> None:  # pragma: no cover
            if d.get("status") == "finished":
                filename = d.get("filename")
                if filename and isinstance(filename, str):
                    nonlocal downloaded_path
                    downloaded_path = Path(filename)

        ydl_opts["progress_hooks"] = [_hook]

        try:
            with YoutubeDL(ydl_opts) as ydl:
                result = ydl.extract_info(url, download=True)
        except Exception as exc:
            logger.exception("URL ingestion failed for %s", url)
            raise UrlDownloadError(
                "Failed to download URL", context={"url": url}, original_error=exc
            ) from exc

        downloaded_path = self._resolve_download_path(downloaded_path, result, safe_dir, url)
        return downloaded_path

    def _resolve_download_path(
        self, downloaded_path: Path | None, result: dict | None, safe_dir: Path, url: str
    ) -> Path:
        """Resolve and validate the downloaded file path."""
        if not downloaded_path:
            filename = result.get("_filename") if isinstance(result, dict) else None
            if filename and isinstance(filename, str):
                downloaded_path = Path(filename)

        if downloaded_path:
            downloaded_path = self._sanitize_download_path(downloaded_path, safe_dir, url)

        if not downloaded_path or not downloaded_path.exists():
            raise UrlDownloadError(
                "yt-dlp did not produce a downloadable file", context={"url": url}
            )

        return downloaded_path

    def _process_downloaded_file(
        self, downloaded_path: Path, safe_dir: Path, url: str, quality: AudioQuality
    ) -> UrlIngestionResult:
        """Process downloaded file - return as-is if audio, extract if video."""
        audio_exts = {".mp3", ".m4a", ".aac", ".flac", ".wav", ".ogg", ".opus"}

        if downloaded_path.suffix.lower() in audio_exts:
            return UrlIngestionResult(audio_path=downloaded_path, source_video_path=None)

        return self._extract_audio_from_video(downloaded_path, url, quality)

    def _extract_audio_from_video(
        self, downloaded_path: Path, url: str, quality: AudioQuality
    ) -> UrlIngestionResult:
        """Extract audio from video file."""
        try:
            audio_path = self._extractor.extract_audio(
                input_path=downloaded_path, output_path=None, quality=quality
            )
        except AudioAnalysisError as exc:
            logger.exception("Audio extraction from downloaded video failed: %s", downloaded_path)
            raise UrlIngestionError(
                "Failed to extract audio from downloaded video",
                context={"url": url, "downloaded_path": str(downloaded_path)},
                original_error=exc,
            ) from exc
        except Exception as exc:
            logger.exception("Unexpected error during audio extraction: %s", downloaded_path)
            raise AudioExtractionError(
                "Unexpected error during audio extraction",
                context={"url": url, "downloaded_path": str(downloaded_path)},
                original_error=exc,
            ) from exc

        if audio_path is None:
            raise UrlIngestionError("Audio extraction returned no path.")

        source_video_path = self._cleanup_video_if_needed(downloaded_path)
        return UrlIngestionResult(audio_path=Path(audio_path), source_video_path=source_video_path)

    def _cleanup_video_if_needed(self, downloaded_path: Path) -> Path | None:
        """Clean up video file if not keeping, return source path if keeping."""
        if self._keep_video:
            return downloaded_path
        try:
            downloaded_path.unlink(missing_ok=True)
        except OSError:
            logger.warning("Failed to remove downloaded video: %s", downloaded_path)
        return None

    @staticmethod
    def _validate_url(parsed: ParseResult, raw_url: str) -> None:
        allowed_schemes = {"http", "https"}

        if parsed.scheme.lower() not in allowed_schemes:
            raise UnsupportedUrlError(
                "Only http(s) URLs are allowed for ingestion.",
                context={"url": raw_url, "reason": "scheme"},
            )

        if not parsed.hostname:
            raise UnsupportedUrlError(
                "URL must include a hostname.", context={"url": raw_url, "reason": "hostname"}
            )

        hostname = parsed.hostname.lower()
        if hostname in {"localhost", "localhost.localdomain"}:
            raise UnsupportedUrlError(
                "Localhost URLs are not allowed for ingestion.",
                context={"url": raw_url, "reason": "localhost"},
            )

        try:
            import ipaddress

            host_ip = ipaddress.ip_address(hostname)
            if host_ip.is_private or host_ip.is_loopback or host_ip.is_link_local:
                raise UnsupportedUrlError(
                    "Private or loopback hosts are not allowed for ingestion.",
                    context={"url": raw_url, "reason": "private_ip"},
                )
        except ValueError:
            # Hostname is not an IP literal; skip IP-only checks
            pass

    @staticmethod
    def _sanitize_download_path(downloaded_path: Path, download_root: Path, url: str) -> Path:
        try:
            safe_path = ensure_subpath(download_root, downloaded_path)
        except ValueError as exc:
            raise UrlIngestionError(
                "Download path is not within the allowed directory.",
                context={"url": url, "download_path": str(downloaded_path)},
                original_error=exc,
            ) from exc

        sanitized_name = PathSanitizer.sanitize_filename(safe_path.name)
        sanitized_path = safe_path.with_name(sanitized_name)

        if sanitized_path != safe_path:
            target_path = sanitized_path
            counter = 1
            while target_path.exists():
                target_path = sanitized_path.with_name(
                    f"{sanitized_path.stem}_{counter}{sanitized_path.suffix}"
                )
                counter += 1
            try:
                safe_path.rename(target_path)
            except OSError as exc:
                raise UrlIngestionError(
                    "Failed to rename downloaded file to a safe filename.",
                    context={
                        "url": url,
                        "download_path": str(downloaded_path),
                        "target_path": str(target_path),
                    },
                    original_error=exc,
                ) from exc
            sanitized_path = target_path

        return sanitized_path
