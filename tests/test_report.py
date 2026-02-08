from __future__ import annotations

from pathlib import Path

from bitrate_ladder.ladder import LadderSelection, RatedPoint
from bitrate_ladder.report import build_report


def test_build_report_shape(tmp_path: Path) -> None:
    source_path = tmp_path / "source.mp4"
    source_path.write_bytes(b"video")
    points = [
        {
            "id": "p001",
            "bitrate_kbps": 500,
            "width": 640,
            "height": 360,
            "codec": "h264",
            "vmaf_mean": 80.0,
            "vmaf_min": 72.0,
            "vmaf_max": 86.0,
            "vmaf_p95": 84.0,
        },
        {
            "id": "p002",
            "bitrate_kbps": 1000,
            "width": 1280,
            "height": 720,
            "codec": "h264",
            "vmaf_mean": 90.0,
            "vmaf_min": 84.0,
            "vmaf_max": 95.0,
            "vmaf_p95": 94.0,
        },
    ]
    selection = LadderSelection(
        selected_ids=["p001", "p002"],
        hull_points=[RatedPoint("p001", 500, 80.0), RatedPoint("p002", 1000, 90.0)],
    )
    runtime = {"threads": 4, "total_seconds": 1.2}
    metadata = {"codec_name": "h264"}
    report = build_report(source_path, metadata, points, selection, runtime)

    assert report["source"]["path"] == str(source_path)
    assert report["source"]["metadata"]["codec_name"] == "h264"
    assert report["selected_ladder"] == ["p001", "p002"]
    assert report["hull"]["points"][0]["id"] == "p001"
    assert len(report["hull"]["segments"]) == 1
