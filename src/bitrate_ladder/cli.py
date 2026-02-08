from __future__ import annotations

import argparse
import shutil
import sys
import time
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from .config import (
    AppConfig,
    ConfigError,
    load_config,
    parse_resolution_string,
)
from .encode import EncodeError, encode_rendition, ensure_ffmpeg_available, output_extension_for_codec
from .ladder import LadderSelection, RatedPoint, select_ladder
from .plots import PlotError, generate_plots
from .report import build_report, probe_source_metadata, write_report
from .vmaf import VmafError, compute_vmaf_metrics, ensure_libvmaf_available


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bitrate-ladder",
        description="Generate bitrate ladders using VMAF + upper convex hull selection.",
    )
    parser.add_argument("--config", required=True, help="Path to YAML/JSON config file")
    parser.add_argument(
        "--output",
        default=None,
        help="Output report JSON path (default: config output.report_path or out/report.json)",
    )
    parser.add_argument(
        "--plots-dir",
        default=None,
        help="Directory to write PNG/SVG plots (optional)",
    )
    parser.add_argument(
        "--work-dir",
        default=None,
        help="Directory for temporary encodes and VMAF logs",
    )
    parser.add_argument(
        "--keep-temp",
        action="store_true",
        default=False,
        help="Keep intermediate encoded files and VMAF logs",
    )
    parser.add_argument(
        "--threads",
        type=int,
        default=None,
        help="Encoding/VMAF thread count (default: cpu count or config.runtime.threads)",
    )
    parser.add_argument(
        "--evaluation-resolution",
        default=None,
        help=(
            "VMAF evaluation resolution as <width>x<height>. Required when ladder points "
            "contain multiple resolutions unless set in config vmaf.evaluation_resolution."
        ),
    )
    return parser


