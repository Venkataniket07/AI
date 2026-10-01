"""Rebuilds a Direction Sense puzzle's coordinates and answer from the text the player sees."""

import math
import re

from games.reasoning.direction import walk

_VEC = {"North": (0, 1), "East": (1, 0), "South": (0, -1), "West": (-1, 0)}
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
_MOVE = re.compile(r"^  (\d+)m (North|East|South|West)$")
_TURN = re.compile(r"^  (Turns right|Turns left|Turns around|Keeps going), walks (\d+)m\.$")
_TURN_ACTION = {"Turns right": "right", "Turns left": "left", "Turns around": "back", "Keeps going": "straight"}
_OFFSET = re.compile(r"^(\w+) is (.+) of (\w+)\.$")
_PART = re.compile(r"(\d+)m (North|East|South|West)")


def _compass(dx, dy):
    return _EIGHT[((dx > 0) - (dx < 0), (dy > 0) - (dy < 0))]


def _steps(lines):
    """Moves from the indented lines: compass legs, or turn steps."""
    out = []
    for line in lines:
        if m := _MOVE.match(line):
            out.append((m.group(2), int(m.group(1))))
        elif m := _TURN.match(line):
            out.append((_TURN_ACTION[m.group(1)], int(m.group(2))))
    return out


class Solved:
    """Everything a player could work out from the text alone."""

    def __init__(self, puzzle):
        self.puzzle = puzzle
        self.clues = []  # (name, ref, dx, dy)
        self.pos = {}
        self.mover = self.move = self.facing = None
        lines = list(puzzle.lines)
        head = lines[0]
        if head.endswith(" walks:") or " starts facing " in head:
            self._walker(lines)
        else:
            self._grid(lines)

    def _walker(self, lines):
        name, facing = lines[0].split(" ")[0], "North"
        if " starts facing " in lines[0]:
            facing = lines[0].rstrip(".").rsplit(" ", 1)[1]
        self.facing = facing
        self.steps = _steps(lines[1:])
        self.walker = name
        self.net = walk(facing, self.steps)

    def _grid(self, lines):
        self.walker = None
        self.pos[lines[0].split(" ")[0]] = (0, 0)
        i = 1
        while i < len(lines) and not lines[i].startswith("Then "):
            m = _OFFSET.match(lines[i])
            name, parts, ref = m.groups()
            dx = dy = 0
            for n, d in _PART.findall(parts):
                vx, vy = _VEC[d]
                dx, dy = dx + vx * int(n), dy + vy * int(n)
            self.clues.append((name, ref, dx, dy))
            self.pos[name] = (self.pos[ref][0] + dx, self.pos[ref][1] + dy)
            i += 1
        self.placed = dict(self.pos)
        if i < len(lines):
            m = re.match(r"^Then (\w+) walks (\d+)m (\w+)\.$", lines[i])
            if m:
                self.mover, self.move = m.group(1), (m.group(3), int(m.group(2)))
                vx, vy = _VEC[self.move[0]]
                x, y = self.pos[self.mover]
                self.pos[self.mover] = (x + vx * self.move[1], y + vy * self.move[1])
            else:
                m = re.match(r"^Then (\w+) starts facing (\w+) and walks:$", lines[i])
                self.mover, self.facing = m.groups()
                steps = _steps(lines[i + 1 :])
                dx, dy = walk(self.facing, steps)
                x, y = self.pos[self.mover]
                self.pos[self.mover] = (x + dx, y + dy)
                self.steps = steps

    def _gap(self, a, b):
        return self.pos[a][0] - self.pos[b][0], self.pos[a][1] - self.pos[b][1]

    def answer(self):
        q = self.puzzle.question
        if m := re.match(r"In which direction is (\w+) from the starting point\?", q):
            return _compass(*self.net)
        if m := re.match(r"Which way is (\w+) facing at the end\?", q):
            heading = ["North", "East", "South", "West"].index(self.facing)
            for turn, _ in self.steps:
                heading = (heading + {"straight": 0, "right": 1, "back": 2, "left": 3}[turn]) % 4
            return ["North", "East", "South", "West"][heading]
        if re.match(r"How far is (\w+) from the starting point\?", q):
            return str(round(math.hypot(*self.net)))
        if m := re.match(r"(?:After the walk, i|I)n which direction is (\w+) from (\w+)\?", q):
            return _compass(*self._gap(m.group(1), m.group(2)))
        if m := re.match(r"How far is (\w+) from (\w+)\?", q):
            return str(round(math.hypot(*self._gap(m.group(1), m.group(2)))))
        if m := re.match(r"After the move, who is (nearest|farthest) to (\w+)\?", q):
            return self.extreme(m.group(1), m.group(2))
        if m := re.match(r"Who stands directly between (\w+) and (\w+)\?", q):
            return self.between(m.group(1), m.group(2))
        raise AssertionError(q)

    def extreme(self, word, ref, pos=None):
        pos = pos or self.pos
        d2 = {n: (p[0] - pos[ref][0]) ** 2 + (p[1] - pos[ref][1]) ** 2 for n, p in pos.items() if n != ref}
        best = min(d2.values()) if word == "nearest" else max(d2.values())
        winners = [n for n, v in d2.items() if v == best]
        assert len(winners) == 1, f"tie for {word}: {d2}"
        return winners[0]

    def between(self, a, b):
        (ax, ay), (bx, by) = self.pos[a], self.pos[b]
        inside = [
            n
            for n, (x, y) in self.pos.items()
            if n not in (a, b)
            and (bx - ax) * (y - ay) == (by - ay) * (x - ax)
            and min(ax, bx) <= x <= max(ax, bx)
            and min(ay, by) <= y <= max(ay, by)
        ]
        assert len(inside) == 1, inside
        return inside[0]


def solve_round(output: str) -> str:
    """The answer to the last round printed in `output` ("Round k/n:" lines, then "Question: ...")."""
    m = list(re.finditer(r"Round \d+/\d+:\n(.*?)\n\nQuestion: (.*)", output, re.S))[-1]
    puzzle = type("Round", (), {"lines": m.group(1).split("\n"), "question": m.group(2).strip()})
    return Solved(puzzle).answer()
