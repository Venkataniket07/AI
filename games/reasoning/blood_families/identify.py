"""Identify: everyone is named in the statements, then "Who is the mother of A's uncle?" asks for one person's name."""

import dataclasses
import random

from games.engine.puzzle import Puzzle
from games.reasoning.blood_families.common import (
    Voice,
    assemble,
    generation_hint,
    known_genders,
    red_herrings,
    render_facts,
)
from games.reasoning.blood_families.names import rename
from games.reasoning.family import Family, _edge_fact, _edges, _shortest_path, evaluate, relation

weight = 2
min_level = 3
MAX_LINKS = 4  # statements needed to join the three people
PICK_TRIES = 60


def _adjacency(family: Family) -> dict[str, list]:
    adj: dict[str, list] = {n: [] for n in family.names}
    for e in _edges(family):
        adj[e[1]].append((e[2], e))
        adj[e[2]].append((e[1], e))
    return adj


def _pick(rng: random.Random, family: Family):
    """(p, q, z, first, second, edges): q is p's `first`, z is q's `second`, joined by at most MAX_LINKS links."""
    adj = _adjacency(family)
    names = list(family.names)
    for _ in range(PICK_TRIES):
        p, q, z = rng.sample(names, 3)
        first, second = relation(family, q, p), relation(family, z, q)
        if not first or not second:
            continue
        links = _shortest_path(adj, p, q) + _shortest_path(adj, q, z)
        if 1 < len(links) <= MAX_LINKS:
            return p, q, z, first, second, list(dict.fromkeys(links))
    raise ValueError("no identifiable triple")


def build(rng: random.Random, family: Family, params) -> Puzzle:
    tree = rename(rng, family)  # names carry the gender, so no gender statements are needed
    p, q, z, first, second, links = _pick(rng, tree)
    facts = [_edge_fact(tree, rng, e, "mixed") for e in links]

    def query(fam):
        middles = [n for n in fam.names if relation(fam, n, p) == first]
        return frozenset(n for n in fam.names for m in middles if relation(fam, n, m) == second)

    want = frozenset((z,))

    def holds(fs):
        return evaluate([*fs, *known_genders(tree, fs)], query, (p, q, z)) == {want}

    herrings = (
        red_herrings(rng, tree, facts, params.red_herrings, holds, avoid=(p, q, z)) if params.red_herrings else []
    )
    stated = facts + herrings
    rng.shuffle(stated)
    voice = Voice()
    puzzle = assemble(
        family_name="identify",
        family=tree,
        voice=voice,
        lines=render_facts(rng, stated, voice),
        check_facts=[*stated, *known_genders(tree, stated)],
        query=query,
        truth=want,
        must_name=(p, q, z),
        a=z,
        b=q,
        answer=z,
        answer_type="name",
        bucket=f"name:{second}",
        shape=f"{first.lower()}>{second.lower()}",
        question=f"Who is the {second.lower()} of {p}'s {first.lower()}?",
        hint3=generation_hint(tree, z, p, voice, anonymous=True),
        explanation=f"{q} is {p}'s {first.lower()}, and {z} is {q}'s {second.lower()}, so the answer is {z}.",
        stated=stated,
        herrings=herrings,
    )
    # the relation words in the question would give the answer away as well
    return dataclasses.replace(puzzle, forbidden=(*puzzle.forbidden, second, second.lower()))
