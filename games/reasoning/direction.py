"""Direction Sense: walk a route, then give the straight-line distance back to the start."""

import random
import re
from dataclasses import dataclass
from typing import Sequence

from core.difficulty import MAX_DIFFICULTY
from core.profile_manager import ProfileManager
from games.common import parse_int
from games.engine.puzzle import Puzzle, PuzzleError
from games.engine.round_loop import GameSpec, play_rounds

_UNIT = re.compile(r"\s*(?:m|meters?|metres?)\s*$", re.IGNORECASE)  # "13m", "13 meters"

# Primitive Pythagorean triples (hypotenuse <= 50); the generator scales them by 1..scale_max.
TRIPLES = ((3, 4, 5), (5, 12, 13), (8, 15, 17), (7, 24, 25), (20, 21, 29), (12, 35, 37), (9, 40, 41))
NAMES = ("John", "Alice", "Bob", "Emma", "David", "Priya", "Omar", "Mei", "Lucas", "Zara")

COMPASS = ("North", "East", "South", "West")  # clockwise
_VECTOR = {"North": (0, 1), "East": (1, 0), "South": (0, -1), "West": (-1, 0)}
_TURN = {"straight": 0, "right": 1, "back": 2, "left": 3}  # quarter turns clockwise
_TURN_BY_QUARTERS = {v: k for k, v in _TURN.items()}
_TURN_TEXT = {"straight": "Keeps going", "right": "Turns right", "back": "Turns around", "left": "Turns left"}


@dataclass(frozen=True)
class DirectionParams:
    n_moves: int  # legs walked, including each out-and-back leg
    backtrack: int  # out-and-back pairs that cancel
    turns: bool  # told as "turns left/right" from a facing direction instead of compass points
    scale_max: int  # the triple is multiplied by 1..scale_max


_BY_LEVEL = (
    DirectionParams(2, 0, False, 1),
    DirectionParams(3, 0, False, 1),
    DirectionParams(3, 0, False, 1),
    DirectionParams(4, 1, False, 2),
    DirectionParams(5, 1, False, 2),
    DirectionParams(5, 1, False, 2),
    DirectionParams(5, 1, True, 3),
    DirectionParams(6, 1, True, 3),
    DirectionParams(7, 2, True, 3),
    DirectionParams(8, 2, True, 3),
)


def params_for(level: int) -> DirectionParams:
    return _BY_LEVEL[max(1, min(MAX_DIFFICULTY, level)) - 1]


def walk(facing: str, steps: Sequence) -> tuple[int, int]:
    """Net (dx, dy), x east and y north, of `steps` starting while facing `facing`.

    A step is (action, metres): a compass point moves that way; "left", "right", "back" or "straight"
    turns from the current heading first. This is also the oracle the tests check answers against.
    """
    heading = COMPASS.index(facing)
    x = y = 0
    for action, dist in steps:
        if action in _TURN:
            heading = (heading + _TURN[action]) % 4
        else:
            heading = COMPASS.index(action)
        vx, vy = _VECTOR[COMPASS[heading]]
        x += vx * dist
        y += vy * dist
    return x, y


def _legs(rng: random.Random, p: DirectionParams, a: int, b: int, scale: int) -> list[tuple[str, int]]:
    """Compass legs whose net is (±a, ±b): the two net legs, out-and-back pairs, then splits to reach n_moves."""
    legs = [("East" if rng.random() < 0.5 else "West", a), ("North" if rng.random() < 0.5 else "South", b)]
    for _ in range(p.backtrack):
        d = rng.choice(COMPASS)
        k = rng.randint(2, 2 + 3 * scale)
        legs += [(d, k), (COMPASS[(COMPASS.index(d) + 2) % 4], k)]
    while len(legs) < p.n_moves:
        i = rng.choice([i for i, (_, k) in enumerate(legs) if k >= 2])
        d, k = legs.pop(i)
        first = rng.randint(1, k - 1)
        legs += [(d, first), (d, k - first)]
    rng.shuffle(legs)
    return legs


def _relative(facing: str, legs: Sequence[tuple[str, int]]) -> list[tuple[str, int]]:
    """The same route as turns: each leg becomes the turn from the previous heading."""
    heading = COMPASS.index(facing)
    steps = []
    for d, k in legs:
        target = COMPASS.index(d)
        steps.append((_TURN_BY_QUARTERS[(target - heading) % 4], k))
        heading = target
    return steps


def generate(level: int, rng: random.Random) -> Puzzle:
    p = params_for(level)
    a, b, c = rng.choice(TRIPLES)
    scale = rng.randint(1, p.scale_max)
    a, b, c = a * scale, b * scale, c * scale
    if rng.random() < 0.5:
        a, b = b, a
    legs = _legs(rng, p, a, b, scale)

    name = rng.choice(NAMES)
    if p.turns:
        facing = rng.choice(COMPASS)
        steps = _relative(facing, legs)
        moves = [f"  {_TURN_TEXT[t]}, walks {k}m." for t, k in steps]
        header = f"{name} starts facing {facing}."
        key_head = facing
    else:
        facing = "North"
        steps = legs
        moves = [f"  {k}m {d}" for d, k in legs]
        header = f"{name} walks:"
        key_head = ""

    dx, dy = walk(facing, steps)
    if dx * dx + dy * dy != c * c:
        raise PuzzleError(f"route ends {dx},{dy} from the start, expected distance {c}")
    walked = sum(k for _, k in legs)
    ew, ns = abs(dx), abs(dy)
    compass = ", ".join(f"{k}m {d}" for d, k in legs)

    hints = [
        "Add up the East and West moves (opposite directions cancel), then the North and South moves.",
        f"The net East-West distance is {ew}m and the net North-South distance is {ns}m.",
        "The two net distances are the legs of a right triangle. Use Pythagoras for the straight-line distance.",
    ]
    explanation = f"Net East-West = {ew}m, net North-South = {ns}m. Distance = sqrt({ew}^2 + {ns}^2) = sqrt({ew * ew + ns * ns}) = {c}m."
    if p.turns:
        hints[0] = (
            "Work out the compass direction of each leg first: a right turn from North faces East, a left turn faces West. "
            "Then add the East/West legs (opposite ones cancel) and the North/South legs."
        )
        explanation = f"In compass terms the route is {compass}. " + explanation

    return Puzzle(
        game_id="direction_sense",
        lines=(header, *moves),
        question=f"How far is {name} from the starting point? (in meters)",
        answer=str(c),
        answer_bucket="",
        key=f"{key_head}|{';'.join(moves)}",
        static_hints=tuple(hints),
        explanation=explanation,
        meta={"dx": dx, "dy": dy, "walked": walked, "legs": tuple(legs), "facing": facing, "turns": p.turns},
    )


def _grade(raw: str, puzzle: Puzzle) -> bool:
    return parse_int(_UNIT.sub("", raw)) == int(puzzle.answer)


SPEC = GameSpec(
    game_id="direction_sense",
    title="Direction Sense",
    intro=("Calculate the shortest distance from the starting point.",),
    rounds=5,
    base_points=20,
    generator=generate,
    grade=_grade,
    answer_display=lambda p: f"{p.answer}m",
)


def play_direction_sense(profile: ProfileManager):
    play_rounds(profile, SPEC)
