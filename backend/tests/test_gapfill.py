from datetime import date, timedelta

from app.services.gapfill import interpolate


def _dates(n: int) -> list[date]:
    start = date(2024, 1, 1)
    return [start + timedelta(days=i) for i in range(n)]


def test_interpolate_fills_single_gap_linearly():
    dates = _dates(3)
    values = [0.2, None, 0.6]
    assert interpolate(dates, values) == [0.2, 0.4, 0.6]


def test_interpolate_keeps_known_values():
    dates = _dates(3)
    values = [0.1, 0.2, 0.3]
    assert interpolate(dates, values) == [0.1, 0.2, 0.3]


def test_interpolate_edge_gaps_use_nearest_known():
    dates = _dates(4)
    values = [None, 0.3, 0.5, None]
    result = interpolate(dates, values)
    assert result[0] == 0.3
    assert result[3] == 0.5


def test_interpolate_no_known_values_returns_zeros():
    dates = _dates(2)
    values = [None, None]
    assert interpolate(dates, values) == [0.0, 0.0]
