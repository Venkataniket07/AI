"""Blood Relations: puzzles generated from a random family tree, in pluggable families (see blood_families/)."""

import dataclasses
import random
import re
from dataclasses import dataclass
from typing import Sequence

from core.difficulty import MAX_DIFFICULTY
from core.profile_manager import ProfileManager
from games.common import parse_int
from games.engine.puzzle import Puzzle, PuzzleError
from games.engine.round_loop import GameSpec, play_rounds
from games.reasoning import blood_families
from games.reasoning.blood_families.vocab import (  # noqa: F401  (re-exported: one vocabulary)
    ALIASES,
    KNOWN_RELATIONS,
    OTHER_RELATIONS,
    TERM_OF,
    normalize,
)
from games.reasoning.family import random_family, relation

MAX_BUILD_TRIES = 60
FAMILY_ROUND_CAP = 2  # of one family per four rounds

# Kept until the generator has proved itself in the field; only used if generation fails (removed in P14).
EASY_TEMPLATES = [
    {
        "setup": "{P1} is {P2}'s brother. {P2} is {P3}'s mother. {P4} is {P3}'s father.",
        "questions": [
            ("Who is {P1} to {P4}?", "Brother-in-law"),
            ("Who is {P4} to {P1}?", "Brother-in-law"),
            ("Who is {P1} to {P3}?", "Uncle"),
        ],
    },
    {
        "setup": "{P1} is the son of {P2}. {P3}, {P2}'s sister, has a son {P4} and a daughter {P5}.",
        "questions": [
            ("How is {P1} related to {P4}?", "Cousin"),
            ("How is {P3} related to {P1}?", "Aunt"),
            ("How is {P5} related to {P2}?", "Niece"),
        ],
    },
    {
        "setup": "{P2} is a man. Pointing to {P1}, {P2} said, 'He is the son of my father's only son.'",
        "questions": [
            ("How is {P1} related to {P2}?", "Son"),
            ("How is {P2} related to {P1}?", "Father"),
        ],
    },
]


@dataclass(frozen=True)
class BloodParams:
    hops: int  # family links between the two people asked about (no relation in the vocabulary is more than 3)
    generations: int
    people: int
    indirect: bool  # links worded either way round ("A is B's son" and "B is A's father")
    red_herrings: int  # true statements that do not matter
    options: bool  # relation choices shown


_BY_LEVEL = (
    *(BloodParams(2, 3, 8, False, 0, True),) * 3,
    *(BloodParams(2, 3, 8, True, 1, False),) * 3,
    *(BloodParams(3, 3, 12, True, 2, False),) * 4,
)


def params_for(level: int) -> BloodParams:
    return _BY_LEVEL[max(1, min(MAX_DIFFICULTY, level)) - 1]


# ---- generating -----------------------------------------------------------------------------


def _legacy_puzzle(rng: random.Random) -> Puzzle:
    names = list("ABCDE")
    rng.shuffle(names)
    template = rng.choice(EASY_TEMPLATES)
    fill = dict(zip(("P1", "P2", "P3", "P4", "P5"), names))
    setup = template["setup"].format(**fill)
    question, answer = rng.choice(template["questions"])
    question = question.format(**fill)
    return Puzzle(
        game_id="blood_relations",
        lines=(setup,),
        question=question,
        answer=answer,
        answer_bucket=answer,
        key=f"{setup}|{question}",
        static_hints=(
            "Sketch a small family tree from the statements.",
            "Work out each person's generation and gender before naming the relation.",
        ),
        forbidden=(answer,),
        meta={"family": "legacy", "answer_type": "relation", "signature": f"legacy|{setup}|{answer}", "tree": None},
    )


def generate(level: int, rng: random.Random) -> Puzzle:
    p = params_for(level)
    module = blood_families.pick(rng, level)
    for _ in range(MAX_BUILD_TRIES):
        try:
            return module.build(rng, random_family(rng, p.generations, p.people), p)
        except (ValueError, RuntimeError, PuzzleError):
            continue  # this draw had no unique, checkable puzzle; draw another family
    return _legacy_puzzle(rng)


