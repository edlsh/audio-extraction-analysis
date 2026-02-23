"""JSON-RPC backend for the OpenTUI frontend.

This module provides a stdio JSON-RPC 2.0 server that powers the TypeScript
OpenTUI frontend in ``frontend/src``.
"""

from __future__ import annotations

import asyncio
import fnmatch
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from time import time
from typing import Any

from src.config import get_config
from src.models.events import Event, QueueEventSink, generate_run_id
from src.pipeline.simple_pipeline import process_pipeline_v2
from src.providers.factory import TranscriptionProviderFactory
from src.services.audio_extraction import AudioQuality
from src.services.url_ingestion import UrlIngestionService
from src.utils.paths import ensure_subpath
from src.utils.sanitization import PathSanitizer
from src.utils.secure_file import secure_write_json

_JSON_RPC_VERSION = "2.0"

# JSON-RPC standard errors + app-specific errors
_PARSE_ERROR = -32700
_INVALID_REQUEST = -32600
_METHOD_NOT_FOUND = -32601
_INVALID_PARAMS = -32602
_INTERNAL_ERROR = -32603
_FILE_ERROR = -32003

_STAGE_MAP: dict[str, str] = {
    "url_download": "download",
    "url_prepare": "extract",
}

_DEFAULT_THEME = "ocean-dark"


def _coerce_int(value: object, default: int) -> int:
    """Safely coerce a value to int."""
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return default
    return default


def _coerce_float(value: object, default: float) -> float:
    """Safely coerce a value to float."""
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return default
    return default


def _get_user_config_dir() -> Path:
    """Return platform-specific app config directory."""
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "audio-extraction-analysis"
    if os.name == "nt":
        appdata = os.getenv("APPDATA")
        base = Path(appdata) if appdata else Path.home()
        return base / "audio-extraction-analysis"
    xdg_config_home = os.getenv("XDG_CONFIG_HOME")
    base = Path(xdg_config_home) if xdg_config_home else (Path.home() / ".config")
    return base / "audio-extraction-analysis"


def _default_settings_data() -> dict[str, object]:
    """Default settings payload matching frontend protocol."""
    return {
        "version": "1.0",
        "last_input_dir": None,
        "last_output_dir": None,
        "defaults": {
            "quality": "speech",
            "language": "en",
            "provider": "auto",
            "analysis_style": "concise",
            "keep_downloaded_videos": False,
        },
        "exports": {
            "markdown": True,
            "html": False,
        },
        "ui": {
            "theme": _DEFAULT_THEME,
            "verbose_logs": False,
            "log_panel_height": 12,
        },
        "api_keys": {
            "deepgram": "",
            "elevenlabs": "",
            "gemini": "",
        },
        "recent_files": [],
    }


def _merge_settings(defaults: dict[str, object], loaded: dict[str, object]) -> dict[str, object]:
    """Deep-merge loaded settings onto defaults."""
    result: dict[str, object] = {**defaults}
    for key, value in loaded.items():
        existing = result.get(key)
        if isinstance(value, dict) and isinstance(existing, dict):
            merged = dict(existing)
            merged.update(value)
            result[key] = merged
        else:
            result[key] = value
    return result


def normalize_event_for_frontend(event: Event) -> dict[str, object]:
    """Normalize backend event payloads to frontend protocol expectations."""
    payload = event.to_dict()

    stage_value = payload.get("stage")
    if isinstance(stage_value, str):
        payload["stage"] = _STAGE_MAP.get(stage_value, stage_value)

    data = payload.get("data")
    if not isinstance(data, dict):
        data = {}

    event_type = payload.get("type")
    if event_type == "artifact":
        if "kind" not in data and isinstance(data.get("type"), str):
            data["kind"] = data["type"]

    if event_type == "cancelled" and "reason" not in data:
        data["reason"] = "User cancelled"

    payload["data"] = data
    return payload


