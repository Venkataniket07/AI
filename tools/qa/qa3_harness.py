"""QA harness 3: Circular Seating (17) and Puzzle Grids / Zebra (18), reusing the qa2 bot machinery.

The bot solves each puzzle with its own solver, answers through a patched input(), and checks verdicts, scores, XP,
integrity, hints, explanations, accepted input formats and crash behaviour.
"""
import itertools, random, re
from collections import deque
import qa2_harness as h

h.GAMES["Circular Seating"] = ("circular_seating", 3, 33)
h.GAMES["Puzzle Grids (Zebra)"] = ("puzzle_grid", 1, 100)

# ------------------------------------------------------------------ circular seating solver
def solve_circular(clues, mirrored=False):
    """All arrangements (as strings starting with A) meeting the clues. `mirrored` reads 'X left of Y' the way a diner
    facing the centre would (Y is clockwise-before X)."""
    sols = []
    for rest in itertools.permutations("BCDEF"):
        s = "A" + "".join(rest); n = 6; ok = True
        for c in clues:
            m = re.fullmatch(r"(\w) sits immediately left of (\w)\.", c)
            if m:
                i, j = s.index(m.group(1)), s.index(m.group(2))
                ok &= ((i + 1) % n == j) if mirrored else ((j + 1) % n == i); continue
            m = re.fullmatch(r"(\w) sits opposite to (\w)\.", c)
            if m:
                ok &= (s.index(m.group(1)) - s.index(m.group(2))) % n == 3; continue
            raise ValueError(c)
            if not ok: break
        if ok: sols.append(s)
    return sols

def rot(s, k): k %= len(s); return s[k:] + s[:k]

def ans_circular_seating(self, c, rt):
    clues = re.findall(r"^  - (.+)$", rt, re.M)
    sols = solve_circular(clues); alt = solve_circular(clues, mirrored=True)
    if len(sols) != 1: self.flag("seating-not-unique", c, f"{len(sols)} solutions for {clues}")
    self.samples["circ_clues"].append(len(clues))
    ans = sols[0] if sols else "ABCDEF"
    if alt and alt != sols: self.facts["circ_convention_differs"] += 1; self.samples["circ_conv"].append((clues, sols, alt))
    c["truth"][c["round"]] = ans
    self.samples["circ_kinds"].append(sum("opposite" in x for x in clues))
    return ans, ans[::-1] if ans[::-1] != ans else "ABCDEF", "circ"

# ------------------------------------------------------------------ zebra solver
def solve_grid(clues):
    sols = []
    for cp in itertools.permutations(["Red", "Blue", "Green"]):
        colors = dict(zip("ABC", cp))
        for pp in itertools.permutations(["Dog", "Cat", "Fish"]):
            pets = dict(zip("ABC", pp)); ok = True
            for cl in clues:
                m = re.fullmatch(r"The (\w+) house owner has a (\w+)\.", cl)
                if m: ok &= any(colors[p] == m[1] and pets[p] == m[2] for p in "ABC"); continue
                m = re.fullmatch(r"(\w) lives in the (\w+) house\.", cl)
                if m: ok &= colors[m[1]] == m[2]; continue
                m = re.fullmatch(r"(\w) owns the (\w+)\.", cl)
                if m: ok &= pets[m[1]] == m[2]; continue
                m = re.fullmatch(r"The (\w+) owner is not (\w)\.", cl)
                if m: ok &= pets[m[2]] != m[1]; continue
                m = re.fullmatch(r"(\w) does not live in the (\w+) house\.", cl)
                if m: ok &= colors[m[1]] != m[2]; continue
                raise ValueError(cl)
            if ok: sols.append((colors, pets))
    return sols

GRID_FMT = [
    ("plain", "{p} {a} {v}"), ("lower", "@lower"), ("upper", "@upper"),
    ("extra-spaces", "{p}   {a}    {v}"), ("padded", "  {p} {a} {v}  "), ("colon", "{p}: {a} {v}"),
    ("equals", "{p} {a} = {v}"), ("dashes", "{p}-{a}-{v}"), ("comma", "{p}, {a}, {v}"),
    ("trailing-dot", "{p} {a} {v}."), ("british-colour", "{p} {a} {v}"),
]
GRID_GARBAGE = ["", "   ", "1", "A", "A Color", "A Color Red extra", "D Pet Dog", "A Pet Unicorn", "A Colour Red", "Red",
                "a color red", "A  PET  dog", "'; DROP TABLE users;--", "A" * 3000, "🙂 🙂 🙂", "\t", "1 A Color Red",
                "A Color Red Dog", "hint", "/ai", "3", "22", "1e3", "12", "x"]

def build_grid_cmds(self, c):
    text = self.out.getvalue()[c["start"]:]
    body = text[text.rfind("Clues:"): text.rfind("Fill in the table")]
    clues = re.findall(r"^\d+\. (.+)$", body, re.M)
    sols = solve_grid(clues)
    if len(sols) != 1: self.flag("grid-not-unique", c, f"{len(sols)} solutions for {clues}")
    self.samples["grid_clues"].append(len(clues))
    if not sols: return deque()
    colors, pets = sols[0]; c["grid_sol"] = (colors, pets)
    ok = random.random() < self.p_of(c["mode"]) if c["mode"] not in ("edge", "format") else True
    if not ok:
        colors = dict(colors); pets = dict(pets)
        a, b = random.sample("ABC", 2)
        if random.random() < .5: colors[a], colors[b] = colors[b], colors[a]
        else: pets[a], pets[b] = pets[b], pets[a]
    c["expect"] = ok
    if c["mode"] == "format":
        i = c["n_fmt"] = c["n_fmt"] + 1
        name, tmpl = GRID_FMT[i % len(GRID_FMT)]; c["fmt"].append(name)
    else:
        name, tmpl = "plain", GRID_FMT[0][1]
    sets = deque()
    for p in "ABC":
        col = colors[p]
        for a, v in (("Colour" if name == "british-colour" else "Color", col), ("Pet", pets[p])):
            if tmpl.startswith("@"): sets.append(getattr(f"{p} {a} {v}", tmpl[1:])())
            else: sets.append(tmpl.format(p=p, a=a, v=v))
    return sets

