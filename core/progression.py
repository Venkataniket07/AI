"""XP normalisation.

Raw scores are not comparable between games (a perfect Mental Arithmetic run scores ~190, a perfect
Direction Sense run 100), so XP is the score as a percentage of a perfect run of that game.
A perfect game is worth XP_FOR_PERFECT XP; the stored session score stays the raw score.

Every game has its own XP and level (`game_level`); the player's overall XP is the sum of the per-game XP and
the overall level is derived from that sum (`overall`), so a game the player has never played changes nothing.
"""

from dataclasses import dataclass
from typing import Iterable

XP_FOR_PERFECT = 100

# Maximum score of a flawless run, derived from each game's scoring formula.
PERFECT_SCORE = {
    "mental_math": 190,        # 10 rounds x (10 + 2*streak)
    "quick_calc": 240,         # 10 rounds x (10 + 2*streak + up to 5 speed bonus)
    "n_back": 145,             # 10 rounds x (10 + streak)
    "number_recall": 150,      # 5 rounds x (20 + 5*streak)
    "pattern_memory": 130,     # 4 rounds x (25 + 5*streak)
    "matrix": 130,             # 4 rounds x (25 + 5*streak)
    "seq_predict": 150,        # 5 rounds x (20 + 5*streak)
    "pattern_comp": 150,
    "missing_num": 150,
    "anagrams": 95,            # 5 rounds x 15 + 2*streak, hint-free
    "blood_relations": 100,
    "syllogisms": 100,
    "coding_decoding": 100,
    "direction_sense": 100,
    "rankings": 100,
    "linear_seating": 99,
    "circular_seating": 99,
    "puzzle_grid": 100,
}


XP_STEP = 50  # total XP to reach level L is XP_STEP * L * (L - 1): 100, 300, 600, 1000, ... 4500 at level 10


def xp_to_reach(level: int) -> int:
    """Total XP needed to be at `level` (level 1 needs none)."""
    return XP_STEP * level * (level - 1)


def level_for_xp(xp: int) -> int:
    """The level a given total XP corresponds to. Each level costs more than the one before."""
    level = 1
    while xp >= xp_to_reach(level + 1):
        level += 1
    return level


def xp_for(game_id: str, score: int, accuracy: float = 1.0, difficulty: int | None = None) -> int:
    """XP earned for `score` in the game `game_id`: the one formula every game uses.

    xp = round(score / PERFECT_SCORE[game_id] * XP_FOR_PERFECT), limited to 0..XP_FOR_PERFECT.
    A game without a reference score earns its raw score (never below 0).

    `accuracy` and `difficulty` are accepted so callers can pass the whole result, but they do not change the XP
    yet: the defaults reproduce the stored XP of every existing session.
    """
    perfect = PERFECT_SCORE.get(game_id)
    if not perfect:
        return max(0, score)
    return min(XP_FOR_PERFECT, max(0, round(score / perfect * XP_FOR_PERFECT)))


def game_level(xp: int) -> int:
    """The level of one game for the XP earned in that game, on the same curve as the overall level."""
    return level_for_xp(max(xp, 0))


@dataclass(frozen=True)
class Overall:
    level: int
    xp: int          # total XP over all games
    into_level: int  # XP earned since this level was reached
    needed: int      # XP this level costs (into_level reaches it at the next level)


def overall(rows: Iterable) -> Overall:
    """Overall level and XP from per-game rows (anything with an `xp` attribute); unplayed games add nothing."""
    total = sum(max(r.xp, 0) for r in rows)
    level = level_for_xp(total)
    return Overall(level, total, total - xp_to_reach(level), xp_to_reach(level + 1) - xp_to_reach(level))


def format_header(username: str, ov: Overall) -> str:
    """The main-menu header line."""
    return f"User: {username} (Player Level {ov.level} | XP {ov.into_level}/{ov.needed})"
