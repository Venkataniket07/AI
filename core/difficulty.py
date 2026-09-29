"""Per-game adaptive difficulty.

A player's level is overall progress; how hard a *particular* game should be also depends on how
they have been doing in that game. Difficulty starts at the player's level and moves by up to two
steps depending on recent accuracy in that game.
"""

from typing import Sequence

WINDOW = 5          # most recent sessions of the game that are considered
MIN_SESSIONS = 2    # below this there is not enough evidence to adjust
MAX_ADJUST = 2


def adjustment_for_accuracy(accuracy: float) -> int:
    if accuracy >= 0.95:
        return 2
    if accuracy >= 0.85:
        return 1
    if accuracy < 0.35:
        return -2
    if accuracy < 0.55:
        return -1
    return 0


def difficulty_for(recent_sessions: Sequence, level: int) -> int:
    """
    Difficulty (>= 1) for a game, given the player's recent sessions of that game (newest first)
    and their overall level.
    """
    sessions = list(recent_sessions)[:WINDOW]
    if len(sessions) < MIN_SESSIONS:
        return max(1, level)
    avg_accuracy = sum(s.accuracy for s in sessions) / len(sessions)
    return max(1, level + adjustment_for_accuracy(avg_accuracy))
