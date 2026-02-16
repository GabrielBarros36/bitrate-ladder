# GUI Compare Module

## Overview

The compare module launches a local web app for visual encode comparisons from a ladder report.

Modes:
- Tile mode (2-4 videos)
- Wipe mode (2 videos with vertical split)

## Launch

```bash
uv sync --extra compare
uv run python -m bitrate_ladder compare --report out/report.json
```

Recommended: generate report with retained artifacts:

```bash
uv run python -m bitrate_ladder --config config.json --keep-temp
```

## Path Resolution

The compare session uses:
- `source.path` from report
- `points[].encode_path`
- `points[].vmaf_log_path`

If these are missing or stale, use:
- `--encodes-dir` and `--vmaf-dir` fallback flags
- Repair panel in the UI

## Preprocessing and Cache

Before playback, selected assets are transcoded to aligned H.264 MP4 proxies with shared:
- resolution
- fps
- duration (trimmed to shortest input)

Cache location defaults to `<runtime.work_dir>/compare_cache` and can be cleared with:
- CLI `--clear-cache`
- UI `Clear cache` button

## Troubleshooting

- If compare command fails with missing dependencies:
  - run `uv sync --extra compare`
- If no videos can be prepared:
  - fix missing paths in repair panel
  - verify ffmpeg/ffprobe are available
- If frame-level overlay is empty:
  - ensure selected points have valid `vmaf_log_path` files
