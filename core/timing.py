"""Timing and size policy for the memory games (pure functions, no I/O)."""

MAX_DIFFICULTY = 10

RECALL_START_DIGITS = 4
MAX_LENGTH = 12
VIEW_BASE_S = 2.0
VIEW_PER_ITEM_S = 0.6
STREAK_SPEEDUP = 0.0

NBACK_N_BY_LEVEL = (1, 1, 1, 2, 2, 2, 3, 3, 3, 4)


def _clamp(level: int) -> int:
    return max(1, min(MAX_DIFFICULTY, level))


def answer_floor_ms(answer: str, question: str = "") -> int:
    """The fastest a person could read `question`, type `answer` and press Enter (a deliberately low bound).

    Reading is 15 ms per character (~800 words a minute); typing is 150 ms per character plus 400 ms to react.
    """
    return 400 + 150 * len(answer) + 15 * len(question)


def recall_length(level: int, streak: int = 0) -> int:
    """Digits to remember: 4 at level 1, one more every two levels and every two streak wins, at most 12."""
    return min(MAX_LENGTH, RECALL_START_DIGITS + (_clamp(level) - 1) // 2 + max(0, streak) // 2)


def recall_view_seconds(length: int, streak: int = 0) -> float:
    """How long the digits stay up: a base time plus time per digit."""
    return VIEW_BASE_S + VIEW_PER_ITEM_S * length - STREAK_SPEEDUP * streak


def grid_size_and_xs(level: int) -> tuple[int, int]:
    """Grid side and number of [X]s for an effective difficulty."""
    level = _clamp(level)
    grid_size = min(5, 3 + level // 3)
    return grid_size, min(grid_size * grid_size // 2, 2 + (level + 1) // 2)


def grid_view_seconds(num_xs: int, streak: int = 0) -> float:
    """More squares need longer to take in; a streak shortens it a little."""
    return max(2.0, 1.5 + 0.8 * num_xs - 0.2 * streak)


def nback_n(level: int) -> int:
    return NBACK_N_BY_LEVEL[_clamp(level) - 1]


def nback_window_seconds(n: int, streak: int) -> float:
    """Time to answer one letter: longer for bigger N, shortening with a streak, never under 1.5 s."""
    return max(1.5, 2.5 + 0.25 * (n - 1) - 0.1 * streak)
