"""Direction Sense generator: coordinates rebuilt from the clue text, no ties, caps per level, session rules."""

import builtins
import math
import random
import re

import pytest

from core.textguard import leaks
from games.engine.variety import Variety
from games.reasoning import direction
from games.reasoning.direction import SPEC, TRIPLE_HYP, generate, params_for, parse_compass, walk
from tests.direction_solver import _EIGHT, Solved, _compass, _MOVE, _TURN
from tests.helpers import assert_params_contract

SEEDS = range(100)
LEVELS = range(1, 11)
QUESTIONS_BY_LEVEL = {
    1: {"compass_final", "distance_start"},
    3: {"facing", "position_dir"},
    5: {"dir_pair", "dist_pair"},
    9: {"near_far", "between", "dir_turns", "dir_pair", "dist_pair"},
}


def _all(levels=LEVELS, seeds=SEEDS):
    for level in levels:
        for seed in seeds:
            yield level, seed, generate(level, random.Random(seed))


def _symmetries(points):
    shapes = []
    for sx in (1, -1):
        for sy in (1, -1):
            for swap in (False, True):
                pts = [(sy * y, sx * x) if swap else (sx * x, sy * y) for x, y in points]
                mx, my = min(x for x, _ in pts), min(y for _, y in pts)
                shapes.append(tuple(sorted((x - mx, y - my) for x, y in pts)))
    return shapes


def _layout_ids(solved):
    """A layout's identity independent of the game's own signature: net for a walker, the point set otherwise."""
    if solved.walker is not None:
        return {("net", tuple(sorted(map(abs, solved.net))))}
    return {("set", s) for s in _symmetries(list(solved.placed.values()))}


def test_answer_matches_the_text_and_coordinates():
    for level, seed, puzzle in _all():
        solved = Solved(puzzle)
        assert solved.answer() == puzzle.answer, (level, seed, puzzle.lines, puzzle.question)
        if solved.walker is None:
            assert solved.placed == puzzle.meta["positions"], (level, seed)
        else:
            assert solved.net == puzzle.meta["net"], (level, seed)


def test_levels_ask_their_own_question_types():
    for level, expected in QUESTIONS_BY_LEVEL.items():
        seen = {generate(level, random.Random(s)).meta["qtype"] for s in range(200)}
        assert seen == expected, (level, seen)
        assert {generate(level + 1, random.Random(s)).meta["qtype"] for s in range(200)} == expected


def test_band_shapes():
    for level, seed, puzzle in _all():
        solved = Solved(puzzle)
        if level <= 2:
            moves = [ln for ln in puzzle.lines[1:] if _MOVE.match(ln)]
            assert 2 <= len(moves) <= 3 and len(moves) == len(puzzle.lines) - 1
            assert solved.facing == "North" and puzzle.lines[0].endswith("walks:")
        elif level <= 4:
            assert puzzle.lines[0].startswith(tuple(f"{n} starts facing" for n in direction.NAMES))
            assert 3 <= len(puzzle.lines) - 1 <= 4 and all(_TURN.match(ln) for ln in puzzle.lines[1:])
        elif level <= 6:
            assert 3 <= len(solved.pos) <= 4
        elif level <= 8:
            assert 5 <= len(solved.pos) <= 6
        else:
            assert len(solved.placed) == 7


def test_level_changes_what_is_asked_not_just_the_numbers():
    kinds = {lv: {generate(lv, random.Random(s)).meta["kind"] for s in range(100)} for lv in LEVELS}
    assert kinds[1] == kinds[2] == {"compass", "distance"}
    assert kinds[3] == kinds[4] == {"compass"}
    assert kinds[9] == kinds[10] == {"compass", "distance", "name"}


def test_distance_answers_are_integers_within_the_level_cap():
    seen_max = {}
    for level, seed, puzzle in _all():
        if puzzle.meta["kind"] != "distance":
            continue
        solved = Solved(puzzle)
        a, b = solved.net if solved.walker else solved._gap(puzzle.meta["a"], puzzle.meta["b"])
        c = int(puzzle.answer)
        assert a * a + b * b == c * c, (level, seed)
        if a and b:
            assert TRIPLE_HYP[(abs(a), abs(b))] == c
        assert c <= params_for(level).max_distance, (level, seed, c)
        seen_max[level] = max(seen_max.get(level, 0), c)
    assert seen_max[1] <= 13 and seen_max[2] <= 15
    assert all(v <= 50 for v in seen_max.values())


