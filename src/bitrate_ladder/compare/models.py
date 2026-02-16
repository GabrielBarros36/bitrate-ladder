from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

AssetKind = Literal["source", "point"]


@dataclass
class SessionIssue:
    code: str
    message: str
    field: str
    point_id: str | None = None


@dataclass
class PointAsset:
    point_id: str
    codec: str
    bitrate_kbps: int
    width: int
    height: int
    encode_path: Path | None
    vmaf_log_path: Path | None


@dataclass
class CompareSession:
    report_path: Path
    source_path: Path | None
    points: dict[str, PointAsset]
    evaluation_resolution: tuple[int, int] | None
    evaluation_fps: str | None
    cache_dir: Path
    issues: list[SessionIssue] = field(default_factory=list)
    asset_registry: dict[str, Path] = field(default_factory=dict)


@dataclass(frozen=True)
class AssetRef:
    kind: AssetKind
    point_id: str | None = None


@dataclass(frozen=True)
class PreparedAsset:
    token: str
    source_ref: AssetRef
    proxy_path: Path
    duration_seconds: float


@dataclass(frozen=True)
class PreparedSet:
    assets: list[PreparedAsset]
    evaluation_resolution: tuple[int, int]
    evaluation_fps: str