def session_veto(puzzle: Puzzle, drawn: Sequence[Puzzle]) -> bool:
    """Per-game rules: no repeated signature, a family at most twice in four rounds, never the same answer twice running."""
    if any(d.meta["signature"] == puzzle.meta["signature"] for d in drawn):
        return True
    if sum(1 for d in drawn if d.meta["family"] == puzzle.meta["family"]) >= FAMILY_ROUND_CAP:
        return True
    return bool(drawn) and drawn[-1].answer_bucket == puzzle.answer_bucket


# ---- grading --------------------------------------------------------------------------------


def is_correct_relation(user_ans: str, target: str, db=None, ask_ai=None) -> bool:
    """
    Exact / known-variant match first. Only unrecognised phrasings (e.g. "mother's brother") are
    passed to the AI equivalence check, and only when AI is enabled.
    """
    got, want = normalize(user_ans), normalize(target)
    if not got:
        return False
    if got == want or got in ALIASES.get(want, set()):
        return True
    if got in KNOWN_RELATIONS:
        return False  # a recognised but different relation
    if ask_ai is None:
        ask_ai = _ask_ai
    return ask_ai(target, user_ans, db)


def _ask_ai(target: str, user_ans: str, db) -> bool:
    from games.assist import _ai_enabled

    if not _ai_enabled():
        return False
    try:
        from ai.background import result_or_none, submit
        from ai.services.assist_service import semantically_equivalent

        print("Checking your answer...")
        return bool(
            result_or_none(submit(semantically_equivalent, target, user_ans, "blood_relations", db), timeout=8.0)
        )
    except Exception:
        return False


def wrong_but_valid_feedback(user_ans: str, puzzle: Puzzle) -> str | None:
    """If the typed relation is true of the asked person and someone else in the puzzle, say so."""
    tree, a, b = puzzle.meta.get("tree"), puzzle.meta.get("a"), puzzle.meta.get("b")
    term = TERM_OF.get(normalize(user_ans))
    hidden = puzzle.meta.get("unnamed")  # a person the puzzle never names, so feedback must not either
    if (
        tree is None
        or term is None
        or puzzle.meta["answer_type"] != "relation"
        or (hidden is not None and hidden in (a, b))
    ):
        return None
    speaker = puzzle.meta.get("speaker")
    for other in puzzle.meta["named"]:
        if other not in (a, b) and other != hidden and relation(tree, a, other) == term:
            asked = "you" if b == speaker else b
            return f"{term} is {a} to {other}, not {a} to {asked}."
    return None


def grade(user_ans: str, puzzle: Puzzle, db=None) -> bool:
    kind = puzzle.meta["answer_type"]
    if kind == "count":
        return parse_int(user_ans) == int(puzzle.answer)
    if kind == "name":
        return re.sub(r"[^a-z0-9]", "", user_ans.lower()) == re.sub(r"[^a-z0-9]", "", puzzle.answer.lower())
    if is_correct_relation(user_ans, puzzle.answer, db):
        return True
    tree = puzzle.meta.get("tree")
    if puzzle.answer == "Cousin" and tree is not None:  # "cousin brother" is right if the cousin is male
        if normalize(user_ans) == ("cousinbrother" if tree.gender(puzzle.meta["a"]) == "M" else "cousinsister"):
            return True
    feedback = wrong_but_valid_feedback(user_ans, puzzle)
    if feedback:
        print(feedback)
    return False


SPEC = GameSpec(
    game_id="blood_relations",
    title="Blood Relations",
    intro=("Deduce the family relationship based on the clues.",),
    rounds=4,
    base_points=25,
    generator=generate,
    grade=lambda raw, puzzle: grade(raw, puzzle),
    ai_hints=True,
    session_veto=session_veto,
)


def play_blood_relations(profile: ProfileManager):
    play_rounds(profile, dataclasses.replace(SPEC, grade=lambda raw, puzzle: grade(raw, puzzle, profile.db)))
