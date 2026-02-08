from __future__ import annotations

import subprocess
import time
from pathlib import Path

from .config import Codec, CodecEncodingSettings, LadderPointConfig


class EncodeError(RuntimeError):
    """Raised when ffmpeg encoding fails."""


_CODEC_LIBRARY: dict[Codec, str] = {
    "h264": "libx264",
    "h265": "libx265",
    "av1": "libaom-av1",
}

_CONTAINER_EXTENSION: dict[Codec, str] = {
    "h264": "mp4",
    "h265": "mp4",
    "av1": "mkv",
}


def output_extension_for_codec(codec: Codec) -> str:
    return _CONTAINER_EXTENSION[codec]


def ensure_ffmpeg_available(ffmpeg_bin: str = "ffmpeg") -> str:
    try:
        proc = subprocess.run(
            [ffmpeg_bin, "-version"],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as exc:
        raise EncodeError(f"ffmpeg binary not found: {ffmpeg_bin}") from exc

    if proc.returncode != 0:
        stderr = (proc.stderr or "").strip()
        raise EncodeError(f"ffmpeg is not executable: {stderr}")

    first_line = (proc.stdout or "").splitlines()
    return first_line[0] if first_line else "ffmpeg (version unknown)"


def encode_rendition(
    source_path: Path,
    point: LadderPointConfig,
    destination_path: Path,
    encoding: CodecEncodingSettings,
    threads: int,
    ffmpeg_bin: str = "ffmpeg",
) -> float:
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    codec_lib = _CODEC_LIBRARY[point.codec]
    bitrate = f"{point.bitrate_kbps}k"
    command = [
        ffmpeg_bin,
        "-hide_banner",
        "-y",
        "-i",
        str(source_path),
        "-an",
        "-vf",
        f"scale={point.width}:{point.height}:flags=lanczos",
        "-c:v",
        codec_lib,
        "-b:v",
        bitrate,
        "-maxrate",
        bitrate,
        "-bufsize",
        f"{point.bitrate_kbps * 2}k",
        "-threads",
        str(max(1, threads)),
    ]

    if point.codec in {"h264", "h265"}:
        preset = encoding.preset or "medium"
        command.extend(["-preset", preset])
    else:
        # libaom uses cpu-used instead of preset.
        command.extend(["-cpu-used", encoding.preset or "6", "-row-mt", "1"])

    if encoding.profile:
        command.extend(["-profile:v", encoding.profile])
    if encoding.pix_fmt:
        command.extend(["-pix_fmt", encoding.pix_fmt])
    if encoding.keyint:
        command.extend(["-g", str(encoding.keyint), "-keyint_min", str(encoding.keyint)])

    command.append(str(destination_path))

    started = time.monotonic()
    proc = subprocess.run(command, capture_output=True, text=True, check=False)
    elapsed = time.monotonic() - started
    if proc.returncode != 0:
        stderr = (proc.stderr or "").strip()
        raise EncodeError(
            f"Encoding failed for {point.codec} {point.width}x{point.height} @{point.bitrate_kbps}kbps: {stderr}"
        )
    return elapsed
