"""Presentation-independent statistics logic plus plain-text formatting for the stats screen."""

from datetime import date, datetime, timedelta
from typing import Optional, Sequence

from core.scoring import difficulty_label

TREND_DELTA = 0.05        # accuracy change that counts as a trend
MIN_TREND_PLAYS = 3       # plays needed before ai.context compares recent runs
TREND_MIN_PLAYS = 10      # plays of a game before the stats screen shows a trend (last 5 vs the 5 before)
TREND_PLACEHOLDER = "n/a (10 plays)"
PAGE_SIZE = 20

_DISPLAY_NAMES = {
    "mental_math": "Mental Math",
    "anagrams": "Anagrams",
    "seq_predict": "Sequence Prediction",
    "matrix": "Matrix Reasoning",
    "pattern_comp": "Pattern Completion",
    "missing_num": "Missing Number",
    "quick_calc": "Quick Calculation",
    "number_recall": "Number Recall",
    "n_back": "N-Back",
    "pattern_memory": "Pattern Memory",
    "blood_relations": "Blood Relations",
    "direction_sense": "Direction Sense",
    "coding_decoding": "Coding-Decoding",
    "rankings": "Rankings",
    "syllogisms": "Syllogisms",
    "linear_seating": "Linear Seating",
    "circular_seating": "Circular Seating",
    "puzzle_grid": "Puzzle Grids (Zebra)",
}


def display_name(game_type: str) -> str:
    return _DISPLAY_NAMES.get(game_type) or game_type.replace("_", " ").title()


def trend_arrow(summary) -> str:
    """↑ improving, ↓ declining, → steady, `n/a (10 plays)` until the game has 10 plays (last 5 vs the 5 before)."""
    if summary.plays < TREND_MIN_PLAYS or summary.previous_accuracy is None or summary.previous_plays < MIN_TREND_PLAYS:
        return TREND_PLACEHOLDER
    delta = summary.recent_accuracy - summary.previous_accuracy
    if delta > TREND_DELTA:
        return "↑"
    if delta < -TREND_DELTA:
        return "↓"
    return "→"


def _parse_days(days: Sequence[str]) -> list[date]:
    parsed = set()
    for d in days:
        try:
            parsed.add(datetime.strptime(d, "%Y-%m-%d").date())
        except ValueError:
            continue
    return sorted(parsed, reverse=True)


def current_streak(days: Sequence[str], today: Optional[date] = None) -> int:
    """
    Consecutive days played, ending today. A streak that ended yesterday still counts (the player
    can extend it today), so it only resets after a full missed day.
    """
    today = today or date.today()
    played = _parse_days(days)
    if not played or (today - played[0]).days > 1:
        return 0
    streak, expected = 0, played[0]
    for d in played:
        if d != expected:
            break
        streak += 1
        expected -= timedelta(days=1)
    return streak


def longest_streak(days: Sequence[str]) -> int:
    played = sorted(_parse_days(days))
    best = run = 0
    prev = None
    for d in played:
        run = run + 1 if prev is not None and (d - prev).days == 1 else 1
        best = max(best, run)
        prev = d
    return best


def format_summary_table(summaries: Sequence, levels: Optional[dict[str, int]] = None) -> str:
    levels = levels or {}
    header = (f"{'Game':<22} | {'Lvl':>3} | {'Plays':>5} | {'Best':>5} | {'Avg acc':>7} | {'Speed':>7} | "
              f"{'Diff':>4} | Trend")
    lines = [header, "-" * len(header)]
    for s in summaries:
        lines.append(
            f"{display_name(s.game_type):<22} | {levels.get(s.game_type, 1):>3} | {s.plays:>5} | {s.best_score:>5} | "
            f"{s.avg_accuracy * 100:>6.1f}% | {s.avg_reaction_time_ms:>5.0f}ms | "
            f"{difficulty_label(getattr(s, 'last_difficulty', None)):>4} | {trend_arrow(s)}"
        )
    return "\n".join(lines)


def format_history(sessions: Sequence) -> str:
    header = f"{'Date & Time':<16} | {'Game':<22} | {'Diff':>4} | {'Score':>5} | {'Accuracy':>8} | {'Reaction':>9}"
    lines = [header, "-" * len(header)]
    for s in sessions:
        lines.append(
            f"{s.played_at[:16]:<16} | {display_name(s.game_type):<22} | "
            f"{difficulty_label(getattr(s, 'difficulty', None)):>4} | {s.score:>5} | "
            f"{s.accuracy * 100:>7.1f}% | {s.reaction_time_ms:>7.0f}ms"
        )
    return "\n".join(lines)


def page_count(total: int, page_size: int = PAGE_SIZE) -> int:
    return max(1, -(-total // page_size))