def _quality_from_string(quality: str) -> AudioQuality:
    """Convert quality string to AudioQuality enum with safe fallback."""
    mapping = {
        "high": AudioQuality.HIGH,
        "standard": AudioQuality.STANDARD,
        "speech": AudioQuality.SPEECH,
        "compressed": AudioQuality.COMPRESSED,
    }
    return mapping.get(quality, AudioQuality.SPEECH)


@dataclass
class RpcError(Exception):
    """Application JSON-RPC error."""

    code: int
    message: str
    data: dict[str, object] | None = None


@dataclass
class RunState:
    """In-memory tracking for an active pipeline run."""

    run_id: str
    task: asyncio.Task[None]
    is_running: bool = True
    current_stage: str | None = None
    progress: float = 0.0
    output_dir: Path | None = None
    cancel_requested: bool = False
    started_at: float = field(default_factory=time)


class SettingsStore:
    """Small secure settings store for TUI backend."""

    def __init__(self) -> None:
        self._path = _get_user_config_dir() / "tui_settings.json"
        self._data = self._load()

    def _load(self) -> dict[str, object]:
        defaults = _default_settings_data()
        if not self._path.exists():
            return defaults

        try:
            loaded_obj = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return defaults

        if not isinstance(loaded_obj, dict):
            return defaults

        return _merge_settings(defaults, loaded_obj)

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        secure_write_json(self._path, self._data)

    def get_settings(self) -> dict[str, object]:
        settings = dict(self._data)

        api_keys_obj = settings.get("api_keys")
        api_keys: dict[str, object]
        if isinstance(api_keys_obj, dict):
            api_keys = dict(api_keys_obj)
        else:
            api_keys = {}

        # Prefer current environment values so CLI/TUI stay consistent.
        # Return redacted markers (not raw secrets) to avoid accidental leaks.
        deepgram_value = os.getenv("DEEPGRAM_API_KEY", str(api_keys.get("deepgram", "")))
        elevenlabs_value = os.getenv("ELEVENLABS_API_KEY", str(api_keys.get("elevenlabs", "")))
        gemini_value = os.getenv("GEMINI_API_KEY", str(api_keys.get("gemini", "")))

        api_keys["deepgram"] = "__configured__" if deepgram_value else ""
        api_keys["elevenlabs"] = "__configured__" if elevenlabs_value else ""
        api_keys["gemini"] = "__configured__" if gemini_value else ""
        settings["api_keys"] = api_keys
        settings.pop("recent_files", None)
        return settings

    def update_setting(self, key: str, value: object) -> bool:
        normalized_key = "ui.theme" if key == "theme" else key
        parts = normalized_key.split(".")
        if not parts:
            return False

        current: dict[str, object] = self._data
        for part in parts[:-1]:
            next_value = current.get(part)
            if not isinstance(next_value, dict):
                next_value = {}
                current[part] = next_value
            current = next_value

        current[parts[-1]] = value
        self._save()
        return True

    def list_recent(self, max_entries: int) -> list[dict[str, object]]:
        entries = self._data.get("recent_files", [])
        if not isinstance(entries, list):
            return []
        return [entry for entry in entries if isinstance(entry, dict)][:max_entries]

    def add_recent(self, path: Path) -> None:
        entries = self._data.get("recent_files", [])
        if not isinstance(entries, list):
            entries = []

        record: dict[str, object] = {
            "path": str(path),
            "size_mb": round(path.stat().st_size / (1024 * 1024), 2) if path.exists() else 0.0,
            "last_used": datetime.now(UTC).isoformat(),
        }

        filtered = [
            entry for entry in entries if isinstance(entry, dict) and entry.get("path") != str(path)
        ]
        filtered.insert(0, record)

        self._data["recent_files"] = filtered[:100]
        self._save()

    def clear_recent(self) -> None:
        self._data["recent_files"] = []
        self._save()


