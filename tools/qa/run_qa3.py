import json, random, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import qa3_harness  # noqa: F401  (patches the qa2 bot)
import qa2_harness as h

seed = int(sys.argv[1]) if len(sys.argv) > 1 else 1
random.seed(seed)
real_stdout = sys.stdout
h.install(real_network=False)

TITLES = ["Circular Seating", "Puzzle Grids (Zebra)"]
def interleave(modes, titles=TITLES):
    return [(t, m) for m in modes for t in titles]

run = h.run_campaign
run("qa_mixed", interleave(["strong", "avg", "weak", "wrong", "edge", "edge", "format", "format", "format", "format", "format", "format",
                            "format", "format", "hints", "hintfast", "fast", "expert", "cancel", "cancel", "assist", "slow"]) + ["STATS"],
    hist=["n", "p", "zzz", "p", "n", "n", "n", ""], xp=5000)
run("qa_pro", interleave(["strong"] * 6) + ["STATS"], xp=5000)
run("qa_low", interleave(["strong"] * 2) + ["STATS"])          # level 1: both games should be locked
run("qa_eof", [(t, "eof") for t in TITLES], xp=5000)

sys.stdout = real_stdout
res = h.bot.results
json.dump(dict(results=res, findings=h.bot.findings, crashes=h.bot.crashes, facts=dict(h.bot.facts),
               fmt={f"{g}|{n}": v for (g, n), v in h.bot.fmt.items()}, locked=h.bot.locked,
               samples={k: [str(x) for x in v[:400]] for k, v in h.bot.samples.items()}),
          open(os.path.join(h.SCR, f"out3_{seed}.json"), "w"), indent=1, default=str)
open(os.path.join(h.SCR, f"transcript3_{seed}.txt"), "w", encoding="utf-8").write(h.bot.out.getvalue())
print("sessions saved:", sum(1 for r in res if "score" in r), "| cancelled:", sum(1 for r in res if r["mode"] == "cancel"))
print("findings:", len(h.bot.findings), "| crashes:", len(h.bot.crashes), "| locked skips:", len(h.bot.locked))
