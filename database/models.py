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
