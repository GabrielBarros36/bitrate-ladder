# Bitrate Ladder Project Plan

## Overview

Build a Python CLI that generates bitrate ladders using VMAF metrics for user‑specified bitrate‑resolution pairs. The tool must run entirely on‑device and must not depend on network services. Ladder selection is based on the upper convex hull in bitrate–VMAF space, with BD‑Rate used as a tie‑break when multiple candidates compete. The tool produces a JSON report and an optional plotting module that outputs PNG and SVG charts.

## Goals

- On‑device encoding, VMAF scoring, and ladder selection.
- Deterministic JSON output describing all evaluated points and selected ladder.
- Support H.264, H.265, and AV1 encoding.
- Generate plots from JSON results (PNG + SVG).
- Use `uv` for all package management and execution.

## Non‑Goals

- Cloud or distributed encoding.
- GUI applications.
- Dynamic bitrate/rendition discovery outside the provided config.

## System Requirements

- Python 3.
- `ffmpeg` with `libvmaf` available on the device.
- `uv` for dependency management and running the CLI.

## Repository Structure

- `src/`: core library and CLI entry point.
  - `cli.py`: argument parsing and orchestration.
  - `config.py`: YAML/JSON config validation and defaults.
  - `encode.py`: encode a rendition for a specific bitrate/resolution/codec.
  - `vmaf.py`: compute VMAF metrics using FFmpeg/libvmaf.
  - `metrics.py`: parse VMAF outputs into structured metrics.
  - `ladder.py`: convex hull computation and BD‑Rate tie‑break logic.
  - `report.py`: JSON report builder.
  - `plots.py`: plot generator (PNG + SVG) from JSON results.
- `tests/`: unit and integration tests.
- `docs/PLAN.md`: this project plan.

## CLI Specification

Planned invocation (module name to be finalized):
- `uv run python -m <module> --config path/to/config.yaml --output out/report.json --plots-dir out/plots`

Flags:
- `--config` (required): YAML or JSON config path.
- `--output` (optional): JSON report output path; default `out/report.json`.
- `--plots-dir` (optional): if set, generate PNG + SVG plots.
- `--work-dir` (optional): directory for intermediate encodes/logs.
- `--keep-temp` (optional): keep encoded renditions and intermediates.
- `--threads` (optional): encoder/VMAF parallelism; default CPU count.
- `--evaluation-resolution` (optional): VMAF evaluation resolution in `<width>x<height>` format; required when config points contain multiple resolutions and `vmaf.evaluation_resolution` is not set.

Exit codes:
- `0` success.
- Non‑zero on validation, encoding, or VMAF failures.

## Configuration Schema

YAML or JSON with the following top‑level fields:

- `input.source_path` (string, required): source video path.
- `ladder.points` (list, required): explicit list of renditions.
  - Each item: `{ bitrate_kbps, width, height, codec }`.
  - `codec` in `{ h264, h265, av1 }`.
- `encoding` (object, optional): codec defaults (preset, profile, pix_fmt, keyint).
- `vmaf` (object, optional): model selection, log format, additional args.
  - `evaluation_resolution` (string, conditionally required): shared VMAF evaluation resolution in `<width>x<height>` format for cross-resolution comparisons.
- `output` (object, optional): `report_path`, `plots_dir`.
- `runtime` (object, optional): `threads`, `work_dir`, `keep_temp`.

## Processing Pipeline

1. Validate config and input file presence.
2. For each ladder point:
   - Encode via FFmpeg at requested bitrate/resolution/codec.
   - Compute VMAF versus the reference at a shared evaluation resolution (both streams scaled to `vmaf.evaluation_resolution` / `--evaluation-resolution` for multi-resolution ladders).
   - Record metrics (mean/min/max/p95).
3. Build RD curve in bitrate–VMAF space.
4. Compute upper convex hull.
5. Apply BD‑Rate tie‑breaks when multiple points overlap or compete on a hull segment.
6. Emit JSON report.
7. If `plots_dir` is set, generate PNG + SVG plots.

## Convex Hull and BD‑Rate Tie‑Breaks

- Primary selection is the upper convex hull in (bitrate, VMAF) space.
- When multiple candidates are equivalent or collinear on a segment, compute BD‑Rate between candidate curves and the hull fit; keep the point set with the lowest BD‑Rate.

## Output JSON Schema

Top‑level fields:
- `source`: source path and any extracted metadata.
- `points`: list of all evaluated renditions with metrics.
- `selected_ladder`: ordered list of selected point IDs.
- `hull`: hull points and segments.
- `runtime`: timings and tool versions.

Per‑point fields:
- `bitrate_kbps`, `width`, `height`, `codec`.
- `vmaf_mean`, `vmaf_min`, `vmaf_max`, `vmaf_p95`.
- `encode_path` (only when `keep_temp` is set).

## Plotting Module

Inputs:
- JSON report produced by the CLI.

Outputs (PNG + SVG):
- `rd_curve.*`: bitrate vs VMAF.
- `ladder_selected.*`: highlight selected ladder points vs all points.

## Error Handling and Logging

- Fail fast if `ffmpeg`/`libvmaf` are missing.
- Validate positive bitrates and non‑zero dimensions.
- Log per‑point failures; default behavior is to stop on first failure.

## Testing Strategy

- Unit tests:
  - Config validation.
  - Convex hull and BD‑Rate tie‑break logic.
  - JSON report structure validation.
- Integration tests:
  - Small fixture video with 2–3 ladder points.
  - End‑to‑end run producing JSON + plots.

## Open Decisions

- Exact CLI module/package name.
- Specific FFmpeg parameter defaults per codec.
