import json
import os
from datetime import datetime
from .models import User, GameSession
from typing import List, Optional

class DBManager:
    def __init__(self, db_path: str = "brain_trainer_data.json"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        if not os.path.exists(self.db_path):
            self._write_raw({"users": [], "game_sessions": []})

    def _read_raw(self) -> dict:
        try:
            with open(self.db_path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {"users": [], "game_sessions": []}

    def _write_raw(self, data: dict):
        with open(self.db_path, "w") as f:
            json.dump(data, f, indent=4)

    def create_user(self, username: str) -> Optional[User]:
        data = self._read_raw()
        # Check if user already exists
        for u in data["users"]:
            if u["username"].lower() == username.lower():
                return None
        
        new_id = max([u["id"] for u in data["users"]], default=0) + 1
        new_user = {
            "id": new_id,
            "username": username,
            "level": 1,
            "xp": 0,
            "theme_pref": "dark",
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        data["users"].append(new_user)
        self._write_raw(data)
        return User(**new_user)

    def get_user(self, username: str) -> Optional[User]:
        data = self._read_raw()
        for u in data["users"]:
            if u["username"].lower() == username.lower():
                return User(**u)
        return None

    def update_user_xp(self, user_id: int, xp_gained: int, new_level: int):
        data = self._read_raw()
        for u in data["users"]:
            if u["id"] == user_id:
                u["xp"] += xp_gained
                u["level"] = new_level
                break
        self._write_raw(data)
            
    def update_user_theme(self, user_id: int, theme: str):
        data = self._read_raw()
        for u in data["users"]:
            if u["id"] == user_id:
                u["theme_pref"] = theme
                break
        self._write_raw(data)

    def save_session(self, user_id: int, game_type: str, score: int, accuracy: float, reaction_time_ms: float):
        data = self._read_raw()
        new_id = max([s["id"] for s in data["game_sessions"]], default=0) + 1
        new_session = {
            "id": new_id,
            "user_id": user_id,
            "game_type": game_type,
            "score": score,
            "accuracy": accuracy,
            "reaction_time_ms": reaction_time_ms,
            "played_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        data["game_sessions"].append(new_session)
        self._write_raw(data)
            
    def get_user_stats(self, user_id: int) -> List[GameSession]:
        data = self._read_raw()
        sessions = []
        for s in data["game_sessions"]:
            if s["user_id"] == user_id:
                sessions.append(GameSession(**s))
        # Sort by played_at descending
        sessions.sort(key=lambda x: x.played_at, reverse=True)
        return sessions
