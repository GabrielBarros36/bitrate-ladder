from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


class MetricsError(ValueError):
    """Raised when VMAF logs cannot be parsed."""


@dataclass(frozen=True)
class VmafMetrics:
    mean: float
    minimum: float
    maximum: float
    p95: float
    frame_count: int


def parse_vmaf_log(path: Path) -> VmafMetrics:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise MetricsError(f"Could not read VMAF log: {path}") from exc
    except json.JSONDecodeError as exc:
        raise MetricsError(f"Invalid VMAF JSON log: {path}") from exc
    return parse_vmaf_payload(payload)


def parse_vmaf_payload(payload: dict) -> VmafMetrics:
    if not isinstance(payload, dict):
        raise MetricsError("VMAF payload must be an object")

    values: list[float] = []
    frames = payload.get("frames", [])
    if isinstance(frames, list):
        for frame in frames:
            if not isinstance(frame, dict):
                continue
            metrics = frame.get("metrics")
            if not isinstance(metrics, dict):
                continue
            value = metrics.get("vmaf")
            if isinstance(value, (int, float)):
                values.append(float(value))

    if not values:
        pooled = payload.get("pooled_metrics")
        if isinstance(pooled, dict):
            vmaf_pooled = pooled.get("vmaf")
            if isinstance(vmaf_pooled, dict):
                mean = _as_float(vmaf_pooled.get("mean"))
                minimum = _as_float(vmaf_pooled.get("min"))
                maximum = _as_float(vmaf_pooled.get("max"))
                if mean is not None and minimum is not None and maximum is not None:
                    p95 = _as_float(vmaf_pooled.get("p95")) or mean
                    return VmafMetrics(
                        mean=mean,
                        minimum=minimum,
                        maximum=maximum,
                        p95=p95,
                        frame_count=0,
                    )

        raise MetricsError("No frame-level VMAF values found in payload")

    values.sort()
    count = len(values)
    mean = sum(values) / count
    minimum = values[0]
    maximum = values[-1]
    p95 = _percentile(values, 95.0)
    return VmafMetrics(mean=mean, minimum=minimum, maximum=maximum, p95=p95, frame_count=count)


def _percentile(sorted_values: list[float], percentile: float) -> float:
    if not sorted_values:
        raise ValueError("Cannot compute percentile of empty list")
    if percentile <= 0:
        return sorted_values[0]
    if percentile >= 100:
        return sorted_values[-1]
    index = (len(sorted_values) - 1) * (percentile / 100.0)
    lower = int(index)
    upper = min(lower + 1, len(sorted_values) - 1)
    weight = index - lower
    return sorted_values[lower] * (1.0 - weight) + sorted_values[upper] * weight


def _as_float(value: object) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None
