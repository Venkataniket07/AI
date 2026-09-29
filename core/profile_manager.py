from core.difficulty import WINDOW, difficulty_for
from core.progression import xp_for
from database.db_manager import DBManager
from database.models import User
from typing import Callable, Optional
from utils.logger import get_app_logger

class ProfileManager:
    XP_PER_LEVEL = 100

    def __init__(self, db_manager: DBManager):
        self.db = db_manager
        self.current_user: Optional[User] = None
        # Called after every saved game result (used to prefetch AI coaching in the background).
        self.on_result: Optional[Callable[[], None]] = None
        self.logger = get_app_logger()
        self.logger.info("ProfileManager initialized.")

    def login(self, username: str) -> bool:
        self.logger.info("Processing profile login for user: %s", username)
        user = self.db.get_user(username)
        if not user:
            user = self.db.create_user(username)
        self.current_user = user
        if self.current_user:
            self.logger.info("User '%s' login succeeded (Level: %d, XP: %d)", username, user.level, user.xp)
        else:
            self.logger.error("User '%s' login failed", username)
        return self.current_user is not None

    def refresh(self) -> Optional[User]:
        """Reload the current user's level/XP from the database."""
        if self.current_user:
            self.current_user = self.db.get_user(self.current_user.username) or self.current_user
        return self.current_user

    def difficulty(self, game_type: str) -> int:
        """Difficulty for `game_type`: the player's level adjusted by recent accuracy in that game."""
        if not self.current_user:
            return 1
        recent = self.db.get_recent_sessions(self.current_user.id, game_type, WINDOW)
        return difficulty_for(recent, self.current_user.level)

    def add_xp(self, amount: int):
        if not self.current_user:
            self.logger.warning("Attempted to add XP but no user is currently logged in.")
            return
        
        old_level = self.current_user.level
        new_xp = self.current_user.xp + amount
        new_level = max(1, (new_xp // self.XP_PER_LEVEL) + 1)
        
        self.logger.info("Adding %d XP to user '%s'. XP: %d -> %d",
                         amount, self.current_user.username, self.current_user.xp, new_xp)
        self.db.update_user_xp(self.current_user.id, amount, new_level)
        self.current_user.xp = new_xp
        self.current_user.level = new_level
        
        if new_level > old_level:
            self.logger.info("User '%s' leveled up! Level %d -> %d",
                             self.current_user.username, old_level, new_level)
        
    def save_game_result(self, game_type: str, score: int, accuracy: float, reaction_time_ms: float) -> int:
        """Store the session and award normalised XP. Returns the XP gained."""
        if not self.current_user:
            self.logger.warning("Attempted to save game result but no user is logged in.")
            return 0
        self.logger.info("Saving game result for '%s': game_type='%s', score=%d",
                         self.current_user.username, game_type, score)
        self.db.save_session(self.current_user.id, game_type, score, accuracy, reaction_time_ms)
        xp = xp_for(game_type, score)
        self.add_xp(xp)
        if self.on_result:
            try:
                self.on_result()
            except Exception:
                self.logger.error("on_result hook failed.", exc_info=True)
        return xp
        
    def set_theme_pref(self, theme: str):
        if not self.current_user:
            self.logger.warning("Attempted to set theme preference but no user is logged in.")
            return
        self.logger.info("Setting theme preference for '%s' to '%s'", self.current_user.username, theme)
        self.db.update_user_theme(self.current_user.id, theme)
        self.current_user.theme_pref = theme
