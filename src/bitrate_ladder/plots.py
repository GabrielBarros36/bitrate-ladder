from __future__ import annotations

from pathlib import Path
from typing import Any


class PlotError(RuntimeError):
    """Raised when plot generation fails."""


def generate_plots(report: dict[str, Any], plots_dir: Path) -> list[Path]:
    try:
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise PlotError(
            "Plot generation requires matplotlib. Install it and run again."
        ) from exc

    points = report.get("points", [])
    if not isinstance(points, list) or not points:
        raise PlotError("Report does not contain any points to plot")

    selected_ids = set(report.get("selected_ladder", []))
    plots_dir.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []

    by_resolution: dict[tuple[int, int], list[dict[str, Any]]] = {}
    for point in points:
        key = (int(point["width"]), int(point["height"]))
        by_resolution.setdefault(key, []).append(point)

    for (width, height), resolution_points in sorted(by_resolution.items()):
        resolution_points.sort(key=lambda item: item["bitrate_kbps"])
        selected_points = [
            point for point in resolution_points if point.get("id") in selected_ids
        ]

        fig, ax = plt.subplots(figsize=(8, 5))
        ax.plot(
            [point["bitrate_kbps"] for point in resolution_points],
            [point["vmaf_mean"] for point in resolution_points],
            marker="o",
            linewidth=1.8,
            label=f"All {width}x{height}",
            color="tab:blue",
        )
        if selected_points:
            ax.scatter(
                [point["bitrate_kbps"] for point in selected_points],
                [point["vmaf_mean"] for point in selected_points],
                color="tab:orange",
                s=80,
                label="Selected Ladder",
                zorder=3,
            )
        ax.set_xlabel("Bitrate (kbps)")
        ax.set_ylabel("VMAF")
        ax.set_title(f"RD Curve {width}x{height}")
        ax.grid(True, alpha=0.25)
        ax.legend(loc="lower right")

        base_name = f"rd_curve_{width}x{height}"
        output_png = plots_dir / f"{base_name}.png"
        output_svg = plots_dir / f"{base_name}.svg"
        fig.tight_layout()
        fig.savefig(output_png, dpi=160)
        fig.savefig(output_svg)
        plt.close(fig)
        outputs.extend([output_png, output_svg])

    # Overlay chart for comparing all resolutions on one plot.
    fig, ax = plt.subplots(figsize=(9, 6))
    cmap = plt.get_cmap("tab10")
    for idx, ((width, height), resolution_points) in enumerate(sorted(by_resolution.items())):
        color = cmap(idx % 10)
        resolution_points.sort(key=lambda item: item["bitrate_kbps"])
        ax.plot(
            [point["bitrate_kbps"] for point in resolution_points],
            [point["vmaf_mean"] for point in resolution_points],
            marker="o",
            linewidth=1.8,
            color=color,
            label=f"{width}x{height}",
        )

        selected_points = [
            point for point in resolution_points if point.get("id") in selected_ids
        ]
        if selected_points:
            ax.scatter(
                [point["bitrate_kbps"] for point in selected_points],
                [point["vmaf_mean"] for point in selected_points],
                marker="X",
                s=70,
                color=color,
                edgecolors="black",
                linewidths=0.5,
                zorder=3,
            )

    ax.set_xlabel("Bitrate (kbps)")
    ax.set_ylabel("VMAF")
    ax.set_title("RD Curve Comparison (All Resolutions)")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="lower right", title="Resolution")
    overlay_png = plots_dir / "rd_curve_all_resolutions.png"
    overlay_svg = plots_dir / "rd_curve_all_resolutions.svg"
    fig.tight_layout()
    fig.savefig(overlay_png, dpi=160)
    fig.savefig(overlay_svg)
    plt.close(fig)
    outputs.extend([overlay_png, overlay_svg])
    return outputs
