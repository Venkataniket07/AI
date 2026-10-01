"""Syllogisms: the set-model checker, then the generator built on it."""

import builtins
import itertools
import random
import re
import time
from collections import Counter

import pytest

from core.textguard import leaks
from games.engine.variety import Variety
from games.reasoning import syllogisms
from games.reasoning.syllogism_model import (
    ALL,
    CANNOT,
    FALSE,
    NO,
    SOME,
    SOME_NOT,
    TRUE,
    Stmt,
    UnsatisfiablePremises,
    holds,
    models,
    verdict,
    witness,
)
from games.reasoning.syllogisms import INVENTED_WORDS, OPTION_OF, SPEC, generate, params_for, parse_option
from tests.helpers import assert_params_contract
from tests.variety import variety_report


def _s(kind, x, y):
    return Stmt(kind, x, y)


# (premises, conclusion, verdict): the ten conclusions the old hand-typed templates used.
LEGACY = [
    ([(ALL, "A", "B"), (ALL, "B", "C")], (ALL, "A", "C"), TRUE),
    ([(ALL, "A", "B"), (ALL, "B", "C")], (SOME, "A", "C"), TRUE),
    ([(ALL, "A", "B"), (ALL, "B", "C")], (NO, "A", "C"), FALSE),
    ([(ALL, "A", "B"), (ALL, "B", "C")], (SOME_NOT, "C", "A"), CANNOT),
    ([(ALL, "A", "B"), (SOME, "B", "C")], (SOME, "A", "C"), CANNOT),
    ([(ALL, "A", "B"), (SOME, "B", "C")], (ALL, "A", "C"), CANNOT),
    ([(ALL, "A", "B"), (SOME, "B", "C")], (SOME, "B", "A"), TRUE),
    ([(SOME, "A", "B"), (NO, "B", "C")], (SOME_NOT, "A", "C"), TRUE),
    ([(SOME, "A", "B"), (NO, "B", "C")], (NO, "A", "C"), CANNOT),
    ([(SOME, "A", "B"), (NO, "B", "C")], (ALL, "A", "C"), FALSE),
]


@pytest.mark.parametrize("premises, conclusion, expected", LEGACY)
def test_verdict_classic_cases(premises, conclusion, expected):
    assert verdict([_s(*p) for p in premises], _s(*conclusion)) == expected


def test_nonempty_sets_decide_some_from_all():
    premises = [_s(ALL, "A", "B"), _s(ALL, "B", "C")]
    assert verdict(premises, _s(SOME, "A", "C")) == TRUE
    assert verdict(premises, _s(SOME, "A", "C"), nonempty=False) == CANNOT


def test_unsatisfiable_premises_raise():
    with pytest.raises(UnsatisfiablePremises):
        verdict([_s(ALL, "A", "B"), _s(NO, "A", "B")], _s(SOME, "A", "B"))
    assert models([_s(ALL, "A", "B"), _s(NO, "A", "B")]) == []


def test_holds_and_model_enumeration():
    premises = [_s(SOME, "A", "B")]
    every = models(premises)
    assert every and all(holds(premises[0], m) for m in every)
    assert any(not holds(_s(ALL, "A", "B"), m) for m in every)
    assert all(m.sets == ("A", "B") for m in every)


def test_statement_negation_and_restates():
    assert _s(ALL, "A", "B").negation() == _s(SOME_NOT, "A", "B")
    assert _s(NO, "A", "B").negation().negation() == _s(NO, "A", "B")
    assert _s(SOME, "A", "B").restates(_s(SOME, "B", "A"))
    assert not _s(ALL, "A", "B").restates(_s(ALL, "B", "A"))


def test_witness_shows_holding_and_failing_arrangements():
    premises = [_s(ALL, "A", "B"), _s(SOME, "B", "C")]
    holding, failing = witness(premises, _s(SOME, "A", "C"))
    assert holding is not None and holds(_s(SOME, "A", "C"), holding)
    assert failing is not None and not holds(_s(SOME, "A", "C"), failing)
    assert all(holds(p, m) for p in premises for m in (holding, failing))
    assert witness(premises, _s(SOME, "B", "A"))[1] is None


# ---- generator -------------------------------------------------------------------------------------------------

LEVELS = range(1, 11)
_PREMISE = re.compile(r"^- (All|Some|No) (\w+) are (not )?(\w+)\.$")
_CONCLUSION = re.compile(r"^Conclusion: (All|Some|No) (\w+) are (not )?(\w+)\.$")


def _read(puzzle):
    """The statements and conclusion as the player sees them: (kind, x, y) with 'SomeNot' for "are not"."""

    def parse(m):
        kind, x, neg, y = m.groups()
        return ("SomeNot" if neg else kind), x, y

    premises = [parse(m) for ln in puzzle.lines if (m := _PREMISE.match(ln))]
    conclusion = next(parse(m) for ln in puzzle.lines if (m := _CONCLUSION.match(ln)))
    return premises, conclusion


