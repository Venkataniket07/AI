"""QA harness 2: Mental Arithmetic, Word Anagrams, games 11-16 (reasoning) through the real main() loop.

The bot reads each puzzle from the game's output, solves it with its OWN solver (independent of the game's
generator) and answers through a patched input(). It also verifies the game's printed answers, hints and
explanations, scoring, XP, stored difficulty and integrity verdicts, and logs which answer formats are accepted.
"""
import builtins, collections, io, itertools, json, math, os, random, re, sys, time, traceback

import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SCR = WORK = Path(tempfile.gettempdir()) / "brain_trainer_qa"
SCR.mkdir(exist_ok=True)
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

import main as app
from games.reasoning.blood_families.names import FEMALE_NAMES, MALE_NAMES
from core.progression import xp_for, level_for_xp
from database.db_manager import DBManager
import games.assist as g_assist
import games.language.anagrams as g_ana
import games.reasoning.seating as g_seat
from games.language.wordlist import offline_words

DB = os.path.join(SCR, "qa2.db")
for ext in ("", "-wal", "-shm"):
    if os.path.exists(DB + ext):
        os.remove(DB + ext)

GAMES = {  # menu title -> (db id, rounds, base points per round or None)
    "Mental Arithmetic": ("mental_math", 10, None), "Word Anagrams": ("anagrams", 5, None),
    "Blood Relations": ("blood_relations", 4, 25), "Direction Sense": ("direction_sense", 5, 20),
    "Coding-Decoding": ("coding_decoding", 5, 20), "Ranking Puzzles": ("rankings", 4, 25),
    "Syllogisms": ("syllogisms", 4, 25), "Linear Seating": ("linear_seating", 3, 33),
}
PENALTY = (0.0, 0.15, 0.30, 0.50)

# ---------------------------------------------------------------- fake clock
CLOCK = [1000.0]
time.perf_counter = lambda: CLOCK[0]
def fake_sleep(s): CLOCK[0] += s
time.sleep = fake_sleep
def advance(s): CLOCK[0] += s

# ---------------------------------------------------------------- solvers (independent of the games)
def solve_arith(q):
    if not re.fullmatch(r"[\d\s+\-*/()]+", q): raise ValueError(q)
    v = eval(q.replace("/", "//"))
    return v

KNOWN = collections.defaultdict(set)   # sorted letters -> words the bot may answer with
for w in offline_words():
    KNOWN["".join(sorted(w["word"]))].add(w["word"])

def solve_anagram(scr):
    c = sorted(KNOWN.get("".join(sorted(scr)), ()))
    return c

# ---- Blood Relations: a solver that shares no code with games.reasoning.family -----------------
_B_NOUN = "father|mother|son|daughter|brother|sister|husband|wife"
_B_SEX = {"father": "M", "son": "M", "brother": "M", "husband": "M", "mother": "F", "daughter": "F", "sister": "F", "wife": "F"}
_B_PATHS = [  # (steps taken from b to reach a, term for a male, term for a female); first hit wins
    ("P", "Father", "Mother"), ("C", "Son", "Daughter"), ("S", "Brother", "Sister"), ("W", "Husband", "Wife"),
    ("PP", "Grandfather", "Grandmother"), ("CC", "Grandson", "Granddaughter"),
    ("PS", "Uncle", "Aunt"), ("PSW", "Uncle", "Aunt"), ("SC", "Nephew", "Niece"), ("WSC", "Nephew", "Niece"),
    ("PSC", "Cousin", "Cousin"), ("WS", "Brother-in-law", "Sister-in-law"), ("SW", "Brother-in-law", "Sister-in-law"),
    ("WP", "Father-in-law", "Mother-in-law"), ("CW", "Son-in-law", "Daughter-in-law"),
]

class Kin:
    """People, parent links, spouses and genders read from the statements alone."""
    def __init__(self):
        self.parents, self.spouse, self.sex, self.sib, self.nodes, self._anon = {}, {}, {}, [], set(), 0
    def anon(self):
        self._anon += 1; return f"?{self._anon}"
    def fact(self, x, noun, y):
        self.nodes |= {x, y}
        if self.sex.setdefault(x, _B_SEX[noun]) != _B_SEX[noun]: raise ValueError(f"{x} given two genders")
        if noun in ("father", "mother"): self.parents.setdefault(y, set()).add(x)
        elif noun in ("son", "daughter"): self.parents.setdefault(x, set()).add(y)
        elif noun in ("brother", "sister"): self.sib.append((x, y))
        else: self.spouse[x], self.spouse[y] = y, x
    def finish(self):
        group = {}
        def find(n):
            group.setdefault(n, n)
            while group[n] != n: n = group[n]
            return n
        for x, y in self.sib: group[find(x)] = find(y)
        members = {}
        for n in list(group): members.setdefault(find(n), []).append(n)
        for ms in members.values():
            shared = set().union(*(self.parents.get(m, set()) for m in ms))
            if not shared:
                f, m = f"_hf{ms[0]}", f"_hm{ms[0]}"
                self.sex[f], self.sex[m] = "M", "F"; self.spouse[f], self.spouse[m] = m, f; shared = {f, m}
            for m_ in ms: self.parents[m_] = set(shared)
        for ps in list(self.parents.values()):
            if len(ps) == 2:
                p, q = sorted(ps); self.spouse.setdefault(p, q); self.spouse.setdefault(q, p)
        for x, y in list(self.spouse.items()):  # spouses are of opposite sex
            if x in self.sex and y not in self.sex: self.sex[y] = "F" if self.sex[x] == "M" else "M"
    def step(self, nodes, s):
        out = set()
        for n in nodes:
            if s == "P": out |= self.parents.get(n, set())
            elif s == "C": out |= {c for c, ps in self.parents.items() if n in ps}
            elif s == "S": out |= {c for c, ps in self.parents.items() if c != n and ps & self.parents.get(n, set())}
            elif s == "W" and n in self.spouse: out.add(self.spouse[n])
        return out
    def term(self, a, b):
        sex = self.sex.get(a)
        for path, male, female in _B_PATHS:
            here = {b}
            for s in path: here = self.step(here, s)
            if a in here:
                return male if sex == "M" else female if sex == "F" else None
        return None

