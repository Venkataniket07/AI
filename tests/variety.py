"""Variety measurements shared by the per-game floor tests."""

import random
from collections import Counter
from typing import NamedTuple

from games.engine.puzzle import Generator


class Report(NamedTuple):
    distinct_keys: int
    distinct_answers: int
    family_share: float  # share of puzzles in the most common meta["family"]; 0 if no puzzle has one


def variety_report(gen: Generator, level: int, n: int = 200, seed: int = 0) -> Report:
    rng = random.Random(seed)
    puzzles = [gen(level, rng) for _ in range(n)]
    families = Counter(p.meta["family"] for p in puzzles if p.meta.get("family"))
    share = max(families.values()) / n if families and n else 0.0
    return Report(
        distinct_keys=len({p.key for p in puzzles}),
        distinct_answers=len({p.answer for p in puzzles}),
        family_share=share,
    )
