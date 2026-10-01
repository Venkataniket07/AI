"""Shared pieces for the Blood Relations families: wording, generations, red herrings, the final puzzle check."""

import random
from typing import Callable, Hashable, Sequence

from core.textguard import leaks
from games.engine.puzzle import Puzzle, PuzzleError
from games.reasoning.blood_families.vocab import aliases_of
from games.reasoning.family import Fact, Family, _edge_fact, _edges, evaluate, relation

MAX_OPTION_DECOYS = 4
_COUNT_WORDS = {1: "one", 2: "two", 3: "three", 4: "four"}


# ---- wording --------------------------------------------------------------------------------


class Voice:
    """Who is "you": the speaker is written in the second person wherever they appear."""

    def __init__(self, speaker: str | None = None):
        self.speaker = speaker

    def ref(self, n: str) -> str:
        return "you" if n == self.speaker else n

    def poss(self, n: str) -> str:
        return "your" if n == self.speaker else f"{n}'s"

    def be(self, n: str) -> str:
        return "are" if n == self.speaker else "is"

    def have(self, n: str) -> str:
        return "have" if n == self.speaker else "has"


def _cap(text: str) -> str:
    return text[0].upper() + text[1:]


def render_fact(rng: random.Random, fact: Fact, voice: Voice) -> str:
    """One statement in one of several wordings (3-4 for a family link, 2 for a gender)."""
    x = fact.x
    if fact.y is None:
        word = rng.choice(("a man", "male") if fact.kind == "man" else ("a woman", "female"))
        return _cap(f"{voice.ref(x)} {voice.be(x)} {word}.")
    y, n = fact.y, fact.kind
    forms = [f"{voice.ref(x)} {voice.be(x)} {voice.poss(y)} {n}."]
    if y != voice.speaker:
        forms.append(f"{voice.ref(x)} {voice.be(x)} the {n} of {y}.")
    if x != voice.speaker:
        forms.append(f"{voice.poss(y)} {n} is {x}.")
        forms.append(f"{voice.ref(y)} {voice.have(y)} a {n}, {x}.")
    return _cap(rng.choice(forms))


def render_facts(rng: random.Random, facts: Sequence[Fact], voice: Voice) -> list[str]:
    return [render_fact(rng, f, voice) for f in facts]


def ask_relation(rng: random.Random, a: str, b: str, voice: Voice) -> str:
    ra, rb = voice.ref(a), voice.ref(b)
    return rng.choice((f"What is {ra} to {rb}?", f"How is {ra} related to {rb}?", f"What relation is {ra} to {rb}?"))


# ---- family facts ---------------------------------------------------------------------------


def generations(family: Family) -> dict[str, int]:
    """Generation of each person (oldest 0); a married-in spouse shares their partner's."""
    memo: dict[str, int] = {}

    def gen(n: str) -> int:
        if n not in memo:
            parents = family.parents_of(n)
            spouse = family.spouse_of(n)
            if parents:
                memo[n] = 1 + gen(parents[0])
            elif spouse is not None and family.parents_of(spouse):
                memo[n] = gen(spouse)
            else:
                memo[n] = 0
        return memo[n]

    return {n: gen(n) for n in family.names}


def edge_key(fact: Fact) -> Hashable:
    """What a statement links, ignoring wording: the same link stated twice has the same key."""
    if fact.y is None:
        return ("gender", fact.x)
    if fact.kind in ("father", "mother"):
        return ("parent", fact.x, fact.y)
    if fact.kind in ("son", "daughter"):
        return ("parent", fact.y, fact.x)
    return (fact.kind in ("husband", "wife"), frozenset((fact.x, fact.y)))


def known_genders(family: Family, facts: Sequence[Fact]) -> list[Fact]:
    """Gender statements for every person the facts name; used when names (not labels) are shown."""
    names = sorted({n for f in facts for n in (f.x, f.y) if n is not None and not n.startswith("_")})
    return [Fact("man" if family.gender(n) == "M" else "woman", n) for n in names]