def read_blood(text):
    """(Kin, question) parsed from the round text; question is ('rel', x, y), ('name', term, y) or ('count', word, x)."""
    kin, you = Kin(), "YOU"
    who = lambda w: you if w.lower() in ("you", "your") else w
    for pool, g in ((MALE_NAMES, "M"), (FEMALE_NAMES, "F")):
        for n in pool: kin.sex[n] = g
    question, defs, read, rows = None, {}, None, []
    photo = "the person in the photograph"
    for line in (l.strip().removeprefix("Question: ") for l in text.splitlines()):
        cells = re.split(r"\s{2,}", line)
        if len(cells) == 5 and cells[1] in ("Male", "Female"):  # a row of a family table
            rows.append(cells); continue
        m = re.match(rf'^Pointing to a photograph, (\w+) said, "(?:He|She) is the ({_B_NOUN}) of my ((?:(?:{_B_NOUN})\'s )*)({_B_NOUN})\."$', line)
        if m:
            outward = [n.removesuffix("'s") for n in m.group(3).split()] + [m.group(4)]  # from the speaker outward
            ids = [m.group(1)] + [kin.anon() for _ in outward]
            for i, n in enumerate(outward): kin.fact(ids[i + 1], n, ids[i])
            kin.fact("PHOTO", m.group(2), ids[-1])
            continue
        m = re.match(rf"^P (\S) Q means P is the ({_B_NOUN}) of Q\.$", line)
        if m: defs[m.group(1)] = m.group(2); continue
        m = re.match(r"^Read (.+) with these meanings\.$", line)
        if m: read = m.group(1).split(); continue
        m = re.match(rf"^Who is the ([\w-]+) of (\w+)'s ([\w-]+)\?$", line)
        if m: question = ("name2", m.group(1).lower(), m.group(3).lower(), m.group(2)); continue
        m = re.match(rf"^(?:What|How) is (the person in the photograph|\w+?)(?: related)? to (the person in the photograph|\w+)\?$", line)
        if m: question = ("rel", *("PHOTO" if g == photo else who(g) for g in m.groups())); continue
        m = re.match(rf"^(\w+) (?:is|are) (?:a man|male)\.$", line) or None
        if m: kin.sex[who(m.group(1))] = "M"; kin.nodes.add(who(m.group(1))); continue
        m = re.match(rf"^(\w+) (?:is|are) (?:a woman|female)\.$", line)
        if m: kin.sex[who(m.group(1))] = "F"; kin.nodes.add(who(m.group(1))); continue
        m = re.match(rf"^(\w+) (?:is|are) the ((?:{_B_NOUN})(?: of the (?:{_B_NOUN}))*) of (\w+)\.$", line)
        if m:
            nouns, a, b = m.group(2).split(" of the "), who(m.group(1)), who(m.group(3))
            ids = [a] + [kin.anon() for _ in nouns[1:]] + [b]
            for i, n in enumerate(nouns): kin.fact(ids[i], n, ids[i + 1])
            continue
        m = re.match(rf"^(\w+) (?:is|are) (your|\w+'s) ((?:(?:{_B_NOUN})'s )*)({_B_NOUN})\.$", line)
        if m:
            a, b = who(m.group(1)), who(m.group(2).removesuffix("'s"))
            nouns = [n.removesuffix("'s") for n in m.group(3).split()] + [m.group(4)]  # from b outward
            ids = [b] + [kin.anon() for _ in nouns[1:]] + [a]
            for i, n in enumerate(nouns): kin.fact(ids[i + 1], n, ids[i])
            continue
        m = re.match(rf"^(Your|\w+'s) ({_B_NOUN}) is (\w+)\.$", line)
        if m: kin.fact(who(m.group(3)), m.group(2), who(m.group(1).removesuffix("'s"))); continue
        m = re.match(rf"^(\w+) (?:has|have) a ({_B_NOUN}), (\w+)\.$", line)
        if m: kin.fact(who(m.group(3)), m.group(2), who(m.group(1))); continue
        m = re.match(r"^(?:What is|How is|What relation is) (\w+?)(?: related)? to (\w+)\?$", line)
        if m: question = ("rel", who(m.group(1)), who(m.group(2))); continue
        m = re.match(r"^Which person is (your|\w+'s) ([\w-]+)\?$", line)
        if m: question = ("name", m.group(2).lower(), who(m.group(1).removesuffix("'s"))); continue
        m = re.match(r"^How many (\w+) does (\w+) have\?$", line)
        if m: question = ("count", m.group(1), who(m.group(2))); continue
    for name, gender, _gen, parents, spouse in rows:
        kin.sex[name] = "M" if gender == "Male" else "F"; kin.nodes.add(name)
    for name, gender, _gen, parents, spouse in rows:
        for p_ in (parents.split(", ") if parents != "-" else []): kin.fact(p_, "father" if kin.sex[p_] == "M" else "mother", name)
        if spouse != "-": kin.fact(name, "husband" if gender == "Male" else "wife", spouse)
    if read:
        people, ops = read[0::2], read[1::2]
        for i, op in enumerate(ops): kin.fact(people[i], defs[op], people[i + 1])
    kin.finish()
    return kin, question

def solve_blood(text):
    """Answer string for the round text, worked out from the statements alone; None if it cannot be."""
    kin, q = read_blood(text)
    if q is None: return None
    if q[0] == "name2":
        _, second, first, p = q
        middles = [n for n in kin.nodes if kin.term(n, p) and kin.term(n, p).lower() == first]
        found = {n for m in middles for n in kin.nodes if not n.startswith(("?", "_")) and n != "PHOTO" and kin.term(n, m) and kin.term(n, m).lower() == second}
        return next(iter(found)) if len(found) == 1 else None
    kind, a, b = q
    if kind == "rel": return kin.term(a, b)
    if kind == "name":
        found = [n for n in sorted(kin.nodes) if not n.startswith(("?", "_")) and kin.term(n, b) and kin.term(n, b).lower() == a]
        return found[0] if len(found) == 1 else None
    x, word = b, a
    if word in ("sons", "daughters"):
        kids = kin.step({x}, "C"); return str(sum(1 for k in kids if kin.sex.get(k) == ("M" if word == "sons" else "F")))
    if word in ("brothers", "sisters"):
        sibs = kin.step({x}, "S"); return str(sum(1 for k in sibs if kin.sex.get(k) == ("M" if word == "brothers" else "F")))
    if word == "cousins": return str(len(kin.step(kin.step(kin.step({x}, "P"), "S"), "C")))
    if word == "grandchildren": return str(len(kin.step(kin.step({x}, "C"), "C")))
    return None

