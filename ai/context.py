"""
Facts about a player's history, worked out in code and handed to the AI to put into words.

The model never has to compute a trend, pick a baseline or compare speeds across games: small free
models get those wrong, and a speed in milliseconds means different things in different games.
Sessions are always newest first.
"""

from typing import Sequence

from core.insights import advice_phrase, compute_insights
from core.stats import MIN_TREND_PLAYS, TREND_DELTA, display_name

RECENT = 5                 # plays per window when comparing recent with earlier results
SPEED_DELTA = 0.10         # relative speed change that counts as faster / slower
_OTHER_GAMES_SHOWN = 3


def _avg(values: Sequence[float]) -> float:
    return sum(values) / len(values)


def _pct(x: float) -> str:
    return f"{x * 100:.0f}%"


def _seconds(ms: float) -> str:
    return f"{ms / 1000:.1f}s"


def _accuracy_change(now: float, before: float) -> str:
    delta = now - before
    if delta > TREND_DELTA:
        return f"up {abs(delta) * 100:.0f} points"
    if delta < -TREND_DELTA:
        return f"down {abs(delta) * 100:.0f} points"
    return "about the same"


def _speed_change(now_ms: float, before_ms: float) -> str:
    if before_ms <= 0:
        return "about the same"
    change = (now_ms - before_ms) / before_ms
    if change < -SPEED_DELTA:
        return f"faster by {abs(change) * 100:.0f}%"
    if change > SPEED_DELTA:
        return f"slower by {change * 100:.0f}%"
    return "about the same"


def _difficulties(sessions: Sequence) -> list[int]:
    return [s.difficulty for s in sessions if getattr(s, "difficulty", None) is not None]


def latest_game_facts(sessions: Sequence) -> str:
    """Facts about the most recent game, compared with the player's earlier plays of the same game."""
    latest = sessions[0]
    earlier = [s for s in sessions[1:] if s.game_type == latest.game_type][:RECENT]

    result = f"{_pct(latest.accuracy)} correct"
    if getattr(latest, "difficulty", None) is not None:
        result += f" at difficulty {latest.difficulty}"
    lines = [f"Game: {display_name(latest.game_type)}",
             f"Result: {result}",
             f"Speed: {_seconds(latest.reaction_time_ms)} per question"]

    if not earlier:
        lines.append("History: this is their first recorded play of this game.")
    else:
        avg_acc = _avg([s.accuracy for s in earlier])
        lines.append(f"Accuracy compared with their previous {len(earlier)} plays of this game "
                     f"(average {_pct(avg_acc)}): {_accuracy_change(latest.accuracy, avg_acc)}")
        avg_ms = _avg([s.reaction_time_ms for s in earlier])
        lines.append(f"Speed compared with those plays (average {_seconds(avg_ms)}): "
                     f"{_speed_change(latest.reaction_time_ms, avg_ms)}")
        before = _difficulties(earlier)
        if getattr(latest, "difficulty", None) is not None and before:
            prev = before[0]
            if latest.difficulty > prev:
                lines.append(f"Difficulty: rose from {prev} to {latest.difficulty}")
            elif latest.difficulty < prev:
                lines.append(f"Difficulty: fell from {prev} to {latest.difficulty}")
            else:
                lines.append(f"Difficulty: unchanged at {latest.difficulty}")
        if len(earlier) >= MIN_TREND_PLAYS and latest.score > max(s.score for s in earlier):
            lines.append("Score: a new personal best in this game")

    insight = compute_insights([latest] + [s for s in sessions[1:] if s.game_type == latest.game_type])
    lines.append(f"Advice (worked out by the app; state it as given): {advice_phrase(insight, latest.game_type)}")

    others = []
    for s in sessions[1:]:
        name = display_name(s.game_type)
        if s.game_type != latest.game_type and all(name != o[0] for o in others):
            others.append((name, s.accuracy))
        if len(others) == _OTHER_GAMES_SHOWN:
            break
    if others:
        lines.append("Other games played recently: " + ", ".join(f"{n} ({_pct(a)})" for n, a in others))
    return "\n".join(lines)


def _by_game(sessions: Sequence) -> dict[str, list]:
    grouped: dict[str, list] = {}
    for s in sessions:
        grouped.setdefault(s.game_type, []).append(s)
    return grouped


def game_history_facts(sessions: Sequence) -> str:
    """One block per game: recent accuracy and speed against the player's earlier results in that game."""
    if not sessions:
        return "No games played yet."
    insight = compute_insights(sessions)
    lines = []
    games = sorted(_by_game(sessions).items(), key=lambda kv: (-len(kv[1]), kv[0]))
    for game_type, plays in games:
        recent, previous = plays[:RECENT], plays[RECENT:2 * RECENT]
        acc = _avg([s.accuracy for s in recent])
        parts = [f"{len(plays)} plays", f"recent accuracy {_pct(acc)}"]
        if len(previous) >= MIN_TREND_PLAYS:
            prev_acc = _avg([s.accuracy for s in previous])
            parts.append(f"accuracy vs the {len(previous)} plays before: {_accuracy_change(acc, prev_acc)}")
            ms, prev_ms = _avg([s.reaction_time_ms for s in recent]), _avg([s.reaction_time_ms for s in previous])
            parts.append(f"speed {_seconds(ms)} per question, {_speed_change(ms, prev_ms)}")
        else:
            parts.append("too few earlier plays to show a trend")
        levels = _difficulties(plays)
        if levels:
            parts.append(f"latest difficulty {levels[0]} (highest so far {max(levels)})")
        parts.append(f"advice: {advice_phrase(insight, game_type)}")
        lines.append(f"- {display_name(game_type)}: " + "; ".join(parts))

    if insight.strongest and insight.weakest:
        lines.append(f"Highest recent accuracy: {display_name(insight.strongest)} "
                     f"({_pct(insight.accuracy[insight.strongest])}). "
                     f"Lowest: {display_name(insight.weakest)} ({_pct(insight.accuracy[insight.weakest])}).")
    return "\n".join(lines)