def test_level_1_distance_never_exceeds_13_over_many_seeds():
    for seed in range(500):
        puzzle = generate(1, random.Random(seed))
        if puzzle.meta["kind"] == "distance":
            assert int(puzzle.answer) in (5, 10, 13)


def test_distance_questions_need_both_gaps_at_the_axis_levels():
    for level in (1, 2):
        for seed in SEEDS:
            puzzle = generate(level, random.Random(seed))
            if puzzle.meta["kind"] == "distance":
                assert all(Solved(puzzle).net)


def test_no_ties_and_the_move_changes_the_answer():
    hit = 0
    for level in (9, 10):
        for seed in SEEDS:
            puzzle = generate(level, random.Random(seed))
            if puzzle.meta["qtype"] != "near_far":
                continue
            solved = Solved(puzzle)
            word, ref = re.match(r"After the move, who is (\w+) to (\w+)\?", puzzle.question).groups()
            assert solved.extreme(word, ref) == puzzle.answer  # raises on a tie
            assert solved.extreme(word, ref, solved.placed) != puzzle.answer
            hit += 1
    assert hit > 20


def test_between_has_exactly_one_person_between():
    hit = 0
    for _, _, puzzle in _all((9, 10)):
        if puzzle.meta["qtype"] == "between":
            Solved(puzzle).answer()  # asserts exactly one
            hit += 1
    assert hit > 20


def test_answer_is_not_readable_from_one_clue():
    for level, seed, puzzle in _all():
        solved = Solved(puzzle)
        if puzzle.meta["kind"] == "compass" and solved.clues:
            for _, _, dx, dy in solved.clues:
                assert puzzle.answer != _compass(dx, dy), (level, seed)
        if puzzle.meta["kind"] == "compass" and solved.walker:
            assert puzzle.answer not in {d for d, _ in puzzle.meta["legs"]} or puzzle.meta["qtype"] == "facing"
            if puzzle.meta["qtype"] == "facing":
                assert sum(not ln.startswith("  Keeps") for ln in puzzle.lines[1:]) >= 2
        if puzzle.meta["kind"] == "distance":
            c = int(puzzle.answer)
            if solved.walker:
                assert all(k != c for _, k in puzzle.meta["legs"]), (level, seed)
            for _, _, dx, dy in solved.clues:
                assert c not in (abs(dx), abs(dy)) and math.hypot(dx, dy) != c, (level, seed)


def test_pairs_asked_are_not_directly_linked():
    for level, seed, puzzle in _all((5, 6, 7, 8)):
        solved = Solved(puzzle)
        a, b = puzzle.meta["a"], puzzle.meta["b"]
        assert all({n, r} != {a, b} for n, r, _, _ in solved.clues), (level, seed)
        if level >= 7:  # at least three links apart
            linked = {n: r for n, r, _, _ in solved.clues}
            chain = lambda x: [x] + (chain(linked[x]) if x in linked else [])  # noqa: E731
            ca, cb = chain(a), chain(b)
            meet = next(x for x in ca if x in cb)
            assert ca.index(meet) + cb.index(meet) >= 3, (level, seed)


@pytest.mark.parametrize("level", LEVELS)
def test_session_never_repeats_an_answer_a_type_run_or_a_layout(level):
    for seed in SEEDS:
        variety = Variety(random.Random(seed), veto=SPEC.session_veto)
        session = [variety.draw(generate, level) for _ in range(5)]
        assert len({p.answer.lower() for p in session}) == 5, (level, seed, [p.answer for p in session])
        types = [p.meta["qtype"] for p in session]
        assert all(a != b for a, b in zip(types, types[1:])), (level, seed, types)
        layouts = [_layout_ids(Solved(p)) for p in session]
        for i in range(5):
            for j in range(i):
                assert not layouts[i] & layouts[j], (level, seed, i, j)


def test_mirrored_route_is_vetoed_in_a_session():
    first = generate(1, random.Random(0))
    flipped = [(direction._OPPOSITE[d] if d in ("East", "West") else d, k) for d, k in first.meta["legs"]]
    mirrored = direction._walker_puzzle(first.meta["qtype"], "Zed", None, flipped, first.answer)
    assert mirrored.key == first.key
    assert SPEC.session_veto(mirrored, [first])


def test_params_contract():
    assert_params_contract(params_for, monotone_fields=("people", "max_distance", "mover"))
    assert [params_for(lv).max_distance for lv in LEVELS][:2] == [13, 15]


