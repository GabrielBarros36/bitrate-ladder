from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from ..metrics import MetricsError, parse_vmaf_payload
from .models import AssetRef, CompareSession
from .preprocess import PreprocessError, clear_cache_dir, prepare_aligned_assets
from .session import apply_repairs, session_payload


class AssetRefRequest(BaseModel):
    kind: Literal["source", "point"]
    point_id: str | None = None

    def to_asset_ref(self) -> AssetRef:
        return AssetRef(kind=self.kind, point_id=self.point_id)


class PrepareRequest(BaseModel):
    assets: list[AssetRefRequest] = Field(min_length=2, max_length=4)
    evaluation_resolution: str | None = None
    evaluation_fps: str | None = None


class RepairRequest(BaseModel):
    source_path: str | None = None
    encode_paths: dict[str, str] = Field(default_factory=dict)
    vmaf_paths: dict[str, str] = Field(default_factory=dict)


def create_app(
    session: CompareSession,
    *,
    ffmpeg_bin: str = "ffmpeg",
    ffprobe_bin: str = "ffprobe",
) -> FastAPI:
    app = FastAPI(title="bitrate-ladder compare")
    static_dir = _resolve_static_dir()
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(static_dir / "index.html")

    @app.get("/api/session")
    def get_session() -> dict:
        payload = session_payload(session)
        payload["capabilities"] = {
            "max_tiles": 4,
            "modes": ["tile", "wipe"],
        }
        return payload

    @app.post("/api/session/repair")
    def repair_session(request: RepairRequest) -> dict:
        apply_repairs(
            session,
            source_path=request.source_path,
            encode_paths=request.encode_paths,
            vmaf_paths=request.vmaf_paths,
        )
        return session_payload(session)

    @app.post("/api/compare/prepare")
    def prepare_compare(request: PrepareRequest) -> dict:
        if session.issues:
            raise HTTPException(
                status_code=400,
                detail="Session has unresolved missing paths. Repair issues before preparing compare assets.",
            )

        asset_refs = [item.to_asset_ref() for item in request.assets]
        input_paths = [_resolve_asset_path(session, item) for item in asset_refs]

        width, height = _resolve_evaluation_resolution(session, request.evaluation_resolution)
        fps = _resolve_evaluation_fps(session, request.evaluation_fps)
        try:
            proxy_paths, duration_seconds = prepare_aligned_assets(
                input_paths,
                evaluation_width=width,
                evaluation_height=height,
                evaluation_fps=fps,
                cache_dir=session.cache_dir,
                ffmpeg_bin=ffmpeg_bin,
                ffprobe_bin=ffprobe_bin,
            )
        except PreprocessError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        prepared_assets = []
        for source_ref, proxy_path in zip(asset_refs, proxy_paths):
            token = _register_asset(session, proxy_path)
            prepared_assets.append(
                {
                    "token": token,
                    "media_url": f"/api/media/{token}",
                    "source": {
                        "kind": source_ref.kind,
                        "point_id": source_ref.point_id,
                    },
                }
            )

        return {
            "duration_seconds": duration_seconds,
            "evaluation_resolution": {
                "width": width,
                "height": height,
            },
            "evaluation_fps": fps,
            "assets": prepared_assets,
        }

    @app.get("/api/media/{asset_token}")
    def get_media(asset_token: str) -> FileResponse:
        media_path = session.asset_registry.get(asset_token)
        if media_path is None or not media_path.exists():
            raise HTTPException(status_code=404, detail="Unknown media asset")
        return FileResponse(media_path, media_type="video/mp4")

    @app.get("/api/vmaf/{point_id}")
    def get_vmaf_series(point_id: str) -> dict:
        point = session.points.get(point_id)
        if point is None:
            raise HTTPException(status_code=404, detail=f"Unknown point id: {point_id}")
        if point.vmaf_log_path is None or not point.vmaf_log_path.exists():
            raise HTTPException(status_code=404, detail=f"Missing VMAF log for point {point_id}")

        try:
            payload = json.loads(point.vmaf_log_path.read_text(encoding="utf-8"))
            summary = parse_vmaf_payload(payload)
        except (OSError, json.JSONDecodeError, MetricsError) as exc:
            raise HTTPException(status_code=400, detail=f"Invalid VMAF log for point {point_id}") from exc

        fps = _fps_to_float(_resolve_evaluation_fps(session, None))
        series = []
        frames = payload.get("frames") if isinstance(payload, dict) else None
        if isinstance(frames, list):
            for index, frame in enumerate(frames):
                if not isinstance(frame, dict):
                    continue
                metrics = frame.get("metrics")
                if not isinstance(metrics, dict):
                    continue
                value = metrics.get("vmaf")
                if isinstance(value, (float, int)):
                    series.append(
                        {
                            "frame": index,
                            "time_seconds": index / fps,
                            "vmaf": float(value),
                        }
                    )

        return {
            "point_id": point_id,
            "summary": {
                "mean": summary.mean,
                "min": summary.minimum,
                "max": summary.maximum,
                "p95": summary.p95,
                "frame_count": summary.frame_count,
            },
            "series": series,
        }

    @app.post("/api/cache/clear")
    def clear_cache() -> dict:
        clear_cache_dir(session.cache_dir)
        session.cache_dir.mkdir(parents=True, exist_ok=True)
        return {"status": "ok", "cache_dir": str(session.cache_dir)}

    return app


