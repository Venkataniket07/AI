import json, random, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import qa2_harness as h

seed = int(sys.argv[1]) if len(sys.argv) > 1 else 1
real = len(sys.argv) > 2 and sys.argv[2] == "real"
random.seed(seed)
real_stdout = sys.stdout
h.install(real_network=real)

TITLES = list(h.GAMES)
def interleave(modes, titles=TITLES):
    return [(t, m) for m in modes for t in titles]

run = h.run_campaign
if real:
    # real word service: anagrams only, several difficulty bands
    run("qa_net", [("Word Anagrams", m) for m in ["strong"] * 4 + ["avg", "format", "hints", "assist", "cancel", "strong"]] + ["STATS"], xp=900)
else:
    # mixed player at level 4 (all level-gated games open)
    run("qa_mixed", interleave(["strong", "avg", "weak", "wrong", "edge", "format", "format", "format", "format", "format", "hints", "hintfast", "fast", "expert", "cancel", "assist", "slow"]) + ["STATS"],
        hist=["n", "p", "zzz", "p", "n", "n", "n", ""], xp=600)
    # new player, average skill: does difficulty follow?
    run("qa_new", interleave(["avg"] * 6) + ["STATS"])
    # expert: always right, natural unlock order
    run("qa_pro", interleave(["strong"] * 7) + ["STATS"])
    # crash probes
    run("qa_eof", [(t, "eof") for t in TITLES], xp=600)

sys.stdout = real_stdout
res = h.bot.results
tag = f"{seed}{'r' if real else ''}"
json.dump(dict(results=res, findings=h.bot.findings, crashes=h.bot.crashes, facts=dict(h.bot.facts),
               fmt={f"{g}|{n}": v for (g, n), v in h.bot.fmt.items()},
               amb=[(g, s, [list(x) for x in hy]) for g, s, hy in h.bot.amb], locked=h.bot.locked,
               samples={k: [str(x) for x in v[:400]] for k, v in h.bot.samples.items()}),
          open(os.path.join(h.SCR, f"out2_{tag}.json"), "w"), indent=1, default=str)
open(os.path.join(h.SCR, f"transcript2_{tag}.txt"), "w", encoding="utf-8").write(h.bot.out.getvalue())
print("sessions saved:", sum(1 for r in res if "score" in r), "| cancelled:", sum(1 for r in res if r["mode"] == "cancel"))
print("findings:", len(h.bot.findings), "| crashes:", len(h.bot.crashes), "| ambiguous puzzles:", len(h.bot.amb), "| locked skips:", len(h.bot.locked))
