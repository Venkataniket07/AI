"""Collapse: one compound sentence ("A is B's father's sister's son.") whose chain the player reduces to one relation."""

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
from games.reasoning.family import Fact, Family, _edges, _shortest_path, evaluate, relation

weight = 3
min_level = 1
SPEAKER_SHARE = 0.25


def _noun(family: Family, kind: str, u: str, node: str) -> str:
    """What `node` (one end of a link whose first end is `u`) is to the other end."""
    g = family.gender(node)
    if kind == "parent":
        if node == u:
            return "father" if g == "M" else "mother"
        return "son" if g == "M" else "daughter"
    if kind == "sibling":
        return "brother" if g == "M" else "sister"
    return "husband" if g == "M" else "wife"


def _route(rng: random.Random, family: Family, hops: int):
    """(a, b, nouns, people): two people `hops` links apart, and what each person on the way is to the next."""
    adj: dict[str, list] = {n: [] for n in family.names}
    for e in _edges(family):
        adj[e[1]].append((e[2], e))
        adj[e[2]].append((e[1], e))
    pairs = [
        (a, b)
        for a in family.names
        for b in family.names
        if a != b and relation(family, a, b) and len(_shortest_path(adj, a, b)) == hops
    ]
    if not pairs:
        raise ValueError(f"no pair of people is {hops} links apart")
    a, b = rng.choice(pairs)
    nouns, people, here = [], [a], a
    for kind, u, v in _shortest_path(adj, a, b):
        nouns.append(_noun(family, kind, u, here))
        here = v if here == u else u
        people.append(here)
    return a, b, nouns, people


def build(rng: random.Random, family: Family, params) -> Puzzle:
    named = rng.random() < 0.5
    tree = rename(rng, family) if named else family
    a, b, nouns, people = _route(rng, tree, params.hops)
    truth = relation(tree, a, b)

    ids = [a, *(f"_{i}" for i in range(1, len(nouns))), b]  # people on the way are never named
    chain_facts = [Fact(n, ids[i], ids[i + 1]) for i, n in enumerate(nouns)]

    def checked(fs):
        return [*fs, *known_genders(tree, fs)] if named else list(fs)

    def holds(fs):
        return evaluate(checked(fs), lambda fam: relation(fam, a, b), (a, b)) == {truth}

    herrings = (
        red_herrings(rng, tree, chain_facts, params.red_herrings, holds, avoid=people) if params.red_herrings else []
    )
    voice = Voice(b if rng.random() < SPEAKER_SHARE else None)
    if voice.speaker is None and rng.random() < 0.5:
        compound = f"{a} is the " + " of the ".join(nouns) + f" of {b}."
    else:
        compound = f"{a} is {voice.poss(b)} " + "'s ".join(reversed(nouns)) + "."
    lines = [compound, *render_facts(rng, herrings, voice)]
    rng.shuffle(lines)
    return assemble(
        family_name="collapse",
        family=tree,
        voice=voice,
        lines=lines,
        check_facts=checked([*chain_facts, *herrings]),
        query=lambda fam: relation(fam, a, b),
        truth=truth,
        must_name=(a, b),
        a=a,
        b=b,
        answer=truth,
        answer_type="relation",
        bucket=truth,
        shape="+".join(nouns),
        question=ask_relation(rng, a, b, voice),
        hint3=generation_hint(tree, a, b, voice, anonymous=False),
        explanation=(
            f"Follow the chain one link at a time from {voice.ref(b)} to {a}: "
            f"{' then '.join(reversed(nouns))}. That makes {a} {voice.poss(b)} {truth.lower()}."
        ),
        options=relation_options(rng, tree, a, b, truth) if params.options else (),
        stated=herrings,
        herrings=herrings,
    )
