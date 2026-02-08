from __future__ import annotations

import subprocess
import time
from pathlib import Path

from .config import VmafConfig
from .metrics import MetricsError, VmafMetrics, parse_vmaf_log


class VmafError(RuntimeError):
    """Raised when libvmaf execution fails."""


def probe_video_fps(video_path: Path, ffprobe_bin: str = "ffprobe") -> str:
    command = [
        ffprobe_bin,
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=avg_frame_rate,r_frame_rate",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(video_path),
    ]
    try:
        proc = subprocess.run(command, capture_output=True, text=True, check=False)
    except FileNotFoundError as exc:
        raise VmafError(f"ffprobe binary not found: {ffprobe_bin}") from exc

    if proc.returncode != 0:
        stderr = (proc.stderr or "").strip()
        raise VmafError(f"Unable to probe frame rate for {video_path.name}: {stderr}")

    lines = [line.strip() for line in (proc.stdout or "").splitlines() if line.strip()]
    for candidate in lines:
        if _is_valid_fps(candidate):
            return candidate
    raise VmafError(f"Could not determine frame rate for {video_path.name}")


def ensure_libvmaf_available(ffmpeg_bin: str = "ffmpeg") -> None:
    try:
        proc = subprocess.run(
            [ffmpeg_bin, "-hide_banner", "-filters"],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as exc:
        raise VmafError(f"ffmpeg binary not found: {ffmpeg_bin}") from exc

    if proc.returncode != 0:
        stderr = (proc.stderr or "").strip()
        raise VmafError(f"Unable to inspect ffmpeg filters: {stderr}")
    output = (proc.stdout or "") + "\n" + (proc.stderr or "")
    if "libvmaf" not in output:
        raise VmafError("ffmpeg does not report libvmaf support")


def compute_vmaf_metrics(
    reference_path: Path,
    distorted_path: Path,
    evaluation_width: int,
    evaluation_height: int,
    evaluation_fps: str,
    config: VmafConfig,
    threads: int,
    log_path: Path,
    ffmpeg_bin: str = "ffmpeg",
) -> tuple[VmafMetrics, float]:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    filter_options = [
        f"log_fmt={config.log_format}",
        f"log_path={_escape_filter_value(str(log_path))}",
        f"n_threads={max(1, threads)}",
    ]
    if config.model_path:
        filter_options.append(f"model=path={_escape_filter_value(str(config.model_path))}")
    filter_options.extend(config.extra_filter_options)

    # Normalize both streams to the same CFR timeline before VMAF.
    filter_graph = (
        f"[0:v]fps={evaluation_fps},scale={evaluation_width}:{evaluation_height}:flags=bicubic,"
        f"settb=AVTB,setpts=N/FRAME_RATE/TB[ref];"
        f"[1:v]fps={evaluation_fps},scale={evaluation_width}:{evaluation_height}:flags=bicubic,"
        f"settb=AVTB,setpts=N/FRAME_RATE/TB[dist];"
        f"[dist][ref]libvmaf={':'.join(filter_options)}"
    )

    command = [
        ffmpeg_bin,
        "-hide_banner",
        "-y",
        "-i",
        str(reference_path),
        "-i",
        str(distorted_path),
        "-lavfi",
        filter_graph,
        "-f",
        "null",
        "-",
    ]
    started = time.monotonic()
    proc = subprocess.run(command, capture_output=True, text=True, check=False)
    elapsed = time.monotonic() - started
    if proc.returncode != 0:
        stderr = (proc.stderr or "").strip()
        raise VmafError(f"libvmaf failed for {distorted_path.name}: {stderr}")

    try:
        return parse_vmaf_log(log_path), elapsed
    except MetricsError as exc:
        raise VmafError(f"Failed to parse VMAF output for {distorted_path.name}") from exc


def _escape_filter_value(value: str) -> str:
    return value.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")


def _is_valid_fps(value: str) -> bool:
    if "/" in value:
        parts = value.split("/")
        if len(parts) != 2:
            return False
        try:
            numerator = float(parts[0])
            denominator = float(parts[1])
        except ValueError:
            return False
        return numerator > 0 and denominator > 0
    try:
        return float(value) > 0
    except ValueError:
        return False
