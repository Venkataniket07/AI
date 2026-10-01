"""QA harness: plays games 3-10 through the real main() loop against a throwaway DB."""
import builtins, io, os, random, re, sys, time, traceback, collections

import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SCR = WORK = Path(tempfile.gettempdir()) / "brain_trainer_qa"
SCR.mkdir(exist_ok=True)
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

import main as app
from core.progression import xp_for, level_for_xp
from database.db_manager import DBManager
import games.memory.number_recall as m_nr, games.memory.n_back as m_nb, games.memory.pattern_memory as m_pm
import games.math.quick_calc as m_qc

DB = os.path.join(SCR, "qa.db")
for ext in ("", "-wal", "-shm"):
    if os.path.exists(DB + ext):
        os.remove(DB + ext)

GAMES = {  # menu title -> (db id, rounds)
    "Sequence Prediction": ("seq_predict", 5), "Matrix Reasoning": ("matrix", 4),
    "Pattern Completion": ("pattern_comp", 5), "Missing Number": ("missing_num", 5),
    "Quick Calculation Duel": ("quick_calc", 10), "Number Recall": ("number_recall", 5),
    "N-Back Memory": ("n_back", 10), "Pattern Memory": ("pattern_memory", 4),
}
STEP = {"seq_predict": (20, 5), "pattern_comp": (20, 5), "missing_num": (20, 5), "matrix": (25, 5),
        "number_recall": (20, 5), "pattern_memory": (25, 5)}

# ---------------------------------------------------------------- fake clock
CLOCK = [1000.0]
time.perf_counter = lambda: CLOCK[0]
def fake_sleep(s): CLOCK[0] += s
time.sleep = fake_sleep
def advance(s): CLOCK[0] += s

# ---------------------------------------------------------------- solvers
def is_prime(n):
    return n > 1 and all(n % d for d in range(2, int(n ** .5) + 1))
def next_prime(n):
    n += 1
    while not is_prime(n): n += 1
    return n

