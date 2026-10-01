import json, random, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import qa_harness as h

seed = int(sys.argv[1]) if len(sys.argv) > 1 else 1
random.seed(seed)
setattr(h.Bot, "isatty", lambda self: False)
real_stdout = sys.stdout
h.install()

TITLES = list(h.GAMES)

def interleave(modes, titles=TITLES):
    return [(t, m) for m in modes for t in titles]

# 1) mixed-behaviour player: every mode on every game (7 saved + 1 cancelled per game)
run = h.run_campaign
run("qa_mixed", interleave(["strong", "avg", "weak", "wrong", "edge", "format", "cancel", "strong", "slow"]) + ["STATS"],
    hist=["n", "p", "zzz", "p", "n", "n", "n", ""])
# 2) new player, average skill: does the difficulty ramp too fast?
run("qa_new", interleave(["avg"] * 6) + ["STATS"])
# 3) expert: always right
run("qa_pro", interleave(["strong"] * 6) + ["STATS"])
# 4) crash probes
run("qa_eof", [("Sequence Prediction", "eof"), ("Pattern Memory", "eof"), ("Number Recall", "eof")])
# 5) menu / auth junk
run("qa_menu", [("RAW", x) for x in ["", "abc", "0", "-1", "99", "3.5", " 3 ", "１", "1e1", "  ", "\x00", "🙂", "-0", "+2"]])
for u in ["", "   ", "  qa_mixed  ", "QA_MIXED", "a" * 300, "x'; DROP TABLE users;--", "ünï©ode", "🙂"]:
    run(u, [])

sys.stdout = real_stdout
res = h.bot.results
json.dump(dict(results=res, findings=h.bot.findings, crashes=h.bot.crashes,
               amb=[(g, str(s), str(f)) for g, s, f in h.bot.amb]), open(os.path.join(h.SCR, f"out_{seed}.json"), "w"), indent=1, default=str)
open(os.path.join(h.SCR, f"transcript_{seed}.txt"), "w", encoding="utf-8").write(h.bot.out.getvalue())
print("sessions saved:", sum(1 for r in res if "score" in r), "| cancelled:", sum(1 for r in res if r["mode"] == "cancel"))
print("findings:", len(h.bot.findings), "| crashes:", len(h.bot.crashes), "| ambiguous puzzles:", len(h.bot.amb))