def grid_respond(self, c, prompt):
    c["n"] += 1
    if c["cancel_at"] and c["n"] == c["cancel_at"]: raise KeyboardInterrupt
    if c["mode"] == "eof" and c["n"] == 2: raise EOFError
    if "sets" not in c:
        c["sets"] = build_grid_cmds(self, c); self.timing(c); c["prompts"] = 0
    c["prompts"] += 1
    if c["prompts"] > 1: h.advance(random.uniform(.5, 2) if c["mode"] not in ("fast", "hintfast") else .05)
    if c["mode"] == "edge" and random.random() < .45: return random.choice(GRID_GARBAGE)
    if prompt == ">> ":
        return c["sets"].popleft() if c["sets"] else "A Color Red"
    return "1" if c["sets"] else "2"

_orig_respond = h.Bot.respond
def respond(self, prompt):
    c = self.cur
    if c and c["gid"] == "puzzle_grid" and prompt in ("> ", ">> "): return grid_respond(self, c, prompt)
    return _orig_respond(self, prompt)

_orig_begin = h.Bot.begin
def begin(self, title, mode, user):
    if title == "Puzzle Grids (Zebra)" and mode == "cancel":
        h.GAMES[title] = ("puzzle_grid", 2, 100)
        try: _orig_begin(self, title, mode, user)
        finally: h.GAMES[title] = ("puzzle_grid", 1, 100)
        self.cur["cancel_at"] = random.randint(1, 8)
    else:
        _orig_begin(self, title, mode, user)

_orig_finish = h.Bot.finish
def finish(self):
    c = self.cur
    text = self.out.getvalue()[c["start"]:] if c else ""
    _orig_finish(self)
    if c and c["gid"] == "puzzle_grid" and c["mode"] != "cancel" and self.results and "flags" in self.results[-1]:
        fl = self.results[-1]["flags"]
        if c["mode"] not in ("format", "edge") and "expect" in c and fl != ("1" if c["expect"] else "0"):
            self.flag("wrong-verdict", c, f"bot's table correct={c['expect']} but game said {fl}")
        m = re.search(r"The actual table was:\nPerson   Color    Pet\n((?:\w+ +\w+ +\w+\n?){3})", text)
        if m and "grid_sol" in c:
            colors, pets = c["grid_sol"]
            shown = [tuple(l.split()) for l in m.group(1).strip().splitlines()]
            want = [(p, colors[p], pets[p]) for p in "ABC"]
            if shown != want: self.flag("solution-shown-wrong", c, f"{shown} vs {want}")
        if c["mode"] == "edge": self.facts["grid_edge_completed"] += 1

_orig_check = h.Bot.check_round_text
def check_round_text(self, c, k, txt):
    _orig_check(self, c, k, txt)
    if c["gid"] != "circular_seating": return
    tr = c["truth"].get(k)
    if tr is None: return
    bad = []
    isrot = lambda s: len(s) == 6 and s in tr + tr
    for n, hh in re.findall(r"Hint (\d): (.*?)  \(-", txt):
        m = re.fullmatch(r"(\w) sits immediately left of (\w)\.", hh)
        if m and m.group(2) + m.group(1) not in tr + tr: bad.append(hh)
        m = re.search(r"three consecutive people are (\w), (\w), (\w)", hh)
        if m and "".join(m.groups()) not in tr + tr: bad.append(hh)
    for e in re.findall(r"📘 (.*)", txt):
        m = re.search(r"loop satisfies all (\d+) clues: (\w+)", e)
        if not m or not isrot(m.group(2)): bad.append(e)
    m = re.search(r"The arrangement was: (\w+)", txt)
    if m and not isrot(m.group(1)): bad.append("arrangement printed " + m.group(1) + " vs " + tr)
    for b in bad: self.flag("hint/explain-wrong", c, f"round {k}: {b}")

_orig_fmt = h.Bot.fmt_variant
def fmt_variant(self, c, truth, kind):
    if kind != "circ": return _orig_fmt(self, c, truth, kind)
    t = str(truth)
    V = [("plain", t), ("rotated-1", rot(t, 1)), ("rotated-3", rot(t, 3)), ("rotated-5", rot(t, 5)), ("lower", t.lower()),
         ("spaced", " ".join(t)), ("commas", ",".join(t)), ("arrows", ">".join(t)), ("reversed", t[::-1]),
         ("padded", f"  {t}  "), ("dot", t + "."), ("quoted", f"'{t}'"), ("no-A-first", rot(t, 2).lower())]
    i = c["n_fmt"] = c["n_fmt"] + 1
    name, val = V[i % len(V)]; c["fmt"].append(name)
    return val

h.Bot.respond = respond; h.Bot.begin = begin; h.Bot.finish = finish
h.Bot.check_round_text = check_round_text; h.Bot.fmt_variant = fmt_variant
setattr(h.Bot, "ans_circular_seating", ans_circular_seating)
