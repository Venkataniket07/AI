"""Helpers shared by every game module."""

import re
from typing import Optional

from core.integrity import assess, encode_trials
from core.profile_manager import ProfileManager
from utils.performance_tracker import PerformanceTracker


def finish_game(
    profile: ProfileManager,
    game_id: str,
    score: int,
    tracker: PerformanceTracker,
    pause_prompt: str = "Press Enter to return...",
    difficulty: Optional[int] = None,
) -> None:
    """Persist the result (score, accuracy, reaction time), report the XP earned and wait for the player."""
    profile.require_user()
    result = profile.save_game_result(
        game_id, score, tracker.accuracy, tracker.avg_reaction_time_ms, difficulty,
        integrity=assess(tracker.trial_log), assisted=tracker.assisted, trial_data=encode_trials(tracker.trial_log))
    if tracker.assisted:
        print("Assisted game: saved, but it earns no XP and does not change your difficulty.")
    else:
        print(f"+{result.xp} XP")
    if result.game_leveled_up:
        print(f"🎉 Level up! You are now level {result.game_level} in this game.")
    if result.overall_leveled_up:
        print(f"🎉 Level up! You are now Player Level {result.overall_level}.")
    input(f"\n{pause_prompt.lstrip()}")  # some callers still pass a leading newline of their own


_INT_RE = re.compile(r"[+-]?\d+(\.0*)?")


def parse_int(text: str) -> Optional[int]:
    """A whole number typed the way people write one ("12", "+5", "1,024", "12.", "12.0"), else None."""
    t = text.strip().replace(",", "")
    if t.endswith(".") and len(t) > 1:
        t = t[:-1]
    if not _INT_RE.fullmatch(t):
        return None
    return int(t.split(".")[0])


def letters_only(text: str) -> str:
    """An arrangement typed as "ABCDE", "A B C D E", "A,B,C,D,E" or "A>B>C>D>E", as "ABCDE"."""
    return re.sub(r"[^A-Za-z]", "", text).upper()


def compact_answer(text: str) -> str:
    """Answer text without spaces, commas, dashes, dots and quote marks, in one case."""
    return re.sub(r"[\s,\-.'\"`]", "", text).upper()


def normalize_symbol(text: str) -> str:
    """Answer text without spaces and quote marks, in one case, so "'b 3'" matches "B3"."""
    return re.sub(r"[\s'\"`]", "", text).upper()
