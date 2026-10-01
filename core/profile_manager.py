from core.difficulty import WINDOW, difficulty_for
from core.progression import Overall, game_level, level_for_xp, overall, xp_for
from database.db_manager import DBManager
from database.models import User
from dataclasses import dataclass
from typing import Callable, Optional
from utils.logger import get_app_logger

@dataclass(frozen=True)
class GameResult:
    """What saving one game result did: the XP earned and the game's and the player's levels before and after."""
    xp: int
    game_level_before: int
    game_level: int
    overall_level_before: int
    overall_level: int

    @property
    def game_leveled_up(self) -> bool:
        return self.game_level > self.game_level_before

    @property
    def overall_leveled_up(self) -> bool:
        return self.overall_level > self.overall_level_before


class ProfileManager:
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
        if user:
            self.logger.info("User '%s' login succeeded (Level: %d, XP: %d)", username, user.level, user.xp)
        else:
            self.logger.error("User '%s' login failed", username)
        return self.current_user is not None

    def require_user(self) -> User:
        """The logged-in user; raises if nobody is logged in (a programming error, not a user error)."""
        if self.current_user is None:
            raise RuntimeError("No user is logged in.")
        return self.current_user

    def refresh(self) -> Optional[User]:
        """Reload the current user's level/XP from the database."""
        if self.current_user:
            self.current_user = self.db.get_user(self.current_user.username) or self.current_user
        return self.current_user

    def game_xp(self, game_id: str) -> int:
        """XP the current user has earned in one game (0 if never played)."""
        if not self.current_user:
            return 0
        return next((p.xp for p in self.db.get_game_progress(self.current_user.id) if p.game_id == game_id), 0)

    def game_levels(self) -> dict[str, int]:
        """The current user's level in every game they have played."""
        if not self.current_user:
            return {}
        return {p.game_id: game_level(p.xp) for p in self.db.get_game_progress(self.current_user.id)}

    def overall(self) -> Overall:
        """Overall level and XP, summed over the per-game rows."""
        return overall(self.db.get_game_progress(self.current_user.id) if self.current_user else [])

    def difficulty(self, game_type: str) -> int:
        """Difficulty for `game_type`: that game's own level adjusted by recent accuracy, capped by sessions played."""
        if not self.current_user:
            return 1
        recent = self.db.get_recent_sessions(self.current_user.id, game_type, WINDOW)
        played = self.db.count_sessions(self.current_user.id, game_type)
        return difficulty_for(recent, game_level(self.game_xp(game_type)), played)

    def add_xp(self, amount: int):
        if not self.current_user:
            self.logger.warning("Attempted to add XP but no user is currently logged in.")
            return
        
        old_level = self.current_user.level
        new_xp = self.current_user.xp + amount
        # Never lower a level the player already has (older versions levelled up every 100 XP).
        new_level = max(old_level, level_for_xp(new_xp))
        
        self.logger.info("Adding %d XP to user '%s'. XP: %d -> %d",
                         amount, self.current_user.username, self.current_user.xp, new_xp)
        self.db.update_user_xp(self.current_user.id, amount, new_level)
        self.current_user.xp = new_xp
        self.current_user.level = new_level
        
        if new_level > old_level:
            self.logger.info("User '%s' leveled up! Level %d -> %d",
                             self.current_user.username, old_level, new_level)
        
    def save_game_result(self, game_type: str, score: int, accuracy: float, reaction_time_ms: float,
                         difficulty: Optional[int] = None, integrity: Optional[str] = None,
                         assisted: bool = False, trial_data: Optional[str] = None) -> GameResult:
        """Store the session and award normalised XP (none if assisted) to the game and the player."""
        if not self.current_user:
            self.logger.warning("Attempted to save game result but no user is logged in.")
            return GameResult(0, 1, 1, 1, 1)
        self.logger.info("Saving game result for '%s': game_type='%s', score=%d",
                         self.current_user.username, game_type, score)
        game_xp_before = self.game_xp(game_type)
        overall_before = self.overall().level
        self.db.save_session(self.current_user.id, game_type, score, accuracy, reaction_time_ms, difficulty,
                             integrity, assisted, trial_data)
        xp = 0 if assisted else xp_for(game_type, score)
        self.db.add_game_progress(self.current_user.id, game_type, xp)
        self.add_xp(xp)  # users.xp / users.level stay a cache of the per-game sum
        result = GameResult(xp, game_level(game_xp_before), game_level(game_xp_before + xp),
                            overall_before, self.overall().level)
        if self.on_result:
            try:
                self.on_result()
            except Exception:
                self.logger.error("on_result hook failed.", exc_info=True)
        return result
        
    def set_theme_pref(self, theme: str):
        if not self.current_user:
            self.logger.warning("Attempted to set theme preference but no user is logged in.")
            return
        self.logger.info("Setting theme preference for '%s' to '%s'", self.current_user.username, theme)
        self.db.update_user_theme(self.current_user.id, theme)
        self.current_user.theme_pref = theme
