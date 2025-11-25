from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from src.ui.tui.services.os_open import open_path


@pytest.mark.unit
def test_open_path_handles_os_error(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / "file.txt"
    path.write_text("data")

    def fake_run(*_: object, **__: object) -> None:
        raise OSError("fail")

    monkeypatch.setattr(subprocess, "run", fake_run)

    assert open_path(path) is False
