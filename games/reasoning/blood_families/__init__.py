"""Puzzle families for Blood Relations. Each module has `weight`, `min_level` and `build(rng, family, params)`."""

import random

from games.reasoning.blood_families import chain, collapse, counting

FAMILIES = (chain, collapse, counting)


def pick(rng: random.Random, level: int):
    """A family module chosen by weight among those available at `level`."""
    available = [m for m in FAMILIES if m.min_level <= level]
    return rng.choices(available, weights=[m.weight for m in available])[0]