_DIR_VEC = {"North": (0, 1), "East": (1, 0), "South": (0, -1), "West": (-1, 0)}
_DIR_TURN = {"Turns right": 1, "Turns left": 3, "Turns around": 2, "Keeps going": 0}
_EIGHT = {(0, 1): "North", (1, 1): "North-East", (1, 0): "East", (1, -1): "South-East", (0, -1): "South",
          (-1, -1): "South-West", (-1, 0): "West", (-1, 1): "North-West"}

def _eight(dx, dy): return _EIGHT[((dx > 0) - (dx < 0), (dy > 0) - (dy < 0))]

def solve_direction(rt):
    """Reads a Direction Sense round's text (clues, then "Question: ...") and returns a dict:
    kind (int|compass|name), answer, net (walker net or None), legs (compass legs walked), ties (any tie or non-unique answer)."""
    body, _, tail = rt.partition("Question: ")
    q, order = tail.splitlines()[0].strip(), ["North", "East", "South", "West"]
    pos, heading, who, legs, ties = {}, None, None, [], []
    net = [0, 0]
    def step(d, n):
        vx, vy = _DIR_VEC[d]
        if who is None: net[0] += vx * n; net[1] += vy * n
        else: pos[who] = (pos[who][0] + vx * n, pos[who][1] + vy * n)
        legs.append((d, n))
    for ln in body.splitlines()[1:]:
        if m := re.match(r"(\w+) is at the centre\.$", ln): pos[m.group(1)] = (0, 0)
        elif m := re.match(r"(\w+) is (.+) of (\w+)\.$", ln):
            dx = dy = 0
            for n, d in re.findall(r"(\d+)m (North|East|South|West)", m.group(2)): dx += int(n) * _DIR_VEC[d][0]; dy += int(n) * _DIR_VEC[d][1]
            pos[m.group(1)] = (pos[m.group(3)][0] + dx, pos[m.group(3)][1] + dy)
        elif m := re.match(r"Then (\w+) walks (\d+)m (\w+)\.$", ln): who = m.group(1); step(m.group(3), int(m.group(2)))
        elif m := re.match(r"(?:Then )?(\w+) starts facing (\w+)", ln):
            heading = order.index(m.group(2)); who = m.group(1) if ln.startswith("Then ") else None
        elif m := re.match(r"  (\d+)m (North|East|South|West)$", ln): step(m.group(2), int(m.group(1)))
        elif m := re.match(r"  (Turns right|Turns left|Turns around|Keeps going), walks (\d+)m\.$", ln):
            heading = (heading + _DIR_TURN[m.group(1)]) % 4; step(order[heading], int(m.group(2)))
    def gap(a, b): return pos[a][0] - pos[b][0], pos[a][1] - pos[b][1]
    walker = who is None and not pos
    wnet = tuple(net) if walker else None
    if re.match(r"In which direction is \w+ from the starting point\?", q): return dict(kind="compass", answer=_eight(*net), net=wnet, legs=legs, ties=ties)
    if re.match(r"Which way is \w+ facing at the end\?", q): return dict(kind="compass", answer=order[heading], net=wnet, legs=legs, ties=ties)
    if re.match(r"How far is \w+ from the starting point\?", q):
        d = math.hypot(*net)
        if abs(d - round(d)) > 1e-9: ties.append(f"non-integer distance {d}")
        return dict(kind="int", answer=str(round(d)), net=wnet, legs=legs, ties=ties)
    if m := re.match(r"(?:After the walk, i|I)n which direction is (\w+) from (\w+)\?", q):
        return dict(kind="compass", answer=_eight(*gap(m.group(1), m.group(2))), net=None, legs=legs, ties=ties)
    if m := re.match(r"How far is (\w+) from (\w+)\?", q):
        d = math.hypot(*gap(m.group(1), m.group(2)))
        if abs(d - round(d)) > 1e-9: ties.append(f"non-integer distance {d}")
        return dict(kind="int", answer=str(round(d)), net=None, legs=legs, ties=ties)
    if m := re.match(r"After the move, who is (nearest|farthest) to (\w+)\?", q):
        ref = m.group(2)
        d2 = {n: (p[0] - pos[ref][0]) ** 2 + (p[1] - pos[ref][1]) ** 2 for n, p in pos.items() if n != ref}
        best = (min if m.group(1) == "nearest" else max)(d2.values()); win = [n for n, v in d2.items() if v == best]
        if len(win) != 1: ties.append(f"tie {win}")
        return dict(kind="name", answer=win[0], net=None, legs=legs, ties=ties)
    if m := re.match(r"Who stands directly between (\w+) and (\w+)\?", q):
        (ax, ay), (bx, by) = pos[m.group(1)], pos[m.group(2)]
        inside = [n for n, (x, y) in pos.items() if n not in m.groups() and (bx - ax) * (y - ay) == (by - ay) * (x - ax)
                  and min(ax, bx) <= x <= max(ax, bx) and min(ay, by) <= y <= max(ay, by)]
        if len(inside) != 1: ties.append(f"between {inside}")
        return dict(kind="name", answer=inside[0] if inside else "?", net=None, legs=legs, ties=ties)
    raise AssertionError("unreadable Direction Sense question: " + q)

def enc_num(word, off): return "".join(str(ord(c) - 64 + off) for c in word)
def enc_shift(word, sh):
    out = ""
    for c in word:
        v = ord(c) + sh
        if v > 90: v -= 26
        if v < 65: v += 26
        out += chr(v)
    return out

def solve_coding(w1, c1, w2):
    """Every (rule, parameter) that reproduces the example, with what it predicts for w2."""
    hyp = []
    if c1.isdigit():
        for off in range(-3, 30):
            try:
                if enc_num(w1, off) == c1: hyp.append((f"offset {off}", enc_num(w2, off)))
            except Exception: pass
    else:
        for sh in range(-25, 26):
            if enc_shift(w1, sh) == c1: hyp.append((f"shift {sh}", enc_shift(w2, sh)))
    return hyp

def solve_ranking(clues):
    sols = []
    for p in itertools.permutations("ABCDE"):
        s = "".join(p); ok = True
        for c in clues:
            m = re.fullmatch(r"(\w) ranks above (\w)\.", c)
            if m: ok &= s.index(m.group(1)) < s.index(m.group(2)); continue
            m = re.fullmatch(r"(\w) ranks at the top\.", c)
            if m: ok &= s[0] == m.group(1); continue
            m = re.fullmatch(r"(\w) ranks at the bottom\.", c)
            if m: ok &= s[-1] == m.group(1); continue
            raise ValueError(c)
        if ok: sols.append(s)
    return sols

