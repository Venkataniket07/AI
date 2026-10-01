# QA bot harnesses

Bots that play the real `main()` loop against a throwaway database, solve each puzzle with their own solver and
check the game's verdicts, scores, XP, hints, explanations and integrity flags. They are scripts, not tests:
pytest ignores `tools/` and ruff skips E/F/W/I here.

| Harness | Run | Covers |
|---|---|---|
| `qa_harness.py` | `python tools/qa/run_qa.py <seed>` | games 1-10 including the memory games |
| `qa2_harness.py` | `python tools/qa/run_qa2.py <seed> [real]` | Mental Arithmetic, Word Anagrams, games 11-16 |
| `qa3_harness.py` | `python tools/qa/run_qa3.py <seed>` | Circular Seating (17), Puzzle Grids (18); reuses the qa2 bot |

Run from the repo root. `<seed>` defaults to 1; the same seed replays the same session. The network is off by
default (no AI calls); `real` in `run_qa2.py` switches on the real-input path for that harness.

## Output
Everything goes to `%TEMP%/brain_trainer_qa/` (never the repo's `brain_trainer.db`):
`qa.db`/`qa2.db` (throwaway DBs, recreated each run), `out*_<seed>.json` (structured findings) and
`transcript*_<seed>.txt` (full console text).

## Reading the result
Lines starting `FAIL` are defects in the game (or the bot); `AMBIGUOUS` entries in the JSON are puzzles with more
than one valid answer. A clean run prints no `FAIL` lines. Check the transcript around any FAIL for the puzzle text.
