"""The shape every generated puzzle takes, so verification, variety and hints work the same for every game."""

import random
from dataclasses import dataclass, field
from typing import Any, Protocol

from core.difficulty import band_of

__all__ = ["Generator", "Puzzle", "PuzzleError", "band_of"]


class PuzzleError(Exception):
    """A generated puzzle failed verification (no solution, several solutions, or a wrong answer)."""


@dataclass(frozen=True)
class Puzzle:
    game_id: str
    lines: tuple[str, ...]
    question: str
    answer: str  # canonical; used for grading and the answer floor
    answer_bucket: str  # balance tracking; "" if not applicable
    key: str  # dedup identity
    static_hints: tuple[str, ...] = ()
    explanation: str | None = None
    forbidden: tuple[str, ...] = ()
    meta: dict[str, Any] = field(default_factory=dict)


class Generator(Protocol):
    def __call__(self, level: int, rng: random.Random) -> Puzzle: ...
