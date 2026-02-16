from __future__ import annotations

from pathlib import Path

import pytest

from bitrate_ladder.compare.preprocess import (
    PreprocessError,
    build_cache_key,
    prepare_aligned_assets,
)


def test_build_cache_key_changes_with_inputs(tmp_path: Path) -> None:
    first = tmp_path / "a.mp4"
    second = tmp_path / "b.mp4"
    first.write_bytes(b"one")
    second.write_bytes(b"two")

    key_one = build_cache_key(
        [first, second],
        evaluation_width=1920,
        evaluation_height=1080,
        evaluation_fps="24/1",
        common_duration=1.0,
    )
    key_two = build_cache_key(
        [first, second],
        evaluation_width=1920,
        evaluation_height=1080,
        evaluation_fps="24/1",
        common_duration=1.0,
    )
    second.write_bytes(b"changed")
    key_three = build_cache_key(
        [first, second],
        evaluation_width=1920,
        evaluation_height=1080,
        evaluation_fps="24/1",
        common_duration=1.0,
    )

    assert key_one == key_two
    assert key_one != key_three


def test_prepare_aligned_assets_requires_at_least_two_inputs(tmp_path: Path) -> None:
    source = tmp_path / "source.mp4"
    source.write_bytes(b"x")

    with pytest.raises(PreprocessError, match="At least two assets"):
        prepare_aligned_assets(
            [source],
            evaluation_width=320,
            evaluation_height=180,
            evaluation_fps="24/1",
            cache_dir=tmp_path / "cache",
        )
