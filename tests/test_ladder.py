from __future__ import annotations

from bitrate_ladder.ladder import RatedPoint, bd_rate, select_ladder


def test_upper_hull_selection() -> None:
    points = [
        RatedPoint("p1", 500, 80.0),
        RatedPoint("p2", 1000, 90.0),
        RatedPoint("p3", 1500, 91.0),
        RatedPoint("p4", 2000, 94.0),
    ]
    selection = select_ladder(points)
    assert selection.selected_ids == ["p1", "p2", "p4"]


def test_bd_rate_identical_curves_is_zero() -> None:
    curve = [(500.0, 80.0), (1000.0, 90.0), (2000.0, 95.0)]
    delta = bd_rate(curve, curve)
    assert delta is not None
    assert abs(delta) < 1e-9


def test_same_bitrate_tie_is_deterministic() -> None:
    points = [
        RatedPoint("a", 500, 75.0),
        RatedPoint("c", 1000, 85.0),
        RatedPoint("b", 1000, 85.0),
        RatedPoint("d", 1500, 90.0),
    ]
    selection = select_ladder(points)
    assert "b" in selection.selected_ids
    assert "c" not in selection.selected_ids
