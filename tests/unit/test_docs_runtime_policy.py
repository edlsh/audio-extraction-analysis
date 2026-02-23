"""Documentation drift tests for runtime and provider policy decisions."""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = [
    pytest.mark.unit,
    pytest.mark.fast,
]


def _read_doc(*parts: str) -> str:
    """Read a documentation file from repository root."""
    root = Path(__file__).resolve().parents[2]
    return (root / Path(*parts)).read_text(encoding="utf-8")


def test_readme_does_not_advertise_removed_provider_or_tui_flags() -> None:
    """README should match current provider support and TUI CLI surface."""
    readme = _read_doc("README.md")

    assert "Whisper, Parakeet" not in readme
    assert "Whisper/Parakeet" not in readme
    assert "Provider Configuration](docs/PROVIDERS.md) — Whisper, Parakeet" not in readme
    assert "audio-extraction-analysis tui --input" not in readme
    assert "audio-extraction-analysis tui -i" not in readme


def test_tui_doc_mentions_source_checkout_policy_and_no_removed_flags() -> None:
    """TUI docs should lock in source-checkout-only and Bun-only execution."""
    tui_doc = _read_doc("docs", "TUI.md")

    assert "source-checkout-only" in tui_doc
    assert "cd frontend && bun install --frozen-lockfile" in tui_doc
    assert "audio-extraction-analysis tui --input" not in tui_doc
    assert "audio-extraction-analysis tui --output-dir" not in tui_doc
    assert "audio-extraction-analysis tui -i" not in tui_doc
    assert "audio-extraction-analysis tui -o" not in tui_doc


def test_tui_doc_contains_support_contract() -> None:
    """TUI docs should state the explicit runtime/distribution support contract."""
    tui_doc = _read_doc("docs", "TUI.md")

    assert "Support Contract" in tui_doc
    assert "Bun" in tui_doc
    assert "source-checkout-only" in tui_doc
    assert "frontend/" in tui_doc
    assert "wheel" in tui_doc


def test_troubleshooting_doc_does_not_suggest_removed_runtime_paths() -> None:
    """Troubleshooting docs should not suggest removed extras or Node fallback."""
    troubleshooting = _read_doc("docs", "TROUBLESHOOTING.md")

    assert "uv sync --extra tui" not in troubleshooting
    assert "node --version" not in troubleshooting
    assert "PARAKEET_" not in troubleshooting
    assert "Whisper/Parakeet" not in troubleshooting


def test_provider_doc_keeps_parakeet_removed_and_env_table_clean() -> None:
    """Provider docs should keep Parakeet only as removed context, never active support."""
    providers_doc = _read_doc("docs", "PROVIDERS.md")

    assert "Parakeet (Removed)" in providers_doc
    assert "| Parakeet | Local | No |" not in providers_doc
    assert "PARAKEET_" not in providers_doc
