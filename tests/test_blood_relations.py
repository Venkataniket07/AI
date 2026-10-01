"""Blood Relations generator: unique answers, families, answer types, options, hints, session rules."""

import random
import re

import pytest

from core.textguard import leaks
from games.engine.variety import Variety
from games.reasoning import blood_relations
from games.reasoning.blood_families.names import FEMALE_NAMES, MALE_NAMES
from games.reasoning.blood_relations import generate, grade, params_for, session_veto, wrong_but_valid_feedback
from games.reasoning.family import _outcomes, answers_unique, evaluate, relation
from tests.helpers import assert_params_contract
from tests.variety import variety_report

SEEDS = range(200)
LEVELS = range(1, 11)
BANDS = (1, 5, 9)


def _puzzles(levels=LEVELS, seeds=SEEDS):
    for level in levels:
        for seed in seeds:
            yield level, generate(level, random.Random(seed))


def _of_type(answer_type, levels=LEVELS, seeds=SEEDS):
    return [(lv, p) for lv, p in _puzzles(levels, seeds) if p.meta["answer_type"] == answer_type]


def test_answers_unique_over_200_puzzles():
    for level, p in _puzzles():
        assert p.meta["family"] != "legacy", f"generation failed at level {level}"
        tree, a, b = p.meta["tree"], p.meta["a"], p.meta["b"]
        if p.meta["answer_type"] == "relation":
            assert answers_unique(p.meta["check_facts"], a, b), p.lines
            assert relation(tree, a, b) == p.answer
        elif p.meta["answer_type"] == "name":
            term = p.answer_bucket.removeprefix("name:")
            assert _outcomes(p.meta["check_facts"], p.answer, b) == {term}, p.lines
        else:
            assert p.answer == str(int(p.answer))


def test_same_person_never_both_sides():
    for _, p in _puzzles(seeds=range(60)):
        if p.meta["b"] is not None:
            assert p.meta["a"] != p.meta["b"]
        assert all(f.x != f.y for f in p.meta["check_facts"])


def test_gender_clues_sufficient():
    """Hide any one gender statement: the answer is then either still the same or no longer settled."""
    checked = 0
    for _, p in _of_type("relation", seeds=range(80)):
        a, b = p.meta["a"], p.meta["b"]
        for fact in p.meta["check_facts"]:
            if fact.y is None:
                rest = [f for f in p.meta["check_facts"] if f is not fact]
                outcomes = _outcomes(rest, a, b)
                assert outcomes == {p.answer} or len(outcomes) > 1, (p.lines, fact)
                checked += 1
    assert checked > 0


def test_answer_types_graded_correctly():
    relation_p = _of_type("relation", seeds=range(30))[0][1]
    assert grade(relation_p.answer, relation_p) and grade(relation_p.answer.upper(), relation_p)
    wrong = "Wife" if relation_p.answer != "Wife" else "Husband"
    assert not grade(wrong, relation_p)

    name_p = _of_type("name", seeds=range(60))[0][1]
    assert grade(name_p.answer, name_p) and grade(f" {name_p.answer.lower()} ", name_p)
    assert not grade("Nobody", name_p)

    count_p = _of_type("count", seeds=range(30))[0][1]
    n = int(count_p.answer)
    assert grade(str(n), count_p) and grade(f" {n}. ", count_p)
    assert not grade(str(n + 1), count_p) and not grade("many", count_p)


def test_name_answers_are_names_or_labels():
    pool = set(MALE_NAMES) | set(FEMALE_NAMES)
    for _, p in _of_type("name", seeds=range(80)):
        assert p.answer in pool or re.fullmatch(r"[A-L]", p.answer)


def test_name_pools():
    assert len(MALE_NAMES) >= 60 and len(set(MALE_NAMES)) == len(MALE_NAMES)
    assert len(FEMALE_NAMES) >= 60 and len(set(FEMALE_NAMES)) == len(FEMALE_NAMES)
    assert not set(MALE_NAMES) & set(FEMALE_NAMES)


def test_no_options_at_medium_and_hard():
    for _, p in _puzzles(levels=range(4, 11), seeds=range(60)):
        assert p.meta["options"] == ()
        assert not any(line.startswith("Options") for line in p.lines)


def test_options_contain_answer_and_no_etc():
    shown = 0
    for _, p in _of_type("relation", levels=range(1, 4)):
        options = p.meta["options"]
        if options:
            shown += 1
            assert p.answer in options and len(set(options)) == len(options)
            assert any(line == f"Options: {', '.join(options)}" for line in p.lines)
        assert not any("etc" in line.lower() for line in p.lines)
    assert shown > 0


def test_options_exclude_impossible_relations():
    for _, p in _of_type("relation", levels=range(1, 4)):
        tree, a = p.meta["tree"], p.meta["a"]
        possible = {relation(tree, a, c) for c in tree.names} - {None}
        assert set(p.meta["options"]) <= possible | {p.answer}
        assert "Nephew" not in p.meta["options"] or "Nephew" in possible


