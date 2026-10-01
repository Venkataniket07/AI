"""Coded: operators are defined as relations ("P # Q means P is the mother of Q"), then a chain of them is read off."""

import random

from games.engine.puzzle import Puzzle
from games.reasoning.blood_families.collapse import _route
from games.reasoning.blood_families.common import Voice, assemble, ask_relation, generation_hint
from games.reasoning.family import Fact, Family, evaluate, relation, relation_of

weight = 1
min_level = 7
OPERATORS: tuple[str, ...] = ("+", "-", "*", "/", "@", "#", "$", "%", "&")
NOUNS = ("father", "mother", "son", "daughter", "brother", "sister", "husband", "wife")
MAX_DEFINED = 4  # operators defined in one puzzle, used or not
REVERSE_SHARE = 0.4


def decode(mapping: dict[str, str], ops: list[str], people: list[str]) -> list[Fact]:
    """The statements an expression stands for: people[i] (op i) people[i+1] means people[i] is that noun of people[i+1]."""
    return [Fact(mapping[op], people[i], people[i + 1]) for i, op in enumerate(ops)]


def build(rng: random.Random, family: Family, params) -> Puzzle:
    a, b, nouns, people = _route(rng, family, rng.choice((2, 3)))
    used = list(dict.fromkeys(nouns))
    spare = [n for n in NOUNS if n not in used]
    defined = used + rng.sample(spare, rng.randint(0, min(len(spare), MAX_DEFINED - len(used))))
    symbols = rng.sample(OPERATORS, len(defined))
    mapping = dict(zip(symbols, defined))
    code = {noun: op for op, noun in mapping.items()}
    ops = [code[n] for n in nouns]

    facts = decode(mapping, ops, people)
    truth = relation_of(family, a, b)
    x, y = a, b
    if rng.random() < REVERSE_SHARE:
        reverse = relation(family, b, a)
        if reverse and evaluate(facts, lambda fam: relation(fam, b, a), (a, b)) == {reverse}:
            x, y, truth = b, a, reverse

    expression = people[0] + "".join(f" {op} {p}" for op, p in zip(ops, people[1:]))
    definitions = [f"P {op} Q means P is the {noun} of Q." for op, noun in mapping.items()]
    rng.shuffle(definitions)
    voice = Voice()
    puzzle = assemble(
        family_name="coded",
        family=family,
        voice=voice,
        lines=[*definitions, f"Read {expression} with these meanings."],
        check_facts=facts,
        query=lambda fam: relation(fam, x, y),
        truth=truth,
        must_name=(a, b),
        a=x,
        b=y,
        answer=truth,
        answer_type="relation",
        bucket=truth,
        shape="+".join(nouns),
        question=ask_relation(rng, x, y, voice),
        hint3=generation_hint(family, x, y, voice, anonymous=False),
        explanation=(
            "Decode each step: "
            + "; ".join(f"{op} means {mapping[op]}" for op in dict.fromkeys(ops))
            + f". So {expression} says "
            + ", then ".join(f"{f.x} is {f.y}'s {f.kind}" for f in facts)
            + f", which makes {x} {y}'s {truth.lower()}."
        ),
        stated=facts,
    )
    puzzle.meta["code"] = {"mapping": mapping, "ops": tuple(ops), "people": tuple(people)}
    return puzzle
