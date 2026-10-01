"""Syllogisms: judge a conclusion from statements about groups. Answers come from the set-model checker."""

import random
import re
from dataclasses import dataclass

from core.difficulty import MAX_DIFFICULTY
from core.profile_manager import ProfileManager
from games.engine.puzzle import Puzzle, PuzzleError
from games.engine.round_loop import GameSpec, play_rounds
from games.reasoning.syllogism_model import (
    ALL,
    CANNOT,
    FALSE,
    KINDS,
    NO,
    SOME,
    SOME_NOT,
    TRUE,
    Model,
    Stmt,
    UnsatisfiablePremises,
    verdict,
    witness,
)

# What a player may type for each option, compared after dropping everything but letters and digits.
OPTIONS = {
    "1": {"1", "true", "t"},
    "2": {"2", "false", "f"},
    "3": {"3", "cannotbedetermined", "cannot", "cbd", "c"},
}
OPTION_OF = {TRUE: "1", FALSE: "2", CANNOT: "3"}
VERDICTS = (TRUE, FALSE, CANNOT)


def parse_option(text: str) -> str:
    """ "1", "1.", "(1)", "True" and "t" are all option 1; anything unrecognised gives ""."""
    word = re.sub(r"[^a-z0-9]", "", text.lower())
    return next((opt for opt, names in OPTIONS.items() if word in names), "")


REAL_WORDS = ("cats", "dogs", "pets", "animals", "birds", "cars", "trees", "phones", "books", "plants", "boats", "toys")
INVENTED_WORDS = ("blicks", "zorps", "flems", "wugs", "snarks", "plinks", "drabs", "quibs", "vorns", "glorps")

_TEXT = {ALL: "All {x} are {y}.", SOME: "Some {x} are {y}.", NO: "No {x} are {y}.", SOME_NOT: "Some {x} are not {y}."}
_PHRASE = {
    TRUE: "definitely follows from the statements",
    FALSE: "is contradicted by the statements",
    CANNOT: "neither follows from nor is contradicted by the statements",
}

# Two-premise shapes over sets 0, 1, 2 (A, B, C): (kind, x, y) with indices into the sets.
Shape = tuple[tuple[str, int, int], ...]
_EASY: tuple[Shape, ...] = (
    ((ALL, 0, 1), (ALL, 1, 2)),
    ((ALL, 0, 1), (SOME, 1, 2)),
    ((SOME, 0, 1), (NO, 1, 2)),
)
_MEDIUM_EXTRA: tuple[Shape, ...] = (
    ((NO, 0, 1), (ALL, 2, 0)),
    ((ALL, 0, 1), (NO, 1, 2)),
    ((SOME_NOT, 0, 1), (ALL, 1, 2)),
)


@dataclass(frozen=True)
class SyllParams:
    shape_pool: tuple[Shape, ...]  # premise shapes used when the premises are not a random chain
    chain_len: int  # premises; 3 or more means a random chain over chain_len + 1 sets
    invented_words: bool  # made-up group names, so real-world knowledge cannot help


_BY_LEVEL = (
    *(SyllParams(_EASY, 2, False),) * 3,
    *(SyllParams(_EASY + _MEDIUM_EXTRA, 2, False),) * 3,
    *(SyllParams(_EASY + _MEDIUM_EXTRA, 3, True),) * 4,
)


def params_for(level: int) -> SyllParams:
    return _BY_LEVEL[max(1, min(MAX_DIFFICULTY, level)) - 1]


def _chain(rng: random.Random, premises: int) -> list[tuple[str, int, int]]:
    """Premises linking set i to set i+1, each with a random kind and direction."""
    out = []
    for i in range(premises):
        x, y = (i, i + 1) if rng.random() < 0.5 else (i + 1, i)
        out.append((rng.choice(KINDS), x, y))
    return out


def _render(stmt: Stmt) -> str:
    return _TEXT[stmt.kind].format(x=stmt.x, y=stmt.y)


def _describe(model: Model) -> str:
    """One arrangement in words: what is in each occupied region of the diagram."""
    parts = []
    for region in model.occupied():
        inside = [s for i, s in enumerate(model.sets) if region >> i & 1]
        outside = [s for i, s in enumerate(model.sets) if not region >> i & 1]
        text = "something in " + " and ".join(inside)
        parts.append(text + (f" but not in {' or '.join(outside)}" if outside else ""))
    return "; ".join(parts)


