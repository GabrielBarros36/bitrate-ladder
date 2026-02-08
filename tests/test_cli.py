from __future__ import annotations

from pathlib import Path

import pytest

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
