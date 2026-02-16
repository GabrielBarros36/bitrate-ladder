from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from typing import Sequence


class PreprocessError(RuntimeError):
    """Raised when preprocessing for compare playback fails."""


def prepare_aligned_assets(
    input_paths: Sequence[Path],
    *,
    evaluation_width: int,
    evaluation_height: int,
    evaluation_fps: str,
    cache_dir: Path,
    ffmpeg_bin: str = "ffmpeg",
    ffprobe_bin: str = "ffprobe",
) -> tuple[list[Path], float]:
    if len(input_paths) < 2:
        raise PreprocessError("At least two assets are required for preprocessing")

    resolved_inputs = [path.expanduser().resolve() for path in input_paths]
    for path in resolved_inputs:
        if not path.exists():
            raise PreprocessError(f"Input asset not found: {path}")

    durations = [probe_duration_seconds(path, ffprobe_bin=ffprobe_bin) for path in resolved_inputs]
    common_duration = min(durations)
    if common_duration <= 0:
        raise PreprocessError("Unable to determine a valid shared duration for compared assets")

    cache_key = build_cache_key(
        resolved_inputs,
        evaluation_width=evaluation_width,
        evaluation_height=evaluation_height,
        evaluation_fps=evaluation_fps,
        common_duration=common_duration,
    )
    set_dir = cache_dir / "sets" / cache_key
    set_dir.mkdir(parents=True, exist_ok=True)

    outputs = [set_dir / f"asset_{index + 1}.mp4" for index in range(len(resolved_inputs))]
    metadata_path = set_dir / "metadata.json"

    if metadata_path.exists() and all(path.exists() for path in outputs):
        return outputs, common_duration

    fps_float = _fps_to_float(evaluation_fps)
    gop_size = max(1, int(round(fps_float)))
    vf_filter = (
        f"fps={evaluation_fps},"
        f"scale={evaluation_width}:{evaluation_height}:flags=lanczos,"
        "format=yuv420p,settb=AVTB,setpts=N/FRAME_RATE/TB"
    )

    for source_path, output_path in zip(resolved_inputs, outputs):
        command = [
            ffmpeg_bin,
            "-hide_banner",
            "-y",
            "-i",
            str(source_path),
            "-an",
            "-t",
            f"{common_duration:.6f}",
            "-vf",
            vf_filter,
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "12",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            "-g",
            str(gop_size),
            "-keyint_min",
            str(gop_size),
            "-sc_threshold",
            "0",
            str(output_path),
        ]
        proc = subprocess.run(command, capture_output=True, text=True, check=False)
        if proc.returncode != 0:
            stderr = (proc.stderr or "").strip()
            raise PreprocessError(f"Failed to build compare proxy for {source_path.name}: {stderr}")

    metadata = {
        "cache_key": cache_key,
        "inputs": [str(path) for path in resolved_inputs],
        "outputs": [str(path) for path in outputs],
        "evaluation_resolution": {
            "width": evaluation_width,
            "height": evaluation_height,
        },
        "evaluation_fps": evaluation_fps,
        "duration_seconds": common_duration,
    }
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return outputs, common_duration


def clear_cache_dir(cache_dir: Path) -> None:
    if not cache_dir.exists():
        return
    shutil.rmtree(cache_dir, ignore_errors=True)


def build_cache_key(
    input_paths: Sequence[Path],
    *,
    evaluation_width: int,
    evaluation_height: int,
    evaluation_fps: str,
    common_duration: float,
) -> str:
    fingerprint = {
        "inputs": [_file_fingerprint(path) for path in input_paths],
        "evaluation_width": evaluation_width,
        "evaluation_height": evaluation_height,
        "evaluation_fps": evaluation_fps,
        "common_duration": f"{common_duration:.6f}",
    }
    encoded = json.dumps(fingerprint, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]


def probe_duration_seconds(path: Path, ffprobe_bin: str = "ffprobe") -> float:
    command = [
        ffprobe_bin,
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(path),
    ]
    try:
        proc = subprocess.run(command, capture_output=True, text=True, check=False)
    except FileNotFoundError as exc:
        raise PreprocessError(f"ffprobe binary not found: {ffprobe_bin}") from exc

    if proc.returncode != 0:
        stderr = (proc.stderr or "").strip()
        raise PreprocessError(f"Unable to probe duration for {path.name}: {stderr}")

    value = (proc.stdout or "").strip()
    try:
        duration = float(value)
    except ValueError as exc:
        raise PreprocessError(f"Unable to parse duration for {path.name}: {value}") from exc

    if duration <= 0:
        raise PreprocessError(f"Duration for {path.name} must be positive")
    return duration


def _file_fingerprint(path: Path) -> dict[str, str | int]:
    stats = path.stat()
    return {
        "path": str(path),
        "size": stats.st_size,
        "mtime_ns": stats.st_mtime_ns,
    }


def _fps_to_float(value: str) -> float:
    cleaned = value.strip()
    if "/" in cleaned:
        numerator_str, denominator_str = cleaned.split("/", maxsplit=1)
        numerator = float(numerator_str)
        denominator = float(denominator_str)
        if denominator <= 0:
            raise PreprocessError(f"Invalid evaluation_fps: {value}")
        fps = numerator / denominator
    else:
        fps = float(cleaned)

    if fps <= 0:
        raise PreprocessError(f"Invalid evaluation_fps: {value}")
    return fps