def _reference(premises, conclusion):
    """Second checker: element types as membership vectors, every set of types tried (no region bitmasks)."""
    names = list(dict.fromkeys(n for _, x, y in (*premises, conclusion) for n in (x, y)))
    types = list(itertools.product((0, 1), repeat=len(names)))

    def ok(stmt, present):
        kind, x, y = stmt
        i, j = names.index(x), names.index(y)
        if kind == "All":
            return all(t[j] for t in present if t[i])
        if kind == "No":
            return not any(t[i] and t[j] for t in present)
        if kind == "Some":
            return any(t[i] and t[j] for t in present)
        return any(t[i] and not t[j] for t in present)

    seen = set()
    for flags in itertools.product((False, True), repeat=len(types)):
        present = [t for t, f in zip(types, flags) if f]
        if not all(any(t[i] for t in present) for i in range(len(names))):
            continue
        if all(ok(p, present) for p in premises):
            seen.add(ok(conclusion, present))
            if len(seen) == 2:
                return "Cannot be determined"
    return {True: "True", False: "False"}[seen.pop()]


def _all_levels(n=300, seed=0):
    rng = random.Random(seed)
    return [generate(1 + i % 10, rng) for i in range(n)]


def test_generated_answer_equals_checker():
    four_set = 0
    for puzzle in _all_levels():
        if puzzle.meta["chain_len"] > 2:  # 65 536 models each in the reference: check a sample
            four_set += 1
            if four_set > 40:
                continue
        premises, conclusion = _read(puzzle)
        assert puzzle.answer == _reference(premises, conclusion), puzzle.lines


def test_answer_mix_balanced():
    for level in (1, 5, 9):
        rng = random.Random(0)
        counts = Counter(generate(level, rng).answer for _ in range(300))
        for answer in ("True", "False", "Cannot be determined"):
            assert 0.25 * 300 <= counts[answer] <= 0.42 * 300, (level, counts)


def test_no_run_longer_than_two():
    for seed in range(50):
        variety = Variety(random.Random(seed))
        for level in (1, 5, 9):
            answers = [variety.draw(generate, level).answer for _ in range(4)]
            variety.reset()
            assert all(len(set(answers[i : i + 3])) > 1 for i in range(2)), (level, seed, answers)


def test_no_repeat_in_session():
    for level in (1, 5, 9):
        for seed in range(50):
            variety = Variety(random.Random(seed))
            keys = [variety.draw(generate, level).key for _ in range(4)]
            assert len(set(keys)) == 4, (level, seed)


def test_invented_words_at_hard():
    for seed in range(40):
        hard, easy = generate(8, random.Random(seed)), generate(2, random.Random(seed))
        assert set(hard.meta["words"]) <= set(INVENTED_WORDS) and len(hard.meta["words"]) == 4
        assert not set(easy.meta["words"]) & set(INVENTED_WORDS)
        assert len(_read(hard)[0]) == 3 and len(_read(easy)[0]) == 2


def test_hint_guard_blocks_verdict_phrases():
    puzzle = generate(1, random.Random(0))
    for text in ("So it cannot be determined.", "The conclusion is true.", "It is false here.", "The answer is 2."):
        assert leaks(text, puzzle.answer, puzzle.forbidden), text
    assert not leaks("Draw a circle for each group and see how they overlap.", puzzle.answer, puzzle.forbidden)


def test_unsatisfiable_premises_never_generated():
    for puzzle in _all_levels():
        assert models(list(puzzle.meta["premises"])), puzzle.lines


def test_params_contract():
    assert_params_contract(params_for, monotone_fields=("chain_len", "invented_words"))
    pools = [len(params_for(level).shape_pool) for level in LEVELS]
    assert pools == sorted(pools) and pools[0] == 3 and pools[-1] > 3
    assert [params_for(level).chain_len for level in (1, 4, 7)] == [2, 2, 3]


def test_medium_adds_new_shapes():
    seen = {tuple(p.kind for p in generate(5, random.Random(s)).meta["premises"]) for s in range(300)}
    assert ("No", "All") in seen and ("SomeNot", "All") in seen


def test_generation_time_budget():
    start = time.perf_counter()
    _all_levels()
    assert time.perf_counter() - start < 5


def test_variety_report_floor():
    for level in (1, 4, 7, 10):
        assert variety_report(generate, level).distinct_keys >= 150, level


def test_explanation_is_checker_derived():
    for puzzle in _all_levels(60):
        w = puzzle.meta["witness"]
        assert (w["holds"] is None) == (puzzle.answer == "False")
        assert (w["fails"] is None) == (puzzle.answer == "True")
        assert puzzle.explanation.endswith("Every group has at least one member.")


def test_parse_option_and_grading():
    assert parse_option("(1)") == "1" and parse_option("Cannot be determined") == "3" and parse_option("x") == ""
    puzzle = generate(1, random.Random(0))
    assert SPEC.grade(OPTION_OF[puzzle.answer], puzzle)
    assert not SPEC.grade(next(o for o in "123" if o != OPTION_OF[puzzle.answer]), puzzle)


def test_play_scores_every_round(monkeypatch, capsys, profile):
    monkeypatch.setattr(builtins, "input", lambda prompt="": "1" if prompt == "> " else "")
    monkeypatch.setattr("time.sleep", lambda s: None)
    syllogisms.play_syllogisms(profile)
    stats = profile.db.get_user_stats(profile.require_user().id, limit=1)[0]
    assert stats.difficulty == 1
    assert "Round 4/4" in capsys.readouterr().out
