import json
import sqlite3

from core.integrity import OK, REVIEW, assess, encode_trials
from database.db_manager import DBManager
from games.language import anagrams
from utils.performance_tracker import PerformanceTracker


def trial(ms, correct=True, hints=0, floor=2000):
    return (ms, correct, hints, floor)


def test_no_floor_means_not_judged():
    assert assess([]) is None
    assert assess([(500, True, 0, None)]) is None


def test_normal_play_is_ok():
    assert assess([trial(9000), trial(30000), trial(1500), trial(12000, False), trial(8000)]) == OK


def test_one_quick_answer_is_not_enough():
    assert assess([trial(500)] + [trial(9000)] * 4) == OK


def test_two_implausibly_fast_correct_answers_are_reviewed():
    assert assess([trial(500), trial(700)] + [trial(9000)] * 3) == REVIEW


def test_fast_wrong_or_hinted_answers_do_not_count():
    assert assess([trial(300, correct=False), trial(300, hints=1)] + [trial(9000)] * 3) == OK


def test_slow_perfect_play_is_never_flagged():
    assert assess([trial(120_000)] * 5) == OK


def test_encoding_round_trips():
    assert json.loads(encode_trials([trial(1234, True, 1, 2000)])) == [[1234, 1, 1, 2000]]


def test_floor_grows_with_word_length():
    assert anagrams.min_plausible_ms("abcd") < anagrams.min_plausible_ms("abcdefghij")


def test_v5_migration_adds_columns_and_keeps_rows(tmp_path):
    path = tmp_path / "old.db"
    conn = sqlite3.connect(path)
    for script in __import__("database.db_manager", fromlist=["MIGRATIONS"]).MIGRATIONS[:4]:
        conn.executescript(script)
    conn.execute("PRAGMA user_version = 4")
    conn.execute("INSERT INTO users (username, created_at) VALUES ('a', 'now')")
    conn.execute("INSERT INTO game_sessions (user_id, game_type, score, accuracy, reaction_time_ms, played_at) "
                 "VALUES (1, 'g', 1, 1.0, 1.0, 'now')")
    conn.commit()
    conn.close()
    db = DBManager(str(path), legacy_json=None)
    s = db.get_user_stats(1)[0]
    assert (s.integrity, s.assisted, s.trial_data) == (None, 0, None)


def test_session_stores_integrity_fields(db, profile):
    profile.save_game_result("g", 10, 1.0, 1.0, 3, integrity="review", trial_data="[]")
    s = db.get_user_stats(profile.current_user.id)[0]
    assert (s.integrity, s.assisted, s.trial_data) == ("review", 0, "[]")


def test_assisted_game_earns_no_xp_and_is_ignored_for_difficulty(profile):
    uid = profile.current_user.id
    assert profile.save_game_result("mental_math", 190, 1.0, 1.0, assisted=True) == 0
    assert profile.current_user.xp == 0
    for _ in range(3):
        profile.db.save_session(uid, "mental_math", 190, 1.0, 1.0, assisted=True)
    assert profile.difficulty("mental_math") == 1  # assisted wins do not raise it


def test_tracker_logs_each_trial():
    t = PerformanceTracker()
    t.start_trial()
    t.end_trial(True, hints_used=2, min_plausible_ms=1500)
    ms, correct, hints, floor = t.trial_log[0]
    assert (correct, hints, floor) == (True, 2, 1500) and ms >= 0


def test_ai_feedback_can_leave_out_assisted_sessions(profile):
    uid = profile.current_user.id
    profile.db.save_session(uid, "mental_math", 10, 0.5, 1.0)
    profile.db.save_session(uid, "mental_math", 190, 1.0, 1.0, assisted=True)
    profile.db.save_session(uid, "mental_math", 20, 0.6, 1.0)
    assert [s.assisted for s in profile.db.get_user_stats(uid)] == [0, 1, 0]
    assert [s.score for s in profile.db.get_user_stats(uid, include_assisted=False)] == [20, 10]
    assert [s.score for s in profile.db.get_user_stats(uid, limit=1, include_assisted=False)] == [20]


def test_coaching_ignores_assisted_games(profile, monkeypatch):
    import ai.background
    import main
    seen = []
    monkeypatch.setattr(main, "_ai_enabled", lambda: True)
    monkeypatch.setattr(ai.background, "submit", lambda fn, *a: seen.append(a[2]) or "pending")
    coach = main.CoachingPrefetcher(profile)
    uid = profile.current_user.id

    profile.db.save_session(uid, "mental_math", 10, 0.5, 1.0)
    profile.db.save_session(uid, "mental_math", 190, 1.0, 1.0, assisted=True)
    coach.start()
    assert coach.pending is None and seen == []      # the game just played was assisted: no coaching

    profile.db.save_session(uid, "mental_math", 20, 0.6, 1.0)
    coach.start()
    assert [s.score for s in seen[0]] == [20, 10]    # the earlier assisted game is not in the history
