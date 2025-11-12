"""HTML dashboard rendering helpers."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, TemplateError, select_autoescape


def build_dashboard_context(
    transcript_dict: dict[str, Any],
    pipeline_result: dict[str, Any],
    *,
    source_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    """Normalise pipeline data for HTML template consumption."""

    stage_results = pipeline_result.get("stage_results", {}) or {}
    files_created = pipeline_result.get("files_created", []) or []

    def _format_duration(seconds: float | int | None) -> str:
        if seconds is None:
            return "—"
        try:
            seconds = float(seconds)
        except (TypeError, ValueError):
            return str(seconds)

        minutes, secs = divmod(seconds, 60)
        hours, minutes = divmod(int(minutes), 60)
        if hours:
            return f"{hours:d}h {minutes:02d}m {secs:04.1f}s"
        if minutes:
            return f"{minutes:d}m {secs:04.1f}s"
        return f"{secs:.1f}s"

    rendered_stages = [
        {
            "name": name.replace("_", " ").title(),
            "status": data.get("status", "unknown"),
            "duration": _format_duration(data.get("duration")),
        }
        for name, data in stage_results.items()
        if isinstance(data, dict)
    ]

    rendered_stages.sort(key=lambda item: (item["name"].lower() == "total", item["name"]))

    topics = transcript_dict.get("topics") or {}
    top_topics = sorted(topics.items(), key=lambda kv: kv[1], reverse=True)

    sentiment = transcript_dict.get("sentiment_distribution") or {}
    speakers = transcript_dict.get("speakers") or []

    files = []
    for item in files_created:
        try:
            path = Path(item)
        except TypeError:  # pragma: no cover - defensive
            continue
        label = path.name
        try:
            rel_path = path.relative_to(output_dir)
        except ValueError:
            rel_path = path
        files.append(
            {
                "label": label,
                "path": rel_path.as_posix() if isinstance(rel_path, Path) else str(rel_path),
            }
        )

    return {
        "source_name": source_path.name,
        "source_path": str(source_path),
        "processed_at": datetime.now().isoformat(),
        "provider": transcript_dict.get("provider_name", "unknown"),
        "duration": _format_duration(transcript_dict.get("duration")),
        "summary": transcript_dict.get("summary"),
        "chapters": transcript_dict.get("chapters", []),
        "topics": top_topics[:10],
        "sentiment": sentiment,
        "speakers": speakers,
        "stage_results": rendered_stages,
        "files": files,
        "raw_json": json.dumps(
            {
                "transcript": transcript_dict,
                "pipeline": pipeline_result,
            },
            indent=2,
            default=str,
        ),
        "output_dir": str(output_dir),
    }


class HtmlDashboardRenderer:
    """Render dashboard HTML files based on pipeline context."""

    def __init__(self, template_dir: Path | None = None) -> None:
        if template_dir is None:
            template_dir = Path(__file__).parent / "templates"

        self._template_dir = template_dir
        self._env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=select_autoescape(["html", "xml"]),
        )

    def render(self, context: dict[str, Any], output_dir: Path) -> Path:
        """Render the dashboard to the target directory."""

        output_dir.mkdir(parents=True, exist_ok=True)
        dashboard_dir = output_dir / "html-dashboard"
        assets_dir = dashboard_dir / "assets"
        dashboard_dir.mkdir(parents=True, exist_ok=True)
        assets_dir.mkdir(parents=True, exist_ok=True)

        template = self._env.get_template("dashboard.html")

        try:
            html = template.render(**context)
        except TemplateError as exc:
            raise RuntimeError(f"Failed to render HTML dashboard: {exc}") from exc

        index_path = dashboard_dir / "index.html"
        index_path.write_text(html, encoding="utf-8")

        style_path = assets_dir / "styles.css"
        style_path.write_text(_DEFAULT_STYLESHEET, encoding="utf-8")

        return index_path


_DEFAULT_STYLESHEET = """
:root {
  color-scheme: light dark;
  font-family: "Inter", "Segoe UI", sans-serif;
  background-color: #0f172a;
  color: #e2e8f0;
}

body {
  margin: 0;
  padding: 2.5rem;
  background: radial-gradient(circle at top left, #1e293b 0%, #020617 60%);
  min-height: 100vh;
}

.dashboard {
  max-width: 960px;
  margin: 0 auto;
  background: rgba(15, 23, 42, 0.88);
  border-radius: 18px;
  padding: 2.5rem 3rem;
  box-shadow: 0 32px 120px rgba(15, 23, 42, 0.7);
  backdrop-filter: blur(18px);
}

h1, h2, h3 {
  font-weight: 600;
  color: #dbeafe;
  margin-bottom: 0.75rem;
}

section {
  margin-bottom: 2.5rem;
}

.badge {
  display: inline-flex;
  align-items: center;
  padding: 0.25rem 0.75rem;
  border-radius: 999px;
  background: rgba(59, 130, 246, 0.2);
  color: #bfdbfe;
  font-size: 0.85rem;
  margin-right: 0.35rem;
}

.metric-grid {
  display: grid;
  gap: 1rem;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
}

.metric-card {
  background: rgba(30, 41, 59, 0.75);
  border-radius: 14px;
  padding: 1rem 1.25rem;
  border: 1px solid rgba(148, 163, 184, 0.15);
}

.metric-card span {
  display: block;
  font-size: 0.8rem;
  color: #94a3b8;
}

.metric-card strong {
  display: block;
  font-size: 1.2rem;
  margin-top: 0.35rem;
  color: #e0f2fe;
}

.list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.list li {
  padding: 0.5rem 0;
  border-bottom: 1px solid rgba(148, 163, 184, 0.1);
}

.stage-grid {
  display: grid;
  gap: 1rem;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
}

.stage-card {
  background: rgba(30, 41, 59, 0.72);
  padding: 1rem;
  border-radius: 12px;
  border: 1px solid rgba(94, 234, 212, 0.2);
}

.files a {
  display: inline-block;
  margin-right: 0.75rem;
  margin-bottom: 0.5rem;
  color: #38bdf8;
  text-decoration: none;
}

.files a:hover {
  text-decoration: underline;
}

pre {
  background: rgba(15, 23, 42, 0.6);
  padding: 1rem;
  border-radius: 12px;
  overflow-x: auto;
}
"""
