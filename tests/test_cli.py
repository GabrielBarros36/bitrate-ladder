from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType

import pytest

import bitrate_ladder.cli as cli
from bitrate_ladder.cli import run_pipeline
from bitrate_ladder.config import AppConfig, ConfigError, LadderPointConfig


def test_multi_resolution_requires_evaluation_resolution(tmp_path: Path) -> None:
    source = tmp_path / "source.mp4"
    source.write_bytes(b"fake")
    config = AppConfig(
        source_path=source,
        points=[
            LadderPointConfig(bitrate_kbps=300, width=640, height=360, codec="h264"),
            LadderPointConfig(bitrate_kbps=900, width=1280, height=720, codec="h264"),
        ],
    )

    with pytest.raises(ConfigError, match="Multiple ladder resolutions detected"):
        run_pipeline(config)


def test_main_dispatches_compare_subcommand(monkeypatch: pytest.MonkeyPatch) -> None:
    compare_module = ModuleType("bitrate_ladder.compare.cli")
    compare_calls: list[list[str]] = []

    def _fake_compare_main(args: list[str]) -> int:
        compare_calls.append(args)
        return 0

    compare_module.main = _fake_compare_main  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "bitrate_ladder.compare.cli", compare_module)

    exit_code = cli.main(["compare", "--report", "report.json"])

    assert exit_code == 0
    assert compare_calls == [["--report", "report.json"]]
