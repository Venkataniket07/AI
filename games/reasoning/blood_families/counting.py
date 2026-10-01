"""Counting: the members of a family are listed, then "How many sons / brothers / cousins ...?" is asked."""

import random

from games.engine.puzzle import Puzzle
from games.reasoning.blood_families.common import Voice, assemble, known_genders, render_facts
from games.reasoning.blood_families.names import rename
from games.reasoning.family import Fact, Family, _edge_fact, _is_cousin

weight = 3
min_level = 1

# Count types by difficulty tier (the number of red herrings): (word, who is counted, gender counted or None)
_BY_TIER = (
    (("sons", "children", "M"), ("daughters", "children", "F")),
    (("brothers", "siblings", "M"), ("sisters", "siblings", "F")),
    (("cousins", "cousins", None), ("grandchildren", "grandchildren", None)),
)


def _child_facts(rng: random.Random, family: Family, parent: str, mixed: bool) -> list[Fact]:
    facts = []
    for child in family.children_of(parent):
        sex = family.gender(child)
        if mixed and rng.random() < 0.4:
            facts.append(Fact("father" if family.gender(parent) == "M" else "mother", parent, child))
            facts.append(Fact("man" if sex == "M" else "woman", child))
        else:
            facts.append(Fact("son" if sex == "M" else "daughter", child, parent))
    return facts


def _pick_subject(rng: random.Random, family: Family, who: str) -> str | None:
    people = list(family.names)
    rng.shuffle(people)
    for n in people:
        kids = family.children_of(n)
        parents = family.parents_of(n)
        if who == "children" and len(kids) >= 2:
            return n
        if who == "siblings" and parents and family.siblings_of(n):
            return n
        if who == "grandchildren" and any(family.children_of(k) for k in kids):
            return n
        if who == "cousins" and parents and any(family.children_of(s) for s in family.siblings_of(parents[0])):
            return n
    return None


def build(rng: random.Random, family: Family, params) -> Puzzle:
    named = rng.random() < 0.5
    tree = rename(rng, family) if named else family
    word, who, sex = rng.choice(_BY_TIER[min(params.red_herrings, 2)])
    subject = _pick_subject(rng, tree, who)
    if subject is None:
        raise ValueError(f"no one to count {word} for")
    mixed = params.indirect
    gender_word = "males" if sex == "M" else "females"

    if who == "children":
        facts = _child_facts(rng, tree, subject, mixed)
        closing = f"{subject} has no other children."
        hint = f"Go through every child of {subject} and count only the {gender_word}."

        def query(fam):
            return sum(1 for c in fam.children_of(subject) if fam.gender(c) == sex)

    elif who == "siblings":
        parent = rng.choice(tree.parents_of(subject))
        facts = _child_facts(rng, tree, parent, mixed)
        closing = f"{parent} has no other children."
        hint = f"List the other children of {parent}, then count only the {gender_word}."

        def query(fam):
            return sum(1 for s in fam.siblings_of(subject) if fam.gender(s) == sex)

    elif who == "grandchildren":
        facts = _child_facts(rng, tree, subject, mixed)
        for kid in tree.children_of(subject):
            facts += _child_facts(rng, tree, kid, mixed)
        closing = "Nobody else is in this family."
        hint = f"Count the children of each of {subject}'s children."

        def query(fam):
            return sum(len(fam.children_of(k)) for k in fam.children_of(subject))

    else:
        parent = tree.parents_of(subject)[0]
        facts = [f for f in _child_facts(rng, tree, parent, mixed) if subject in (f.x, f.y)]
        for s in tree.siblings_of(parent):
            low, high = sorted((s, parent))
            facts.append(_edge_fact(tree, rng, ("sibling", low, high), "mixed" if mixed else "direct"))
            facts += _child_facts(rng, tree, s, mixed)
        closing = "Nobody else is in this family."
        hint = f"Find the brothers and sisters of {subject}'s parent, then count their children."

        def query(fam):
            return sum(1 for n in fam.names if _is_cousin(fam, n, subject))

    truth = query(tree)
    if named:
        facts = [f for f in facts if f.y is not None]  # a name already tells the gender
    voice = Voice()
    stated = list(facts)
    rng.shuffle(stated)
    return assemble(
        family_name="counting",
        family=tree,
        voice=voice,
        lines=[*render_facts(rng, stated, voice), closing],
        check_facts=[*facts, *known_genders(tree, facts)] if named else facts,
        query=query,
        truth=truth,
        must_name=(subject,),
        a=subject,
        b=None,
        answer=str(truth),
        answer_type="count",
        bucket=f"count:{truth}",
        shape=word,
        question=f"How many {word} does {subject} have?",
        hint3=hint,
        explanation=f"Counting only the people listed, {subject} has {truth} {word}.",
        stated=stated,
    )
