"""Brute-force checks that a clue set pins down exactly one arrangement."""

from itertools import permutations
from typing import Callable, Protocol, Sequence

from games.engine.puzzle import Puzzle, PuzzleError


def count_solutions(
    items: Sequence[str],
    clues: Sequence,
    satisfies: Callable[[str, object], bool],
    fix_first: bool = False,
) -> int:
    """Orderings of `items` (as a string) that satisfy every clue.

    `fix_first` pins the first item in place so rotations of a circular table count once.
    """
    items = list(items)
    if fix_first:
        first, rest = items[0], items[1:]
        orders = ((first,) + p for p in permutations(rest))
    else:
        orders = permutations(items)
    return sum(1 for p in orders if all(satisfies("".join(p), c) for c in clues))


def assert_unique(items, clues, satisfies, fix_first: bool = False) -> None:
    n = count_solutions(items, clues, satisfies, fix_first)
    if n != 1:
        raise PuzzleError(f"expected exactly one solution, found {n}")


def drop_redundant(items, clues, satisfies, fix_first: bool = False) -> list:
    """`clues` without any clue the others already imply (assumes `clues` is already unique)."""
    kept = list(clues)
    for clue in list(kept):
        rest = [c for c in kept if c is not clue]
        if count_solutions(items, rest, satisfies, fix_first) == 1:
            kept = rest
    return kept


class Checker(Protocol):
    def verdict(self, puzzle: Puzzle) -> str:
        """Independently re-derive `puzzle.answer` from the puzzle text."""
        ...
