import json
import sqlite3
import time

from database.db_manager import MIGRATIONS, DBManager


def test_fresh_db_is_at_latest_version(db):
    assert db.schema_version() == len(MIGRATIONS)


def test_unversioned_legacy_db_is_upgraded_and_keeps_data(tmp_path):
    path = str(tmp_path / "old.db")
    conn = sqlite3.connect(path)
    conn.executescript(MIGRATIONS[0])  # pre-versioning schema, user_version == 0
    conn.execute("INSERT INTO users (username, created_at) VALUES ('old', '2024-01-01 00:00:00')")
    conn.commit()
    conn.close()

    db = DBManager(path, legacy_json=None)
    assert db.schema_version() == len(MIGRATIONS)
    old = db.get_user("OLD")
    assert old is not None and old.username == "old"


def test_reopening_does_not_reapply_migrations(tmp_path):
    path = str(tmp_path / "t.db")
    first = DBManager(path, legacy_json=None)
    first.cache_set("k", "v", 60)
    assert DBManager(path, legacy_json=None).cache_get("k") == "v"  # v3 would have dropped it


def test_user_crud_is_case_insensitive(db):
    user = db.create_user("Alice")
    assert db.get_user("alice").id == user.id
    assert db.create_user("ALICE") is None


def test_sessions_are_saved_and_listed(db):
    user = db.create_user("bob")
    db.save_session(user.id, "a", 10, 1.0, 100)
    db.save_session(user.id, "b", 20, 0.5, 200)
    stats = db.get_user_stats(user.id)
    assert {s.game_type for s in stats} == {"a", "b"}
    assert len(stats) == 2


def test_count_sessions_excludes_assisted(db):
    user = db.create_user("carol")
    db.save_session(user.id, "a", 10, 1.0, 100)
    db.save_session(user.id, "a", 10, 1.0, 100, assisted=True)
    db.save_session(user.id, "b", 10, 1.0, 100)
    assert db.count_sessions(user.id, "a") == 1
    assert db.count_sessions(user.id, "a", include_assisted=True) == 2
    assert db.count_sessions(user.id, "never") == 0


def test_cache_hit_expiry_and_purge(db):
    db.cache_set("live", "1", 60)
    db.cache_set("dead", "2", -1)
    assert db.cache_get("live") == "1"
    assert db.cache_get("dead") is None
    db.cache_set("dead2", "3", -1)
    db.cache_purge_expired()
    with db._conn() as conn:
        keys = {r["cache_key"] for r in conn.execute("SELECT cache_key FROM ai_cache")}
    assert keys == {"live"}


def test_cache_expiry_uses_ttl(db):
    db.cache_set("k", "v", 1)
    assert db.cache_get("k") == "v"
    time.sleep(1.1)
    assert db.cache_get("k") is None


def test_legacy_json_migrated_once(tmp_path):
    legacy = tmp_path / "legacy.json"
    legacy.write_text(json.dumps({
        "users": [{"id": 1, "username": "zed", "level": 2, "xp": 150}],
        "game_sessions": [{"id": 1, "user_id": 1, "game_type": "g", "score": 5, "accuracy": 1.0,
                           "reaction_time_ms": 10, "played_at": "2024-01-01 00:00:00"}],
    }))
    db = DBManager(str(tmp_path / "t.db"), legacy_json=str(legacy))
    zed = db.get_user("zed")
    assert zed is not None and zed.xp == 150
    assert len(db.get_user_stats(1)) == 1
    assert not legacy.exists() and (tmp_path / "legacy.json.migrated").exists()