def test_red_herring_never_changes_answer():
    herring_puzzles = 0
    for level, p in _puzzles(seeds=range(60)):
        herrings = p.meta["herrings"]
        if level <= 3:
            assert herrings == ()
        if not herrings or p.meta["answer_type"] == "count":
            continue
        herring_puzzles += 1
        base = [f for f in p.meta["check_facts"] if f not in herrings]
        a, b = p.meta["a"], p.meta["b"]
        term = p.answer if p.meta["answer_type"] == "relation" else p.answer_bucket.removeprefix("name:")
        assert _outcomes(base, a if p.meta["answer_type"] == "relation" else p.answer, b) == {term}, p.lines
    assert herring_puzzles > 0


def test_variety_floors_per_band():
    for level in BANDS:
        report = variety_report(generate, level)
        assert report.distinct_keys >= 40
        assert report.distinct_answers >= 12, (level, report)
        assert report.family_share <= 0.4, (level, report)


def test_at_least_20_distinct_story_answer_pairs_over_200():
    for level in BANDS:
        rng = random.Random(0)
        pairs = {(p.key, p.answer) for p in (generate(level, rng) for _ in range(200))}
        assert len(pairs) >= 20


def _session(seed, level=None):
    rng = random.Random(seed)
    level = level or 1 + seed % 10
    variety = Variety(rng, veto=session_veto)
    return [variety.draw(generate, level) for _ in range(4)]


def test_session_never_repeats_signature():
    for seed in range(100):
        signatures = [p.meta["signature"] for p in _session(seed)]
        assert len(set(signatures)) == 4, signatures


def test_family_at_most_twice_in_four():
    for seed in range(100):
        families = [p.meta["family"] for p in _session(seed)]
        assert max(families.count(f) for f in set(families)) <= 2, families


def test_answer_differs_from_previous_round():
    for seed in range(100):
        buckets = [p.answer_bucket for p in _session(seed)]
        assert all(x != y for x, y in zip(buckets, buckets[1:])), buckets


def test_wrong_but_valid_feedback_text(capsys):
    for _, p in _of_type("relation", levels=range(1, 4)):
        tree, a, b = p.meta["tree"], p.meta["a"], p.meta["b"]
        if p.meta["speaker"]:
            continue
        for other in p.meta["named"]:
            term = relation(tree, a, other) if other not in (a, b) else None
            if term and term != p.answer:
                first = next(c for c in p.meta["named"] if c not in (a, b) and relation(tree, a, c) == term)
                expected = f"{term} is {a} to {first}, not {a} to {b}."
                assert wrong_but_valid_feedback(term, p) == expected
                assert not grade(term, p)
                assert expected in capsys.readouterr().out
                return
    pytest.fail("no puzzle with a wrong-but-valid relation found")


def test_no_feedback_when_typed_relation_fits_nobody_else():
    p = _of_type("relation", seeds=range(5))[0][1]
    assert wrong_but_valid_feedback("zzz", p) is None
    assert wrong_but_valid_feedback("", p) is None


def test_hint3_never_leaks():
    for _, p in _puzzles(seeds=range(80)):
        assert not leaks(p.static_hints[2], p.answer, p.forbidden), (p.static_hints[2], p.answer)
        assert "starts with the letter" not in p.static_hints[2]


def test_speaker_is_never_named():
    seen = 0
    for _, p in _puzzles(seeds=range(80)):
        speaker = p.meta["speaker"]
        if speaker:
            seen += 1
            text = " ".join((*p.lines, p.question, *p.static_hints, p.explanation))
            assert not re.search(rf"\b{re.escape(speaker)}\b", text), text
            assert "you" in text.lower()
    assert seen > 0


def test_statement_order_and_wording_vary():
    stories = {generate(5, random.Random(s)).lines[0] for s in range(100)}
    assert len(stories) > 50


def test_params_contract():
    assert_params_contract(params_for, monotone_fields=["hops", "generations", "people", "red_herrings"])
    assert params_for(1).options and not params_for(4).options and not params_for(10).options
    assert params_for(1).red_herrings == 0 and params_for(4).red_herrings >= 1


def test_vocabulary_is_derived_from_the_rule_table():
    from games.reasoning.family import VOCABULARY

    for term in VOCABULARY:
        assert blood_relations.normalize(term) in blood_relations.KNOWN_RELATIONS


def test_cousin_gender_variants_follow_the_cousin():
    for _, p in _puzzles(levels=range(5, 11), seeds=range(200)):
        if p.answer == "Cousin" and p.meta["answer_type"] == "relation":
            male = p.meta["tree"].gender(p.meta["a"]) == "M"
            assert grade("cousin brother" if male else "cousin sister", p)
            assert not grade("cousin sister" if male else "cousin brother", p)
            return
    pytest.fail("no cousin puzzle found")


def test_falls_back_to_the_old_templates_if_generation_keeps_failing(monkeypatch):
    def boom(*args, **kwargs):
        raise ValueError("no family")

    monkeypatch.setattr(blood_relations, "random_family", boom)
    p = generate(3, random.Random(0))
    assert p.meta["family"] == "legacy"
    assert grade(p.answer, p) and not grade("Wife", p)
    assert not session_veto(p, [])


def test_evaluate_counts_over_every_completion():
    from games.reasoning.family import Fact

    facts = [Fact("father", "A", "B"), Fact("father", "A", "C")]
    # B and C have unknown genders, so the number of sons A has can be 0, 1 or 2.
    result = evaluate(facts, lambda fam: sum(1 for c in fam.children_of("A") if fam.gender(c) == "M"), ("A",))
    assert result == {0, 1, 2}
