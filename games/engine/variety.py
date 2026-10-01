"""Draws puzzles without repeating one and without long runs of the same answer type."""

import random

from games.engine.puzzle import Generator, Puzzle


class Variety:
    def __init__(self, rng: random.Random, max_run: int = 2, tries: int = 50):
        self.rng = rng
        self.max_run = max_run
        self.tries = tries
        self._seen: set[str] = set()
        self._run_bucket = ""
        self._run_length = 0

    def draw(self, gen: Generator, level: int) -> Puzzle:
        """A puzzle whose key is new and whose bucket does not extend a run past `max_run`.

        Gives up after `tries` and returns the last puzzle drawn.
        """
        puzzle = gen(level, self.rng)
        for _ in range(self.tries - 1):
            if not self._rejects(puzzle):
                break
            puzzle = gen(level, self.rng)
        self._record(puzzle)
        return puzzle

    def reset(self) -> None:
        self._seen.clear()
        self._run_bucket = ""
        self._run_length = 0

    def _rejects(self, puzzle: Puzzle) -> bool:
        if puzzle.key in self._seen:
            return True
        return (
            bool(puzzle.answer_bucket) and puzzle.answer_bucket == self._run_bucket and self._run_length >= self.max_run
        )

    def _record(self, puzzle: Puzzle) -> None:
        self._seen.add(puzzle.key)
        if puzzle.answer_bucket and puzzle.answer_bucket == self._run_bucket:
            self._run_length += 1
        else:
            self._run_bucket = puzzle.answer_bucket
            self._run_length = 1 if puzzle.answer_bucket else 0
