"""XP normalisation.

Raw scores are not comparable between games (a perfect Mental Arithmetic run scores ~190, a perfect
Direction Sense run 100), so XP is the score as a percentage of a perfect run of that game.
A perfect game is worth XP_FOR_PERFECT XP; the stored session score stays the raw score.
"""

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


def xp_for(game_type: str, score: int) -> int:
    """XP earned for `score` in `game_type` (0..XP_FOR_PERFECT). Unknown games earn their raw score."""
    perfect = PERFECT_SCORE.get(game_type)
    if not perfect:
        return max(0, score)
    return min(XP_FOR_PERFECT, max(0, round(score / perfect * XP_FOR_PERFECT)))