def run_pipeline(
    config: AppConfig,
    *,
    output_path: Path | None = None,
    plots_dir: Path | None = None,
    work_dir: Path | None = None,
    keep_temp: bool | None = None,
    threads: int | None = None,
    evaluation_resolution: tuple[int, int] | None = None,
    ffmpeg_bin: str = "ffmpeg",
    ffprobe_bin: str = "ffprobe",
) -> dict:
    effective_output = config.output
    if output_path is not None or plots_dir is not None:
        effective_output = replace(
            effective_output,
            report_path=output_path if output_path is not None else effective_output.report_path,
            plots_dir=plots_dir if plots_dir is not None else effective_output.plots_dir,
        )

    effective_runtime = config.runtime
    runtime_keep_temp = keep_temp if keep_temp is not None else effective_runtime.keep_temp
    if work_dir is not None or keep_temp is not None or threads is not None:
        effective_runtime = replace(
            effective_runtime,
            work_dir=work_dir if work_dir is not None else effective_runtime.work_dir,
            keep_temp=runtime_keep_temp,
            threads=threads if threads is not None else effective_runtime.threads,
        )

    if effective_runtime.threads <= 0:
        raise ConfigError("threads must be a positive integer")

    unique_resolutions = {(point.width, point.height) for point in config.points}
    effective_evaluation_resolution = (
        evaluation_resolution
        if evaluation_resolution is not None
        else config.vmaf.evaluation_resolution
    )
    if len(unique_resolutions) > 1 and effective_evaluation_resolution is None:
        raise ConfigError(
            "Multiple ladder resolutions detected. Set vmaf.evaluation_resolution in config "
            "or pass --evaluation-resolution <width>x<height>."
        )
    if effective_evaluation_resolution is None:
        effective_evaluation_resolution = next(iter(unique_resolutions))
    evaluation_width, evaluation_height = effective_evaluation_resolution

    ffmpeg_version = ensure_ffmpeg_available(ffmpeg_bin=ffmpeg_bin)
    ensure_libvmaf_available(ffmpeg_bin=ffmpeg_bin)

    encodes_dir = effective_runtime.work_dir / "encodes"
    vmaf_dir = effective_runtime.work_dir / "vmaf"
    encodes_dir.mkdir(parents=True, exist_ok=True)
    vmaf_dir.mkdir(parents=True, exist_ok=True)
    start = time.monotonic()
    started_at = datetime.now(timezone.utc)

    points_report: list[dict] = []
    rated_points: list[RatedPoint] = []
    for idx, point in enumerate(config.points, start=1):
        point_id = f"p{idx:03d}"
        extension = output_extension_for_codec(point.codec)
        encode_path = encodes_dir / f"{point_id}.{extension}"
        vmaf_log_path = vmaf_dir / f"{point_id}.json"

        encoding_settings = config.encoding.resolve(point.codec)
        encode_seconds = encode_rendition(
            config.source_path,
            point,
            encode_path,
            encoding_settings,
            threads=effective_runtime.threads,
            ffmpeg_bin=ffmpeg_bin,
        )

        vmaf_metrics, vmaf_seconds = compute_vmaf_metrics(
            config.source_path,
            encode_path,
            evaluation_width=evaluation_width,
            evaluation_height=evaluation_height,
            config=config.vmaf,
            threads=effective_runtime.threads,
            log_path=vmaf_log_path,
            ffmpeg_bin=ffmpeg_bin,
        )

        point_row = {
            "id": point_id,
            "bitrate_kbps": point.bitrate_kbps,
            "width": point.width,
            "height": point.height,
            "codec": point.codec,
            "vmaf_mean": vmaf_metrics.mean,
            "vmaf_min": vmaf_metrics.minimum,
            "vmaf_max": vmaf_metrics.maximum,
            "vmaf_p95": vmaf_metrics.p95,
            "frame_count": vmaf_metrics.frame_count,
            "timings": {
                "encode_seconds": encode_seconds,
                "vmaf_seconds": vmaf_seconds,
            },
            "evaluation_resolution": {
                "width": evaluation_width,
                "height": evaluation_height,
            },
        }
        if effective_runtime.keep_temp:
            point_row["encode_path"] = str(encode_path)
            point_row["vmaf_log_path"] = str(vmaf_log_path)

        points_report.append(point_row)
        rated_points.append(
            RatedPoint(
                point_id=point_id,
                bitrate_kbps=point.bitrate_kbps,
                vmaf=vmaf_metrics.mean,
            )
        )

    selection: LadderSelection = select_ladder(rated_points)

    source_metadata = probe_source_metadata(config.source_path, ffprobe_bin=ffprobe_bin)
    elapsed = time.monotonic() - start
    runtime = {
        "started_at": started_at.isoformat(),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "total_seconds": elapsed,
        "threads": effective_runtime.threads,
        "work_dir": str(effective_runtime.work_dir),
        "keep_temp": effective_runtime.keep_temp,
        "evaluation_resolution": f"{evaluation_width}x{evaluation_height}",
        "ffmpeg_version": ffmpeg_version,
    }
    report = build_report(
        source_path=config.source_path,
        source_metadata=source_metadata,
        points=points_report,
        selection=selection,
        runtime=runtime,
    )
    write_report(report, effective_output.report_path)

    if effective_output.plots_dir is not None:
        plot_paths = generate_plots(report, effective_output.plots_dir)
        report["runtime"]["plot_outputs"] = [str(path) for path in plot_paths]
        write_report(report, effective_output.report_path)

    if not effective_runtime.keep_temp:
        shutil.rmtree(encodes_dir, ignore_errors=True)
        shutil.rmtree(vmaf_dir, ignore_errors=True)
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    try:
        config = load_config(args.config)
        output_path = Path(args.output).resolve() if args.output else None
        plots_dir = Path(args.plots_dir).resolve() if args.plots_dir else None
        work_dir = Path(args.work_dir).resolve() if args.work_dir else None
        threads = args.threads
        keep_temp = args.keep_temp if args.keep_temp else None
        evaluation_resolution = (
            parse_resolution_string(args.evaluation_resolution, field_name="--evaluation-resolution")
            if args.evaluation_resolution
            else None
        )

        report = run_pipeline(
            config,
            output_path=output_path,
            plots_dir=plots_dir,
            work_dir=work_dir,
            keep_temp=keep_temp,
            threads=threads,
            evaluation_resolution=evaluation_resolution,
        )
    except (ConfigError, EncodeError, VmafError, PlotError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    resolved_report_path = output_path if output_path is not None else config.output.report_path
    selected_ids = report.get("selected_ladder", [])
    total_points = len(report.get("points", []))
    total_seconds = float(report.get("runtime", {}).get("total_seconds", 0.0))
    plot_outputs = report.get("runtime", {}).get("plot_outputs", [])
    plot_count = len(plot_outputs) if isinstance(plot_outputs, list) else 0

    message = (
        f"Success: evaluated {total_points} points, selected {len(selected_ids)} hull points, "
        f"runtime {total_seconds:.1f}s, report={resolved_report_path}"
    )
    if plot_count:
        message += f", plots={plot_count}"
    print(message)

    if selected_ids:
        preview_count = 8
        selected_preview = ", ".join(selected_ids[:preview_count])
        if len(selected_ids) > preview_count:
            selected_preview += ", ..."
        print(f"Selected IDs: {selected_preview}")
    return 0
