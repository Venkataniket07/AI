"""Chain: the links are stated one at a time ("A is B's mother. B is C's brother."), then one relation is asked."""

import random

from games.engine.puzzle import Puzzle
from games.reasoning.blood_families.common import (
    Voice,
    assemble,
    ask_relation,
    generation_hint,
    known_genders,
    red_herrings,
    relation_options,
    render_facts,
)
from games.reasoning.blood_families.names import rename
from games.reasoning.family import Family, evaluate, pose, relation

weight = 3
min_level = 1
NAME_QUESTION_SHARE = 0.3  # asked as "Which person is X's uncle?" instead of "What is A to X?"
SPEAKER_SHARE = 0.25  # the asked-about person is "you"
REVERSE_SHARE = 0.5  # ask what the second person is to the first


def build(rng: random.Random, family: Family, params) -> Puzzle:
    named = rng.random() < 0.5
    tree = rename(rng, family) if named else family
    scenario = pose(tree, rng, params.hops, "mixed" if params.indirect else "direct")
    facts = [f for f in scenario.facts if not (named and f.y is None)]
    a, b, truth = scenario.a, scenario.b, scenario.answer

    def checked(fs):
        return [*fs, *known_genders(tree, fs)] if named else list(fs)

    def holds_for(x, y, want):
        return lambda fs: evaluate(checked(fs), lambda fam: relation(fam, x, y), (x, y)) == {want}

    if rng.random() < REVERSE_SHARE:
        reverse = relation(tree, b, a)
        if reverse and holds_for(b, a, reverse)(facts):
            a, b, truth = b, a, reverse

    as_name = rng.random() < NAME_QUESTION_SHARE
    if as_name:
        people = sorted({n for f in facts for n in (f.x, f.y) if n and n != b})

        def query(fam):
            return frozenset(n for n in people if relation(fam, n, b) == truth)

        as_name = evaluate(checked(facts), query, (a, b)) == {frozenset((a,))}
    if not as_name:

        def query(fam):
            return relation(fam, a, b)

    want = frozenset((a,)) if as_name else truth

    def holds(fs):
        return evaluate(checked(fs), query, (a, b)) == {want}

    herrings = red_herrings(rng, tree, facts, params.red_herrings, holds) if params.red_herrings else []
    stated = facts + herrings
    rng.shuffle(stated)
    voice = Voice(b if rng.random() < SPEAKER_SHARE else None)
    if as_name:
        question = f"Which person is {voice.poss(b)} {truth.lower()}?"
    else:
        question = ask_relation(rng, a, b, voice)
    options = relation_options(rng, tree, a, b, truth) if params.options and not as_name else ()
    answer = a if as_name else truth
    shape = "+".join(f.kind for f in scenario.facts if f.y is not None)
    return assemble(
        family_name="chain",
        family=tree,
        voice=voice,
        lines=render_facts(rng, stated, voice),
        check_facts=checked(stated),
        query=query,
        truth=want,
        must_name=(a, b),
        a=a,
        b=b,
        answer=answer,
        answer_type="name" if as_name else "relation",
        bucket=f"name:{truth}" if as_name else truth,
        shape=("name:" if as_name else "") + shape,
        question=question,
        hint3=generation_hint(tree, a, b, voice, anonymous=as_name),
        explanation=(
            f"Putting the statements together, {voice.ref(a)} {voice.be(a)} {voice.poss(b)} {truth.lower()}"
            + (f", so the answer is {a}." if as_name else ".")
        ),
        options=options,
        stated=stated,
        herrings=herrings,
    )
