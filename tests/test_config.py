from __future__ import annotations

import json
from pathlib import Path

import pytest

from bitrate_ladder.config import ConfigError, load_config


def _write_source(tmp_path: Path) -> Path:
    source = tmp_path / "source.mp4"
    source.write_bytes(b"fake")
    return source


def test_load_valid_json_config(tmp_path: Path) -> None:
    source = _write_source(tmp_path)
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "input": {"source_path": str(source)},
                "ladder": {
                    "points": [
                        {"bitrate_kbps": 500, "width": 640, "height": 360, "codec": "h264"},
                        {"bitrate_kbps": 1000, "width": 1280, "height": 720, "codec": "h265"},
                    ]
                },
                "runtime": {"threads": 2},
            }
        ),
        encoding="utf-8",
    )

    config = load_config(config_path)
    assert config.source_path == source
    assert len(config.points) == 2
    assert config.points[0].codec == "h264"
    assert config.runtime.threads == 2


def test_invalid_point_bitrate_raises(tmp_path: Path) -> None:
    source = _write_source(tmp_path)
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "input": {"source_path": str(source)},
                "ladder": {
                    "points": [{"bitrate_kbps": 0, "width": 640, "height": 360, "codec": "h264"}]
                },
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ConfigError):
        load_config(config_path)


def test_invalid_codec_raises(tmp_path: Path) -> None:
    source = _write_source(tmp_path)
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "input": {"source_path": str(source)},
                "ladder": {
                    "points": [{"bitrate_kbps": 600, "width": 640, "height": 360, "codec": "vp9"}]
                },
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ConfigError):
        load_config(config_path)


def test_vmaf_evaluation_resolution_is_parsed(tmp_path: Path) -> None:
    source = _write_source(tmp_path)
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "input": {"source_path": str(source)},
                "ladder": {
                    "points": [{"bitrate_kbps": 600, "width": 640, "height": 360, "codec": "h264"}]
                },
                "vmaf": {"evaluation_resolution": "1920x1080"},
            }
        ),
        encoding="utf-8",
    )

    config = load_config(config_path)
    assert config.vmaf.evaluation_resolution == (1920, 1080)


def test_vmaf_evaluation_resolution_invalid_format_raises(tmp_path: Path) -> None:
    source = _write_source(tmp_path)
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "input": {"source_path": str(source)},
                "ladder": {
                    "points": [{"bitrate_kbps": 600, "width": 640, "height": 360, "codec": "h264"}]
                },
                "vmaf": {"evaluation_resolution": "foo"},
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ConfigError):
        load_config(config_path)
