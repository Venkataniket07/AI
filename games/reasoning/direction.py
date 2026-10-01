"""Direction Sense: people on an integer grid; clues are offsets, questions and answers come from the coordinates."""

import random
import re
from dataclasses import dataclass
from typing import NamedTuple, Sequence

from core.difficulty import MAX_DIFFICULTY
from core.profile_manager import ProfileManager
from core.textguard import leaks
from games.common import parse_int
from games.engine.puzzle import Puzzle, PuzzleError
from games.engine.round_loop import GameSpec, play_rounds

_UNIT = re.compile(r"\s*(?:m|meters?|metres?)\s*$", re.IGNORECASE)  # "13m", "13 meters"

# Primitive Pythagorean triples with hypotenuse <= 50; TRIPLE_HYP holds every multiple, both leg orders.
_PRIMITIVE = ((3, 4, 5), (5, 12, 13), (8, 15, 17), (7, 24, 25), (20, 21, 29), (12, 35, 37), (9, 40, 41))
TRIPLE_HYP = {
    pair: c * k for a, b, c in _PRIMITIVE for k in range(1, 50 // c + 1) for pair in ((a * k, b * k), (b * k, a * k))
}
NAMES = ("John", "Alice", "Bob", "Emma", "David", "Priya", "Omar", "Mei", "Lucas", "Zara")

COMPASS = ("North", "East", "South", "West")  # clockwise
_VECTOR = {"North": (0, 1), "East": (1, 0), "South": (0, -1), "West": (-1, 0)}
_OPPOSITE = {"North": "South", "South": "North", "East": "West", "West": "East"}
_TURN = {"straight": 0, "right": 1, "back": 2, "left": 3}  # quarter turns clockwise
_TURN_BY_QUARTERS = {v: k for k, v in _TURN.items()}
_TURN_TEXT = {"straight": "Keeps going", "right": "Turns right", "back": "Turns around", "left": "Turns left"}
_EIGHT = {
    (0, 1): "North",
    (1, 1): "North-East",
    (1, 0): "East",
    (1, -1): "South-East",
    (0, -1): "South",
    (-1, -1): "South-West",
    (-1, 0): "West",
    (-1, 1): "North-West",
}
_PROMPT = "(N, NE, E, SE, S, SW, W or NW)"
_SYMMETRIES = [(sx, sy, swap) for sx in (1, -1) for sy in (1, -1) for swap in (0, 1)]


def _letters(text: str) -> str:
    return re.sub(r"[^a-z]", "", text.lower())


_COMPASS_ANSWERS = {
    form: full
    for full in _EIGHT.values()
    for form in (_letters(full), "".join(part[0] for part in full.lower().split("-")))
}


def parse_compass(raw: str) -> str | None:
    """The canonical compass name for "NE", "north-east", "North East" or "northeast" in any case, else None."""
    return _COMPASS_ANSWERS.get(_letters(raw))


def compass_of(dx: int, dy: int) -> str:
    return _EIGHT[(_sign(dx), _sign(dy))]


def _sign(n: int) -> int:
    return (n > 0) - (n < 0)


@dataclass(frozen=True)
class DirectionParams:
    people: tuple[int, int]  # people on the grid, min and max; 1 is a single walker
    legs: tuple[int, int]  # legs a walker takes, min and max
    turns: bool  # routes are told as turns from a facing direction
    reach: int  # largest single move or offset, in metres
    max_distance: int  # no distance answer is larger
    min_hops: int  # clue links between two people a question asks about
    diagonal: bool  # distance questions need both gaps non-zero (a Pythagorean triple)
    mover: bool  # one person moves after the layout is given
    questions: tuple[str, ...]


_AXIS = ("compass_final", "distance_start")
_TURNS = ("facing", "position_dir")
_PAIR = ("dir_pair", "dist_pair")
_MOVER = ("near_far", "between", "dir_turns", "dir_pair", "dist_pair")

_BY_LEVEL = (
    DirectionParams((1, 1), (2, 3), False, 12, 13, 0, True, False, _AXIS),
    DirectionParams((1, 1), (3, 3), False, 12, 15, 0, True, False, _AXIS),
    DirectionParams((1, 1), (3, 4), True, 12, 20, 0, True, False, _TURNS),
    DirectionParams((1, 1), (4, 4), True, 14, 25, 0, True, False, _TURNS),
    DirectionParams((3, 4), (0, 0), False, 6, 25, 2, False, False, _PAIR),
    DirectionParams((3, 4), (0, 0), False, 8, 30, 2, False, False, _PAIR),
    DirectionParams((5, 6), (0, 0), False, 8, 37, 3, True, False, _PAIR),
    DirectionParams((5, 6), (0, 0), False, 10, 41, 3, True, False, _PAIR),
    DirectionParams((7, 7), (3, 3), True, 6, 50, 2, False, True, _MOVER),
    DirectionParams((7, 7), (3, 4), True, 8, 50, 2, False, True, _MOVER),
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


# ---- geometry and signatures ----------------------------------------------------------------


def _symmetric(points, t):
    sx, sy, swap = t
    return [(sy * y, sx * x) if swap else (sx * x, sy * y) for x, y in points]


def _canon_path(points) -> tuple:
    """The path up to rotation and reflection."""
    return min(tuple(_symmetric(points, t)) for t in _SYMMETRIES)


def _canon_set(points) -> tuple:
    """The point set up to translation, rotation and reflection."""
    best = None
    for t in _SYMMETRIES:
        pts = _symmetric(points, t)
        mx, my = min(x for x, _ in pts), min(y for _, y in pts)
        cand = tuple(sorted((x - mx, y - my) for x, y in pts))
        best = cand if best is None or cand < best else best
    return best


def _path_points(legs: Sequence[tuple[str, int]]) -> list[tuple[int, int]]:
    x = y = 0
    points = [(0, 0)]
    for d, k in legs:
        vx, vy = _VECTOR[d]
        x, y = x + vx * k, y + vy * k
        points.append((x, y))
    return points


def _relative(facing: str, legs: Sequence[tuple[str, int]]) -> list[tuple[str, int]]:
    """The same route as turns: each leg becomes the turn from the previous heading."""
    heading = COMPASS.index(facing)
    steps = []
    for d, k in legs:
        target = COMPASS.index(d)
        steps.append((_TURN_BY_QUARTERS[(target - heading) % 4], k))
        heading = target
    return steps


def _cancels(legs: Sequence[tuple[str, int]]) -> bool:
    heading = {d for d, _ in legs}
    return any(d in heading and _OPPOSITE[d] in heading for d in ("North", "East"))


def _ew(dx: int) -> str:
    return "East" if dx > 0 else "West"


def _ns(dy: int) -> str:
    return "North" if dy > 0 else "South"


# ---- puzzle assembly --------------------------------------------------------------------------


def _make(qtype, kind, lines, question, answer, hints, fallbacks, explanation, forbidden, sigs, key, meta) -> Puzzle:
    """Builds the puzzle; a hint that would leak the answer is replaced by its generic fallback."""
    safe = []
    for hint, fallback in zip(hints, fallbacks):
        text = fallback if leaks(hint, answer, forbidden) else hint
        if leaks(text, answer, forbidden):
            raise PuzzleError(f"hint leaks the answer {answer!r}: {text}")
        safe.append(text)
    return Puzzle(
        game_id="direction_sense",
        lines=tuple(lines),
        question=question,
        answer=answer,
        answer_bucket="",
        key=key,
        static_hints=tuple(safe),
        explanation=explanation,
        forbidden=tuple(forbidden),
        meta={**meta, "qtype": qtype, "kind": kind, "sigs": tuple(sigs)},
    )


_COMPASS_FALLBACKS = (
    "Work out the total movement on the horizontal and the vertical line separately.",
    "Decide which side of the start the person ends on, left or right.",
    "Do the same for the up-down line, then combine the two sides into one direction.",
)
_DISTANCE_FALLBACKS = (
    "Work out the gap between them along each of the two lines.",
    "Find one of the two gaps and write it down.",
    "The two gaps are the short sides of a right triangle; the distance is the long side.",
)


def _axis_hint_pair(a_text: str, dx: int, dy: int, ref_text: str) -> tuple[str, str]:
    """Hints 2 and 3 for a compass answer: one axis relation, then the method for the other axis."""
    if dx and dy:
        return (
            f"{a_text} is {abs(dx)}m {_ew(dx)} of {ref_text} along the East-West line.",
            "Work out the North-South gap the same way, then combine the two.",
        )
    if dy == 0:
        return (f"{a_text} and {ref_text} are level on the North-South line.", "Only the other line differs.")
    return (f"{a_text} and {ref_text} are level on the East-West line.", "Only the other line differs.")


# ---- single walker (levels 1-4) ---------------------------------------------------------------


def _axis_legs(rng, nx, ny, n, reach):
    """Compass legs with net (nx, ny): the two net legs, then splits or overshoot-and-return legs up to n."""
    legs = [("East" if nx > 0 else "West", abs(nx)), ("North" if ny > 0 else "South", abs(ny))]
    while len(legs) < n:
        i = rng.randrange(len(legs))
        d, k = legs[i]
        extra = min(4, reach - k)
        if extra > 0 and (k < 2 or rng.random() < 0.5):
            e = rng.randint(1, extra)
            legs[i] = (d, k + e)
            legs.append((_OPPOSITE[d], e))
        elif k >= 2:
            first = rng.randint(1, k - 1)
            legs[i] = (d, first)
            legs.append((d, k - first))
    rng.shuffle(legs)
    return legs


def _walker_puzzle(qtype, name, facing, legs, answer):
    """Puzzle for one walker: lines as compass moves (facing None) or turns, question by qtype."""
    net = walk("North", legs)
    dx, dy = net
    cancel = _cancels(legs)
    if facing is None:
        lines = [f"{name} walks:"] + [f"  {k}m {d}" for d, k in legs]
    else:
        steps = _relative(facing, legs)
        lines = [f"{name} starts facing {facing}."] + [f"  {_TURN_TEXT[t]}, walks {k}m." for t, k in steps]
    ew, ns = abs(dx), abs(dy)
    cancel_text = " Opposite moves cancel." if cancel else ""
    route = ", ".join(f"{k}m {d}" for d, k in legs)
    sigs = (f"path{_canon_path(_path_points(legs))}", f"net{tuple(sorted((ew, ns)))}")
    key = f"{qtype}|{sigs[0]}"
    meta = {"legs": tuple(legs), "net": net, "facing": facing, "names": (name,)}
    if qtype == "distance_start":
        c = TRIPLE_HYP[(ew, ns)]
        hints = (
            f"Add up the moves along each line, East-West and North-South.{cancel_text}",
            f"The net East-West distance is {ew}m.",
            "The two net distances are the legs of a right triangle. Use Pythagoras for the straight-line distance.",
        )
        explanation = f"Net East-West = {ew}m, net North-South = {ns}m. Distance = sqrt({ew}^2 + {ns}^2) = sqrt({ew * ew + ns * ns}) = {c}m."
        return _make(qtype, "distance", lines, f"How far is {name} from the starting point? (in meters)", str(c),
                     hints, _DISTANCE_FALLBACKS, explanation, (f"{c}m",), sigs, key, meta)  # fmt: skip
    if qtype == "facing":
        headings = [d for d, _ in legs]
        hints = (
            "Track the way the person faces after each turn: a right turn is a quarter-turn clockwise, a left turn anticlockwise, and turning around reverses it.",
            f"After the first move the person faces {headings[0]}.",
            "Apply each later turn to the heading before it; the heading after the last turn is the answer.",
        )
        facings = " -> ".join(headings)
        explanation = f"Starting facing {facing}, the headings are {facings}. The last one is {answer}."
        fallbacks = (hints[0], "Follow the turns one at a time from the starting direction.", hints[2])
        return _make(qtype, "compass", lines, f"Which way is {name} facing at the end?", answer, hints, fallbacks,
                     explanation, (), sigs, key, meta)  # fmt: skip
    horizontal, vertical = _ew(dx), _ns(dy)
    method = "Add up the moves along each line, East-West and North-South."
    if facing is not None:
        method = (
            "Work out the compass direction of each leg first (a right turn from North faces East, a left turn faces West), "
            "then total the East-West and North-South movement."
        )
    hints = (
        method + cancel_text,
        f"The net East-West movement is {ew}m {horizontal}.",
        "Work out the North-South movement the same way, then combine the two directions.",
    )
    explanation = f"As compass moves the route is {route}. Net {ew}m {horizontal} and {ns}m {vertical}, so {answer}."
    question = f"In which direction is {name} from the starting point? {_PROMPT}"
    return _make(qtype, "compass", lines, question, answer, hints, _COMPASS_FALLBACKS, explanation, _forbid(answer),
                 sigs, key, meta)  # fmt: skip


def _build_axis(qtype, p, rng):
    for _ in range(40):
        if qtype == "distance_start":
            a, b = rng.choice([ab for ab, c in TRIPLE_HYP.items() if c <= p.max_distance and max(ab) <= p.reach])
        else:
            a, b = rng.randint(1, p.reach), rng.randint(1, p.reach)
            if (a, b) in TRIPLE_HYP:  # keep the triple nets for the distance questions
                continue
        nx, ny = a * rng.choice((-1, 1)), b * rng.choice((-1, 1))
        legs = _axis_legs(rng, nx, ny, rng.randint(*p.legs), p.reach)
        if qtype == "distance_start" and any(k == TRIPLE_HYP[(a, b)] for _, k in legs):
            continue
        answer = str(TRIPLE_HYP[(a, b)]) if qtype == "distance_start" else compass_of(nx, ny)
        return _walker_puzzle(qtype, rng.choice(NAMES), None, legs, answer)
    return None


def _random_turns(rng, p):
    facing = rng.choice(COMPASS)
    heading = COMPASS.index(facing)
    legs = []
    for _ in range(rng.randint(*p.legs)):
        turn = rng.choice(("left", "left", "left", "right", "right", "right", "back", "straight"))
        heading = (heading + _TURN[turn]) % 4
        legs.append((COMPASS[heading], rng.randint(1, p.reach)))
    return facing, legs


def _build_turns(qtype, p, rng):
    for _ in range(60):
        facing, legs = _random_turns(rng, p)
        steps = _relative(facing, legs)
        dx, dy = walk(facing, steps)
        if qtype == "facing":
            if sum(t != "straight" for t, _ in steps) < 2:
                continue
            answer = legs[-1][0]
        else:
            if not (dx and dy):
                continue
            answer = compass_of(dx, dy)
        return _walker_puzzle(qtype, rng.choice(NAMES), facing, legs, answer)
    return None


# ---- several people (levels 5-10) -------------------------------------------------------------


class Scene(NamedTuple):
    names: list
    pos: dict
    clues: list  # (name, ref, dx, dy), the root first with ref None
    parent: dict
    random_tree: bool


def _offset_text(name, ref, dx, dy):
    parts = []
    if dx:
        parts.append(f"{abs(dx)}m {_ew(dx)}")
    if dy:
        parts.append(f"{abs(dy)}m {_ns(dy)}")
    return f"{name} is {' and '.join(parts)} of {ref}."


def _scene_lines(s: Scene) -> list[str]:
    return [f"{s.names[0]} is at the centre."] + [_offset_text(*c) for c in s.clues[1:]]


def _random_tree(rng, p) -> Scene | None:
    n = rng.randint(*p.people)
    names = rng.sample(NAMES, n)
    pos, parent, clues = {names[0]: (0, 0)}, {}, [(names[0], None, 0, 0)]
    for i in range(1, n):
        for _ in range(40):
            ref = names[i - 1] if i > 1 and rng.random() < 0.6 else rng.choice(names[:i])
            dx, dy = rng.randint(-p.reach, p.reach), rng.randint(-p.reach, p.reach)
            if rng.random() < 0.3:
                dx, dy = (dx, 0) if rng.random() < 0.5 else (0, dy)
            where = (pos[ref][0] + dx, pos[ref][1] + dy)
            if (dx, dy) != (0, 0) and where not in pos.values():
                break
        else:
            return None
        pos[names[i]], parent[names[i]] = where, ref
        clues.append((names[i], ref, dx, dy))
    return Scene(names, pos, clues, parent, True)


def _grand_tree(rng, p) -> Scene:
    """Root, two children on opposite sides, two grandchildren under each; one random orientation."""
    names = rng.sample(NAMES, 7)
    d, g = rng.randint(3, 6), rng.randint(1, 2)
    h1, h2 = rng.randint(2, 4), rng.randint(2, 4)
    sx, sy, swap = rng.choice(_SYMMETRIES)
    shape = [
        (1, 0, -d, 0), (2, 0, d, 0),
        (3, 1, -g, -h1), (4, 1, g, -h1), (5, 2, -g, -h2), (6, 2, g, -h2),
    ]  # fmt: skip
    pos, parent, clues = {names[0]: (0, 0)}, {}, [(names[0], None, 0, 0)]
    for i, ref, dx, dy in shape:
        dx, dy = _symmetric([(dx, dy)], (sx, sy, swap))[0]
        pos[names[i]] = (pos[names[ref]][0] + dx, pos[names[ref]][1] + dy)
        parent[names[i]] = names[ref]
        clues.append((names[i], names[ref], dx, dy))
    return Scene(names, pos, clues, parent, False)


def _scene(rng, p) -> Scene | None:
    return _grand_tree(rng, p) if p.mover else _random_tree(rng, p)


def _chain(parent, n):
    chain = [n]
    while chain[-1] in parent:
        chain.append(parent[chain[-1]])
    return chain


def _hops(parent, a, b) -> int:
    ca, cb = _chain(parent, a), _chain(parent, b)
    meet = next(x for x in ca if x in cb)
    return ca.index(meet) + cb.index(meet)


def _clue_gives_direction(s: Scene, answer: str) -> bool:
    """True if one clue, as worded ("X is 2m West and 3m South of Y"), already names `answer`."""
    return any(compass_of(dx, dy) == answer for _, _, dx, dy in s.clues[1:])


def _sig(s: Scene) -> str:
    return f"set{_canon_set(list(s.pos.values()))}"


def _coords_text(s: Scene, names: Sequence[str]) -> str:
    return ", ".join(f"{n} {s.pos[n]}" for n in names)


def _place_meta(s: Scene) -> dict:
    return {"positions": dict(s.pos), "names": tuple(s.names), "clues": tuple(s.clues[1:])}


def _forbid(answer: str) -> tuple[str, ...]:
    abbr = "".join(w[0] for w in answer.split("-"))
    return (abbr,) if len(abbr) == 2 else ()


_GRID_NOTE = "Taking the first person as (0, 0) with East as +x and North as +y"


def _build_dir_pair(qtype, p, rng):
    for _ in range(60):
        s = _scene(rng, p)
        if s is None:
            continue
        pairs = [(a, b) for a in s.names for b in s.names if a != b and _hops(s.parent, a, b) >= p.min_hops]
        if not pairs:
            continue
        a, b = rng.choice(pairs)
        dx, dy = s.pos[a][0] - s.pos[b][0], s.pos[a][1] - s.pos[b][1]
        answer = compass_of(dx, dy)
        if _clue_gives_direction(s, answer):
            continue
        h2, h3 = _axis_hint_pair(a, dx, dy, b)
        hints = (
            f"Choose one person as the starting point and place {a} and {b} relative to them, one clue at a time.",
            h2,
            h3,
        )
        explanation = (
            f"{_GRID_NOTE}: {_coords_text(s, (a, b))}. {a} minus {b} is ({dx}, {dy}), so {a} is {answer} of {b}."
        )
        meta = {**_place_meta(s), "a": a, "b": b}
        return _make(qtype, "compass", _scene_lines(s), f"In which direction is {a} from {b}? {_PROMPT}", answer,
                     hints, _COMPASS_FALLBACKS, explanation, _forbid(answer), (_sig(s),), f"{qtype}|{_sig(s)}", meta)  # fmt: skip
    return None


def _distance_vectors(p, rng):
    vecs = [
        (sx * a, sy * b) for (a, b), c in TRIPLE_HYP.items() if c <= p.max_distance for sx in (1, -1) for sy in (1, -1)
    ]
    if not p.diagonal:
        vecs += [(k * sx, 0) for k in range(3, min(p.max_distance, 4 * p.reach) + 1) for sx in (1, -1)]
        vecs += [(0, k * sy) for k in range(3, min(p.max_distance, 4 * p.reach) + 1) for sy in (1, -1)]
    rng.shuffle(vecs)
    return vecs


def _retarget(s: Scene, rng, p) -> Scene | None:
    """Move one leaf so a pair that is not directly linked ends up a valid distance apart."""
    leaves = [n for n in s.names[1:] if n not in s.parent.values()]
    leaf = rng.choice(leaves)
    anchors = [n for n in s.names if n != leaf and _hops(s.parent, n, leaf) >= p.min_hops]
    if not anchors:
        return None
    anchor, bound = rng.choice(anchors), 3 * p.reach
    for vx, vy in _distance_vectors(p, rng):
        where = (s.pos[anchor][0] + vx, s.pos[anchor][1] + vy)
        ref = s.parent[leaf]
        dx, dy = where[0] - s.pos[ref][0], where[1] - s.pos[ref][1]
        if (dx, dy) == (0, 0) or max(abs(dx), abs(dy)) > bound or where in s.pos.values():
            continue
        pos = {**s.pos, leaf: where}
        clues = [(n, r, dx, dy) if n == leaf else (n, r, x, y) for n, r, x, y in s.clues]
        return Scene(s.names, pos, clues, s.parent, True)
    return None


def _distance_of(dx, dy, p) -> int | None:
    if dx and dy:
        c = TRIPLE_HYP.get((abs(dx), abs(dy)))
        return c if c is not None and c <= p.max_distance else None
    k = abs(dx or dy)
    return k if not p.diagonal and 3 <= k <= p.max_distance else None


def _build_dist_pair(qtype, p, rng):
    for _ in range(80):
        s = _scene(rng, p)
        if s is None:
            continue
        if s.random_tree:
            s = _retarget(s, rng, p)
            if s is None:
                continue
        pairs = [
            (a, b)
            for i, a in enumerate(s.names)
            for b in s.names[i + 1 :]
            if _hops(s.parent, a, b) >= p.min_hops and _distance_of(*_gap(s, a, b), p) is not None
        ]
        if not pairs:
            continue
        a, b = rng.choice(pairs)
        dx, dy = _gap(s, a, b)
        c = _distance_of(dx, dy, p)
        if any(c in (abs(x), abs(y)) or c == _distance_of(x, y, p) for _, _, x, y in s.clues[1:]):
            continue
        if dx and dy:
            hints = (
                f"Place {a} and {b} relative to one person, then find the gap between them along each of the two lines.",
                f"The East-West gap between {a} and {b} is {abs(dx)}m.",
                "The two gaps are the short sides of a right triangle; the distance is the long side (Pythagoras).",
            )
            how = f"sqrt({dx * dx} + {dy * dy}) = sqrt({dx * dx + dy * dy}) = {c}"
        else:
            line = "row" if dy == 0 else "column"
            hints = (
                f"Place {a} and {b} relative to one person, then compare their positions.",
                f"{a} and {b} stand in the same {line}.",
                "They are in a straight line, so the distance is just the gap between them.",
            )
            how = f"{c}"
        explanation = (
            f"{_GRID_NOTE}: {_coords_text(s, (a, b))}. The gap is ({abs(dx)}, {abs(dy)}), so the distance is {how}m."
        )
        meta = {**_place_meta(s), "a": a, "b": b}
        return _make(qtype, "distance", _scene_lines(s), f"How far is {a} from {b}? (in meters)", str(c), hints,
                     _DISTANCE_FALLBACKS, explanation, (f"{c}m",), (_sig(s),), f"{qtype}|{_sig(s)}", meta)  # fmt: skip
    return None


def _gap(s: Scene, a: str, b: str) -> tuple[int, int]:
    return s.pos[a][0] - s.pos[b][0], s.pos[a][1] - s.pos[b][1]


def _extreme(pos: dict, ref: str, nearest: bool) -> str | None:
    """The person nearest to (or farthest from) `ref`, or None if the best is tied."""
    d2 = {n: (x - pos[ref][0]) ** 2 + (y - pos[ref][1]) ** 2 for n, (x, y) in pos.items() if n != ref}
    best = min(d2.values()) if nearest else max(d2.values())
    winners = [n for n, v in d2.items() if v == best]
    return winners[0] if len(winners) == 1 else None


def _build_near_far(qtype, p, rng):
    for _ in range(60):
        s = _grand_tree(rng, p)
        x = rng.choice(s.names)
        d, m = rng.choice(COMPASS), rng.randint(2, 8)
        where = (s.pos[x][0] + _VECTOR[d][0] * m, s.pos[x][1] + _VECTOR[d][1] * m)
        after = {**s.pos, x: where}
        if where in s.pos.values():
            continue
        nearest = rng.random() < 0.5
        answer, before = _extreme(after, x, nearest), _extreme(s.pos, x, nearest)
        if answer is None or before is None or answer == before:
            continue
        word = "nearest" if nearest else "farthest"
        hints = (
            "Place everyone relative to one person first, then apply the move.",
            f"Before {x} moves, {before} is the {word} person to {x}.",
            f"The move shifts {x} by {m}m, so compare every other person's gap to {x} again.",
        )
        gaps = ", ".join(
            f"{n} {(px - where[0]) ** 2 + (py - where[1]) ** 2}" for n, (px, py) in after.items() if n != x
        )
        explanation = f"{_GRID_NOTE}, {x} ends at {where}. Squared gaps to {x}: {gaps}. The {word} is {answer}."
        meta = {**_place_meta(s), "mover": x, "move": (d, m), "word": word}
        lines = [*_scene_lines(s), f"Then {x} walks {m}m {d}."]
        fallbacks = (hints[0], "Work out where the person who moves ends up.", hints[2])
        return _make(qtype, "name", lines, f"After the move, who is {word} to {x}?", answer, hints, fallbacks,
                     explanation, (), (_sig(s),), f"{qtype}|{_sig(s)}", meta)  # fmt: skip
    return None


def _between(pos: dict, a: str, b: str) -> list[str]:
    (ax, ay), (bx, by) = pos[a], pos[b]
    inside = []
    for n, (x, y) in pos.items():
        if n in (a, b):
            continue
        cross = (bx - ax) * (y - ay) - (by - ay) * (x - ax)
        dot = (x - ax) * (bx - ax) + (y - ay) * (by - ay)
        if cross == 0 and 0 < dot < (bx - ax) ** 2 + (by - ay) ** 2:
            inside.append(n)
    return inside


def _build_between(qtype, p, rng):
    for _ in range(60):
        s = _grand_tree(rng, p)
        pairs = [(a, b) for i, a in enumerate(s.names) for b in s.names[i + 1 :] if len(_between(s.pos, a, b)) == 1]
        if not pairs:
            continue
        a, b = rng.choice(pairs)
        answer = _between(s.pos, a, b)[0]
        hints = (
            f"Place everyone relative to one person, then look at where {a} and {b} stand.",
            f"{a} and {b} stand on one straight line.",
            "Check the other people's positions along that line; exactly one lies between them.",
        )
        explanation = (
            f"{_GRID_NOTE}: {_coords_text(s, (a, b, answer))}. Only {answer} lies on the line between {a} and {b}."
        )
        meta = {**_place_meta(s), "a": a, "b": b}
        return _make(qtype, "name", _scene_lines(s), f"Who stands directly between {a} and {b}?", answer, hints,
                     (hints[0], "Look for two people who share a row, a column or a diagonal.", hints[2]),
                     explanation, (), (_sig(s),), f"{qtype}|{_sig(s)}", meta)  # fmt: skip
    return None


def _build_dir_turns(qtype, p, rng):
    for _ in range(80):
        s = _grand_tree(rng, p)
        x, y = rng.sample(s.names, 2)
        facing, legs = _random_turns(rng, p)
        steps = _relative(facing, legs)
        if sum(t != "straight" for t, _ in steps) < 2:
            continue
        mx, my = walk(facing, steps)
        end = (s.pos[x][0] + mx, s.pos[x][1] + my)
        dx, dy = end[0] - s.pos[y][0], end[1] - s.pos[y][1]
        if (dx, dy) == (0, 0):
            continue
        answer = compass_of(dx, dy)
        if _clue_gives_direction(s, answer):
            continue
        h2, h3 = _axis_hint_pair(x, dx, dy, y)
        hints = (
            f"Turn {x}'s moves into compass legs (a right turn from North faces East, a left turn faces West), then place {x} again.",
            h2,
            h3,
        )
        explanation = (
            f"{_GRID_NOTE}: {x} starts at {s.pos[x]}. The walk is {', '.join(f'{k}m {d}' for d, k in legs)}, "
            f"ending at {end}. Compared with {y} at {s.pos[y]} that is ({dx}, {dy}): {x} is {answer} of {y}."
        )
        lines = [*_scene_lines(s), f"Then {x} starts facing {facing} and walks:"]
        lines += [f"  {_TURN_TEXT[t]}, walks {k}m." for t, k in steps]
        meta = {**_place_meta(s), "mover": x, "facing": facing, "b": y}
        return _make(qtype, "compass", lines, f"After the walk, in which direction is {x} from {y}? {_PROMPT}",
                     answer, hints, _COMPASS_FALLBACKS, explanation, _forbid(answer), (_sig(s),),
                     f"{qtype}|{_sig(s)}", meta)  # fmt: skip
    return None


_BUILDERS = {
    "compass_final": _build_axis,
    "distance_start": _build_axis,
    "facing": _build_turns,
    "position_dir": _build_turns,
    "dir_pair": _build_dir_pair,
    "dist_pair": _build_dist_pair,
    "near_far": _build_near_far,
    "between": _build_between,
    "dir_turns": _build_dir_turns,
}


def generate(level: int, rng: random.Random) -> Puzzle:
    p = params_for(level)
    for _ in range(20):
        qtype = rng.choice(p.questions)
        puzzle = _BUILDERS[qtype](qtype, p, rng)
        if puzzle is not None:
            return puzzle
    raise PuzzleError(f"no Direction Sense puzzle found at level {level}")


# ---- session rules and grading ----------------------------------------------------------------


def session_veto(puzzle: Puzzle, drawn: Sequence[Puzzle]) -> bool:
    """No repeated answer, no question type twice running, no repeated layout (mirrored or rotated)."""
    if not drawn:
        return False
    if puzzle.answer.lower() in {d.answer.lower() for d in drawn}:
        return True
    if puzzle.meta["qtype"] == drawn[-1].meta["qtype"]:
        return True
    seen = {sig for d in drawn for sig in d.meta["sigs"]}
    return any(sig in seen for sig in puzzle.meta["sigs"])


def _grade(raw: str, puzzle: Puzzle) -> bool:
    kind = puzzle.meta["kind"]
    if kind == "distance":
        return parse_int(_UNIT.sub("", raw)) == int(puzzle.answer)
    if kind == "compass":
        return parse_compass(raw) == puzzle.answer
    return _letters(raw) == _letters(puzzle.answer)


SPEC = GameSpec(
    game_id="direction_sense",
    title="Direction Sense",
    intro=(
        "Work out directions and distances from the clues.",
        "North-East means both North and East of the other person or spot.",
    ),
    rounds=5,
    base_points=20,
    generator=generate,
    grade=_grade,
    answer_display=lambda p: f"{p.answer}m" if p.meta["kind"] == "distance" else p.answer,
    session_veto=session_veto,
)


def play_direction_sense(profile: ProfileManager):
    play_rounds(profile, SPEC)
