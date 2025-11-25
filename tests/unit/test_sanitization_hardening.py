from __future__ import annotations

import pytest

from src.utils.sanitization import PathSanitizer


@pytest.mark.unit
def test_sanitize_filename_strips_control_chars() -> None:
    name = "bad\nname\r.txt"
    sanitized = PathSanitizer.sanitize_filename(name)
    assert "\n" not in sanitized
    assert "\r" not in sanitized


@pytest.mark.unit
def test_sanitize_dirname_strips_control_chars() -> None:
    name = "dir\nwith\rcontrol"
    sanitized = PathSanitizer.sanitize_dirname(name)
    assert "\n" not in sanitized
    assert "\r" not in sanitized
