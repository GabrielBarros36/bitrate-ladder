from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from ..config import Codec, parse_resolution_string
from ..encode import output_extension_for_codec
from .models import CompareSession, PointAsset, SessionIssue


class SessionError(RuntimeError):
    """Raised when a compare session cannot be created from a report."""


def load_session(
    report_path: Path,
    *,
    encodes_dir: Path | None = None,
    vmaf_dir: Path | None = None,
    cache_dir: Path | None = None,
) -> CompareSession:
    report_file = report_path.expanduser().resolve()
    if not report_file.exists():
        raise SessionError(f"Report not found: {report_file}")

    try:
        payload = json.loads(report_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SessionError(f"Unable to read report: {report_file}") from exc

    if not isinstance(payload, dict):
        raise SessionError("Report root must be a JSON object")

    report_dir = report_file.parent
    source_path = _parse_source_path(payload, report_dir)
    runtime = payload.get("runtime") if isinstance(payload.get("runtime"), dict) else {}

    evaluation_resolution = _parse_resolution(runtime)
    evaluation_fps = runtime.get("evaluation_fps") if isinstance(runtime, dict) else None
    if not isinstance(evaluation_fps, str) or not evaluation_fps.strip():
        evaluation_fps = None

    points: dict[str, PointAsset] = {}
    points_raw = payload.get("points")
    if not isinstance(points_raw, list):
        raise SessionError("Report field 'points' must be a list")

    resolved_encodes_dir = encodes_dir.expanduser().resolve() if encodes_dir else None
    resolved_vmaf_dir = vmaf_dir.expanduser().resolve() if vmaf_dir else None

    for point_raw in points_raw:
        if not isinstance(point_raw, dict):
            continue

        point_id = point_raw.get("id")
        if not isinstance(point_id, str) or not point_id:
            continue
        codec = point_raw.get("codec")
        if not isinstance(codec, str):
            codec = "h264"

        bitrate_kbps = _as_int(point_raw.get("bitrate_kbps"))
        width = _as_int(point_raw.get("width"))
        height = _as_int(point_raw.get("height"))

        encode_path = _parse_path_from_row(point_raw, report_dir, "encode_path")
        if encode_path is None and resolved_encodes_dir is not None:
            encode_path = _build_fallback_encode_path(resolved_encodes_dir, point_id, codec)

        vmaf_log_path = _parse_path_from_row(point_raw, report_dir, "vmaf_log_path")
        if vmaf_log_path is None and resolved_vmaf_dir is not None:
            vmaf_log_path = resolved_vmaf_dir / f"{point_id}.json"

        points[point_id] = PointAsset(
            point_id=point_id,
            codec=codec,
            bitrate_kbps=bitrate_kbps,
            width=width,
            height=height,
            encode_path=encode_path,
            vmaf_log_path=vmaf_log_path,
        )

    if not points:
        raise SessionError("Report has no point entries")

    runtime_work_dir = runtime.get("work_dir") if isinstance(runtime, dict) else None
    default_cache_dir = report_dir / "compare_cache"
    if isinstance(runtime_work_dir, str) and runtime_work_dir:
        default_cache_dir = _resolve_path(runtime_work_dir, report_dir) / "compare_cache"

    session = CompareSession(
        report_path=report_file,
        source_path=source_path,
        points=points,
        evaluation_resolution=evaluation_resolution,
        evaluation_fps=evaluation_fps,
        cache_dir=cache_dir.expanduser().resolve() if cache_dir else default_cache_dir,
    )
    validate_session(session)
    return session


def validate_session(session: CompareSession) -> None:
    issues: list[SessionIssue] = []

    if session.source_path is None:
        issues.append(
            SessionIssue(
                code="missing_source",
                message="Source path is missing from the report or has not been repaired.",
                field="source_path",
            )
        )
    elif not session.source_path.exists():
        issues.append(
            SessionIssue(
                code="missing_source",
                message=f"Source path does not exist: {session.source_path}",
                field="source_path",
            )
        )

    for point in session.points.values():
        if point.encode_path is None:
            issues.append(
                SessionIssue(
                    code="missing_encode",
                    message=f"Encode path missing for point {point.point_id}",
                    field="encode_path",
                    point_id=point.point_id,
                )
            )
        elif not point.encode_path.exists():
            issues.append(
                SessionIssue(
                    code="missing_encode",
                    message=f"Encode path does not exist: {point.encode_path}",
                    field="encode_path",
                    point_id=point.point_id,
                )
            )

        if point.vmaf_log_path is None:
            issues.append(
                SessionIssue(
                    code="missing_vmaf",
                    message=f"VMAF log path missing for point {point.point_id}",
                    field="vmaf_log_path",
                    point_id=point.point_id,
                )
            )
        elif not point.vmaf_log_path.exists():
            issues.append(
                SessionIssue(
                    code="missing_vmaf",
                    message=f"VMAF log path does not exist: {point.vmaf_log_path}",
                    field="vmaf_log_path",
                    point_id=point.point_id,
                )
            )

    session.issues = issues


def apply_repairs(
    session: CompareSession,
    *,
    source_path: str | None = None,
    encode_paths: dict[str, str] | None = None,
    vmaf_paths: dict[str, str] | None = None,
) -> None:
    report_dir = session.report_path.parent

    if source_path is not None and source_path.strip():
        session.source_path = _resolve_path(source_path, report_dir)

    for point_id, raw_path in (encode_paths or {}).items():
        point = session.points.get(point_id)
        if point is None or not raw_path.strip():
            continue
        point.encode_path = _resolve_path(raw_path, report_dir)

    for point_id, raw_path in (vmaf_paths or {}).items():
        point = session.points.get(point_id)
        if point is None or not raw_path.strip():
            continue
        point.vmaf_log_path = _resolve_path(raw_path, report_dir)

    validate_session(session)


def session_payload(session: CompareSession) -> dict[str, Any]:
    points_payload = []
    for point in sorted(session.points.values(), key=lambda item: item.point_id):
        points_payload.append(
            {
                "id": point.point_id,
                "codec": point.codec,
                "bitrate_kbps": point.bitrate_kbps,
                "width": point.width,
                "height": point.height,
                "encode_path": str(point.encode_path) if point.encode_path is not None else None,
                "vmaf_log_path": (
                    str(point.vmaf_log_path) if point.vmaf_log_path is not None else None
                ),
                "encode_exists": bool(point.encode_path and point.encode_path.exists()),
                "vmaf_exists": bool(point.vmaf_log_path and point.vmaf_log_path.exists()),
            }
        )

    return {
        "report_path": str(session.report_path),
        "source_path": str(session.source_path) if session.source_path is not None else None,
        "cache_dir": str(session.cache_dir),
        "evaluation_resolution": (
            {
                "width": session.evaluation_resolution[0],
                "height": session.evaluation_resolution[1],
            }
            if session.evaluation_resolution is not None
            else None
        ),
        "evaluation_fps": session.evaluation_fps,
        "points": points_payload,
        "issues": [
            {
                "code": issue.code,
                "message": issue.message,
                "field": issue.field,
                "point_id": issue.point_id,
            }
            for issue in session.issues
        ],
    }


def _parse_source_path(payload: dict[str, Any], report_dir: Path) -> Path | None:
    source_raw = payload.get("source")
    if not isinstance(source_raw, dict):
        return None
    source_path_raw = source_raw.get("path")
    if not isinstance(source_path_raw, str) or not source_path_raw:
        return None
    return _resolve_path(source_path_raw, report_dir)


def _parse_resolution(runtime: Any) -> tuple[int, int] | None:
    if not isinstance(runtime, dict):
        return None
    value = runtime.get("evaluation_resolution")
    if not isinstance(value, str) or not value:
        return None
    try:
        return parse_resolution_string(value, field_name="runtime.evaluation_resolution")
    except ValueError:
        return None


def _build_fallback_encode_path(encodes_dir: Path, point_id: str, codec: str) -> Path:
    extension = "mp4"
    if codec in {"h264", "h265", "av1"}:
        extension = output_extension_for_codec(cast(Codec, codec))
    return encodes_dir / f"{point_id}.{extension}"


def _parse_path_from_row(row: dict[str, Any], report_dir: Path, field: str) -> Path | None:
    raw_value = row.get(field)
    if not isinstance(raw_value, str) or not raw_value:
        return None
    return _resolve_path(raw_value, report_dir)


def _resolve_path(raw_path: str, report_dir: Path) -> Path:
    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        path = report_dir / path
    return path.resolve()


def _as_int(value: Any) -> int:
    if isinstance(value, int):
        return value
    return 0
