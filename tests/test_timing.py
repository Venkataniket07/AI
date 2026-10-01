"""Timing and size policy for the memory games."""

import pytest

from core import timing
from core.timing import (
    answer_floor_ms, grid_size_and_xs, grid_view_seconds, nback_n, nback_window_seconds, recall_length,
    recall_view_seconds,
)


def test_recall_length_curve():
    assert [recall_length(level) for level in range(1, 11)] == [4, 4, 5, 5, 6, 6, 7, 7, 8, 8]
    assert recall_length(10, 4) == 10
    assert recall_length(10, 99) == 12


def test_recall_view_seconds():
    assert recall_view_seconds(9) == pytest.approx(7.4)
    assert recall_view_seconds(4) == pytest.approx(4.4)
    times = [recall_view_seconds(n) for n in range(4, 13)]
    assert times == sorted(set(times))


def test_view_time_per_digit_floor():
    for level in range(1, 11):
        length = recall_length(level)
        assert recall_view_seconds(length) / length >= 0.6


def test_grid_view_seconds_monotone():
    times = [grid_view_seconds(n) for n in range(2, 13)]
    assert times == sorted(times)
    assert grid_view_seconds(3, 0) > grid_view_seconds(3, 4) >= 2.0
    assert grid_view_seconds(3, 99) == 2.0


def test_grid_layout_fits_the_grid_and_grows():
    prev = (0, 0)
    for level in range(1, 11):
        size, xs = grid_size_and_xs(level)
        assert 3 <= size <= 5 and 2 <= xs <= size * size // 2
        assert size >= prev[0] and xs >= prev[1]
        prev = (size, xs)
    assert grid_size_and_xs(1) == (3, 3)


def test_nback_n_mapping():
    assert [nback_n(level) for level in range(1, 11)] == [1, 1, 1, 2, 2, 2, 3, 3, 3, 4]


def test_nback_window_floor():
    assert all(nback_window_seconds(n, streak) >= 1.5 for n in range(1, 5) for streak in range(0, 40))
    assert nback_window_seconds(1, 0) == 2.5


def test_answer_floor_unchanged():
    assert answer_floor_ms("12345", "q") == 400 + 750 + 15
    from core.integrity import answer_floor_ms as reexported
    assert reexported is timing.answer_floor_ms