def solve_seating(clues):
    sols = []
    for p in itertools.permutations("ABCDE"):
        s = "".join(p); ok = True
        for c in clues:
            m = re.fullmatch(r"(\w) sits immediately left of (\w)\.", c)
            if m: ok &= s.index(m.group(1)) + 1 == s.index(m.group(2)); continue
            m = re.fullmatch(r"(\w) sits at the extreme left end\.", c)
            if m: ok &= s[0] == m.group(1); continue
            m = re.fullmatch(r"(\w) sits at the extreme right end\.", c)
            if m: ok &= s[-1] == m.group(1); continue
            raise ValueError(c)
        if ok: sols.append(s)
    return sols

def _holds(kind, types, X, Y, neg=False):
    """types: set of (a,b,c) tuples present. X,Y indexes 0..2."""
    if kind == "All": return all(t[Y] for t in types if t[X])
    if kind == "No": return not any(t[X] and t[Y] for t in types)
    if kind == "Some": return any(t[X] and not t[Y] for t in types) if neg else any(t[X] and t[Y] for t in types)
    raise ValueError(kind)

def solve_syllogism(stmts, concl, import_=True):
    names = []
    for k, x, y in stmts + [concl[:1] + concl[1:3]]:
        for n in (x, y):
            if n not in names: names.append(n)
    idx = {n: i for i, n in enumerate(names)}
    all_types = list(itertools.product((0, 1), repeat=3))
    verdicts = set()
    for mask in range(1, 256):
        types = {all_types[i] for i in range(8) if mask >> i & 1}
        if import_ and not all(any(t[i] for t in types) for i in range(3)): continue
        if not all(_holds(k, types, idx[x], idx[y]) for k, x, y in stmts): continue
        kind, x, y, neg = concl
        verdicts.add(_holds(kind, types, idx[x], idx[y], neg))
    if verdicts == {True}: return "1"
    if verdicts == {False}: return "2"
    return "3"

# ---------------------------------------------------------------- bot
GARBAGE = ["", "   ", "abc", "-1", "0", "99999999999999999999999999", "1e3", "3.5", "１２", "1_0", "12abc",
           "'; DROP TABLE users;--", "A" * 5000, "None", "\t", "hint hint", " HINT ", "/ai", "/AI", "\x00", "🙂", "ABCDEF", "AAAAA",
           "A B C D E", "5", "9", "true", "yes"]