def red_herrings(
    rng: random.Random,
    family: Family,
    facts: Sequence[Fact],
    count: int,
    holds: Callable[[Sequence[Fact]], bool],
    avoid: Sequence[str] = (),
    style: str = "mixed",
) -> list[Fact]:
    """Up to `count` true statements that add nothing: `holds(facts + herrings)` stays true for each added."""
    seen = {edge_key(f) for f in facts}
    edges = _edges(family)
    rng.shuffle(edges)
    chosen: list[Fact] = []
    for edge in edges:
        if len(chosen) >= count:
            break
        if edge[1] in avoid or edge[2] in avoid:
            continue
        fact = _edge_fact(family, rng, edge, style)
        if edge_key(fact) in seen:
            continue
        try:
            ok = holds([*facts, *chosen, fact])
        except ValueError:  # too many named people to check
            ok = False
        if ok:
            chosen.append(fact)
            seen.add(edge_key(fact))
    return chosen


# ---- hints, options -------------------------------------------------------------------------


def generation_hint(family: Family, a: str, b: str, voice: Voice, *, anonymous: bool) -> str:
    """Which generation `a` is in relative to `b`. Never names the answer; avoids the word "a"."""
    gen = generations(family)
    diff = gen[a] - gen[b]
    if diff == 0:
        where = "in the same generation as"
    else:
        where = f"{_COUNT_WORDS.get(abs(diff), str(abs(diff)))} generation{'s' if abs(diff) > 1 else ''} " + (
            "older than" if diff < 0 else "younger than"
        )
    who = (
        f"The person you want is {'male' if family.gender(a) == 'M' else 'female'} and is"
        if anonymous
        else f"{voice.ref(a)} {voice.be(a)}"
    )
    return f"{who} {where} {voice.ref(b)}."


def relation_options(rng: random.Random, family: Family, a: str, b: str, answer: str) -> tuple[str, ...]:
    """The answer plus other relations `a` really has to people in this family, shuffled; () if too few."""
    decoys = sorted({relation(family, a, c) for c in family.names if c not in (a, b)} - {answer, None})
    if len(decoys) < 2:
        return ()
    rng.shuffle(decoys)
    options = [answer, *decoys[:MAX_OPTION_DECOYS]]
    rng.shuffle(options)
    return tuple(options)


# ---- the finished puzzle --------------------------------------------------------------------


def assemble(
    *,
    family_name: str,
    family: Family,
    voice: Voice,
    lines: Sequence[str],
    check_facts: Sequence[Fact],
    query: Callable[[Family], Hashable],
    truth: Hashable,
    must_name: Sequence[str],
    a: str | None,
    b: str | None,
    answer: str,
    answer_type: str,
    bucket: str,
    shape: str,
    question: str,
    hint3: str,
    explanation: str,
    options: Sequence[str] = (),
    stated: Sequence[Fact] = (),
    herrings: Sequence[Fact] = (),
) -> Puzzle:
    """Verify that the facts alone force `truth` as the value of `query`, then build the Puzzle."""
    if evaluate(check_facts, query, must_name) != {truth}:
        raise PuzzleError(f"{family_name}: statements do not force a unique answer")
    forbidden = (answer, *aliases_of(answer)) if answer_type == "relation" else (answer,)
    if leaks(hint3, answer, forbidden[1:]):
        raise PuzzleError(f"hint leaks the answer: {hint3}")
    shown = [*lines, f"Options: {', '.join(options)}"] if options else list(lines)
    named = sorted({n for f in stated for n in (f.x, f.y) if n and not n.startswith("_")} | {x for x in (a, b) if x})
    return Puzzle(
        game_id="blood_relations",
        lines=tuple(shown),
        question=question,
        answer=answer,
        answer_bucket=bucket,
        key=" ".join(lines) + "|" + question,
        static_hints=(
            "Sketch a small family tree from the statements.",
            "Work out each person's generation and gender before naming the relation.",
            hint3,
        ),
        explanation=explanation,
        forbidden=forbidden,
        meta={
            "family": family_name,
            "answer_type": answer_type,
            "shape": shape,
            "signature": f"{family_name}|{shape}|{bucket}",
            "tree": family,
            "check_facts": tuple(check_facts),
            "stated": tuple(stated),
            "herrings": tuple(herrings),
            "a": a,
            "b": b,
            "named": tuple(named),
            "speaker": voice.speaker,
            "options": tuple(options),
        },
    )
