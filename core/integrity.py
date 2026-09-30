"""Spotting games that were probably not played unaided.

This runs in shadow mode: the verdict is stored with the session (so thresholds can be tuned against real
play) but nothing in the game reacts to it. Only a player's own "/ai" declaration (assisted) changes anything.

The check is deliberately narrow. A correct, hint-free answer given faster than a person could read the
question and type the reply is a strong sign the answer was already known or pasted in. Slow answers are
not flagged: a hard puzzle can honestly take a long time.
"""

import json
from typing import Optional, Sequence

REVIEW = "review"
OK = "ok"

MIN_FAST_TRIALS = 2      # this many implausibly fast correct answers ...
MIN_FAST_SHARE = 0.4     # ... or this share of all trials


def answer_floor_ms(answer: str, question: str = "") -> int:
    """The fastest a person could read `question`, type `answer` and press Enter (a deliberately low bound).

    Reading is 15 ms per character (~800 words a minute); typing is 150 ms per character plus 400 ms to react.
    """
    return 400 + 150 * len(answer) + 15 * len(question)


def implausibly_fast(trial_log: Sequence) -> int:
    """Number of correct, hint-free trials answered quicker than the game's minimum plausible time."""
    return sum(1 for ms, correct, hints, floor in trial_log
               if correct and hints == 0 and floor is not None and ms < floor)


def assess(trial_log: Sequence) -> Optional[str]:
    """`OK`, `REVIEW`, or None when the game gave no timing floors (nothing to judge)."""
    if not trial_log or all(t[3] is None for t in trial_log):
        return None
    fast = implausibly_fast(trial_log)
    if fast >= MIN_FAST_TRIALS or fast >= MIN_FAST_SHARE * len(trial_log):
        return REVIEW
    return OK


def encode_trials(trial_log: Sequence) -> str:
    """Compact JSON for storage: [[elapsed_ms, correct(0/1), hints, floor_ms|null], ...]."""
    return json.dumps([[ms, int(correct), hints, floor] for ms, correct, hints, floor in trial_log],
                      separators=(",", ":"))
