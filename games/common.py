"""Helpers shared by every game module."""

from typing import Optional

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
    level_before = profile.current_user.level
    xp = profile.save_game_result(game_id, score, tracker.accuracy, tracker.avg_reaction_time_ms, difficulty)
    print(f"+{xp} XP")
    if profile.current_user.level > level_before:
        print(f"🎉 Level up! You are now level {profile.current_user.level}.")
    input(f"\n{pause_prompt}")