def _explain(premises: list[Stmt], conclusion: Stmt, answer: str) -> tuple[str, dict]:
    holding, failing = witness(premises, conclusion)
    shown = {"holds": _describe(holding) if holding else None, "fails": _describe(failing) if failing else None}
    text = f'"{_render(conclusion)}"'
    if answer == TRUE:
        why = f"Every arrangement that fits the statements makes {text} hold. For example: {shown['holds']}."
    elif answer == FALSE:
        why = f"Every arrangement that fits the statements makes {text} fail. For example: {shown['fails']}."
    else:
        why = (
            f"The statements allow arrangements either way. It holds if there is {shown['holds']}; "
            f"it fails if there is {shown['fails']}."
        )
    return why + " Every group has at least one member.", shown


def _pick(rng: random.Random, p: SyllParams, target: str) -> tuple[list[Stmt], Stmt, str, tuple[str, ...]] | None:
    """Premises and a conclusion whose verdict is `target`, or None if this draw has none."""
    n_sets = p.chain_len + 1 if p.chain_len > 2 else 3
    words = tuple(rng.sample(INVENTED_WORDS if p.invented_words else REAL_WORDS, n_sets))
    shape = _chain(rng, p.chain_len) if p.chain_len > 2 else rng.choice(p.shape_pool)
    premises = [Stmt(k, words[x], words[y]) for k, x, y in shape]
    candidates = [
        Stmt(k, x, y)
        for k in KINDS
        for x in words
        for y in words
        if x != y and not any(Stmt(k, x, y).restates(q) for q in premises)
    ]
    rng.shuffle(candidates)
    try:
        for conclusion in candidates[:12]:
            answer = verdict(premises, conclusion)
            if answer == target:
                return premises, conclusion, answer, words
    except UnsatisfiablePremises:
        pass
    return None


def generate(level: int, rng: random.Random) -> Puzzle:
    p = params_for(level)
    target = rng.choice(VERDICTS)  # chosen first so the answers stay balanced
    picked = None
    for _ in range(200):
        picked = _pick(rng, p, target)
        if picked:
            break
    if not picked:
        raise PuzzleError(f"no syllogism with answer {target!r} at level {level}")
    premises, conclusion, answer, words = picked

    statements = [_render(s) for s in premises]
    conclusion_text = _render(conclusion)
    explanation, shown = _explain(premises, conclusion, answer)
    return Puzzle(
        game_id="syllogisms",
        lines=(
            "Statements:",
            *(f"- {s}" for s in statements),
            "",
            f"Conclusion: {conclusion_text}",
            "1. True",
            "2. False",
            "3. Cannot be determined",
        ),
        question="Does the conclusion follow? (1, 2 or 3)",
        answer=answer,
        answer_bucket=answer,
        key=f"{' '.join(statements)}|{conclusion_text}",
        static_hints=(
            "Picture each group as a circle and draw how the statements make the circles overlap.",
            "Use ONLY what the statements force to be true, not what seems likely in real life.",
            f"The conclusion {_PHRASE[answer]}.",
        ),
        explanation=explanation,
        forbidden=("cannot be determined", "is true", "is false", "answer is"),  # would give the verdict away
        meta={
            "premises": tuple(premises),
            "conclusion": conclusion,
            "words": words,
            "witness": shown,
            "chain_len": p.chain_len,
        },
    )


def _grade(raw: str, puzzle: Puzzle) -> bool:
    return parse_option(raw) == OPTION_OF[puzzle.answer]


SPEC = GameSpec(
    game_id="syllogisms",
    title="Syllogisms",
    intro=(
        "Evaluate the conclusion based ONLY on the statements.",
        "Every group named has at least one member.",
    ),
    rounds=4,
    base_points=25,
    generator=generate,
    grade=_grade,
    ai_hints=True,
    answer_display=lambda p: f"{OPTION_OF[p.answer]}. {p.answer}",
)


def play_syllogisms(profile: ProfileManager):
    play_rounds(profile, SPEC)
