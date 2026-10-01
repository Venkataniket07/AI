"""
Facts and advice about a player's history, worked out in code. The AI only puts them into words.

Sessions are newest first. Nothing here touches the database or the network, so the same input always
gives the same facts and play without AI still gets advice (`template_text`).
"""

import json
import re
from dataclasses import dataclass
from enum import Enum
from statistics import median
from typing import Mapping, Optional, Sequence

from core.stats import _DISPLAY_NAMES, TREND_DELTA, TREND_MIN_PLAYS, TREND_PLACEHOLDER, display_name

MIN_RANK_PLAYS = 5  # plays of a game before it can be called strongest / weakest, or get advice
RECENT = 5  # plays averaged for a game's accuracy and trend windows
ACTION_WINDOW = 3  # latest plays that decide RAISE / HOLD / LOWER
RAISE_AT = 0.90
LOWER_AT = 0.60
SLOW_DOWN_BELOW = 0.80  # accuracy under this, while answering faster than usual, means "slow down"


class Action(Enum):
    RAISE = "raise"
    HOLD = "hold"
    LOWER = "lower"
    TRY_NEW = "try_new"
    NEED_DATA = "need_data"


@dataclass(frozen=True)
class Insight:
    strongest: Optional[str]
    weakest: Optional[str]
    accuracy: Mapping[str, float]  # average of the latest RECENT plays, per game played
    trend: Mapping[str, str]  # "up" / "down" / "steady" / TREND_PLACEHOLDER
    action: Mapping[str, Action]
    speed_target_ms: Mapping[str, Optional[int]]  # only set when the advice is to slow down


def _avg(values: Sequence[float]) -> float:
    return sum(values) / len(values)


def _by_game(sessions: Sequence) -> dict[str, list]:
    grouped: dict[str, list] = {}
    for s in sessions:
        grouped.setdefault(s.game_type, []).append(s)
    return grouped


def _correct_times(plays: Sequence) -> list[float]:
    """Times (ms) of correct answers from the stored trials; falls back to the average time of accurate plays."""
    times: list[float] = []
    for s in plays[:RECENT]:
        try:
            trials = json.loads(getattr(s, "trial_data", None) or "[]")
            times += [float(t[0]) for t in trials if t[1]]
        except (ValueError, TypeError, IndexError):
            continue
    if times:
        return times
    return [s.reaction_time_ms for s in plays[:RECENT] if s.accuracy >= SLOW_DOWN_BELOW]


def _action(plays: Sequence) -> Action:
    if not plays:
        return Action.TRY_NEW
    if len(plays) < MIN_RANK_PLAYS:
        return Action.NEED_DATA
    acc = _avg([s.accuracy for s in plays[:ACTION_WINDOW]])
    if acc >= RAISE_AT:
        return Action.RAISE
    if acc <= LOWER_AT:
        return Action.LOWER
    return Action.HOLD


def _trend(plays: Sequence) -> str:
    if len(plays) < TREND_MIN_PLAYS:
        return TREND_PLACEHOLDER
    delta = _avg([s.accuracy for s in plays[:RECENT]]) - _avg([s.accuracy for s in plays[RECENT : 2 * RECENT]])
    if delta > TREND_DELTA:
        return "up"
    if delta < -TREND_DELTA:
        return "down"
    return "steady"


def _speed_target(plays: Sequence) -> Optional[int]:
    """The median correct-answer time, but only when the player is rushing (inaccurate and quicker than it)."""
    if len(plays) < MIN_RANK_PLAYS:
        return None
    current = plays[0].reaction_time_ms
    if plays[0].accuracy >= SLOW_DOWN_BELOW:
        return None
    times = _correct_times(plays)
    if not times:
        return None
    target = median(times)
    return round(target) if current < target else None  # never a target quicker than the current time


def compute_insights(sessions: Sequence, all_games: Sequence[str] = ()) -> Insight:
    """`all_games` (optional) lists every game id, so games with no plays get `TRY_NEW`."""
    grouped = _by_game(sessions)
    accuracy = {g: _avg([s.accuracy for s in p[:RECENT]]) for g, p in grouped.items()}
    action = {g: _action(p) for g, p in grouped.items()}
    for g in all_games:
        action.setdefault(g, Action.TRY_NEW)

    ranked = sorted((accuracy[g], g) for g, p in grouped.items() if len(p) >= MIN_RANK_PLAYS)
    strongest = weakest = None
    if len(ranked) >= 2 and ranked[-1][0] - ranked[0][0] >= TREND_DELTA:
        weakest, strongest = ranked[0][1], ranked[-1][1]

    return Insight(
        strongest=strongest,
        weakest=weakest,
        accuracy=accuracy,
        trend={g: _trend(p) for g, p in grouped.items()},
        action=action,
        speed_target_ms={g: _speed_target(p) for g, p in grouped.items()},
    )


