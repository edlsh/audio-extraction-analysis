from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import ParseResult, urlparse

from yt_dlp import YoutubeDL

from src.utils.log_redaction import sanitize_url
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

if TYPE_CHECKING:
    from ..models.events import EventSink

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
        event_sink: EventSink | None = None,
    ) -> None:
        self._download_dir = download_dir
        self._prefer_audio_only = prefer_audio_only
        self._keep_video = keep_video
        self._extractor = AudioExtractor()
        self._event_sink = event_sink

    def _emit_event(
        self,
        event_type: str,
        *,
        stage: str | None = None,
        data: dict | None = None,
    ) -> None:
        """Emit an event via the injected sink (thread-safe for use with asyncio.to_thread)."""
        if self._event_sink is None:
            return

        from ..models.events import Event, EventType

        # Validate event_type is a valid EventType before creating Event
        valid_types = ("stage_start", "stage_progress", "stage_end", "artifact", "log", "warning", "error", "summary", "cancelled")
        if event_type not in valid_types:
            return

        event = Event(
            type=event_type,  # type: ignore[arg-type]
            stage=stage,
            data=data or {},
        )
        self._event_sink.emit(event)

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
        last_percent: float = 0.0

        def _hook(d: dict[str, object]) -> None:  # pragma: no cover
            nonlocal downloaded_path, last_percent
            status = d.get("status")

            if status == "downloading":
                # Emit progress events for TUI feedback
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                downloaded = d.get("downloaded_bytes", 0)
                is_valid_total = total and isinstance(total, (int, float))
                is_valid_downloaded = isinstance(downloaded, (int, float))
                if is_valid_total and is_valid_downloaded:
                    percent = (downloaded / total) * 100
                    # Only emit if progress changed by at least 1%
                    if percent - last_percent >= 1.0:
                        last_percent = percent
                        self._emit_event(
                            "stage_progress",
                            stage="url_download",
                            data={
                                "completed": int(percent),
                                "total": 100,
                                "message": f"Downloading... {percent:.0f}%",
                            },
                        )

            elif status == "finished":
                filename = d.get("filename")
                if filename and isinstance(filename, str):
                    downloaded_path = Path(filename)
                    self._emit_event(
                        "stage_progress",
                        stage="url_download",
                        data={"completed": 100, "total": 100, "message": "Download complete"},
                    )

        ydl_opts["progress_hooks"] = [_hook]

        try:
            with YoutubeDL(ydl_opts) as ydl:
                result = ydl.extract_info(url, download=True)
        except Exception as exc:
            logger.exception("URL ingestion failed for %s", sanitize_url(url))
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
        import time

        # Emit stage start for url_prepare
        self._emit_event(
            "stage_start",
            stage="url_prepare",
            data={"description": "Extracting audio from video", "total": 100},
        )
        start_time = time.time()

        try:
            # Emit initial progress
            self._emit_event(
                "stage_progress",
                stage="url_prepare",
                data={"completed": 10, "total": 100, "message": "Starting audio extraction..."},
            )

            audio_path = self._extractor.extract_audio(
                input_path=downloaded_path, output_path=None, quality=quality
            )

            # Emit completion progress
            self._emit_event(
                "stage_progress",
                stage="url_prepare",
                data={"completed": 100, "total": 100, "message": "Audio extraction complete"},
            )

        except AudioAnalysisError as exc:
            duration = time.time() - start_time
            self._emit_event(
                "stage_end",
                stage="url_prepare",
                data={"duration": duration, "status": "error"},
            )
            logger.exception("Audio extraction from downloaded video failed: %s", downloaded_path)
            raise UrlIngestionError(
                "Failed to extract audio from downloaded video",
                context={"url": url, "downloaded_path": str(downloaded_path)},
                original_error=exc,
            ) from exc
        except Exception as exc:
            duration = time.time() - start_time
            self._emit_event(
                "stage_end",
                stage="url_prepare",
                data={"duration": duration, "status": "error"},
            )
            logger.exception("Unexpected error during audio extraction: %s", downloaded_path)
            raise AudioExtractionError(
                "Unexpected error during audio extraction",
                context={"url": url, "downloaded_path": str(downloaded_path)},
                original_error=exc,
            ) from exc

        if audio_path is None:
            duration = time.time() - start_time
            self._emit_event(
                "stage_end",
                stage="url_prepare",
                data={"duration": duration, "status": "error"},
            )
            raise UrlIngestionError("Audio extraction returned no path.")

        # Emit stage end on success
        duration = time.time() - start_time
        self._emit_event(
            "stage_end",
            stage="url_prepare",
            data={"duration": duration, "status": "complete"},
        )

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

        # Check if hostname is an IP literal
        UrlIngestionService._validate_ip_address(hostname, raw_url)

        # DNS rebinding protection: resolve hostname and validate all resolved IPs
        UrlIngestionService._validate_resolved_ips(hostname, raw_url)

    @staticmethod
    def _validate_ip_address(hostname: str, raw_url: str) -> None:
        """Validate IP address is not private, loopback, or reserved."""
        import ipaddress

        try:
            host_ip = ipaddress.ip_address(hostname)
        except ValueError:
            # Not an IP literal; will be validated via DNS resolution
            return

        UrlIngestionService._check_ip_is_safe(host_ip, raw_url, "ip_literal")

    @staticmethod
    def _validate_resolved_ips(hostname: str, raw_url: str) -> None:
        """Resolve hostname and validate all resolved IPs against SSRF."""
        import ipaddress
        import socket

        # Skip if hostname is already an IP literal
        try:
            ipaddress.ip_address(hostname)
            return  # Already validated in _validate_ip_address
        except ValueError:
            pass

        try:
            # Resolve both IPv4 and IPv6 addresses
            addr_info = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
        except socket.gaierror:
            # DNS resolution failed - allow yt-dlp to handle this later
            logger.debug("DNS resolution failed for %s, deferring to yt-dlp", hostname)
            return

        for _family, _type, _proto, _canonname, sockaddr in addr_info:
            ip_str = sockaddr[0]
            try:
                resolved_ip = ipaddress.ip_address(ip_str)
                UrlIngestionService._check_ip_is_safe(resolved_ip, raw_url, "dns_resolved")
            except ValueError:
                continue

    @staticmethod
    def _check_ip_is_safe(
        ip: ipaddress.IPv4Address | ipaddress.IPv6Address, raw_url: str, reason_prefix: str
    ) -> None:
        """Check if an IP address is safe (not private, loopback, reserved, etc.)."""
        import ipaddress

        # Handle IPv4-mapped IPv6 addresses (::ffff:127.0.0.1)
        if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
            ip = ip.ipv4_mapped

        # Check all unsafe categories (order matters - check more specific first)
        if ip.is_loopback:
            raise UnsupportedUrlError(
                "Loopback addresses are not allowed for ingestion.",
                context={"url": raw_url, "reason": f"{reason_prefix}_loopback"},
            )
        if ip.is_unspecified:
            raise UnsupportedUrlError(
                "Unspecified addresses (0.0.0.0, ::) are not allowed for ingestion.",
                context={"url": raw_url, "reason": f"{reason_prefix}_unspecified"},
            )
        if ip.is_multicast:
            raise UnsupportedUrlError(
                "Multicast addresses are not allowed for ingestion.",
                context={"url": raw_url, "reason": f"{reason_prefix}_multicast"},
            )
        if ip.is_link_local:
            raise UnsupportedUrlError(
                "Link-local addresses are not allowed for ingestion.",
                context={"url": raw_url, "reason": f"{reason_prefix}_link_local"},
            )
        if ip.is_reserved:
            raise UnsupportedUrlError(
                "Reserved addresses are not allowed for ingestion.",
                context={"url": raw_url, "reason": f"{reason_prefix}_reserved"},
            )
        if ip.is_private:
            raise UnsupportedUrlError(
                "Private network hosts are not allowed for ingestion.",
                context={"url": raw_url, "reason": f"{reason_prefix}_private"},
            )

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