def test_walk_oracle():
    assert walk("North", [("East", 3), ("North", 4)]) == (3, 4)
    assert walk("North", [("right", 5), ("left", 3)]) == (5, 3)
    assert walk("East", [("back", 2), ("straight", 1), ("left", 4)]) == (-3, -4)


def _find(kind, level):
    for seed in range(300):
        puzzle = generate(level, random.Random(seed))
        if puzzle.meta["kind"] == kind:
            return puzzle
    raise AssertionError(kind)


@pytest.mark.parametrize("level", (1, 3, 9))
def test_every_compass_format_is_accepted(level):
    puzzle = _find("compass", level)
    full = puzzle.answer
    abbr = "".join(w[0] for w in full.split("-"))
    forms = [
        full,
        full.lower(),
        full.upper(),
        abbr,
        abbr.lower(),
        full.replace("-", " "),
        full.replace("-", ""),
        f" {abbr} ",
    ]
    forms += [full.replace("-", "").lower(), full.replace("-", " ").upper()]
    for form in forms:
        assert SPEC.grade(form, puzzle), form
    other = "East" if full != "East" else "West"
    assert not SPEC.grade(other, puzzle) and not SPEC.grade("far", puzzle) and not SPEC.grade("5", puzzle)


def test_parse_compass_covers_all_eight():
    for full in _EIGHT.values():
        assert parse_compass(full) == full
        assert parse_compass("".join(w[0] for w in full.split("-")).lower()) == full
    assert parse_compass("north-east") == parse_compass("N E") == parse_compass("northeast") == "North-East"
    assert parse_compass("up") is None and parse_compass("") is None


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
def test_distance_unit_and_format_inputs_parse(fmt):
    puzzle = _find("distance", 1)
    assert SPEC.grade(fmt(int(puzzle.answer)), puzzle)
    assert not SPEC.grade(fmt(int(puzzle.answer) + 1), puzzle)
    assert not SPEC.grade("North", puzzle)


def test_names_are_graded_without_case_or_spacing():
    puzzle = _find("name", 9)
    assert SPEC.grade(puzzle.answer.upper(), puzzle) and SPEC.grade(f" {puzzle.answer.lower()} ", puzzle)
    assert not SPEC.grade("Nobody", puzzle)


def test_hints_never_leak_the_answer_and_cancelling_is_only_mentioned_when_true():
    for level, seed, puzzle in _all():
        assert len(puzzle.static_hints) == 3, (level, seed)
        for hint in puzzle.static_hints:
            assert not leaks(hint, puzzle.answer, puzzle.forbidden), (level, seed, hint, puzzle.answer)
            if "cancel" in hint:
                legs = puzzle.meta["legs"]
                headings = {d for d, _ in legs}
                assert any(d in headings and direction._OPPOSITE[d] in headings for d in ("North", "East")), (
                    level,
                    seed,
                )


def test_explanation_states_the_answer():
    for level, seed, puzzle in _all((1, 5, 9), range(30)):
        assert puzzle.explanation and puzzle.answer.lower().replace("-", "") in puzzle.explanation.lower().replace(
            "-", ""
        )


def test_wording_has_no_he_she():
    for level, seed, puzzle in _all(LEVELS, range(30)):
        text = " ".join((*puzzle.lines, puzzle.question, *puzzle.static_hints, puzzle.explanation))
        assert not re.search(r"\b(he|she|his|her|him)\b", text, re.IGNORECASE), text


def _play(monkeypatch, profile, level=None):
    if level is not None:
        monkeypatch.setattr(profile, "difficulty", lambda game_id: level)
    monkeypatch.setattr(builtins, "input", lambda prompt="": "0" if prompt == "> " else "")
    monkeypatch.setattr("time.sleep", lambda s: None)
    direction.play_direction_sense(profile)
    return profile.db.get_user_stats(profile.require_user().id, limit=1)[0]


def test_play_stores_difficulty_and_scores_every_round(monkeypatch, capsys, profile):
    stats = _play(monkeypatch, profile)
    assert stats.difficulty == 1 and stats.accuracy == 0.0
    out = capsys.readouterr().out
    assert out.count("Correct:") == 5 and "Round 5/5" in out


@pytest.mark.parametrize("level", (4, 10))
def test_play_uses_the_stored_level(monkeypatch, capsys, profile, level):
    stats = _play(monkeypatch, profile, level)
    assert stats.difficulty == level
    assert capsys.readouterr().out.count("Round ") >= 5
