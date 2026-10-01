import sqlite3
import json
import os
import time
from datetime import datetime
from contextlib import contextmanager
from typing import List, Optional

from .models import GameSession, GameSummary, User
from utils.logger import get_app_logger

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "brain_trainer.db")
LEGACY_JSON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "brain_trainer_data.json")


# Ordered schema migrations; index + 1 is the schema version stored in PRAGMA user_version.
# Every script is idempotent, so a database created before versioning existed upgrades cleanly.
MIGRATIONS = [
    # v1: baseline schema
    """
    CREATE TABLE IF NOT EXISTS users (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        username    TEXT    NOT NULL UNIQUE COLLATE NOCASE,
        level       INTEGER NOT NULL DEFAULT 1,
        xp          INTEGER NOT NULL DEFAULT 0,
        theme_pref  TEXT    NOT NULL DEFAULT 'dark',
        created_at  TEXT    NOT NULL
    );
    CREATE TABLE IF NOT EXISTS game_sessions (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id          INTEGER NOT NULL REFERENCES users(id),
        game_type        TEXT    NOT NULL,
        score            INTEGER NOT NULL,
        accuracy         REAL    NOT NULL,
        reaction_time_ms REAL    NOT NULL,
        played_at        TEXT    NOT NULL
    );
    CREATE TABLE IF NOT EXISTS ai_cache (
        cache_key   TEXT    PRIMARY KEY,
        value       TEXT    NOT NULL,
        created_at  TEXT    NOT NULL,
        ttl_seconds INTEGER NOT NULL DEFAULT 3600
    );
    CREATE INDEX IF NOT EXISTS idx_sessions_user ON game_sessions(user_id);
    """,
    # v2: history queries filter by user and sort by time
    """
    CREATE INDEX IF NOT EXISTS idx_sessions_user_played ON game_sessions(user_id, played_at DESC);
    DROP INDEX IF EXISTS idx_sessions_user;
    """,
    # v3: cache expiry stored as an epoch timestamp (no local-time string parsing).
    # The cache only holds regenerable AI output, so the old table is dropped.
    """
    DROP TABLE IF EXISTS ai_cache;
    CREATE TABLE ai_cache (
        cache_key  TEXT PRIMARY KEY,
        value      TEXT NOT NULL,
        expires_at REAL NOT NULL
    );
    CREATE INDEX idx_ai_cache_expires ON ai_cache(expires_at);
    """,
    # v4: the difficulty a game was played at (NULL for sessions saved before this was recorded)
    """
    ALTER TABLE game_sessions ADD COLUMN difficulty INTEGER;
    """,
    # v5: integrity data. `integrity` is the shadow-mode verdict ('ok' / 'review', NULL when not judged),
    # `assisted` is the player's own declaration, `trial_data` the per-question timings as JSON.
    """
    ALTER TABLE game_sessions ADD COLUMN integrity TEXT;
    ALTER TABLE game_sessions ADD COLUMN assisted INTEGER NOT NULL DEFAULT 0;
    ALTER TABLE game_sessions ADD COLUMN trial_data TEXT;
    """,
]


