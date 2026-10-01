import random

import pytest

from games.reasoning.family import (
    RELATION_RULES,
    Fact,
    Family,
    Person,
    answers_unique,
    describe,
    pose,
    random_family,
    relation,
)


def hand_family() -> Family:
    people = [
        Person("GF", "M"), Person("GM", "F"),
        Person("Dad", "M"), Person("Aunt", "F"), Person("Unc", "M"),
        Person("Mom", "F"), Person("AuntH", "M"), Person("UncW", "F"),
        Person("GF2", "M"), Person("GM2", "F"), Person("Bro", "M"),
        Person("S", "M"), Person("D", "F"), Person("C", "M"),
    ]  # fmt: skip
    parents = {
        "Dad": ("GF", "GM"), "Aunt": ("GF", "GM"), "Unc": ("GF", "GM"),
        "Mom": ("GF2", "GM2"), "Bro": ("GF2", "GM2"),
        "S": ("Dad", "Mom"), "D": ("Dad", "Mom"), "C": ("AuntH", "Aunt"),
    }  # fmt: skip
    spouses = [("GF", "GM"), ("GF2", "GM2"), ("Dad", "Mom"), ("AuntH", "Aunt"), ("Unc", "UncW")]
    return Family(people, parents, spouses)


CASES = [
    ("GF", "S", "Grandfather"), ("S", "GF", "Grandson"),
    ("GM", "D", "Grandmother"), ("D", "GM", "Granddaughter"),
    ("Dad", "S", "Father"), ("Mom", "D", "Mother"),
    ("S", "Dad", "Son"), ("D", "Mom", "Daughter"),
    ("S", "D", "Brother"), ("D", "S", "Sister"),
    ("Unc", "S", "Uncle"), ("S", "Unc", "Nephew"),
    ("Aunt", "S", "Aunt"), ("D", "Aunt", "Niece"),
    ("C", "S", "Cousin"), ("S", "C", "Cousin"),
    ("AuntH", "S", "Uncle"),  # aunt's husband
    ("Bro", "S", "Uncle"),  # mother's brother
    ("Bro", "Dad", "Brother-in-law"),  # spouse's brother
    ("Dad", "Bro", "Brother-in-law"),
    ("AuntH", "Dad", "Brother-in-law"),  # sister's husband
    ("Dad", "AuntH", "Brother-in-law"),
    ("UncW", "Dad", "Sister-in-law"), ("Mom", "Aunt", "Sister-in-law"),
    ("GF2", "Dad", "Father-in-law"), ("GM2", "Dad", "Mother-in-law"),
    ("GF", "Mom", "Father-in-law"),
    ("Dad", "GF2", "Son-in-law"), ("Mom", "GF", "Daughter-in-law"),
    ("Dad", "Mom", "Husband"), ("Mom", "Dad", "Wife"),
    ("UncW", "C", "Aunt"),
    ("Bro", "C", None), ("GF", "GF2", None), ("S", "S", None),
]  # fmt: skip


@pytest.mark.parametrize("a,b,expected", CASES)
def test_hand_written_relations(a, b, expected):
    assert relation(hand_family(), a, b) == expected


def test_hand_family_is_valid():
    fam = hand_family()
    fam.validate()
    assert fam.generations() == 3


CATEGORY = {}
for _key, _rule in RELATION_RULES.items():
    CATEGORY[_rule.male] = CATEGORY[_rule.female] = _key
INVERSE = {
    "parent": "child", "child": "parent", "grandparent": "grandchild", "grandchild": "grandparent",
    "uncle": "nephew", "nephew": "uncle", "sibling": "sibling", "spouse": "spouse", "cousin": "cousin",
    "sibling_in_law": "sibling_in_law", "parent_in_law": "child_in_law", "child_in_law": "parent_in_law",
}  # fmt: skip


