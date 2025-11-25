from __future__ import annotations

import types


def test_cli_legacy_main_points_to_new_cli() -> None:
    import src.cli as new_cli
    import src.cli_legacy as legacy

    assert isinstance(legacy.main, types.FunctionType)
    assert legacy.main is new_cli.main
