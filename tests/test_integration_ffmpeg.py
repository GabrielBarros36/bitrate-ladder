from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from bitrate_ladder.cli import run_pipeline
from bitrate_ladder.config import load_config


def _ffmpeg_has_libvmaf() -> bool:
    try:
        proc = subprocess.run(
            ["ffmpeg", "-hide_banner", "-filters"],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return False
    if proc.returncode != 0:
        return False
    return "libvmaf" in ((proc.stdout or "") + (proc.stderr or ""))


@pytest.mark.integration
def test_end_to_end_with_fixture_video(tmp_path: Path) -> None:
    if not _ffmpeg_has_libvmaf():
        pytest.skip("ffmpeg with libvmaf is not available")

    source = tmp_path / "source.mp4"
    create_source = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=320x180:rate=24",
            "-t",
            "1",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(source),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if create_source.returncode != 0:
        pytest.skip("Unable to create ffmpeg fixture video in this environment")

    report_path = tmp_path / "out/report.json"
    plots_dir = tmp_path / "out/plots"
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "input": {"source_path": str(source)},
                "ladder": {
                    "points": [
                        {"bitrate_kbps": 300, "width": 160, "height": 90, "codec": "h264"},
                        {"bitrate_kbps": 700, "width": 320, "height": 180, "codec": "h264"},
                    ]
                },
                "vmaf": {"evaluation_resolution": "320x180"},
                "runtime": {"threads": 1},
            }
        ),
        encoding="utf-8",
    )
    config = load_config(config_path)
    report = run_pipeline(config, output_path=report_path, plots_dir=plots_dir)

    assert report_path.exists()
    assert report["selected_ladder"]
    assert (plots_dir / "rd_curve_h264_all_resolutions.png").exists()
    assert (plots_dir / "rd_curve_all_codecs_all_resolutions.svg").exists()
