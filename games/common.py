"""Helpers shared by every game module."""

from core.profile_manager import ProfileManager
from utils.performance_tracker import PerformanceTracker


def finish_game(
    profile: ProfileManager,
    game_id: str,
    score: int,
    tracker: PerformanceTracker,
    pause_prompt: str = "Press Enter to return...",
) -> None:
    """Persist the result (score, accuracy, reaction time) and wait for the player."""
    profile.save_game_result(game_id, score, tracker.accuracy, tracker.avg_reaction_time_ms)
    input(f"\n{pause_prompt}")
