"""Direction Sense generator: true answers, scaling by level, variety and wording."""

import builtins
import math
import random
import re

import pytest

from games.engine.variety import Variety
from games.reasoning import direction
from games.reasoning.direction import SPEC, generate, params_for, walk
from tests.helpers import assert_params_contract
from tests.variety import variety_report

SEEDS = range(200)
LEVELS = range(1, 11)
_COMPASS_LINE = re.compile(r"^  (\d+)m (North|East|South|West)$")
_TURN_LINE = re.compile(r"^  (Turns right|Turns left|Turns around|Keeps going), walks (\d+)m\.$")
_TURN_ACTION = {"Turns right": "right", "Turns left": "left", "Turns around": "back", "Keeps going": "straight"}


def _steps_from_text(puzzle):
    """Re-read the route from the lines the player sees, independently of the generator's meta."""
    facing, steps = "North", []
    for line in puzzle.lines[1:]:
        if m := _COMPASS_LINE.match(line):
            steps.append((m.group(2), int(m.group(1))))
        else:
            m = _TURN_LINE.match(line)
            steps.append((_TURN_ACTION[m.group(1)], int(m.group(2))))
    if puzzle.lines[0].startswith(tuple(f"{n} starts facing" for n in direction.NAMES)):
        facing = puzzle.lines[0].rstrip(".").rsplit(" ", 1)[1]
    return facing, steps


def test_answer_is_integer_and_true_euclidean():
    for level in LEVELS:
        for seed in SEEDS:
            puzzle = generate(level, random.Random(seed))
            dx, dy = walk(*_steps_from_text(puzzle))
            assert puzzle.answer.isdigit()
            assert math.hypot(dx, dy) == int(puzzle.answer), (level, seed, puzzle.lines)


def test_at_least_15_distinct_answers_over_200_puzzles():
    answers = set()
    for level in range(4, 11):
        report = variety_report(generate, level)
        assert report.distinct_keys >= 150
        answers |= {generate(level, random.Random(s)).answer for s in SEEDS}
    assert len(answers) >= 15


def _leg_lines(puzzle):
    return [ln for ln in puzzle.lines if ln.startswith("  ")]


def test_move_count_by_band():
    for level in LEVELS:
        for seed in SEEDS:
            n = len(_leg_lines(generate(level, random.Random(seed))))
            if level <= 3:
                assert 2 <= n <= 3
            elif level <= 6:
                assert 4 <= n <= 5
            else:
                assert n >= 5


def test_backtracking_present_in_medium_and_hard():
    for level in range(4, 11):
        hits = 0
        for seed in SEEDS:
            meta = generate(level, random.Random(seed)).meta
            hits += meta["walked"] > abs(meta["dx"]) + abs(meta["dy"])  # some moves cancelled
        assert hits >= 0.8 * len(SEEDS), level


def test_hard_band_uses_turns_and_easy_does_not():
    assert generate(8, random.Random(0)).lines[0].endswith(tuple(f"facing {d}." for d in direction.COMPASS))
    assert all(_COMPASS_LINE.match(ln) for ln in _leg_lines(generate(2, random.Random(0))))


def test_no_repeat_within_session():
    for level in (1, 4, 8):
        for seed in range(100):
            variety = Variety(random.Random(seed))
            keys = [variety.draw(generate, level).key for _ in range(5)]
            assert len(set(keys)) == 5, (level, seed)


def test_params_contract():
    assert_params_contract(params_for, monotone_fields=("n_moves", "backtrack", "turns", "scale_max"))


def test_walk_oracle():
    assert walk("North", [("East", 3), ("North", 4)]) == (3, 4)
    assert walk("North", [("right", 5), ("left", 3)]) == (5, 3)
    assert walk("East", [("back", 2), ("straight", 1), ("left", 4)]) == (-3, -4)


@pytest.mark.parametrize(
    "fmt",
    [
        str,
        lambda n: f"{n}m",
        lambda n: f"{n} m",
        lambda n: f"{n} meters",
        lambda n: f"{n} Metres",
        lambda n: f"{n}.",
        lambda n: f"{n}.0",
    ],
)
def test_unit_and_format_inputs_still_parse(fmt):
    puzzle = generate(1, random.Random(3))
    assert SPEC.grade(fmt(int(puzzle.answer)), puzzle)
    assert not SPEC.grade(fmt(int(puzzle.answer) + 1), puzzle)
    assert not SPEC.grade("far", puzzle)


def test_wording_has_no_he_she():
    for level in LEVELS:
        for seed in range(50):
            puzzle = generate(level, random.Random(seed))
            text = " ".join((*puzzle.lines, puzzle.question, *puzzle.static_hints, puzzle.explanation))
            assert not re.search(r"\b(he|she|his|her|him)\b", text, re.IGNORECASE), text
            assert puzzle.question.startswith("How far is ")


def test_play_stores_difficulty_and_scores_every_round(monkeypatch, capsys, profile):
    monkeypatch.setattr(builtins, "input", lambda prompt="": "0" if prompt == "> " else "")
    monkeypatch.setattr("time.sleep", lambda s: None)
    direction.play_direction_sense(profile)
    stats = profile.db.get_user_stats(profile.require_user().id, limit=1)[0]
    assert stats.difficulty == 1 and stats.accuracy == 0.0
    out = capsys.readouterr().out
    assert out.count("Correct:") == 5 and "Round 5/5" in out
