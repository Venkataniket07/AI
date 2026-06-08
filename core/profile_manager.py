from database.db_manager import DBManager
from database.models import User
from typing import Optional

class ProfileManager:
    XP_PER_LEVEL = 100

    def __init__(self, db_manager: DBManager):
        self.db = db_manager
        self.current_user: Optional[User] = None

    def login(self, username: str) -> bool:
        user = self.db.get_user(username)
        if not user:
            user = self.db.create_user(username)
        self.current_user = user
        return self.current_user is not None

    def add_xp(self, amount: int):
        if not self.current_user:
            return
        
        new_xp = self.current_user.xp + amount
        new_level = max(1, (new_xp // self.XP_PER_LEVEL) + 1)
        
        self.db.update_user_xp(self.current_user.id, amount, new_level)
        self.current_user.xp = new_xp
        self.current_user.level = new_level
        
    def save_game_result(self, game_type: str, score: int, accuracy: float, reaction_time_ms: float):
        if not self.current_user:
            return
        self.db.save_session(self.current_user.id, game_type, score, accuracy, reaction_time_ms)
        self.add_xp(score)  # 1 score = 1 xp
        
    def set_theme_pref(self, theme: str):
        if not self.current_user:
            return
        self.db.update_user_theme(self.current_user.id, theme)
        self.current_user.theme_pref = theme