_ADVICE = {
    Action.RAISE: "raise the difficulty",
    Action.HOLD: "hold the difficulty where it is",
    Action.LOWER: "lower the difficulty",
}


def advice_phrase(insight: Insight, game: str) -> str:
    """The app's verdict for one game, worded the way the prompts and the offline text state it."""
    act = insight.action.get(game)
    if act is Action.TRY_NEW:
        return "not played yet, so suggest trying it"
    if act is Action.NEED_DATA or act is None:
        return f"too few plays to judge (needs {MIN_RANK_PLAYS})"
    text = _ADVICE[act]
    target = insight.speed_target_ms.get(game)
    if target:
        text += f"; slow down to about {target / 1000:.0f} seconds per question"
    return text


def _game_sentence(insight: Insight, game: str) -> str:
    name = display_name(game)
    act = insight.action.get(game)
    if act is Action.TRY_NEW:
        return f"You haven't played {name} yet, so try it."
    if act is Action.NEED_DATA or act is None:
        return f"{name}: play it a few more times (at least {MIN_RANK_PLAYS}) before the app can judge your level."
    text = f"{name}: accuracy {insight.accuracy[game] * 100:.0f}% recently, so {_ADVICE[act]}."
    target = insight.speed_target_ms.get(game)
    if target:
        text += f" Slow down to about {target / 1000:.0f} seconds per question."
    return text


def template_text(insight: Insight, game: Optional[str] = None) -> str:
    """An offline sentence or two built only from the facts."""
    if game is not None:
        return _game_sentence(insight, game)
    parts = []
    if insight.strongest and insight.weakest:
        parts.append(
            f"Best recent accuracy: {display_name(insight.strongest)} "
            f"({insight.accuracy[insight.strongest] * 100:.0f}%); lowest: {display_name(insight.weakest)} "
            f"({insight.accuracy[insight.weakest] * 100:.0f}%)."
        )
    else:
        parts.append(f"No best or worst game is named until two games have {MIN_RANK_PLAYS} plays and differ clearly.")
    parts += [_game_sentence(insight, g) for g in sorted(insight.action, key=display_name)]
    return " ".join(parts)


_ACTION_WORDS = {
    Action.RAISE: re.compile(r"\b(raise|increase|harder|step up|level up)\b", re.I),
    Action.LOWER: re.compile(r"\b(lower|reduce|easier|decrease)\b", re.I),
    Action.HOLD: re.compile(r"\b(hold|stay at|keep the difficulty)\b", re.I),
}
_FORBIDDEN = {
    Action.RAISE: (Action.LOWER, Action.HOLD),
    Action.LOWER: (Action.RAISE, Action.HOLD),
    Action.HOLD: (Action.RAISE, Action.LOWER),
    Action.NEED_DATA: (Action.RAISE, Action.LOWER, Action.HOLD),
    Action.TRY_NEW: (Action.RAISE, Action.LOWER, Action.HOLD),
}


def _mentioned(sentence: str, games: Sequence[str]) -> list[str]:
    low = sentence.lower()
    return [g for g in games if display_name(g).lower() in low]


def text_consistent(text: str, insight: Insight) -> bool:
    """False if the text names a game missing from the facts, or advises against the computed action."""
    facts = set(insight.action) | set(insight.accuracy)
    low = text.lower()
    for game in _DISPLAY_NAMES:
        if game not in facts and display_name(game).lower() in low:
            return False

    for sentence in re.split(r"(?<=[.!?])\s+", text):
        games = _mentioned(sentence, sorted(facts))
        if not games and len(facts) == 1:
            games = list(facts)  # one game in the facts: every sentence is about it
        for game in games:
            action = insight.action.get(game)
            for forbidden in _FORBIDDEN.get(action, ()) if action is not None else ():
                if _ACTION_WORDS[forbidden].search(sentence):
                    return False
        if "strongest" in sentence.lower() and (
            insight.strongest is None or any(g != insight.strongest for g in games)
        ):
            return False
        if "weakest" in sentence.lower() and (insight.weakest is None or any(g != insight.weakest for g in games)):
            return False
    return True
