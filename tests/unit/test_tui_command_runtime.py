"""Unit tests for CLI TUI runtime resolution."""

from pathlib import Path
from subprocess import CalledProcessError, CompletedProcess

import pytest

from src.cli.commands import tui as tui_module


class TestFindRuntime:
    """Runtime discovery behavior for TUI launcher."""

    @pytest.mark.unit
    @pytest.mark.fast
    def test_requires_bun_runtime_even_if_node_is_available(self, monkeypatch):
        """Node alone should not be treated as runnable for TSX entrypoints."""

        def fake_run(cmd, capture_output=True, check=True):
            if cmd[0] == "bun":
                raise FileNotFoundError("bun missing")
            if cmd[0] == "node":
                return CompletedProcess(cmd, 0, stdout=b"v22.0.0", stderr=b"")
            raise AssertionError(f"Unexpected command: {cmd}")

        monkeypatch.setattr(tui_module.subprocess, "run", fake_run)

        assert tui_module._find_runtime() is None

    @pytest.mark.unit
    @pytest.mark.fast
    def test_detects_bun_runtime(self, monkeypatch):
        """Bun should be selected when available."""

        def fake_run(cmd, capture_output=True, check=True):
            if cmd[0] == "bun":
                return CompletedProcess(cmd, 0, stdout=b"1.2.0", stderr=b"")
            raise CalledProcessError(returncode=1, cmd=cmd)

        monkeypatch.setattr(tui_module.subprocess, "run", fake_run)

        assert tui_module._find_runtime() == ("bun", ["run"])


class TestTuiCommandPolicy:
    """Distribution-policy behavior for TUI launcher."""

    @pytest.mark.unit
    @pytest.mark.fast
    def test_missing_frontend_mentions_source_checkout_policy(self, monkeypatch, capsys):
        """Missing frontend should clearly state source-checkout-only policy."""
        monkeypatch.setattr(tui_module, "_find_frontend_dir", lambda: None)

        exit_code = tui_module.tui_command(args=object(), console_manager=None)

        captured = capsys.readouterr()
        assert exit_code == 1
        assert "source-checkout-only" in captured.err

    @pytest.mark.unit
    @pytest.mark.fast
    def test_missing_runtime_mentions_source_checkout_policy(
        self, monkeypatch, capsys, tmp_path: Path
    ):
        """Missing runtime should also restate source-checkout-only policy."""
        frontend_dir = tmp_path / "frontend"
        frontend_dir.mkdir()

        monkeypatch.setattr(tui_module, "_find_frontend_dir", lambda: frontend_dir)
        monkeypatch.setattr(tui_module, "_find_runtime", lambda: None)

        exit_code = tui_module.tui_command(args=object(), console_manager=None)

        captured = capsys.readouterr()
        assert exit_code == 1
        assert "source-checkout-only" in captured.err
