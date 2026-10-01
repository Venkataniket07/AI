"""Scoring helpers shared by the games and the stats screen."""

from typing import Optional


def difficulty_label(d: Optional[int]) -> str:
    """Difficulty for display; `-` for sessions saved before difficulty was recorded."""
    return "-" if d is None else str(d)
