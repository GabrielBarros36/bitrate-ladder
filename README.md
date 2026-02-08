# bitrate-ladder

CLI for generating bitrate ladders from explicit bitrate-resolution points using FFmpeg + VMAF and upper convex hull selection.

## Getting Started Requirements

- Python 3.11+
- `uv`
- `ffmpeg` with `libvmaf` enabled (on macOS, `brew install ffmpeg-full`)

## Quick Start

```bash
uv run python -m bitrate_ladder --config path/to/config.json
```

Required config fields:
- `input.source_path`
- `ladder.points` (list of `{ bitrate_kbps, width, height, codec }`)

Important for multi-resolution ladders:
- Set `vmaf.evaluation_resolution` in config (for example, `"1920x1080"`), or pass `--evaluation-resolution 1920x1080`.
