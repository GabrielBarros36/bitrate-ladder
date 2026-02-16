from __future__ import annotations

import json
from pathlib import Path

from bitrate_ladder.compare.session import apply_repairs, load_session


def _write_report(path: Path, source_path: Path) -> None:
    payload = {
        "source": {"path": str(source_path)},
        "runtime": {
            "evaluation_resolution": "320x180",
            "evaluation_fps": "24/1",
            "work_dir": str(path.parent / "work"),
        },
        "points": [
            {
                "id": "p001",
                "codec": "h264",
                "bitrate_kbps": 300,
                "width": 320,
                "height": 180,
            }
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_load_session_uses_fallback_directories(tmp_path: Path) -> None:
    source = tmp_path / "source.mp4"
    source.write_bytes(b"source")

    report_path = tmp_path / "report.json"
    _write_report(report_path, source)

    encodes_dir = tmp_path / "encodes"
    vmaf_dir = tmp_path / "vmaf"
    encodes_dir.mkdir()
    vmaf_dir.mkdir()

    encode_path = encodes_dir / "p001.mp4"
    vmaf_path = vmaf_dir / "p001.json"
    encode_path.write_bytes(b"encode")
    vmaf_path.write_text("{}", encoding="utf-8")

    session = load_session(report_path, encodes_dir=encodes_dir, vmaf_dir=vmaf_dir)

    assert session.points["p001"].encode_path == encode_path.resolve()
    assert session.points["p001"].vmaf_log_path == vmaf_path.resolve()
    assert session.issues == []


def test_apply_repairs_resolves_missing_paths(tmp_path: Path) -> None:
    report_source = tmp_path / "missing_source.mp4"
    report_path = tmp_path / "report.json"
    _write_report(report_path, report_source)

    session = load_session(report_path)
    assert len(session.issues) >= 3

    source = tmp_path / "source.mp4"
    encode = tmp_path / "encode.mp4"
    vmaf = tmp_path / "vmaf.json"
    source.write_bytes(b"source")
    encode.write_bytes(b"encode")
    vmaf.write_text("{}", encoding="utf-8")

    apply_repairs(
        session,
        source_path=str(source),
        encode_paths={"p001": str(encode)},
        vmaf_paths={"p001": str(vmaf)},
    )

    assert session.issues == []
