"""Per-game adaptive difficulty.

A player's level is overall progress; how hard a *particular* game should be also depends on how
they have been doing in that game. Difficulty starts at a base that rises more slowly than the level
(two steps per three levels) and moves by up to two steps depending on recent accuracy in that game.
Levels come quickly at first, so following them one-to-one made new players' games too hard too soon.

A game the player has never played starts at START_LEVEL, and its cap rises RAMP_PER_SESSION per
session played (`session_cap`), so skill shown in other games never makes a first play hard.

`ParamsFor` contract: every game's generator settings come from a `params_for(level)` that is pure,
total (clamps the level into 1..MAX_DIFFICULTY, so 0 and 99 are valid), returns a frozen dataclass,
and never shrinks the puzzle as the level rises. `tests/helpers.assert_params_contract` checks it.
"""

from typing import Literal, Protocol, Sequence, TypeVar

P = TypeVar("P", covariant=True)
Band = Literal["easy", "medium", "hard"]

WINDOW = 5          # most recent sessions of the game that are considered
MIN_SESSIONS = 2    # below this there is not enough evidence to adjust
MAX_ADJUST = 2
MAX_DIFFICULTY = 10  # the games' generators are only tuned up to here; a higher level does not make them harder
START_LEVEL = 1  # difficulty of a game the player has never played
RAMP_PER_SESSION = 1  # how much the cap rises with each session of that game


def _clamp(value: int) -> int:
    return max(1, min(MAX_DIFFICULTY, value))


def base_difficulty(level: int) -> int:
    """Starting difficulty for a player level: 1, 1, 2, 3, 3, 4, 5, 5, 6, 7 for levels 1 to 10."""
    return 1 + (2 * (max(level, 1) - 1)) // 3


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


def band_of(level: int) -> Band:
    """easy 1-3, medium 4-6, hard 7-10 (levels outside 1..10 are clamped)."""
    level = _clamp(level)
    if level <= 3:
        return "easy"
    return "medium" if level <= 6 else "hard"


def session_cap(sessions_played: int) -> int:
    """Highest difficulty allowed after `sessions_played` sessions of a game."""
    return _clamp(START_LEVEL + RAMP_PER_SESSION * max(sessions_played, 0))


class ParamsFor(Protocol[P]):
    """A game's generator settings for a difficulty level; see the module docstring for the contract."""

    def __call__(self, level: int) -> P: ...


def difficulty_for(recent_sessions: Sequence, level: int, sessions_played: int) -> int:
    """
    Difficulty (1..MAX_DIFFICULTY) for a game, given the player's recent sessions of that game (newest first),
    their level and how many sessions of the game they have played. Never above `session_cap`.
    """
    sessions = list(recent_sessions)[:WINDOW]
    result = base_difficulty(level)
    if len(sessions) >= MIN_SESSIONS:
        avg_accuracy = sum(s.accuracy for s in sessions) / len(sessions)
        result += adjustment_for_accuracy(avg_accuracy)
    return _clamp(min(result, session_cap(sessions_played)))
