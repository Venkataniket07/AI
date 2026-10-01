"""Scoring helpers shared by the games and the stats screen."""

from typing import Optional

from games.assist import HINT_PENALTIES


def partial_points(base: int, got: int, total: int) -> int:
    """Points for `got` of `total` parts correct: `base * got / total`, rounded to the nearest point."""
    if total <= 0:
        return 0
    got = max(0, min(got, total))
    return round(base * got / total)


def hinted(base_points: int, hints_used: int) -> int:
    """`base_points` after the cumulative hint penalty (15% / 30% / 50% for the 1st / 2nd / 3rd hint)."""
    if hints_used <= 0:
        return base_points
    penalty = HINT_PENALTIES[min(hints_used, len(HINT_PENALTIES)) - 1]
    return round(base_points * (1 - penalty))


def difficulty_label(d: Optional[int]) -> str:
    """Difficulty for display; `-` for sessions saved before difficulty was recorded."""
    return "-" if d is None else str(d)