class Bot:
    def __init__(self):
        self.out = io.StringIO(); self.reset()
        self.results, self.crashes, self.findings = [], [], []
        self.fmt = collections.defaultdict(lambda: [0, 0])   # (game, variant) -> [accepted, rejected]
        self.amb = []; self.facts = collections.Counter(); self.samples = collections.defaultdict(list)
        self.user = self.username = ""
        self.hist: list[str] = []
        self.locked: list[tuple] = []
        self.explain_prompts = 0

    def reset(self):
        self.queue = collections.deque(); self.cur: dict[str, Any] | None = None; self.mark = 0

    def tail(self): return self.out.getvalue()[self.mark:]
    def write(self, s): self.out.write(s)
    def flush(self): pass

    def flag(self, kind, c, msg):
        self.findings.append(dict(kind=kind, game=c.get("gid"), mode=c.get("mode"), user=c.get("user", self.user), msg=str(msg)[:400]))

    # -- session lifecycle
    def begin(self, title, mode, user):
        gid, rounds, base = GAMES[title]
        prof = app_profile[0]; u = prof.require_user()
        self.cur = dict(title=title, gid=gid, mode=mode, user=user, rounds=rounds, base=base, n=0, fmt=[],
                        diff_before=prof.difficulty(gid), level_before=u.level, xp_before=u.xp,
                        rows_before=prof.db.count_user_sessions(u.id), start=len(self.out.getvalue()),
                        cancel_at=random.randint(1, rounds - 1) if mode == "cancel" else None, n_fmt=random.randrange(40) - 1,
                        round=0, hints_planned=0, hints_given=0, hints_by_round={}, answers={}, truth={}, asked_fmt=None)
        self.mark = len(self.out.getvalue())

    def round_slice(self, c, k):
        text = self.out.getvalue()[c["start"]:]
        starts = [m.start() for m in re.finditer(r"Round \d+/\d+", text)]
        if k > len(starts): return ""
        return text[starts[k - 1]: starts[k] if k < len(starts) else len(text)]

    def check_round_text(self, c, k, txt):
        """Hints and explanations the game printed must agree with the bot's own solution."""
        gid, tr = c["gid"], c["truth"].get(k)
        if tr is None: return
        hints = re.findall(r"Hint (\d): (.*?)  \(-", txt)
        expl = re.findall(r"📘 (.*)", txt)
        bad = []
        if gid == "direction_sense":
            ans, net = tr["answer"], tr["net"]
            for n, h in hints:
                if net is not None:
                    m = re.search(r"net East-West distance is (\d+)m\.", h)
                    if m and int(m.group(1)) != abs(net[0]): bad.append(h)
                    m = re.search(r"net East-West movement is (\d+)m (East|West)", h)
                    if m and (int(m.group(1)), m.group(2)) != (abs(net[0]), "East" if net[0] > 0 else "West"): bad.append(h)
                if re.search(rf"(?<![\w-]){re.escape(ans)}(?![\w-])", h, re.I): bad.append("hint gives the answer: " + h)
            for e in expl:
                if tr["kind"] == "int" and net is not None:
                    ew, nsd = abs(net[0]), abs(net[1])
                    m = re.search(r"Net East-West = (\d+)m, net North-South = (\d+)m\. Distance = sqrt\((\d+)\^2 \+ (\d+)\^2\) = sqrt\((\d+)\) = (\d+)m", e)
                    if not m or tuple(map(int, m.groups())) != (ew, nsd, ew, nsd, ew * ew + nsd * nsd, int(ans)): bad.append(e)
                elif re.sub(r"[^a-z0-9]", "", ans.lower()) not in re.sub(r"[^a-z0-9]", "", e.lower()): bad.append(e)
        elif gid == "rankings":
            for n, h in hints:
                m = re.search(r"top-ranked item is (\w)", h)
                if m and m.group(1) != tr[0]: bad.append(h)
                m = re.search(r"top is (\w) and the bottom is (\w)", h)
                if m and (m.group(1), m.group(2)) != (tr[0], tr[-1]): bad.append(h)
            for e in expl:
                if f"highest to lowest is {tr}" not in e: bad.append(e)
        elif gid == "linear_seating":
            for n, h in hints:
                m = re.search(r"^(\w) sits at the extreme left", h)
                if m and m.group(1) != tr[0]: bad.append(h)
                m = re.search(r"first two are (\w), (\w), and (\w) is at the far right", h)
                if m and (m.group(1), m.group(2), m.group(3)) != (tr[0], tr[1], tr[-1]): bad.append(h)
            for e in expl:
                if f": {tr} from left to right" not in e: bad.append(e)
        elif gid == "coding_decoding":
            hyp = c.get("hyp") or []
            for n, h in hints:
                m = re.search(r"increased by (\d+)", h)
                if m and f"offset {m.group(1)}" not in [r for r, _ in hyp]: bad.append(h)
                m = re.search(r"moves (\d+) place\(s\) (forward|back)", h)
                if m:
                    sh = int(m.group(1)) * (1 if m.group(2) == "forward" else -1)
                    if f"shift {sh}" not in [r for r, _ in hyp]: bad.append(h)
            for e in expl:
                if tr not in e: bad.append(e)
        elif gid == "blood_relations":
            for n, h in hints:
                if re.search(rf"{re.escape(str(tr))}", h, re.I) and not re.fullmatch(r"[A-L]", str(tr)): bad.append("hint gives the answer: " + h)
        elif gid == "syllogisms":
            want = {"1": "definitely follows", "2": "is contradicted", "3": "neither follows"}[tr]
            for n, h in hints:
                if h.startswith("The conclusion") and want not in h: bad.append(h)
            m = re.search(r"The correct answer was (\d) \((.*?)\)\.", txt)
            if m and m.group(1) != tr: bad.append("printed answer " + m.group(1) + " vs " + tr)
        if gid in ("direction_sense", "rankings", "linear_seating", "coding_decoding", "blood_relations", "mental_math", "anagrams"):
            pr = re.search(r"(?:correct (?:answer|arrangement|word) was:? |arrangement was: )(.+?)\.?\s*$", txt, re.M)
            if pr:
                shown = pr.group(1).strip().rstrip(".")
                want = {"direction_sense": "", "anagrams": None}.get(gid, str(tr))
                if gid == "direction_sense": want = tr["answer"] + ("m" if tr["kind"] == "int" else "")
                if gid == "anagrams": shown = shown.lower(); want = tr
                if gid == "mental_math": want = str(tr)
                if gid == "coding_decoding": want = tr
                if want is not None and shown != want and not (gid == "anagrams" and shown in KNOWN.get("".join(sorted(want)), ())):
                    bad.append(f"game says answer {shown!r}, bot solved {want!r}")
        for b in bad: self.flag("hint/explain-wrong", c, f"round {k}: {b}")
        self.facts["rounds_text_checked"] += 1

    def finish(self):
        c = self.cur; self.cur = None
        assert c is not None
        if c["round"]:
            self.check_round_text(c, c["round"], self.round_slice(c, c["round"]))
        prof = app_profile[0]; prof.refresh(); u = prof.require_user()
        text = self.out.getvalue()[c["start"]:]
        rows = prof.db.count_user_sessions(u.id)
        rec = dict(user=c["user"], game=c["gid"], mode=c["mode"], level_before=c["level_before"], level_after=u.level,
                   xp_before=c["xp_before"], xp_after=u.xp, diff_before=c["diff_before"])
        if c["mode"] == "cancel":
            rec["saved"] = rows != c["rows_before"]
            if rec["saved"] or "Game cancelled" not in text: self.flag("cancel", c, f"saved={rec['saved']}")
            self.results.append(rec); return
        if rows != c["rows_before"] + 1:
            self.flag("no-row", c, f"rows {c['rows_before']}->{rows}"); self.results.append(rec); return
        s = prof.db.get_user_stats(u.id, limit=1)[0]
        rec.update(score=s.score, acc=round(s.accuracy, 3), rt=round(s.reaction_time_ms), stored_diff=s.difficulty,
                   integrity=s.integrity, assisted=s.assisted, trials=json.loads(s.trial_data) if s.trial_data else None)
        flags = [bool(m.group(1) == "Correct!") for m in re.finditer(r"^(?:✅ |❌ )?(Correct!|Incorrect)", text, re.M)]
        exp_acc = sum(flags) / len(flags) if flags else 0
        if len(flags) != c["rounds"]: self.flag("rounds", c, f"{len(flags)} trials seen, expected {c['rounds']}")
        if abs(exp_acc - s.accuracy) > 1e-9: self.flag("accuracy", c, f"stored {s.accuracy} vs seen {exp_acc}")
        # score cross-check
        gid = c["gid"]; sc = 0; st = 0
        if gid == "mental_math":
            for f in flags:
                if f: sc += 10 + 2 * st; st += 1
                else: st = 0
            if sc != s.score: self.flag("score", c, f"stored {s.score} vs expected {sc}")
        elif gid == "anagrams":
            pts = [int(x) for x in re.findall(r"Correct! \(\+(\d+) Points\)", text)]
            if sum(pts) != s.score: self.flag("score", c, f"stored {s.score} vs printed points {pts}")
            # each printed value must match max(5, 15-5*hints)+2*streak given the hints the bot saw
            st = 0; k_ok = 0
            for r_i, f in enumerate(flags, 1):
                h = c["hints_by_round"].get(r_i, 0)
                if f:
                    expect = max(5, 15 - 5 * h) + 2 * st; st += 1
                    got = pts[k_ok] if k_ok < len(pts) else None; k_ok += 1
                    if got != expect: self.flag("points", c, f"round {r_i}: printed {got}, expected {expect} (hints {h})")
                else: st = 0
        else:
            for r_i, f in enumerate(flags, 1):
                h = min(c["hints_by_round"].get(r_i, 0), 3)
                if f: sc += round(c["base"] * (1 - PENALTY[h]))
            if sc != s.score: self.flag("score", c, f"stored {s.score} vs expected {sc} (hints {c['hints_by_round']})")
        gained = u.xp - c["xp_before"]
        exp_xp = 0 if s.assisted else xp_for(gid, s.score)
        if gained != exp_xp: self.flag("xp", c, f"gained {gained} vs expected {exp_xp}")
        if u.level < c["level_before"]: self.flag("level-down", c, f"{c['level_before']}->{u.level}")
        if level_for_xp(u.xp) > u.level: self.flag("level-lag", c, f"xp {u.xp} implies {level_for_xp(u.xp)} but level {u.level}")
        want_diff = c["diff_before"] if gid in ("mental_math", "anagrams", "direction_sense", "syllogisms", "blood_relations") else None
        if s.difficulty != want_diff: self.flag("difficulty", c, f"stored {s.difficulty} vs expected {want_diff}")
        if s.integrity not in (None, "ok", "review"): self.flag("integrity", c, s.integrity)
        if s.integrity is None: self.flag("integrity-null", c, "no verdict stored")
        # printed vs stored speed
        m = re.search(r"Average Speed: (\d+)ms", text)
        if m and abs(int(m.group(1)) - s.reaction_time_ms) > 1: self.flag("speed", c, f"printed {m.group(1)} vs stored {s.reaction_time_ms}")
        m = re.search(r"Average Time: ([\d.]+)s per word", text)
        if m and abs(float(m.group(1)) * 1000 - s.reaction_time_ms) > 60: self.flag("speed", c, f"printed {m.group(1)}s vs stored {s.reaction_time_ms}")
        m = re.search(r"Accuracy: ([\d.]+)%", text)
        if m and abs(float(m.group(1)) / 100 - s.accuracy) > 0.001: self.flag("accuracy-print", c, f"printed {m.group(1)} vs stored {s.accuracy}")
        # integrity expectations
        allright = all(flags) and not c["hints_by_round"] and not s.assisted
        if c["mode"] == "fast" and allright and s.integrity != "review": self.flag("integrity-miss", c, f"instant correct answers judged {s.integrity}")
        if c["mode"] in ("avg", "strong", "weak", "format", "expert") and s.integrity == "review":
            self.flag("integrity-false-review", c, f"human-speed play judged review; trials={rec['trials']}")
        if c["mode"] in ("hints", "hintfast") and s.integrity == "review":
            self.flag("integrity-hinted", c, f"answers after hints judged review; trials={rec['trials']}")
        if c["mode"] in ("hints", "hintfast") and c["hints_by_round"] and rec["trials"] and gid != "anagrams":
            if all(t[2] == 0 for t in rec["trials"]): self.flag("hints-not-recorded", c, f"{sum(c['hints_by_round'].values())} hints asked, trial_data says 0")
        if c["mode"] == "assist" and gid == "anagrams" and not s.assisted: self.flag("assist", c, "assisted flag not stored")
        if c["mode"] == "assist" and gid == "anagrams" and gained != 0: self.flag("assist", c, f"assisted game earned {gained} XP")
        # per-format outcome
        if c["mode"] == "format" and len(c["fmt"]) == len(flags):
            for name, f in zip(c["fmt"], flags): self.fmt[(gid, name)][0 if f else 1] += 1
        elif c["mode"] == "format": self.flag("fmt-count", c, f"{len(c['fmt'])} variants vs {len(flags)} outcomes")
        rec["flags"] = "".join("1" if f else "0" for f in flags)
        self.results.append(rec)

    # -- helpers used by respond
    def timing(self, c):
        m = c["mode"]
        exp = random.uniform(1.5, 4) if c["gid"] in ("mental_math", "anagrams") else random.uniform(5, 12)
        t = {"fast": random.uniform(.03, .3), "hintfast": random.uniform(.03, .3), "expert": exp, "slow": random.uniform(90, 200)}.get(m)
        if t is None: t = random.uniform(4, 15)
        if c["gid"] == "syllogisms" or c["gid"] == "linear_seating": t += random.uniform(3, 10) if m not in ("fast",) else 0
        advance(t)

    def p_of(self, mode):
        return {"strong": .97, "expert": 1.0, "avg": .72, "weak": .35, "wrong": 0.0}.get(mode, 1.0)

    def new_round_check(self, c, t):
        """Detect a new round; reset per-round bookkeeping."""
        rounds_seen = len(re.findall(r"Round \d+/\d+", self.out.getvalue()[c["start"]:]))
        if rounds_seen != c["round"]:
            if c["round"]: self.check_round_text(c, c["round"], self.round_slice(c, c["round"]))
            c["round"] = rounds_seen
            c["hints_planned"] = (min(rounds_seen, 4) if c["mode"] in ("hints", "hintfast") else 0)
            c["hints_given"] = 0; c["expl_asked"] = 0
            return True
        return False

    def respond(self, prompt):
        p = prompt
        if "Enter your username" in p: return self.username
        if "Select an option" in p:
            if self.cur: self.finish()
            return self.menu_choice()
        if "Press Enter" in p: return ""
        if "[n]ext" in p or "Enter to return" in p: return self.hist.pop(0) if self.hist else ""
        c = self.cur
        if c is None: return "0"  # unattributed prompt (RAW menu probe): blank answers can loop forever
        gid = c["gid"]; mode = c["mode"]
        if "Show explanation" in p:
            self.explain_prompts += 1
            return random.choice(["y", "n", "Y", "yes", " y ", ""]) if mode != "edge" else random.choice(GARBAGE)
        c["n"] += 1
        if c["cancel_at"] and c["n"] == c["cancel_at"]: raise KeyboardInterrupt
        if mode == "eof" and c["n"] == 2: raise EOFError
        t = self.tail()
        fresh = self.new_round_check(c, t)
        if c["hints_given"] < c["hints_planned"]:
            c["hints_given"] += 1
            c["hints_by_round"][c["round"]] = c["hints_given"]
            return random.choice(["hint", "HINT", " hint "]) if random.random() < .3 else "hint"
        self.timing(c)
        if mode == "edge":
            return GARBAGE[(c["n"] * 7 + hash(gid)) % len(GARBAGE)]
        ok = random.random() < self.p_of(mode)
        rt = t[t.rfind("Round "):]
        fn = getattr(self, "ans_" + gid)
        truth, wrong, kind = fn(c, rt)
        if mode == "assist" and gid == "anagrams" and c["round"] in (2, 4) and not c.get("assisted_" + str(c["round"])):
            c["assisted_" + str(c["round"])] = True
            return random.choice(["/ai", "/AI", " /Ai "])
        if mode == "format": return self.fmt_variant(c, truth, kind)
        return truth if ok else wrong

    # -- per-game readers: return (truth string, plausible-wrong string, kind)
    def ans_mental_math(self, c, rt):
        m = re.search(r"Round (\d+)/10 \[Streak: (\d+)\]: (.+) = \?", rt)
        assert m is not None
        q = m.group(3); ans = solve_arith(q)
        c["truth"][c["round"]] = ans
        if "/" in q and ans != eval(q): pass
        self.facts["mm_max_answer"] = max(self.facts["mm_max_answer"], ans)
        self.facts["mm_max_len"] = max(self.facts["mm_max_len"], len(q))
        self.samples["mm_q"].append(q)
        return str(ans), str(ans + random.choice([-10, -1, 1, 2, 10])), "int"

    def ans_anagrams(self, c, rt):
        m = re.search(r"Scrambled word -> \[ (\w+) \]\nDefinition: (.*)", rt)
        assert m is not None
        scr, clue = m.group(1), m.group(2)
        cands = solve_anagram(scr)
        self.samples["ana"].append((scr, clue))
        if len(clue) > 140 or not clue.strip(): self.flag("clue", c, f"{scr}: clue length {len(clue)}: {clue[:60]}")
        if not cands:
            self.flag("unsolvable", c, f"{scr}: no known word"); return "zzzz", "zzzz", "word"
        pick = random.choice(cands)
        if pick in clue.lower().split(): self.flag("clue-leak", c, f"{pick} in its own clue: {clue}")
        c["truth"][c["round"]] = pick
        wrong = "".join(random.sample(scr, len(scr)))
        if sorted(wrong) == sorted(pick) and wrong in cands: wrong = "qqqqq"
        return pick, "qq" + pick[2:] if len(pick) > 2 else "qq", "word"

    def ans_blood_relations(self, c, rt):
        body = rt.split(chr(10), 1)[-1]  # drop the "Round k/n:" line
        ans = solve_blood(body)
        question = read_blood(body)[1]
        if ans is None: self.flag("unsolvable", c, body); return "Uncle", "Cousin", "rel"
        self.samples["blood"].append((body.strip().replace(chr(10), " | "), ans))
        c["truth"][c["round"]] = ans
        if question[0] == "count": return ans, str(int(ans) + 1), "cnt"
        if question[0] in ("name", "name2"): return ans, "Nobody", "name"
        wrong = random.choice([w for w in ("Uncle", "Aunt", "Cousin", "Niece", "Son", "Father", "Brother-in-law") if w != ans])
        return ans, wrong, "rel"

    def ans_direction_sense(self, c, rt):
        r = solve_direction(rt)
        for t in r["ties"]: self.flag("direction-ambiguous", c, t)
        c["truth"][c["round"]] = r
        if r["net"] is not None and not 2 <= len(r["legs"]) <= 4: self.flag("moves-count", c, str(r["legs"]))
        dirs = [d for d, n in r["legs"]]
        if any(dirs.count(x) > 1 for x in dirs): self.facts["dir_repeat_axis_moves"] += 1
        self.facts["dir_kind_" + r["kind"]] += 1
        if r["kind"] == "int": return r["answer"], str(int(r["answer"]) + random.choice([-2, -1, 1, 3])), "int"
        if r["kind"] == "name": return r["answer"], "Nobody", "name"
        return r["answer"], random.choice([d for d in _EIGHT.values() if d != r["answer"]]), "compass"

    def ans_coding_decoding(self, c, rt):
        m = re.search(r"If (\w+) = (\w+)\nFind: (\w+) = \?", rt)
        assert m is not None
        w1, c1, w2 = m.groups()
        hyp = solve_coding(w1, c1, w2)
        answers = {a for _, a in hyp}
        if not hyp: self.flag("unsolvable", c, f"{w1}={c1}"); return "X", "Y", "code"
        if len(answers) > 1: self.amb.append(("coding", f"{w1}={c1} find {w2}", hyp))
        self.samples["coding"].append((w1, c1, w2, hyp))
        c["truth"][c["round"]] = sorted(answers)[0]
        c["hyp"] = hyp
        ans = sorted(answers)[0]
        wrong = ans[:-1] + ("Z" if not ans.endswith("Z") else "Y") if not ans.isdigit() else str(int(ans) + 1)
        return ans, wrong, "code"

    def ans_rankings(self, c, rt):
        clues = re.findall(r"^- (.+)$", rt, re.M)
        sols = solve_ranking(clues)
        if len(sols) != 1: self.flag("ranking-not-unique", c, f"{len(sols)} solutions for {clues}")
        self.samples["rank_clues"].append(len(clues))
        c["truth"][c["round"]] = sols[0] if sols else "?"
        ans = sols[0] if sols else "ABCDE"
        wrong = ans[1] + ans[0] + ans[2:]
        return ans, wrong, "order"

    def ans_syllogisms(self, c, rt):
        from games.reasoning.syllogism_model import Stmt, verdict
        def stmt(m): return Stmt("SomeNot" if m.group(3) else m.group(1), m.group(2), m.group(4))
        stmts = [stmt(m) for m in re.finditer(r"^- (All|Some|No) (\w+) are (not )?(\w+)\.$", rt, re.M)]
        m = re.search(r"^Conclusion: (All|Some|No) (\w+) are (not )?(\w+)\.$", rt, re.M)
        assert m is not None
        a1 = {"True": "1", "False": "2", "Cannot be determined": "3"}[verdict(stmts, stmt(m))]
        c["truth"][c["round"]] = a1
        self.samples["syl"].append((stmts, stmt(m), a1))
        return a1, random.choice([x for x in "123" if x != a1]), "opt"

    def ans_linear_seating(self, c, rt):
        clues = re.findall(r"^  - (.+)$", rt, re.M)
        sols = solve_seating(clues)
        if len(sols) != 1: self.flag("seating-not-unique", c, f"{len(sols)} solutions for {clues}")
        self.samples["seat_clues"].append(len(clues))
        ans = sols[0] if sols else "ABCDE"
        c["truth"][c["round"]] = ans
        return ans, ans[::-1] if ans[::-1] != ans else "ABCDE", "order"

    # -- format variants
    def fmt_variant(self, c, truth, kind):
        t = str(truth)
        V = {
            "int": lambda: [("plain", t), ("plus-sign", f"+{t}"), ("thousands-comma", f"{int(t):,}" if int(t) > 999 else f"1,{int(t):03d}" if False else f"{int(t):,}"),
                            ("trailing-dot", f"{t}."), ("decimal", f"{t}.0"), ("padded", f"  {t}  "),
                            ("fullwidth", t.translate(str.maketrans("0123456789", "０１２３４５６７８９"))),
                            ("unit-m", f"{t}m"), ("unit-m-space", f"{t} m"), ("unit-meters", f"{t} meters"),
                            ("underscore", t[:1] + "_" + t[1:] if len(t) > 1 else t), ("leading-zero", "0" + t)],
            "word": lambda: [("plain", t), ("upper", t.upper()), ("title", t.title()), ("padded", f"  {t}  "), ("quoted", f"'{t}'"),
                             ("spaced-letters", " ".join(t)), ("trailing-dot", t + "."), ("with-article", "the " + t)],
            "rel": lambda: [("plain", t), ("lower", t.lower()), ("upper", t.upper()), ("padded", f"  {t}  "), ("trailing-dot", t + "."),
                            ("with-article", "an " + t.lower() if t[0] in "AEIOU" else "a " + t.lower()),
                            ("spaces-for-dashes", t.replace("-", " ")), ("no-dashes", t.replace("-", "")),
                            ("initials", "bil" if t == "Brother-in-law" else t)],
            "compass": lambda: [("plain", t), ("abbr", "".join(w[0] for w in t.split("-"))), ("lower", t.lower()), ("upper", t.upper()),
                                ("padded", f"  {t}  "), ("trailing-dot", t + "."), ("spaces-for-dashes", t.replace("-", " ")),
                                ("no-dashes", t.replace("-", "")), ("lower-abbr", "".join(w[0] for w in t.split("-")).lower())],
            "cnt": lambda: [("plain", t), ("plus-sign", f"+{t}"), ("trailing-dot", f"{t}."), ("decimal", f"{t}.0"), ("padded", f"  {t}  "),
                            ("leading-zero", "0" + t)],
            "name": lambda: [("plain", t), ("lower", t.lower()), ("upper", t.upper()), ("padded", f"  {t}  "), ("quoted", f"'{t}'"), ("trailing-dot", t + ".")],
            "code": lambda: [("plain", t), ("lower", t.lower()), ("padded", f"  {t}  "), ("quoted", f"'{t}'"),
                             ("spaced", " ".join(t)), ("comma-separated", ",".join(t)), ("trailing-dot", t + "."), ("dash-separated", "-".join(t))],
            "order": lambda: [("plain", t), ("lower", t.lower()), ("spaced", " ".join(t)), ("commas", ",".join(t)), ("comma-space", ", ".join(t)),
                              ("dashes", "-".join(t)), ("arrows", ">".join(t)), ("spaced-arrows", " > ".join(t)), ("dot", t + "."),
                              ("quoted", f"'{t}'"), ("padded", f"  {t}  ")],
            "opt": lambda: [("plain", t), ("padded", f" {t} "), ("dot", t + "."), ("paren", f"({t})"), ("hash", "#" + t),
                            ("word", {"1": "True", "2": "False", "3": "Cannot be determined"}[t]),
                            ("word-lower", {"1": "true", "2": "false", "3": "cannot be determined"}[t]),
                            ("letter", {"1": "T", "2": "F", "3": "C"}[t]), ("option-word", f"option {t}")],
        }[kind]()
        i = c["n_fmt"] = c["n_fmt"] + 1
        name, val = V[i % len(V)]
        c["fmt"].append(name)
        return val

    # -- menu
    def menu_choice(self):
        t = self.tail()
        menu = t[t.rfind("MAIN MENU"):]
        nums = {m.group(2).strip(): int(m.group(1)) for m in re.finditer(r"^(\d+)\. (?:Play )?(.+?)(?:\s+L\d+)?$", menu, re.M)}
        while True:
            if not self.queue: return str(nums["Exit"])
            item = self.queue.popleft()
            if item == "STATS": choice = str(nums["View Statistics"]); break
            if isinstance(item, tuple) and item[0] == "RAW": self.mark = len(self.out.getvalue()); return item[1]
            title, mode = item
            if title not in nums:
                self.facts["locked_skipped"] += 1; self.locked.append((self.user, title, mode)); continue
            self.begin(title, mode, self.user); choice = str(nums[title]); break
        self.mark = len(self.out.getvalue())
        return choice

