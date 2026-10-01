from typing import Optional

from dataclasses import dataclass

@dataclass
class User:
    id: int
    username: str
    level: int
    xp: int
    theme_pref: str
    created_at: str

@dataclass
class GameSession:
    id: int
    user_id: int
    game_type: str
    score: int
    accuracy: float
    reaction_time_ms: float
    played_at: str
    difficulty: Optional[int] = None  # None for sessions saved before difficulty was recorded
    integrity: Optional[str] = None   # shadow-mode verdict: 'ok', 'review' or None (not judged)
    assisted: int = 0                 # 1 when the player declared outside help
    trial_data: Optional[str] = None  # per-question timings as JSON


@dataclass
class GameSummary:
    """Aggregate of one user's sessions of one game."""
    game_type: str
    plays: int
    best_score: int
    avg_accuracy: float
    avg_reaction_time_ms: float
    recent_accuracy: float            # average of the latest `window` plays
    previous_accuracy: Optional[float]  # average of the `window` plays before those
    previous_plays: int
    last_difficulty: Optional[int] = None  # difficulty of the latest play; None for sessions saved without it


@dataclass
class GameProgress:
    """One user's XP and session count in one game (the game's level is derived from the XP)."""
    game_id: str
    xp: int
    sessions: int