class DBManager:
    def __init__(self, db_path: str = DB_PATH, legacy_json: Optional[str] = LEGACY_JSON):
        self.logger = get_app_logger()
        self.db_path = os.path.abspath(db_path)
        self.legacy_json = legacy_json
        self.logger.info("Initializing DBManager with database path: %s", self.db_path)
        self._init_db()
        self._migrate_from_json()
        self.cache_purge_expired()

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def schema_version(self) -> int:
        with self._conn() as conn:
            return conn.execute("PRAGMA user_version").fetchone()[0]

    def _init_db(self):
        """Apply any schema migrations newer than the database's user_version."""
        current = self.schema_version()
        for version, script in enumerate(MIGRATIONS, 1):
            if version <= current:
                continue
            self.logger.info("Applying database migration v%d", version)
            with self._conn() as conn:
                conn.executescript(script)
                conn.execute(f"PRAGMA user_version = {version}")

    def _migrate_from_json(self):
        """One-time migration from brain_trainer_data.json → SQLite."""
        if not self.legacy_json or not os.path.exists(self.legacy_json):
            return
        self.logger.info("Legacy JSON file found. Starting migration to SQLite database.")
        try:
            with open(self.legacy_json, "r") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            self.logger.error("Failed to read legacy JSON for migration: %s", str(e))
            return

        with self._conn() as conn:
            for u in data.get("users", []):
                conn.execute(
                    """INSERT OR IGNORE INTO users (id, username, level, xp, theme_pref, created_at)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (u["id"], u["username"], u.get("level", 1), u.get("xp", 0),
                     u.get("theme_pref", "dark"), u.get("created_at", datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                )
            for s in data.get("game_sessions", []):
                conn.execute(
                    """INSERT OR IGNORE INTO game_sessions
                       (id, user_id, game_type, score, accuracy, reaction_time_ms, played_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (s["id"], s["user_id"], s["game_type"], s["score"],
                     s["accuracy"], s["reaction_time_ms"], s["played_at"])
                )

        # Rename legacy file so migration only runs once
        try:
            os.rename(self.legacy_json, self.legacy_json + ".migrated")
            self.logger.info("Successfully completed legacy JSON data migration.")
        except OSError as e:
            self.logger.error("Failed to rename legacy JSON file after migration: %s", str(e))

    # ── User CRUD ────────────────────────────────────────────────────────────

    def create_user(self, username: str) -> Optional[User]:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._conn() as conn:
            try:
                cur = conn.execute(
                    "INSERT INTO users (username, level, xp, theme_pref, created_at) VALUES (?, 1, 0, 'dark', ?)",
                    (username, now)
                )
                self.logger.info("Successfully created new user: %s (id: %d)", username, cur.lastrowid)
                if cur.lastrowid is None:
                    return None
                return User(id=cur.lastrowid, username=username, level=1, xp=0, theme_pref="dark", created_at=now)
            except sqlite3.IntegrityError:
                self.logger.warning("Attempted to create duplicate username: %s", username)
                return None  # duplicate username

    def get_user(self, username: str) -> Optional[User]:
        self.logger.debug("Database fetch user request: %s", username)
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM users WHERE username = ? COLLATE NOCASE", (username,)).fetchone()
            return User(**dict(row)) if row else None

    def update_user_xp(self, user_id: int, xp_gained: int, new_level: int):
        self.logger.debug("Updating database user %d: XP gained %d, Level set to %d", user_id, xp_gained, new_level)
        with self._conn() as conn:
            conn.execute(
                "UPDATE users SET xp = xp + ?, level = ? WHERE id = ?",
                (xp_gained, new_level, user_id)
            )

    def update_user_theme(self, user_id: int, theme: str):
        self.logger.debug("Updating database user %d theme preference to: %s", user_id, theme)
        with self._conn() as conn:
            conn.execute("UPDATE users SET theme_pref = ? WHERE id = ?", (theme, user_id))

    # ── Game Sessions ────────────────────────────────────────────────────────

    def save_session(self, user_id: int, game_type: str, score: int, accuracy: float, reaction_time_ms: float,
                     difficulty: Optional[int] = None, integrity: Optional[str] = None,
                     assisted: bool = False, trial_data: Optional[str] = None):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.logger.info("Saving session for user %d: game_type=%s, score=%d, accuracy=%.2f, reaction_time=%dms, "
                         "difficulty=%s, integrity=%s, assisted=%s", user_id, game_type, score, accuracy,
                         int(reaction_time_ms), difficulty, integrity, assisted)
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO game_sessions
                   (user_id, game_type, score, accuracy, reaction_time_ms, played_at, difficulty,
                    integrity, assisted, trial_data)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (user_id, game_type, score, accuracy, reaction_time_ms, now, difficulty,
                 integrity, int(assisted), trial_data)
            )

    def get_user_stats(self, user_id: int, limit: Optional[int] = None, offset: int = 0,
                       include_assisted: bool = True) -> List[GameSession]:
        """The user's sessions, newest first. `limit`/`offset` page through the history.

        `include_assisted=False` leaves out games the player declared as outside-assisted (used for AI feedback).
        """
        self.logger.debug("Retrieving stats for user ID: %d (limit=%s, offset=%d)", user_id, limit, offset)
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM game_sessions WHERE user_id = ? AND (? OR assisted = 0) "
                "ORDER BY played_at DESC, id DESC LIMIT ? OFFSET ?",
                (user_id, include_assisted, -1 if limit is None else limit, offset)  # SQLite: LIMIT -1 means no limit
            ).fetchall()
            return [GameSession(**dict(r)) for r in rows]

    def count_user_sessions(self, user_id: int) -> int:
        with self._conn() as conn:
            return conn.execute("SELECT COUNT(*) FROM game_sessions WHERE user_id = ?", (user_id,)).fetchone()[0]

    def get_game_summaries(self, user_id: int, window: int = 5) -> List[GameSummary]:
        """Per-game aggregates (plays, best score, averages) plus recent-vs-previous accuracy for trends."""
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT game_type,
                       COUNT(*)                                               AS plays,
                       MAX(score)                                             AS best_score,
                       AVG(accuracy)                                          AS avg_accuracy,
                       AVG(reaction_time_ms)                                  AS avg_rt,
                       AVG(CASE WHEN rn <= :w THEN accuracy END)              AS recent_acc,
                       AVG(CASE WHEN rn > :w AND rn <= 2 * :w THEN accuracy END) AS prev_acc,
                       COUNT(CASE WHEN rn > :w AND rn <= 2 * :w THEN 1 END)   AS prev_n
                FROM (
                    SELECT *, ROW_NUMBER() OVER (
                        PARTITION BY game_type ORDER BY played_at DESC, id DESC) AS rn
                    FROM game_sessions WHERE user_id = :uid
                )
                GROUP BY game_type
                ORDER BY plays DESC, game_type
                """,
                {"uid": user_id, "w": window}
            ).fetchall()
        return [GameSummary(r["game_type"], r["plays"], r["best_score"], r["avg_accuracy"], r["avg_rt"],
                            r["recent_acc"], r["prev_acc"], r["prev_n"]) for r in rows]

    def get_play_days(self, user_id: int) -> List[str]:
        """Distinct calendar days (YYYY-MM-DD) on which the user played, newest first."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT DISTINCT substr(played_at, 1, 10) AS day FROM game_sessions "
                "WHERE user_id = ? ORDER BY day DESC", (user_id,)
            ).fetchall()
            return [r["day"] for r in rows]

    def get_recent_sessions(self, user_id: int, game_type: str, limit: int) -> List[GameSession]:
        """The user's most recent unassisted sessions of one game, newest first (these set the difficulty)."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM game_sessions WHERE user_id = ? AND game_type = ? AND assisted = 0 "
                "ORDER BY played_at DESC, id DESC LIMIT ?",
                (user_id, game_type, limit)
            ).fetchall()
            return [GameSession(**dict(r)) for r in rows]

    def count_sessions(self, user_id: int, game_type: str, include_assisted: bool = False) -> int:
        """How many sessions of one game the user has played (assisted ones only if asked)."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM game_sessions WHERE user_id = ? AND game_type = ? AND (? OR assisted = 0)",
                (user_id, game_type, int(include_assisted))
            ).fetchone()
            return row[0]

    # ── AI Cache ─────────────────────────────────────────────────────────────

    def cache_get(self, key: str) -> Optional[str]:
        self.logger.debug("AI Cache request key: %s", key)
        with self._conn() as conn:
            row = conn.execute(
                "SELECT value, expires_at FROM ai_cache WHERE cache_key = ?", (key,)
            ).fetchone()
            if not row:
                self.logger.debug("AI Cache miss: %s", key)
                return None
            if row["expires_at"] <= time.time():
                self.logger.debug("AI Cache key expired: %s", key)
                conn.execute("DELETE FROM ai_cache WHERE cache_key = ?", (key,))
                return None
            self.logger.debug("AI Cache hit: %s", key)
            return row["value"]

    def cache_set(self, key: str, value: str, ttl_seconds: int = 3600):
        self.logger.debug("AI Cache set key: %s (TTL=%d)", key, ttl_seconds)
        with self._conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO ai_cache (cache_key, value, expires_at) VALUES (?, ?, ?)",
                (key, value, time.time() + ttl_seconds)
            )

    def cache_purge_expired(self):
        """Remove all expired cache entries (runs at startup)."""
        with self._conn() as conn:
            cur = conn.execute("DELETE FROM ai_cache WHERE expires_at <= ?", (time.time(),))
            self.logger.debug("Purged %d expired AI cache entries.", cur.rowcount)