def _resolve_static_dir() -> Path:
    repo_dist = Path.cwd() / "web" / "compare" / "dist"
    if repo_dist.exists():
        return repo_dist
    return Path(__file__).with_name("static")


def _resolve_asset_path(session: CompareSession, ref: AssetRef) -> Path:
    if ref.kind == "source":
        if session.source_path is None:
            raise HTTPException(status_code=400, detail="Source path is not available")
        return session.source_path

    if ref.point_id is None:
        raise HTTPException(status_code=400, detail="point_id is required for point assets")

    point = session.points.get(ref.point_id)
    if point is None:
        raise HTTPException(status_code=404, detail=f"Unknown point id: {ref.point_id}")
    if point.encode_path is None:
        raise HTTPException(status_code=404, detail=f"Missing encode for point {ref.point_id}")
    return point.encode_path


def _resolve_evaluation_resolution(
    session: CompareSession,
    override: str | None,
) -> tuple[int, int]:
    if override:
        cleaned = override.strip().lower()
        if "x" not in cleaned:
            raise HTTPException(status_code=400, detail="evaluation_resolution must be <w>x<h>")
        width_raw, height_raw = cleaned.split("x", maxsplit=1)
        try:
            width = int(width_raw)
            height = int(height_raw)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid evaluation_resolution") from exc
        if width <= 0 or height <= 0:
            raise HTTPException(status_code=400, detail="Invalid evaluation_resolution")
        return width, height

    if session.evaluation_resolution is not None:
        return session.evaluation_resolution

    best_width = max(point.width for point in session.points.values())
    best_height = max(point.height for point in session.points.values())
    return best_width, best_height


def _resolve_evaluation_fps(session: CompareSession, override: str | None) -> str:
    if override and override.strip():
        return override.strip()
    if session.evaluation_fps:
        return session.evaluation_fps
    return "30"


def _register_asset(session: CompareSession, path: Path) -> str:
    digest = hashlib.sha1(str(path).encode("utf-8")).hexdigest()[:12]
    token = f"asset_{digest}"
    session.asset_registry[token] = path
    return token


def _fps_to_float(value: str) -> float:
    try:
        if "/" in value:
            numerator_raw, denominator_raw = value.split("/", maxsplit=1)
            numerator = float(numerator_raw)
            denominator = float(denominator_raw)
            if denominator <= 0:
                return 30.0
            return numerator / denominator
        return float(value)
    except ValueError:
        return 30.0
