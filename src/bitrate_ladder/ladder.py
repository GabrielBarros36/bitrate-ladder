from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class RatedPoint:
    point_id: str
    bitrate_kbps: int
    vmaf: float


@dataclass(frozen=True)
class LadderSelection:
    selected_ids: list[str]
    hull_points: list[RatedPoint]


def select_ladder(points: Sequence[RatedPoint], tie_tolerance: float = 1e-3) -> LadderSelection:
    if not points:
        raise ValueError("At least one rated point is required")

    grouped: dict[int, list[RatedPoint]] = {}
    for point in points:
        grouped.setdefault(point.bitrate_kbps, []).append(point)

    selected_per_bitrate: list[RatedPoint] = []
    bitrates_sorted = sorted(grouped.keys())

    baseline: dict[int, float] = {}
    for bitrate in bitrates_sorted:
        baseline[bitrate] = max(candidate.vmaf for candidate in grouped[bitrate])

    for bitrate in bitrates_sorted:
        candidates = grouped[bitrate]
        best_vmaf = baseline[bitrate]
        near_best = [
            candidate
            for candidate in candidates
            if abs(candidate.vmaf - best_vmaf) <= tie_tolerance
        ]
        if len(near_best) == 1:
            selected_per_bitrate.append(near_best[0])
            continue

        base_curve = [(x, baseline[x]) for x in bitrates_sorted]
        best_candidate = sorted(near_best, key=lambda item: item.point_id)[0]
        best_score = float("inf")

        for candidate in near_best:
            curve = list(base_curve)
            curve[bitrates_sorted.index(bitrate)] = (bitrate, candidate.vmaf)
            score = bd_rate(curve, base_curve)
            normalized = abs(score) if score is not None else float("inf")
            if normalized < best_score or (
                math.isclose(normalized, best_score) and candidate.point_id < best_candidate.point_id
            ):
                best_candidate = candidate
                best_score = normalized
        selected_per_bitrate.append(best_candidate)

    selected_per_bitrate.sort(key=lambda item: item.bitrate_kbps)
    hull_indices = _upper_hull_indices(selected_per_bitrate)
    hull_points = [selected_per_bitrate[index] for index in hull_indices]
    selected_ids = [point.point_id for point in hull_points]
    return LadderSelection(selected_ids=selected_ids, hull_points=hull_points)


def bd_rate(
    curve_a: Sequence[tuple[float, float]],
    curve_b: Sequence[tuple[float, float]],
    samples: int = 200,
) -> float | None:
    if len(curve_a) < 2 or len(curve_b) < 2:
        return None

    a_q = sorted((quality, bitrate) for bitrate, quality in curve_a)
    b_q = sorted((quality, bitrate) for bitrate, quality in curve_b)

    q_min = max(a_q[0][0], b_q[0][0])
    q_max = min(a_q[-1][0], b_q[-1][0])
    if q_max <= q_min:
        return None

    step = (q_max - q_min) / samples
    acc = 0.0
    for idx in range(samples + 1):
        quality = q_min + idx * step
        rate_a = _rate_at_quality(a_q, quality)
        rate_b = _rate_at_quality(b_q, quality)
        if rate_a <= 0 or rate_b <= 0:
            return None
        delta = math.log(rate_a) - math.log(rate_b)
        weight = 0.5 if idx in {0, samples} else 1.0
        acc += delta * weight
    mean_delta = acc / samples
    return (math.exp(mean_delta) - 1.0) * 100.0


def _rate_at_quality(points: Sequence[tuple[float, float]], quality: float) -> float:
    if quality <= points[0][0]:
        return points[0][1]
    if quality >= points[-1][0]:
        return points[-1][1]

    for idx in range(1, len(points)):
        q1, r1 = points[idx - 1]
        q2, r2 = points[idx]
        if q1 <= quality <= q2:
            if math.isclose(q1, q2):
                return max(r1, r2)
            ratio = (quality - q1) / (q2 - q1)
            return r1 + ratio * (r2 - r1)
    return points[-1][1]


def _upper_hull_indices(points: Sequence[RatedPoint]) -> list[int]:
    if len(points) <= 2:
        return list(range(len(points)))

    hull: list[int] = []
    for idx, point in enumerate(points):
        while len(hull) >= 2:
            a = points[hull[-2]]
            b = points[hull[-1]]
            cross = _cross(a, b, point)
            if cross < 0:
                break
            hull.pop()
        hull.append(idx)
    return hull


def _cross(a: RatedPoint, b: RatedPoint, c: RatedPoint) -> float:
    return (b.bitrate_kbps - a.bitrate_kbps) * (c.vmaf - a.vmaf) - (
        b.vmaf - a.vmaf
    ) * (c.bitrate_kbps - a.bitrate_kbps)
