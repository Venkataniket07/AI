"""Syllogisms: the set-model checker, then the generator built on it."""

import pytest

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
