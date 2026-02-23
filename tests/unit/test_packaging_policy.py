"""Packaging policy tests.

These tests lock in the current distribution decision:
Python wheels ship only the `src` package, while TUI frontend assets remain
source-checkout-only.
"""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

import pytest


@pytest.mark.unit
@pytest.mark.fast
def test_wheel_target_is_source_only() -> None:
    """Wheel config should keep packaging scope limited to Python sources."""
    pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
    config = tomllib.loads(pyproject.read_text(encoding="utf-8"))

    wheel_target = config["tool"]["hatch"]["build"]["targets"]["wheel"]
    assert wheel_target.get("packages") == ["src"]
    assert "force-include" not in wheel_target


@pytest.mark.unit
@pytest.mark.fast
def test_frontend_opentui_dependencies_are_pinned() -> None:
    """OpenTUI dependencies should be exact-pinned to avoid runtime drift."""
    package_json_path = Path(__file__).resolve().parents[2] / "frontend" / "package.json"
    package_json = json.loads(package_json_path.read_text(encoding="utf-8"))
    deps = package_json.get("dependencies", {})

    core_version = deps.get("@opentui/core")
    react_version = deps.get("@opentui/react")

    assert core_version is not None
    assert react_version is not None
    assert not core_version.startswith("^")
    assert not react_version.startswith("^")
    assert core_version == react_version


@pytest.mark.unit
@pytest.mark.fast
def test_frontend_lockfile_matches_pinned_opentui_versions() -> None:
    """Lockfile should resolve the same exact OpenTUI versions pinned in package.json."""
    repo_root = Path(__file__).resolve().parents[2]
    package_json_path = repo_root / "frontend" / "package.json"
    package_json = json.loads(package_json_path.read_text(encoding="utf-8"))
    deps = package_json.get("dependencies", {})

    core_version = deps.get("@opentui/core")
    react_version = deps.get("@opentui/react")

    assert core_version is not None
    assert react_version is not None

    lockfile = (repo_root / "frontend" / "bun.lock").read_text(encoding="utf-8")

    assert f'"@opentui/core": "{core_version}"' in lockfile
    assert f'"@opentui/react": "{react_version}"' in lockfile
    assert f"@opentui/core@{core_version}" in lockfile
    assert f"@opentui/react@{react_version}" in lockfile


@pytest.mark.unit
@pytest.mark.fast
def test_frontend_smoke_workflow_exists_and_runs_bun_checks() -> None:
    """CI should include a frontend smoke lane for Bun install and typecheck."""
    workflow_path = (
        Path(__file__).resolve().parents[2] / ".github" / "workflows" / "frontend-tui-smoke.yml"
    )
    workflow = workflow_path.read_text(encoding="utf-8")

    assert "oven-sh/setup-bun" in workflow
    assert "bun install --frozen-lockfile" in workflow
    assert "bun run lint" in workflow
    assert "bun run typecheck" in workflow
    assert "bun run test" in workflow
