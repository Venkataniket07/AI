"""Family table: a small table of people (gender, generation, parents, spouse) from which one relation is read off."""

import random

from games.engine.puzzle import Puzzle
from games.reasoning.blood_families.common import Voice, assemble, ask_relation, generation_hint, generations
from games.reasoning.blood_families.names import rename
from games.reasoning.family import Fact, Family, _edges, _shortest_path, evaluate, relation, relation_of

weight = 1
min_level = 5
MAX_ROWS = 7  # evaluate() enumerates at most this many named people
PICK_TRIES = 40
REVERSE_SHARE = 0.5
NONE = "-"


def _table_facts(family: Family, rows: list[str]) -> list[Fact]:
    """Everything the table says: each person's gender, their listed parents, listed married couples."""
    shown = set(rows)
    facts = [Fact("man" if family.gender(n) == "M" else "woman", n) for n in rows]
    for n in rows:
        for p in family.parents_of(n):
            if p in shown:
                facts.append(Fact("father" if family.gender(p) == "M" else "mother", p, n))
    for x, y in family.spouse_pairs():
        if x in shown and y in shown:
            husband, wife = (x, y) if family.gender(x) == "M" else (y, x)
            facts.append(Fact("husband", husband, wife))
    return facts


def _render(family: Family, rows: list[str]) -> list[str]:
    gen = generations(family)
    low = min(gen[n] for n in rows)
    shown = set(rows)
    cells = [("Person", "Gender", "Generation", "Parents", "Spouse")]
    for n in rows:
        parents = ", ".join(p for p in family.parents_of(n) if p in shown) or NONE
        spouse = family.spouse_of(n)
        cells.append(
            (
                n,
                "Male" if family.gender(n) == "M" else "Female",
                str(gen[n] - low + 1),
                parents,
                spouse if spouse in shown else NONE,
            )
        )
    widths = [max(len(row[i]) for row in cells) for i in range(5)]
    return ["  ".join(c.ljust(w) for c, w in zip(row, widths)).rstrip() for row in cells]


def build(rng: random.Random, family: Family, params) -> Puzzle:
    tree = rename(rng, family)
    adj: dict[str, list] = {n: [] for n in tree.names}
    for e in _edges(tree):
        adj[e[1]].append((e[2], e))
        adj[e[2]].append((e[1], e))
    people = list(tree.names)
    for _ in range(PICK_TRIES):
        a, b = rng.sample(people, 2)
        if relation(tree, a, b) and len(_shortest_path(adj, a, b)) <= params.hops:
            break
    else:
        raise ValueError("no pair to ask about")

    rows = {a, b}
    for _, u, v in _shortest_path(adj, a, b):
        rows |= {u, v}
        for n in (u, v):  # brothers and sisters are only visible through a shared parent
            if tree.siblings_of(n):
                rows |= set(tree.parents_of(n))
    if len(rows) > MAX_ROWS:
        raise ValueError("table would be too large")

    truth = relation_of(tree, a, b)

    def holds(chosen: list[str]) -> bool:
        return evaluate(_table_facts(tree, chosen), lambda fam: relation(fam, a, b), (a, b)) == {truth}

    ordered = sorted(rows)
    if not holds(ordered):
        raise ValueError("the table does not settle the relation")
    extras = [n for n in people if n not in rows]
    rng.shuffle(extras)
    for n in extras[: rng.randint(0, 2)]:
        if len(ordered) < MAX_ROWS and holds(sorted([*ordered, n])):
            ordered = sorted([*ordered, n])
    rng.shuffle(ordered)

    if rng.random() < REVERSE_SHARE:
        reverse = relation(tree, b, a)
        if reverse:
            a, b, truth = b, a, reverse
    facts = _table_facts(tree, ordered)
    voice = Voice()
    puzzle = assemble(
        family_name="family_table",
        family=tree,
        voice=voice,
        lines=_render(tree, ordered),
        check_facts=facts,
        query=lambda fam: relation(fam, a, b),
        truth=truth,
        must_name=(a, b),
        a=a,
        b=b,
        answer=truth,
        answer_type="relation",
        bucket=truth,
        shape=f"table{len(ordered)}",
        question=ask_relation(rng, a, b, voice),
        hint3=generation_hint(tree, a, b, voice, anonymous=False),
        explanation=(
            f"Read the parents and spouses off the table to link {a} and {b}: that makes {a} {b}'s {truth.lower()}."
        ),
        stated=facts,
    )
    puzzle.meta["table"] = tuple(ordered)
    return puzzle
