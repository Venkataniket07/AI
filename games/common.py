"""Helpers shared by every game module."""

from typing import Optional

from core.integrity import assess, encode_trials
from core.profile_manager import ProfileManager
from games.engine.parsing import compact_answer, letters_only, normalize_symbol, parse_int  # noqa: F401
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