app_profile: list[Any] = [None]
bot = Bot()

def fake_input(prompt=""):
    bot.write(str(prompt))
    r = bot.respond(str(prompt))
    bot.write(f"{r[:80]}\n")
    return r

def run_campaign(user, plan, hist=None, xp=0):
    bot.reset(); bot.user = user; bot.username = user; bot.hist = list(hist or [])
    if xp:
        d = DBManager(db_path=DB, legacy_json=None); u = d.create_user(user)
        assert u is not None
        d.update_user_xp(u.id, xp, level_for_xp(xp))
    bot.queue.extend(plan)
    while True:
        try:
            app.main(); break
        except SystemExit as e:
            bot.crashes.append(dict(user=user, kind="SystemExit", detail=str(e.code), where=bot.cur and bot.cur["gid"])); break
        except BaseException as e:
            tb = traceback.format_exc().strip().splitlines()
            bot.crashes.append(dict(user=user, kind=type(e).__name__, where=bot.cur and (bot.cur["gid"], bot.cur["mode"]),
                                    detail=tb[-1], line=tb[-3].strip() if len(tb) > 2 else ""))
            bot.cur = None
            if not bot.queue: break
            continue

def install(real_network=False):
    builtins.input = fake_input
    sys.stdout = bot
    app._ai_enabled = lambda: False            # coaching off
    g_assist._ai_enabled = lambda: False       # no AI hints / explanations / relation checks
    g_seat._start_theme_wrap = lambda *a, **k: None   # no AI theme wrap
    if real_network:
        orig = g_ana.fetch_words_from_api
        def spy(n):
            r = orig(n)
            for it in r: KNOWN["".join(sorted(it["word"]))].add(it["word"])
            return r
        g_ana.fetch_words_from_api = spy
    else:
        offline = {w["word"] for w in offline_words()}
        g_ana.fetch_words_from_api = lambda n: []
        g_ana.is_real_word = lambda w: w in offline
        g_ana.fetch_dictionary_clues = lambda w: {"part_of_speech": "noun", "definition": f"a definition of {w[:2]}..", "example": f"I saw the {w} today.",
                                                  "synonyms": ["alpha", "beta"], "antonyms": []}
    class TDB(DBManager):
        def __init__(self, *a, **k):
            super().__init__(db_path=DB, legacy_json=None)
    app.DBManager = lambda *a, **k: TDB()
    orig_pm = app.ProfileManager
    def PM(db):
        p = orig_pm(db); app_profile[0] = p; return p
    app.ProfileManager = PM
    app.load_dotenv = lambda *_: None