def families(seq):
    """{family: next value} for each rule that fits the whole sequence."""
    out, n = {}, len(seq)
    d = [seq[i + 1] - seq[i] for i in range(n - 1)]
    if len(set(d)) == 1: out["arithmetic"] = seq[-1] + d[0]
    if all(x > 0 for x in seq) and all(seq[i + 1] % seq[i] == 0 for i in range(n - 1)):
        r = {seq[i + 1] // seq[i] for i in range(n - 1)}
        if len(r) == 1 and r != {1}: out["geometric"] = seq[-1] * r.pop()
    if n >= 3 and all(seq[i] == seq[i - 1] + seq[i - 2] for i in range(2, n)): out["fibonacci"] = seq[-1] + seq[-2]
    roots = [round(abs(x) ** .5) for x in seq]
    if all(x >= 0 for x in seq) and all(r * r == x for r, x in zip(roots, seq)) and all(roots[i + 1] - roots[i] == 1 for i in range(n - 1)):
        out["squares"] = (roots[-1] + 1) ** 2
    if all(is_prime(x) for x in seq) and all(next_prime(seq[i]) == seq[i + 1] for i in range(n - 1)):
        out["primes"] = next_prime(seq[-1])
    if n >= 4 and all(d[i] == d[i % 2] for i in range(len(d))) and d[0] != d[1]:
        out["alternating"] = seq[-1] + d[len(d) % 2]
    return out

def solve_seq(seq):
    f = families(seq)
    vals = set(f.values())
    return (list(f.values())[0] if f else None), len(vals) > 1, f

def solve_missing(tokens):
    found = {}
    for v in range(-100, 20001):
        full = [int(t) if t != "?" else v for t in tokens]
        f = families(full)
        if f: found.setdefault(v, list(f))
    return found

def solve_pattern(tokens):
    if len(tokens[0]) == 1:
        step = ord(tokens[-1]) - ord(tokens[-2])
        return chr(ord(tokens[-1]) + step)
    step_l = ord(tokens[-1][0]) - ord(tokens[-2][0]); step_n = int(tokens[-1][1:]) - int(tokens[-2][1:])
    return f"{chr(ord(tokens[-1][0]) + step_l)}{int(tokens[-1][1:]) + step_n}"

ROTS = ['^', '>', 'v', '<']
def solve_matrix(rows):
    cells = [c for r in rows for c in r]
    if all(c in ROTS or c == "?" for c in cells):
        step = (ROTS.index(cells[1]) - ROTS.index(cells[0])) % 4
        return ROTS[(ROTS.index(cells[7]) + step) % 4]
    if len(set(c for c in cells if c != "?" and len(set(c)) == 1)) == 1 and all(len(set(c)) == 1 for c in cells if c != "?"):
        return cells[7][0] * (len(cells[7]) + 1)
    return rows[2][0] + rows[2][1]

# ---------------------------------------------------------------- bot
GARBAGE = ["", "   ", "abc", "-1", "0", "99999999999999999999999999", "1e3", "3.5", "１２", "1_0", "12abc",
           "'; DROP TABLE users;--", "A" * 5000, "None", "\t", "0 0", "0,0", "9 9, 9 9", "-1 -1", "\x00", "🙂"]
KEYS = ["Y", " ", "\r", "n", "yy", None, "\x1b", "1"]

class Bot:
    def __init__(self):
        self.out = io.StringIO()
        self.reset()
        self.user = self.username = ""
        self.hist: list[str] = []
        self.results, self.crashes, self.findings = [], [], []
        self.format_log = collections.defaultdict(lambda: [0, 0])  # (game, variant) -> [accepted, rejected]
        self.amb = []  # ambiguous puzzles

    def reset(self):
        self.queue = collections.deque(); self.cur: dict[str, Any] | None = None; self.mark = 0; self.n = 0

    # -- output helpers
    def tail(self): return self.out.getvalue()[self.mark:]
    def write(self, s): self.out.write(s)
    def flush(self): pass
    def encoding(self): return "utf-8"

    # -- session lifecycle
    def begin(self, title, mode, user):
        gid, rounds = GAMES[title]
        u = app_profile[0].require_user()
        self.cur = dict(title=title, gid=gid, mode=mode, user=user, rounds=rounds, flags=[], n=0, seq=[], fmt=[],
                        diff_before=app_profile[0].difficulty(gid), level_before=u.level, xp_before=u.xp,
                        rows_before=app_profile[0].db.count_user_sessions(u.id), start=len(self.out.getvalue()),
                        cancel_at=random.randint(1, rounds - 1) if mode == "cancel" else None)
        self.mark = len(self.out.getvalue())

    def finish(self):
        c = self.cur; self.cur = None
        assert c is not None
        prof = app_profile[0]; prof.refresh(); u = prof.require_user()
        text = self.out.getvalue()[c["start"]:]
        rows = prof.db.count_user_sessions(u.id)
        rec = dict(user=c["user"], game=c["gid"], mode=c["mode"], level_before=c["level_before"], level_after=u.level,
                   xp_before=c["xp_before"], xp_after=u.xp, diff_before=c["diff_before"])
        if c["mode"] == "cancel":
            rec["saved"] = rows != c["rows_before"]
            if rec["saved"] or "Game cancelled" not in text:
                self.flag("cancel", c, f"saved={rec['saved']} cancelled_msg={'Game cancelled' in text}")
            self.results.append(rec); return
        if rows != c["rows_before"] + 1:
            self.flag("no-row", c, f"rows {c['rows_before']}->{rows}"); self.results.append(rec); return
        s = prof.db.get_user_stats(u.id, limit=1)[0]
        rec.update(score=s.score, acc=round(s.accuracy, 3), rt=round(s.reaction_time_ms), stored_diff=s.difficulty,
                   integrity=s.integrity, assisted=s.assisted)
        # cross-checks against what the game printed
        if c["gid"] == "n_back":
            flags = c["flags"]
        else:
            flags = [m.group(1) == "Correct!" for m in re.finditer(r"^(Correct!|Incorrect|Too slow)", text, re.M)]
        exp_acc = sum(flags) / len(flags) if flags else 0
        if len(flags) != c["rounds"]: self.flag("rounds", c, f"{len(flags)} trials seen, expected {c['rounds']}")
        if abs(exp_acc - s.accuracy) > 1e-9: self.flag("accuracy", c, f"stored {s.accuracy} vs seen {exp_acc}")
        if c["gid"] in STEP:
            base, inc = STEP[c["gid"]]; st = 0; sc = 0
            for f in flags:
                if f: sc += base + st * inc; st += 1
                else: st = 0
            if sc != s.score: self.flag("score", c, f"stored {s.score} vs expected {sc}")
        elif c["gid"] == "n_back":
            st = 0; sc = 0
            for f in flags:
                if f: sc += 10 + st; st += 1
                else: st = 0
            if sc != s.score: self.flag("score", c, f"stored {s.score} vs expected {sc}")
        gained = u.xp - c["xp_before"]
        if gained != xp_for(c["gid"], s.score): self.flag("xp", c, f"gained {gained} vs xp_for {xp_for(c['gid'], s.score)}")
        if u.level < c["level_before"]: self.flag("level-down", c, f"{c['level_before']}->{u.level}")
        if level_for_xp(u.xp) > u.level: self.flag("level-lag", c, f"xp {u.xp} implies {level_for_xp(u.xp)} but level {u.level}")
        if s.difficulty is not None and s.difficulty != c["diff_before"] and c["gid"] != "n_back":
            self.flag("difficulty", c, f"stored {s.difficulty} vs expected {c['diff_before']}")
        if s.difficulty is None: rec["no_difficulty"] = True
        if s.integrity not in (None, "ok", "review"): self.flag("integrity", c, s.integrity)
        rec["flags"] = "".join("1" if f else "0" for f in flags)
        rec["fmt"] = c["fmt"]
        self.results.append(rec)

    def flag(self, kind, c, msg):
        self.findings.append(dict(kind=kind, game=c["gid"], mode=c["mode"], user=c["user"], msg=msg))

    # -- answer generation
    def p_of(self, mode):
        return {"strong": .97, "avg": .72, "weak": .35, "wrong": 0.0}.get(mode, .8)

    def respond(self, prompt):
        p = prompt
        if "Enter your username" in p: return self.username
        if "Select an option" in p:
            if self.cur: self.finish()
            return self.menu_choice()
        if "Press Enter" in p: return ""
        if "[n]ext" in p or "Enter to return" in p:
            return self.hist.pop(0) if self.hist else ""
        c = self.cur
        if c is None: return "0"  # game opened by a RAW menu probe: a non-empty answer, or "re-ask on blank" loops never end
        c["n"] += 1
        if c["cancel_at"] and c["n"] == c["cancel_at"]: raise KeyboardInterrupt
        if c["mode"] == "eof" and c["n"] == 2: raise EOFError
        gid = c["gid"]; mode = c["mode"]
        advance(random.uniform(3, 12) if gid not in ("number_recall", "pattern_memory") else random.uniform(4, 15))
        if mode == "edge":
            return GARBAGE[(c["n"] + hash(gid)) % len(GARBAGE)]
        ok = random.random() < self.p_of(mode)
        t = self.tail()
        rt = t[t.rfind("Round "):]
        if gid == "seq_predict":
            toks = rt.split("\n")[0].split(":", 1)[1].replace("?", "").split()
            seq = [int(x) for x in toks]
            ans, amb, f = solve_seq(seq)
            if amb: self.amb.append((gid, seq, f))
            if ans is None: self.flag("unsolvable", c, str(seq)); return "0"
            return self.render(c, ans, ok, "num")
        if gid == "missing_num":
            toks = rt.split("\n")[0].split(":", 1)[1].split()
            found = solve_missing(toks)
            if not found: self.flag("unsolvable", c, str(toks)); return "0"
            if len(found) > 1: self.amb.append((gid, toks, found))
            return self.render(c, min(found, key=lambda v: (len(found[v]), v)), ok, "num")
        if gid == "pattern_comp":
            toks = rt.split("\n")[0].split(":", 1)[1].replace("?", "").split()
            ans = solve_pattern(toks)
            if not re.fullmatch(r"[A-Z]([0-9]+)?", ans): self.flag("bad-answer", c, f"{toks} -> {ans!r}")
            return self.render(c, ans, ok, "pat")
        if gid == "matrix":
            lines = [l for l in rt.split("\n")[1:] if l.strip()][:3]
            rows = [l.split() for l in lines]
            ans = solve_matrix(rows)
            return self.render(c, ans, ok, "mat")
        if gid == "number_recall":
            seqs = re.findall(r"^ {6}([\d-]+)$", t, re.M)
            raw = seqs[-1].replace("-", "")
            span = {"strong": 10, "avg": 8, "weak": 5, "wrong": 0}.get(mode, 7)
            pr = 1.0 if len(raw) <= span else max(0.0, 1 - (len(raw) - span) * .3)
            if mode == "strong": pr = 0.97 if len(raw) <= span else pr
            return self.render(c, raw, random.random() < pr, "rec")
        if gid == "pattern_memory":
            g = t[t.rfind("Memorize the pattern:"):]
            coords = set()
            for line in g.split("\n"):
                m = re.match(r"^  (\d) (.*)$", line)
                if m:
                    cells = re.findall(r"\[.\]", m.group(2))
                    for ci, cell in enumerate(cells):
                        if cell == "[X]": coords.add((int(m.group(1)), ci))
            return self.render(c, coords, ok, "pm")
        return ""

    def render(self, c, truth, ok, kind):
        mode = c["mode"]
        if mode == "format":
            return self.fmt_variant(c, truth, kind)
        if ok: return self.fmt_std(truth, kind)
        # plausible wrong answer
        if kind == "num": return str(truth + random.choice([-3, -1, 1, 2, 10]))
        if kind == "pat": return random.choice("ABCDEFGH") + "9"
        if kind == "mat": return random.choice(["*", "#", "<>", "^", "zz"])
        if kind == "rec":
            s = list(truth); i = random.randrange(len(s)); s[i] = str((int(s[i]) + 1) % 10); return "".join(s)
        if kind == "pm":
            r, cc = random.choice(sorted(truth)); wrong = sorted(truth - {(r, cc)}); wrong.append(((r + 1) % 3, (cc + 1) % 3))
            return ", ".join(f"{a} {b}" for a, b in wrong)

    def fmt_std(self, truth, kind):
        if kind == "pm": return ", ".join(f"{r} {c}" for r, c in sorted(truth))
        return str(truth)

    def fmt_variant(self, c, truth, kind):
        i = c["n"] - 1
        V = {
            "num": lambda: [("plus-sign", f"+{truth}"), ("thousands-comma", f"{truth:,}"), ("trailing-dot", f"{truth}."),
                    ("decimal", f"{truth}.0"), ("padded", f"  {truth}  "), ("fullwidth-digits", str(truth).translate(str.maketrans("0123456789", "０１２３４５６７８９")) if kind == "num" else str(truth))],
            "pat": lambda: [("lowercase", str(truth).lower()), ("spaced", " ".join(str(truth))), ("quoted", f"'{truth}'"), ("padded", f" {truth} ")],
            "mat": lambda: [("lowercase", str(truth).lower()), ("quoted", f"'{truth}'"), ("padded", f" {truth} "), ("with-spaces", " ".join(str(truth)))],
            "rec": lambda: [("space-groups", " ".join(truth[j:j + 3] for j in range(0, len(truth), 3))),
                    ("comma-groups", ",".join(truth[j:j + 3] for j in range(0, len(truth), 3))),
                    ("dash-groups", "-".join(truth[j:j + 3] for j in range(0, len(truth), 3))),
                    ("plain", truth), ("spaced-digits", " ".join(truth))],
            "pm": lambda: [("comma-pairs", ", ".join(f"{r},{c}" for r, c in sorted(truth))),
                   ("flat", " ".join(f"{r} {c}" for r, c in sorted(truth))),
                   ("parens", ", ".join(f"({r}, {c})" for r, c in sorted(truth))),
                   ("semicolons", "; ".join(f"{r} {c}" for r, c in sorted(truth))),
                   ("std", ", ".join(f"{r} {c}" for r, c in sorted(truth))),
                   ("row-col-dash", ", ".join(f"{r}-{c}" for r, c in sorted(truth))),
                   ("extra-space", "  " + ",  ".join(f"{r}   {c}" for r, c in sorted(truth)))],
        }[kind]()
        name, val = V[i % len(V)]
        c["fmt"].append(name); c["last_fmt"] = name
        return val

    # -- menu
    def menu_choice(self):
        t = self.tail()
        menu = t[t.rfind("MAIN MENU"):]
        nums = {m.group(2).strip(): int(m.group(1)) for m in re.finditer(r"^(\d+)\. (?:Play )?(.+)$", menu, re.M)}
        if not self.queue:
            return str(nums["Exit"])
        item = self.queue.popleft()
        if item == "STATS": choice = str(nums["View Statistics"])
        elif isinstance(item, tuple) and item[0] == "RAW": self.mark = len(self.out.getvalue()); return item[1]
        else:
            title, mode = item
            if title not in nums: self.flag("menu", dict(gid=title, mode=mode, user=self.user), "game not in menu"); return "0"
            self.begin(title, mode, self.user); choice = str(nums[title])
        self.mark = len(self.out.getvalue())
        return choice

app_profile: list[Any] = [None]
bot = Bot()

def fake_input(prompt=""):
    bot.write(str(prompt))
    r = bot.respond(str(prompt))
    bot.write(f"{r[:80]}\n")
    return r

def qc_input(prompt, timeout):
    bot.write(prompt)
    c = bot.cur
    assert c is not None
    t = bot.tail()
    q = re.findall(r"Solve: (.+)", t)[-1]
    truth = eval(q)
    c["n"] += 1
    if c["cancel_at"] and c["n"] == c["cancel_at"]: raise KeyboardInterrupt
    mode = c["mode"]
    lat = {"strong": random.uniform(.8, 2.5), "avg": random.uniform(1.5, 5), "weak": random.uniform(3, 9)}.get(mode, random.uniform(1, 5))
    if mode == "slow": lat = timeout + 1
    if lat > timeout:
        advance(timeout); bot.write("\nTime's up!\n"); return None
    advance(lat)
    if mode == "edge": r = GARBAGE[c["n"] % len(GARBAGE)]
    elif mode == "format":
        r = bot.fmt_variant(c, truth, "num")
    else:
        r = str(truth) if random.random() < bot.p_of(mode) else str(truth + random.choice([-2, -1, 1, 10]))
    bot.write(r[:80] + "\n"); return r.strip() if False else r

def nb_key(timeout):
    t = bot.tail(); c = bot.cur
    assert c is not None
    letters = re.findall(r"^ {7}([A-F]) {7}$", t, re.M)
    m = re.search(r"(\d)-Back", t)
    assert m is not None
    n = int(m.group(1))
    i = len(letters) - 1
    is_match = i >= n and letters[i] == letters[i - n]
    c["n"] += 1
    if c["cancel_at"] and c["n"] == c["cancel_at"]: raise KeyboardInterrupt
    mode = c["mode"]
    if mode == "edge":
        key = KEYS[c["n"] % len(KEYS)]
        pressed = key is not None and key.lower() == "y"
    else:
        p = bot.p_of(mode)
        pressed = is_match if random.random() < p else (not is_match)
        key = "y" if pressed else (None if random.random() < .5 else "n")
        if mode == "slow": key, pressed = None, False
    lat = random.uniform(.3, timeout * .9)
    if key is None: advance(timeout)
    else: advance(lat)
    c["flags"].append(is_match == pressed)
    return key

def run_campaign(user, plan, hist=None):
    """One main() run for `user`; plan = list of (game title, mode) / 'STATS' / ('RAW', text)."""
    bot.reset(); bot.user = user; bot.username = user; bot.hist = list(hist or [])
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
            # restart main() with the rest of the plan
            continue

def install():
    builtins.input = fake_input
    sys.stdout = bot
    for m in (m_nr, m_nb, m_pm): setattr(m, "clear_screen", lambda: None)
    m_qc.get_input_with_timeout = qc_input
    m_nb.get_single_keypress_with_timeout = nb_key
    app._ai_enabled = lambda: False
    class TDB(DBManager):
        def __init__(self, *a, **k):
            super().__init__(db_path=DB, legacy_json=None)
    def mk(*a, **k):
        d = TDB(); return d
    app.DBManager = mk
    orig = app.ProfileManager
    def PM(db):
        p = orig(db); app_profile[0] = p; return p
    app.ProfileManager = PM
    app.load_dotenv = lambda *_: None
