from dataclasses import dataclass
from typing import Optional
from datetime import datetime

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