def check_inverses(fam: Family) -> int:
    seen = 0
    for a in fam.names:
        for b in fam.names:
            fwd, back = relation(fam, a, b), relation(fam, b, a)
            if fwd is None or back is None:
                continue
            seen += 1
            # in-law and by-marriage terms may pair with a different family link, so compare categories
            # only where the pair is unambiguous
            assert INVERSE[CATEGORY[fwd]] == CATEGORY[back] or {CATEGORY[fwd], CATEGORY[back]} & {
                "uncle",
                "nephew",
                "sibling_in_law",
                "parent_in_law",
                "child_in_law",
            }, (a, b, fwd, back)
            rule = RELATION_RULES[CATEGORY[back]]
            if rule.male != rule.female:
                assert rule.term(fam.gender(b)) == back, (a, b, fwd, back)
    return seen


def test_relation_symmetry_pairs():
    assert check_inverses(hand_family()) > 40
    for seed in range(50):
        check_inverses(random_family(random.Random(seed), 3, 7))


@pytest.mark.parametrize("generations,people", [(2, 5), (2, 6), (2, 7), (3, 5), (3, 6), (3, 7)])
def test_random_family_valid(generations, people):
    for seed in range(200):
        fam = random_family(random.Random(seed), generations, people)
        fam.validate()  # acyclic, <= 2 parents, matching marriages
        assert len(fam.people) == people
        assert len({p.name for p in fam.people}) == people
        assert all(p.gender in ("M", "F") for p in fam.people)
        assert all(len(fam.parents_of(n)) <= 2 for n in fam.names)
        assert fam.generations() == generations


def test_random_family_rejects_impossible_sizes():
    with pytest.raises(ValueError):
        random_family(random.Random(0), 3, 4)
    with pytest.raises(ValueError):
        random_family(random.Random(0), 1, 5)


def test_answers_unique_detects_ambiguity():
    # Q's gender is never stated, so Q is C's uncle or aunt.
    facts = [Fact("brother", "P", "Q"), Fact("son", "C", "P")]
    assert not answers_unique(facts, "Q", "C")
    assert answers_unique(facts + [Fact("woman", "Q")], "Q", "C")
    assert answers_unique([Fact("sister", "Q", "P"), Fact("son", "C", "P")], "Q", "C")


def test_answers_unique_needs_the_link():
    assert not answers_unique([Fact("brother", "P", "Q")], "Q", "Z")  # Z not mentioned
    assert not answers_unique([Fact("brother", "P", "Q"), Fact("son", "C", "P")], "Z", "C")


def test_answers_unique_rejects_contradictions():
    assert not answers_unique([Fact("man", "A"), Fact("woman", "A")], "A", "B")


def test_parent_gender_decides_in_law_answers():
    # A is a woman married to B's brother, or B's sister's... only B's brother is stated here.
    facts = [Fact("wife", "A", "H"), Fact("brother", "H", "B")]
    assert answers_unique(facts, "A", "B")
    assert answers_unique(facts, "H", "A")


@pytest.mark.parametrize("hops", [1, 2, 3])
def test_pose_is_unique_and_matches_family(hops):
    for seed in range(200):
        rng = random.Random(seed)
        fam = random_family(rng, rng.choice([2, 3]), rng.randint(5, 7))
        try:
            sc = pose(fam, rng, hops)
        except ValueError:
            continue  # no pair that far apart in this family
        assert sc.answer == relation(fam, sc.a, sc.b)
        assert answers_unique(sc.facts, sc.a, sc.b)
        assert len(sc.lines) == len(sc.facts)


def test_pose_exists_for_most_seeds():
    ok = 0
    for seed in range(100):
        rng = random.Random(seed)
        try:
            pose(random_family(rng, 3, 7), rng, 2)
            ok += 1
        except ValueError:
            pass
    assert ok >= 90


def test_describe_wording_and_styles():
    rng = random.Random(4)
    fam = random_family(rng, 3, 7)
    lines = describe(fam, rng, 2, style="direct")
    assert lines and all(line.endswith(".") for line in lines)
    assert str(Fact("brother", "A", "B")) == "A is B's brother."
    assert str(Fact("man", "A")) == "A is a man."
