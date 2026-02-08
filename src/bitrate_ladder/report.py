from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .ladder import LadderSelection


def probe_source_metadata(source_path: Path, ffprobe_bin: str = "ffprobe") -> dict[str, Any]:
    command = [
        ffprobe_bin,
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(source_path),
    ]
    try:
        proc = subprocess.run(command, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        return {}
    if proc.returncode != 0:
        return {}
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {}

    metadata: dict[str, Any] = {}
    streams = payload.get("streams")
    if isinstance(streams, list):
        video_stream = next(
            (stream for stream in streams if isinstance(stream, dict) and stream.get("codec_type") == "video"),
            None,
        )
        if isinstance(video_stream, dict):
            for key in ("codec_name", "width", "height", "pix_fmt", "r_frame_rate"):
                value = video_stream.get(key)
                if value is not None:
                    metadata[key] = value
    fmt = payload.get("format")
    if isinstance(fmt, dict):
        duration = fmt.get("duration")
        bit_rate = fmt.get("bit_rate")
        if duration is not None:
            metadata["duration"] = duration
        if bit_rate is not None:
            metadata["bit_rate"] = bit_rate
    return metadata


def build_report(
    source_path: Path,
    source_metadata: dict[str, Any],
    points: list[dict[str, Any]],
    selection: LadderSelection,
    runtime: dict[str, Any],
) -> dict[str, Any]:
    hull_segments = []
    for left, right in zip(selection.hull_points, selection.hull_points[1:]):
        hull_segments.append(
            {
                "from": left.point_id,
                "to": right.point_id,
                "slope": (right.vmaf - left.vmaf) / (right.bitrate_kbps - left.bitrate_kbps),
            }
        )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": {
            "path": str(source_path),
            "metadata": source_metadata,
        },
        "points": points,
        "selected_ladder": selection.selected_ids,
        "hull": {
            "points": [
                {
                    "id": point.point_id,
                    "bitrate_kbps": point.bitrate_kbps,
                    "vmaf_mean": point.vmaf,
                }
                for point in selection.hull_points
            ],
            "segments": hull_segments,
        },
        "runtime": runtime,
    }


def write_report(report: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, sort_keys=False), encoding="utf-8")
