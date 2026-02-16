# Example Usages

This document shows common command patterns using the configs in `examples/configs/`.

## 1) Basic H.264 Ladder Run

```bash
uv run python -m bitrate_ladder --config examples/configs/basic_h264.json
```

Use this to validate a simple same-resolution, single-codec run.

## 2) Multi-Resolution + Multi-Codec Run

```bash
uv run python -m bitrate_ladder --config examples/configs/multi_resolution_codecs.json
```

This config already defines `vmaf.evaluation_resolution`, so no CLI override is required.

## 3) Minimal AV1 Run

```bash
uv run python -m bitrate_ladder --config examples/configs/minimal_av1.json
```

Useful for a quick AV1-only sanity check.

## 4) Compare-Ready Run (Keep Encodes)

```bash
uv run python -m bitrate_ladder --config examples/configs/compare_ready.json
```

This config has `runtime.keep_temp=true` and stores artifacts under `out/examples/compare_work`.

## 5) Compare-Ready Run with CLI Overrides

```bash
uv run python -m bitrate_ladder \
  --config examples/configs/compare_ready.json \
  --output out/examples/compare_ready_report_override.json \
  --plots-dir out/examples/compare_ready_plots_override \
  --threads 4
```

Use this when you want to override output paths or runtime constraints without editing config files.

## GUI Compare Tool

Install compare dependencies once:

```bash
uv sync --extra compare
```

### A) Open GUI from the Compare-Ready Report

```bash
uv run python -m bitrate_ladder compare --report out/examples/compare_ready_report.json
```

By default it serves on `http://127.0.0.1:8765` and opens your browser automatically.

### B) Open GUI Without Auto Browser and Custom Port

```bash
uv run python -m bitrate_ladder compare \
  --report out/examples/compare_ready_report.json \
  --no-open-browser \
  --port 9000
```

Then open `http://127.0.0.1:9000` manually.

### C) Use Fallback Encode/VMAF Directories

```bash
uv run python -m bitrate_ladder compare \
  --report out/examples/compare_ready_report.json \
  --encodes-dir out/examples/compare_work/encodes \
  --vmaf-dir out/examples/compare_work/vmaf
```

Use this when report paths are stale or artifacts were moved.

### D) Clear Proxy Cache on Startup

```bash
uv run python -m bitrate_ladder compare \
  --report out/examples/compare_ready_report.json \
  --clear-cache
```

Forces fresh preprocessing proxies for the next compare session.
