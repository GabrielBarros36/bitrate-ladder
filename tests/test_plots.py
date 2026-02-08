from __future__ import annotations

from pathlib import Path

import pytest

from bitrate_ladder.plots import PlotError, generate_plots


def test_generate_plots_per_resolution(tmp_path: Path) -> None:
    report = {
        "points": [
            {"id": "p001", "bitrate_kbps": 500, "width": 1280, "height": 720, "codec": "h264", "vmaf_mean": 91.2},
            {"id": "p002", "bitrate_kbps": 1000, "width": 1280, "height": 720, "codec": "h264", "vmaf_mean": 94.1},
            {"id": "p003", "bitrate_kbps": 1400, "width": 1920, "height": 1080, "codec": "h264", "vmaf_mean": 95.0},
            {"id": "p004", "bitrate_kbps": 700, "width": 1280, "height": 720, "codec": "h265", "vmaf_mean": 92.0},
        ],
        "selected_ladder": ["p002", "p003"],
    }
    outputs = generate_plots(report, tmp_path)
    output_names = sorted(path.name for path in outputs)

    assert "rd_curve_h264_all_resolutions.png" in output_names
    assert "rd_curve_h264_all_resolutions.svg" in output_names
    assert "rd_curve_h265_all_resolutions.png" in output_names
    assert "rd_curve_h265_all_resolutions.svg" in output_names
    assert "rd_curve_all_codecs_all_resolutions.png" in output_names
    assert "rd_curve_all_codecs_all_resolutions.svg" in output_names


def test_generate_plots_requires_points(tmp_path: Path) -> None:
    with pytest.raises(PlotError):
        generate_plots({"points": [], "selected_ladder": []}, tmp_path)
