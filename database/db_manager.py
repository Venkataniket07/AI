import sqlite3
import json
import os
from datetime import datetime
from contextlib import contextmanager
from typing import List, Optional

from .models import User, GameSession

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "brain_trainer.db")
LEGACY_JSON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "brain_trainer_data.json")


class DBManager:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = os.path.abspath(db_path)
        self._init_db()
        self._migrate_from_json()

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

    def _init_db(self):
        with self._conn() as conn:
            conn.executescript("""
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
            """)

    def _migrate_from_json(self):
        """One-time migration from brain_trainer_data.json → SQLite."""
        if not os.path.exists(LEGACY_JSON):
            return
        try:
            with open(LEGACY_JSON, "r") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
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
        os.rename(LEGACY_JSON, LEGACY_JSON + ".migrated")

    # ── User CRUD ────────────────────────────────────────────────────────────

    def create_user(self, username: str) -> Optional[User]:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._conn() as conn:
            try:
                cur = conn.execute(
                    "INSERT INTO users (username, level, xp, theme_pref, created_at) VALUES (?, 1, 0, 'dark', ?)",
                    (username, now)
                )
                return User(id=cur.lastrowid, username=username, level=1, xp=0, theme_pref="dark", created_at=now)
            except sqlite3.IntegrityError:
                return None  # duplicate username

    def get_user(self, username: str) -> Optional[User]:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM users WHERE username = ? COLLATE NOCASE", (username,)).fetchone()
            return User(**dict(row)) if row else None

    def update_user_xp(self, user_id: int, xp_gained: int, new_level: int):
        with self._conn() as conn:
            conn.execute(
                "UPDATE users SET xp = xp + ?, level = ? WHERE id = ?",
                (xp_gained, new_level, user_id)
            )

    def update_user_theme(self, user_id: int, theme: str):
        with self._conn() as conn:
            conn.execute("UPDATE users SET theme_pref = ? WHERE id = ?", (theme, user_id))

    # ── Game Sessions ────────────────────────────────────────────────────────

    def save_session(self, user_id: int, game_type: str, score: int, accuracy: float, reaction_time_ms: float):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO game_sessions (user_id, game_type, score, accuracy, reaction_time_ms, played_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (user_id, game_type, score, accuracy, reaction_time_ms, now)
            )

    def get_user_stats(self, user_id: int) -> List[GameSession]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM game_sessions WHERE user_id = ? ORDER BY played_at DESC",
                (user_id,)
            ).fetchall()
            return [GameSession(**dict(r)) for r in rows]

    # ── AI Cache ─────────────────────────────────────────────────────────────

    def cache_get(self, key: str) -> Optional[str]:
        with self._conn() as conn:
            row = conn.execute(
                """SELECT value, created_at, ttl_seconds FROM ai_cache WHERE cache_key = ?""",
                (key,)
            ).fetchone()
            if not row:
                return None
            # TTL check
            created = datetime.strptime(row["created_at"], "%Y-%m-%d %H:%M:%S")
            age = (datetime.now() - created).total_seconds()
            if age > row["ttl_seconds"]:
                conn.execute("DELETE FROM ai_cache WHERE cache_key = ?", (key,))
                return None
            return row["value"]

    def cache_set(self, key: str, value: str, ttl_seconds: int = 3600):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO ai_cache (cache_key, value, created_at, ttl_seconds)
                   VALUES (?, ?, ?, ?)""",
                (key, value, now, ttl_seconds)
            )

    def cache_purge_expired(self):
        """Remove all expired cache entries. Call periodically."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._conn() as conn:
            conn.execute(
                """DELETE FROM ai_cache
                   WHERE CAST((julianday(?) - julianday(created_at)) * 86400 AS INTEGER) > ttl_seconds""",
                (now,)
            )
