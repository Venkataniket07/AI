"""Shared round loop for reasoning games: draw a puzzle, ask, grade, hint, score, save."""

import random
from dataclasses import dataclass
from typing import Callable, Sequence

from core.integrity import answer_floor_ms
from core.profile_manager import ProfileManager
from games.assist import HINT_TIP, RoundHelper
from games.common import finish_game
from games.engine import ui
from games.engine.puzzle import Generator, Puzzle
from games.engine.variety import Variety
from utils.performance_tracker import PerformanceTracker


@dataclass(frozen=True)
class GameSpec:
    game_id: str
    title: str
    intro: Sequence[str]
    rounds: int
    base_points: int
    generator: Generator
    grade: Callable[[str, Puzzle], bool]
    ai_hints: bool = False
    answer_display: Callable[[Puzzle], str] = lambda p: p.answer
    session_veto: Callable[[Puzzle, Sequence[Puzzle]], bool] | None = None  # extra rules on a game's draws


def play_rounds(profile: ProfileManager, spec: GameSpec, rng: random.Random | None = None) -> None:
    print(f"\n================ {spec.title.upper()} ================")
    for line in spec.intro:
        print(line)
    print(HINT_TIP)
    input("Press Enter to start...")

    rng = rng or random.Random()
    level = profile.difficulty(spec.game_id)
    variety = Variety(rng, veto=spec.session_veto)
    tracker = PerformanceTracker()
    score = 0

    for r in range(1, spec.rounds + 1):
        puzzle = variety.draw(spec.generator, level)
        helper = RoundHelper.from_puzzle(puzzle, profile.db, ai_hints=spec.ai_hints)

        print(f"\nRound {r}/{spec.rounds}:")
        for line in puzzle.lines:
            print(line)
        print(f"\nQuestion: {puzzle.question}")

        tracker.start_trial()
        raw = helper.ask("> ")
        is_correct = spec.grade(raw, puzzle)
        tracker.end_trial(
            is_correct,
            helper.hints_used,
            min_plausible_ms=answer_floor_ms(puzzle.answer, " ".join(puzzle.lines)),
        )

        if is_correct:
            score += helper.points(spec.base_points)
        ui.show_result(is_correct, raw, spec.answer_display(puzzle))
        if not is_correct:
            helper.offer_explanation(raw)

    print(f"\nScore: {score}")
    finish_game(profile, spec.game_id, score, tracker, "Press Enter to return...", difficulty=level)