class OpenTuiBackend:
    """JSON-RPC backend serving the OpenTUI frontend over stdio."""

    def __init__(self, project_root: Path | None = None) -> None:
        self.project_root = (project_root or Path.cwd()).resolve()
        self._event_queue: asyncio.Queue[Event] = asyncio.Queue()
        self._runs: dict[str, RunState] = {}
        self._settings = SettingsStore()
        self._write_lock = asyncio.Lock()

    def _resolve_user_path(self, value: str, *, must_exist: bool = False) -> Path:
        path = Path(value)
        PathSanitizer.validate_path_security(path)

        if path.is_absolute():
            resolved = ensure_subpath(Path("/"), path)
        else:
            resolved = ensure_subpath(self.project_root, path)

        if must_exist and not resolved.exists():
            raise RpcError(_FILE_ERROR, f"Path not found: {resolved}")

        return resolved

    async def _send_message(self, payload: dict[str, object]) -> None:
        line = json.dumps(payload, ensure_ascii=False, default=str)
        async with self._write_lock:
            sys.stdout.write(line + "\n")
            sys.stdout.flush()

    async def _send_event_notification(self, event: Event) -> None:
        normalized = normalize_event_for_frontend(event)
        self._update_run_state_from_event(normalized)
        await self._send_message(
            {
                "jsonrpc": _JSON_RPC_VERSION,
                "method": "event",
                "params": normalized,
            }
        )

    def _response_ok(self, request_id: object, result: dict[str, object]) -> dict[str, object]:
        return {
            "jsonrpc": _JSON_RPC_VERSION,
            "id": request_id,
            "result": result,
        }

    def _response_error(
        self,
        request_id: object,
        code: int,
        message: str,
        data: dict[str, object] | None = None,
    ) -> dict[str, object]:
        payload: dict[str, object] = {
            "jsonrpc": _JSON_RPC_VERSION,
            "id": request_id,
            "error": {
                "code": code,
                "message": message,
            },
        }
        if data is not None:
            payload_error = payload["error"]
            if isinstance(payload_error, dict):
                payload_error["data"] = data
        return payload

    def _update_run_state_from_event(self, payload: dict[str, object]) -> None:
        run_id = payload.get("run_id")
        if not isinstance(run_id, str):
            return

        run = self._runs.get(run_id)
        if run is None:
            return

        event_type = payload.get("type")
        stage = payload.get("stage")
        data = payload.get("data", {})
        if not isinstance(data, dict):
            data = {}

        if event_type == "stage_start":
            run.is_running = True
            run.current_stage = str(stage) if isinstance(stage, str) else None
            run.progress = 0.0
            return

        if event_type == "stage_progress":
            run.current_stage = str(stage) if isinstance(stage, str) else run.current_stage
            completed = _coerce_float(data.get("completed"), 0.0)
            total = _coerce_float(data.get("total"), 100.0)
            run.progress = (completed / total) * 100.0 if total > 0 else 0.0
            return

        if event_type == "stage_end":
            run.current_stage = None
            run.progress = 0.0
            return

        if event_type in {"summary", "cancelled"}:
            run.is_running = False
            run.current_stage = None
            if event_type == "summary":
                run.progress = 100.0

    async def _event_pump(self) -> None:
        while True:
            event = await self._event_queue.get()
            await self._send_event_notification(event)

    async def _rpc_system_ping(self, params: dict[str, object]) -> dict[str, object]:
        del params
        return {"pong": True}

    async def _rpc_settings_get(self, params: dict[str, object]) -> dict[str, object]:
        del params
        return {"settings": self._settings.get_settings()}

    async def _rpc_settings_update(self, params: dict[str, object]) -> dict[str, object]:
        key_obj = params.get("key")
        if not isinstance(key_obj, str) or not key_obj:
            raise RpcError(_INVALID_PARAMS, "settings.update requires non-empty key")

        value = params.get("value")

        # Keep runtime env in sync for provider API keys.
        if key_obj.startswith("api_keys."):
            api_key_name = key_obj.split(".", 1)[1]
            env_map = {
                "deepgram": "DEEPGRAM_API_KEY",
                "elevenlabs": "ELEVENLABS_API_KEY",
                "gemini": "GEMINI_API_KEY",
            }
            env_var = env_map.get(api_key_name)
            if env_var:
                as_text = "" if value is None else str(value)
                os.environ[env_var] = as_text
                config = get_config()
                if hasattr(config, env_var):
                    setattr(config, env_var, as_text or None)

        success = self._settings.update_setting(key_obj, value)
        return {"success": success}

    async def _rpc_recent_list(self, params: dict[str, object]) -> dict[str, object]:
        max_entries = _coerce_int(params.get("max_entries"), 10)
        max_entries = max(1, min(max_entries, 100))
        return {"files": self._settings.list_recent(max_entries)}

    async def _rpc_recent_add(self, params: dict[str, object]) -> dict[str, object]:
        path_obj = params.get("path")
        if not isinstance(path_obj, str) or not path_obj:
            raise RpcError(_INVALID_PARAMS, "recent.add requires path")

        path = self._resolve_user_path(path_obj)
        self._settings.add_recent(path)
        return {"success": True}

    async def _rpc_recent_clear(self, params: dict[str, object]) -> dict[str, object]:
        del params
        self._settings.clear_recent()
        return {"success": True}

    async def _rpc_providers_health(self, params: dict[str, object]) -> dict[str, object]:
        del params
        available = TranscriptionProviderFactory.get_available_providers()
        configured = set(TranscriptionProviderFactory.get_configured_providers())

        providers: list[dict[str, object]] = []
        for provider_name in available:
            is_available = provider_name in configured
            providers.append(
                {
                    "name": provider_name,
                    "available": is_available,
                    "reason": None if is_available else "Not configured",
                }
            )

        return {"providers": providers}

    async def _rpc_themes_catalog(self, params: dict[str, object]) -> dict[str, object]:
        del params
        themes: list[dict[str, object]] = [
            {
                "name": "ocean-dark",
                "dark": True,
                "primary": "#0EA5E9",
                "secondary": "#64748B",
                "accent": "#10B981",
                "background": "#020617",
                "foreground": "#F8FAFC",
                "surface": "#0F172A",
                "panel": "#111827",
                "success": "#10B981",
                "warning": "#F59E0B",
                "error": "#EF4444",
            },
            {
                "name": "forest-dark",
                "dark": True,
                "primary": "#22C55E",
                "secondary": "#6B7280",
                "accent": "#84CC16",
                "background": "#030712",
                "foreground": "#F3F4F6",
                "surface": "#111827",
                "panel": "#1F2937",
                "success": "#22C55E",
                "warning": "#F59E0B",
                "error": "#EF4444",
            },
            {
                "name": "solar-light",
                "dark": False,
                "primary": "#0369A1",
                "secondary": "#64748B",
                "accent": "#0D9488",
                "background": "#F8FAFC",
                "foreground": "#0F172A",
                "surface": "#E2E8F0",
                "panel": "#FFFFFF",
                "success": "#16A34A",
                "warning": "#D97706",
                "error": "#DC2626",
            },
        ]

        settings = self._settings.get_settings()
        ui = settings.get("ui", {})
        default_theme = _DEFAULT_THEME
        if isinstance(ui, dict) and isinstance(ui.get("theme"), str):
            default_theme = ui["theme"]

        categories = {
            "dark": [theme["name"] for theme in themes if bool(theme.get("dark"))],
            "light": [theme["name"] for theme in themes if not bool(theme.get("dark"))],
        }

        return {
            "themes": themes,
            "default_theme": default_theme,
            "categories": categories,
        }

    async def _rpc_system_open_path(self, params: dict[str, object]) -> dict[str, object]:
        path_obj = params.get("path")
        if not isinstance(path_obj, str) or not path_obj:
            raise RpcError(_INVALID_PARAMS, "system.openPath requires path")

        path = self._resolve_user_path(path_obj, must_exist=True)

        if sys.platform == "darwin":
            cmd = ["open", str(path)]
        elif os.name == "nt":
            cmd = ["cmd", "/c", "start", "", str(path)]
        else:
            cmd = ["xdg-open", str(path)]

        try:
            subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except OSError as exc:
            raise RpcError(
                _FILE_ERROR, f"Failed to open path: {path}", {"error": str(exc)}
            ) from exc

        return {"success": True}

    async def _rpc_system_list_dir(self, params: dict[str, object]) -> dict[str, object]:
        path_obj = params.get("path")
        base_path_raw = path_obj if isinstance(path_obj, str) and path_obj else str(Path.home())

        directory = self._resolve_user_path(base_path_raw, must_exist=True)
        if not directory.is_dir():
            raise RpcError(_FILE_ERROR, f"Not a directory: {directory}")

        filter_obj = params.get("filter")
        patterns = ["*"]
        if isinstance(filter_obj, str) and filter_obj.strip():
            patterns = [pattern.strip() for pattern in filter_obj.split(",") if pattern.strip()]
            if not patterns:
                patterns = ["*"]

        entries: list[dict[str, object]] = []
        for child in directory.iterdir():
            if child.is_dir():
                include = True
            else:
                include = any(fnmatch.fnmatch(child.name, pattern) for pattern in patterns)

            if not include:
                continue

            entry: dict[str, object] = {
                "name": child.name,
                "path": str(child),
                "is_dir": child.is_dir(),
            }
            if child.is_file():
                entry["size_bytes"] = child.stat().st_size
            entries.append(entry)

        parent_value: str | None = None
        if directory.parent != directory:
            parent_value = str(directory.parent)

        return {
            "entries": entries,
            "parent": parent_value,
        }

    async def _emit_url_download_start(self, run_id: str) -> None:
        await self._event_queue.put(
            Event(
                type="stage_start",
                run_id=run_id,
                stage="url_download",
                data={"description": "Downloading media", "total": 100},
            )
        )

    async def _emit_url_download_end(self, run_id: str, *, status: str) -> None:
        await self._event_queue.put(
            Event(
                type="stage_end",
                run_id=run_id,
                stage="url_download",
                data={"duration": 0.0, "status": status},
            )
        )

    async def _run_pipeline(
        self,
        *,
        run_id: str,
        input_path: str | None,
        url: str | None,
        output_dir: Path,
        quality: str,
        language: str,
        provider: str,
        analysis_style: str,
        keep_downloaded_videos: bool,
    ) -> None:
        run_state = self._runs[run_id]
        event_sink = QueueEventSink(self._event_queue, asyncio.get_running_loop())
        quality_enum = _quality_from_string(quality)

        resolved_input: Path
        skip_extraction = False
        try:
            if url:
                await self._emit_url_download_start(run_id)
                config = get_config()
                ingestion_service = UrlIngestionService(
                    download_dir=config.url_ingest_download_dir,
                    prefer_audio_only=config.url_ingest_prefer_audio_only,
                    keep_video=keep_downloaded_videos,
                    event_sink=event_sink,
                )
                ingest_result = await asyncio.to_thread(
                    ingestion_service.ingest, url, quality=quality_enum
                )
                resolved_input = ingest_result.audio_path
                skip_extraction = True
                await self._emit_url_download_end(run_id, status="complete")
            else:
                if input_path is None:
                    raise RpcError(_INVALID_PARAMS, "pipeline.start requires input_path or url")
                resolved_input = self._resolve_user_path(input_path, must_exist=True)

            result = await process_pipeline_v2(
                input_path=resolved_input,
                output_dir=output_dir,
                quality=quality_enum,
                language=language,
                provider=provider,
                analysis_style=analysis_style,
                run_id=run_id,
                event_sink=event_sink,
                skip_extraction=skip_extraction,
            )

            for artifact in result.artifacts:
                await self._event_queue.put(
                    Event(
                        type="artifact",
                        run_id=run_id,
                        stage=artifact.stage,
                        data={
                            "path": str(artifact.path),
                            "kind": artifact.artifact_type,
                            "type": artifact.artifact_type,
                        },
                    )
                )

            if input_path:
                try:
                    self._settings.add_recent(Path(input_path))
                except (ValueError, OSError):
                    pass

            metrics: dict[str, object] = {
                f"{name}_duration": stage_result.duration
                for name, stage_result in result.stage_results.items()
            }
            summary_provider = provider
            if result.transcript is not None and result.transcript.provider_name:
                summary_provider = result.transcript.provider_name

            await self._event_queue.put(
                Event(
                    type="summary",
                    run_id=run_id,
                    data={
                        "metrics": metrics,
                        "provider": summary_provider,
                        "output_dir": str(output_dir),
                        "success": result.success,
                    },
                )
            )

        except asyncio.CancelledError:
            if not run_state.cancel_requested:
                await self._event_queue.put(
                    Event(
                        type="cancelled",
                        run_id=run_id,
                        data={"reason": "Cancelled"},
                    )
                )
            raise
        except RpcError as exc:
            await self._event_queue.put(
                Event(
                    type="error",
                    run_id=run_id,
                    stage=run_state.current_stage,
                    data={"message": exc.message, "level": "ERROR", "logger": __name__},
                )
            )
            await self._event_queue.put(
                Event(
                    type="summary",
                    run_id=run_id,
                    data={
                        "metrics": {},
                        "provider": provider,
                        "output_dir": str(output_dir),
                        "success": False,
                    },
                )
            )
        except Exception as exc:
            await self._event_queue.put(
                Event(
                    type="error",
                    run_id=run_id,
                    stage=run_state.current_stage,
                    data={"message": str(exc), "level": "ERROR", "logger": __name__},
                )
            )
            await self._event_queue.put(
                Event(
                    type="summary",
                    run_id=run_id,
                    data={
                        "metrics": {},
                        "provider": provider,
                        "output_dir": str(output_dir),
                        "success": False,
                    },
                )
            )
        finally:
            run_state.is_running = False
            run_state.current_stage = None
            run_state.progress = 100.0

    async def _rpc_pipeline_start(self, params: dict[str, object]) -> dict[str, object]:
        input_path_obj = params.get("input_path")
        url_obj = params.get("url")
        output_dir_obj = params.get("output_dir")

        input_path = input_path_obj if isinstance(input_path_obj, str) and input_path_obj else None
        url = url_obj if isinstance(url_obj, str) and url_obj else None

        if (input_path is None and url is None) or (input_path is not None and url is not None):
            raise RpcError(
                _INVALID_PARAMS, "pipeline.start requires exactly one of input_path or url"
            )

        if not isinstance(output_dir_obj, str) or not output_dir_obj:
            raise RpcError(_INVALID_PARAMS, "pipeline.start requires output_dir")

        output_dir = self._resolve_user_path(output_dir_obj)
        output_dir.mkdir(parents=True, exist_ok=True)

        quality = str(params.get("quality", "speech"))
        language = str(params.get("language", "en"))
        provider = str(params.get("provider", "auto"))
        analysis_style = str(params.get("analysis_style", "concise"))
        keep_downloaded_videos = bool(params.get("keep_downloaded_videos"))

        run_id = generate_run_id()
        task = asyncio.create_task(
            self._run_pipeline(
                run_id=run_id,
                input_path=input_path,
                url=url,
                output_dir=output_dir,
                quality=quality,
                language=language,
                provider=provider,
                analysis_style=analysis_style,
                keep_downloaded_videos=keep_downloaded_videos,
            )
        )

        self._runs[run_id] = RunState(
            run_id=run_id,
            task=task,
            is_running=True,
            current_stage=None,
            progress=0.0,
            output_dir=output_dir,
        )

        return {"run_id": run_id}

    async def _rpc_pipeline_cancel(self, params: dict[str, object]) -> dict[str, object]:
        run_id_obj = params.get("run_id")
        if not isinstance(run_id_obj, str) or not run_id_obj:
            raise RpcError(_INVALID_PARAMS, "pipeline.cancel requires run_id")

        run_state = self._runs.get(run_id_obj)
        if run_state is None:
            return {"success": False}

        if run_state.task.done() or run_state.cancel_requested:
            return {"success": False}

        run_state.cancel_requested = True
        run_state.is_running = False
        run_state.task.cancel()

        await self._event_queue.put(
            Event(
                type="cancelled",
                run_id=run_id_obj,
                data={"reason": "Cancelled by user"},
            )
        )

        return {"success": True}

    async def _rpc_pipeline_status(self, params: dict[str, object]) -> dict[str, object]:
        run_id_obj = params.get("run_id")
        if not isinstance(run_id_obj, str) or not run_id_obj:
            raise RpcError(_INVALID_PARAMS, "pipeline.status requires run_id")

        run_state = self._runs.get(run_id_obj)
        if run_state is None:
            return {
                "is_running": False,
                "current_stage": None,
                "progress": 0,
            }

        return {
            "is_running": run_state.is_running and not run_state.task.done(),
            "current_stage": run_state.current_stage,
            "progress": run_state.progress,
        }

    async def handle_request(self, request: dict[str, object]) -> dict[str, object]:
        """Handle a single JSON-RPC request."""
        request_id = request.get("id")

        if request.get("jsonrpc") != _JSON_RPC_VERSION:
            return self._response_error(request_id, _INVALID_REQUEST, "Invalid JSON-RPC version")

        method_obj = request.get("method")
        if not isinstance(method_obj, str) or not method_obj:
            return self._response_error(request_id, _INVALID_REQUEST, "Missing method")

        params_obj = request.get("params", {})
        if not isinstance(params_obj, dict):
            return self._response_error(request_id, _INVALID_PARAMS, "Params must be an object")

        handlers: dict[str, Any] = {
            "pipeline.start": self._rpc_pipeline_start,
            "pipeline.cancel": self._rpc_pipeline_cancel,
            "pipeline.status": self._rpc_pipeline_status,
            "settings.get": self._rpc_settings_get,
            "settings.update": self._rpc_settings_update,
            "recent.list": self._rpc_recent_list,
            "recent.add": self._rpc_recent_add,
            "recent.clear": self._rpc_recent_clear,
            "providers.health": self._rpc_providers_health,
            "themes.catalog": self._rpc_themes_catalog,
            "system.openPath": self._rpc_system_open_path,
            "system.listDir": self._rpc_system_list_dir,
            "system.ping": self._rpc_system_ping,
        }

        handler = handlers.get(method_obj)
        if handler is None:
            return self._response_error(
                request_id, _METHOD_NOT_FOUND, f"Method not found: {method_obj}"
            )

        try:
            result = await handler(params_obj)
            return self._response_ok(request_id, result)
        except RpcError as exc:
            return self._response_error(request_id, exc.code, exc.message, exc.data)
        except Exception as exc:
            return self._response_error(
                request_id,
                _INTERNAL_ERROR,
                "Internal error",
                {"error": str(exc)},
            )

    async def serve_stdio(self) -> None:
        """Serve JSON-RPC requests from stdin and write responses to stdout."""
        event_task = asyncio.create_task(self._event_pump())
        try:
            while True:
                line = await asyncio.to_thread(sys.stdin.readline)
                if not line:
                    break

                line = line.strip()
                if not line:
                    continue

                try:
                    parsed = json.loads(line)
                except json.JSONDecodeError:
                    await self._send_message(
                        self._response_error(
                            None, _PARSE_ERROR, "Parse error", {"line": line[:200]}
                        )
                    )
                    continue

                if not isinstance(parsed, dict):
                    await self._send_message(
                        self._response_error(None, _INVALID_REQUEST, "Request must be an object")
                    )
                    continue

                response = await self.handle_request(parsed)
                await self._send_message(response)
        finally:
            event_task.cancel()
            try:
                await event_task
            except asyncio.CancelledError:
                pass

            for run_state in self._runs.values():
                if not run_state.task.done():
                    run_state.task.cancel()

            if self._runs:
                await asyncio.gather(
                    *(run_state.task for run_state in self._runs.values()),
                    return_exceptions=True,
                )


async def _async_main() -> None:
    backend = OpenTuiBackend(project_root=Path.cwd())
    await backend.serve_stdio()


def main() -> int:
    """CLI entrypoint."""
    try:
        asyncio.run(_async_main())
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
