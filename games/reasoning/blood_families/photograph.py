"""Photograph: "Pointing to a photograph, X said, 'He is the son of my father's brother.'" The pictured person is never named."""

import random

from games.engine.puzzle import Puzzle
from games.reasoning.blood_families.collapse import _route
from games.reasoning.blood_families.common import (
    Voice,
    assemble,
    generation_hint,
    red_herrings,
    render_fact,
    render_facts,
)
from games.reasoning.blood_families.names import rename
from games.reasoning.family import Fact, Family, evaluate, relation

weight = 2
min_level = 4
REVERSE_SHARE = 0.5  # ask what the speaker is to the pictured person
PICTURE = "the person in the photograph"


def build(rng: random.Random, family: Family, params) -> Puzzle:
    tree = rename(rng, family)
    pictured, speaker, nouns, people = _route(rng, tree, params.hops)
    truth = relation(tree, pictured, speaker)
    ids = [pictured, *(f"_{i}" for i in range(1, len(nouns))), speaker]  # people on the way are never named
    chain = [Fact(n, ids[i], ids[i + 1]) for i, n in enumerate(nouns)]
    sex = Fact("man" if tree.gender(speaker) == "M" else "woman", speaker)  # the speaker's gender is stated
    base = [*chain, sex]

    a, b = pictured, speaker
    if rng.random() < REVERSE_SHARE:
        reverse = relation(tree, speaker, pictured)
        if reverse and evaluate(base, lambda fam: relation(fam, speaker, pictured), (pictured, speaker)) == {reverse}:
            a, b, truth = speaker, pictured, reverse

    def query(fam):
        return relation(fam, a, b)

    def holds(fs):
        return evaluate(fs, query, (a, b)) == {truth}

    herrings = red_herrings(rng, tree, base, params.red_herrings, holds, avoid=people) if params.red_herrings else []
    he = "He" if tree.gender(pictured) == "M" else "She"
    riddle = f"{he} is the {nouns[0]} of my " + "'s ".join(reversed(nouns[1:])) + "."
    lines = [
        render_fact(rng, sex, Voice()),
        f'Pointing to a photograph, {speaker} said, "{riddle}"',
        *render_facts(rng, herrings, Voice()),
    ]
    if a == pictured:
        question = f"How is {PICTURE} related to {speaker}?"
        hint = generation_hint(tree, a, b, Voice(), anonymous=True)
    else:
        question = f"How is {speaker} related to {PICTURE}?"
        hint = generation_hint(tree, a, b, Voice(), anonymous=False).replace(pictured, PICTURE)
    puzzle = assemble(
        family_name="photograph",
        family=tree,
        voice=Voice(),
        lines=lines,
        check_facts=[*base, *herrings],
        query=query,
        truth=truth,
        must_name=(pictured, speaker),
        a=a,
        b=b,
        answer=truth,
        answer_type="relation",
        bucket=truth,
        shape="+".join(nouns) + (":reverse" if a == speaker else ""),
        question=question,
        hint3=hint,
        explanation=(
            f"Start from {speaker}: {' then '.join(reversed(nouns[1:]))}, and the person pictured is that "
            f"person's {nouns[0]}. So the pictured person is {speaker}'s {relation(tree, pictured, speaker).lower()}"
            + (f", and {speaker} is the pictured person's {truth.lower()}." if a == speaker else ".")
        ),
        stated=[sex, *herrings],
        herrings=herrings,
    )
    puzzle.meta["unnamed"] = pictured
    return puzzle
