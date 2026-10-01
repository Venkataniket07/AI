from types import SimpleNamespace

import pytest

from core.difficulty import (
    MAX_DIFFICULTY, adjustment_for_accuracy, band_of, base_difficulty, difficulty_for, session_cap,
)
from core.progression import (
    PERFECT_SCORE, XP_FOR_PERFECT, Overall, format_header, game_level, level_for_xp, overall, xp_for, xp_to_reach,
)
from games.common import finish_game
from utils.performance_tracker import PerformanceTracker


def sessions(*accuracies):
    return [SimpleNamespace(accuracy=a) for a in accuracies]


# ── difficulty ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("accuracy,expected", [
    (1.0, 2), (0.95, 2), (0.9, 1), (0.85, 1), (0.7, 0), (0.55, 0), (0.5, -1), (0.35, -1), (0.2, -2), (0.0, -2),
])
def test_accuracy_bands(accuracy, expected):
    assert adjustment_for_accuracy(accuracy) == expected


def test_base_difficulty_rises_more_slowly_than_the_level():
    assert [base_difficulty(level) for level in range(1, 11)] == [1, 1, 2, 3, 3, 4, 5, 5, 6, 7]
    assert base_difficulty(0) == 1


def test_not_enough_history_uses_the_base_for_the_level():
    assert difficulty_for([], 4, sessions_played=0) == 1
    assert difficulty_for(sessions(1.0), 4, sessions_played=10) == 3


def test_strong_and_weak_players_move_in_opposite_directions():
    assert difficulty_for(sessions(1.0, 1.0, 0.9), 3, 10) == 4
    assert difficulty_for(sessions(0.1, 0.2, 0.3), 5, 10) == 1


def test_difficulty_never_drops_below_one():
    assert difficulty_for(sessions(0.0, 0.0), 1, 10) == 1


def test_only_the_most_recent_window_counts():
    recent_bad_old_good = sessions(0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 1.0)
    assert difficulty_for(recent_bad_old_good, 7, 10) == 3  # base 5, -2: the good games fall outside the window


def test_profile_difficulty_reads_that_games_history(profile):
    uid = profile.current_user.id
    for _ in range(3):
        profile.db.save_session(uid, "mental_math", 100, 1.0, 100)
        profile.db.save_session(uid, "n_back", 0, 0.0, 100)
    assert profile.difficulty("mental_math") == 3   # level 1 + 2
    assert profile.difficulty("n_back") == 1        # floor
    assert profile.difficulty("never_played") == 1  # level


def test_difficulty_is_capped():
    assert difficulty_for([], 25, sessions_played=20) == MAX_DIFFICULTY
    assert difficulty_for(sessions(1.0, 1.0), 10, sessions_played=2) == min(9, session_cap(2)) == 3
    assert difficulty_for(sessions(1.0, 1.0), 10, sessions_played=10) == 9  # base 7 + 2


@pytest.mark.parametrize("level", range(1, 26))
def test_new_game_starts_at_start_level(level):
    assert difficulty_for([], level, sessions_played=0) == 1


def test_cap_rises_one_per_session():
    for n in range(13):
        assert difficulty_for(sessions(1.0, 1.0), 25, n) == min(n + 1, 10)


def test_cap_never_raises_above_level_based_value():
    for recent in ([], sessions(1.0, 1.0), sessions(0.0, 0.0)):
        old = max(1, min(10, base_difficulty(1) + (adjustment_for_accuracy(sum(s.accuracy for s in recent) / 2)
                                                   if len(recent) >= 2 else 0)))
        assert difficulty_for(recent, 1, sessions_played=20) == old


def test_band_of():
    assert [band_of(n) for n in (0, 1, 3, 4, 6, 7, 10, 99)] == [
        "easy", "easy", "easy", "medium", "medium", "hard", "hard", "hard"]


def test_profile_difficulty_uses_session_count(profile):
    profile.db.add_game_progress(profile.current_user.id, "mental_math", xp_to_reach(7), sessions=0)  # game level 7
    assert profile.difficulty("mental_math") == 1
    for _ in range(3):
        profile.db.save_session(profile.current_user.id, "mental_math", 100, 1.0, 100)
    assert profile.difficulty("mental_math") == 4


# ── level curve ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("xp,level", [(0, 1), (99, 1), (100, 2), (299, 2), (300, 3), (599, 3), (600, 4), (4499, 9), (4500, 10)])
def test_level_curve(xp, level):
    assert level_for_xp(xp) == level


def test_each_level_costs_more_than_the_last():
    costs = [xp_to_reach(n + 1) - xp_to_reach(n) for n in range(1, 12)]
    assert costs == sorted(costs) and len(set(costs)) == len(costs)


# ── XP normalisation ─────────────────────────────────────────────────────────

def test_perfect_run_of_any_game_is_worth_the_same_xp():
    assert {xp_for(g, s) for g, s in PERFECT_SCORE.items()} == {XP_FOR_PERFECT}


def test_partial_scores_scale_and_are_capped():
    assert xp_for("mental_math", 95) == 50
    assert xp_for("mental_math", 0) == 0
    assert xp_for("quick_calc", 10_000) == XP_FOR_PERFECT  # e.g. an unexpected speed bonus


def test_unknown_game_earns_raw_score():
    assert xp_for("mystery_game", 37) == 37
    assert xp_for("mystery_game", -5) == 0


def test_every_registered_save_id_has_a_reference_score():
    """Guards against adding a game and forgetting to give it an XP reference."""
    import pathlib
    import re
    ids = set()
    for path in pathlib.Path("games").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        ids |= set(re.findall(r'(?:finish_game|save_game_result)\(profile, "(\w+)"', text))
        ids |= set(re.findall(r'GameSpec\(\s+game_id="(\w+)"', text))  # games saved through play_rounds
    assert len(ids) >= 15  # the pattern found the games' save calls
    assert ids <= set(PERFECT_SCORE)
    assert {"linear_seating", "circular_seating"} <= set(PERFECT_SCORE)  # saved via a conditional expression


def test_save_game_result_uses_normalised_xp_but_stores_raw_score(profile):
    xp = profile.save_game_result("mental_math", 95, 1.0, 100.0).xp
    assert xp == 50 and profile.current_user.xp == 50
    assert profile.db.get_user_stats(profile.current_user.id)[0].score == 95


def test_finish_game_reports_xp_and_level_up(profile, monkeypatch, capsys):
    monkeypatch.setattr("builtins.input", lambda *a: "")
    tracker = PerformanceTracker()
    tracker.start_trial()
    tracker.end_trial(True)
    finish_game(profile, "direction_sense", 100, tracker)
    out = capsys.readouterr().out
    assert "+100 XP" in out and "Level up" in out and profile.current_user.level == 2


def test_finish_game_prompt_has_one_blank_line(profile, monkeypatch, capsys):
    prompts = []
    monkeypatch.setattr("builtins.input", lambda p="": prompts.append(p) or "")
    tracker = PerformanceTracker()
    tracker.start_trial()
    tracker.end_trial(True)
    finish_game(profile, "direction_sense", 10, tracker, "\nPress Enter to go on...")
    assert prompts == ["\nPress Enter to go on..."]


# ── params_for contract helper ───────────────────────────────────────────────

def test_params_contract_helper_accepts_good_and_rejects_bad():
    import dataclasses

    from tests.helpers import assert_params_contract

    @dataclasses.dataclass(frozen=True)
    class Good:
        size: int

    @dataclasses.dataclass
    class NotFrozen:
        size: int

    def good(level):
        return Good(max(1, min(10, level)))

    assert_params_contract(good, monotone_fields=["size"])
    with pytest.raises(AssertionError):
        assert_params_contract(lambda level: NotFrozen(max(1, min(10, level))))
    with pytest.raises(AssertionError):  # does not clamp
        assert_params_contract(lambda level: Good(level))
    with pytest.raises(AssertionError):  # shrinks
        assert_params_contract(lambda level: Good(11 - max(1, min(10, level))), monotone_fields=["size"])


# ── per-game progression ─────────────────────────────────────────────────────

def test_backfill_totals_equal_old_totals(tmp_path):
    import sqlite3

    from database.db_manager import MIGRATIONS, DBManager

    path = str(tmp_path / "old.db")
    conn = sqlite3.connect(path)
    for script in MIGRATIONS[:5]:  # the schema before game_progress existed
        conn.executescript(script)
    conn.execute("INSERT INTO users (username, xp, created_at) VALUES ('old', 0, '2024-01-01 00:00:00')")
    rows = [("mental_math", 95, 0), ("mental_math", 190, 0), ("mental_math", 190, 1), ("n_back", 145, 0),
            ("anagrams", 95, 0), ("mystery", 37, 0)]
    for game, score, assisted in rows:
        conn.execute("INSERT INTO game_sessions (user_id, game_type, score, accuracy, reaction_time_ms, played_at, "
                     "assisted) VALUES (1, ?, ?, 1.0, 1.0, '2024-01-01 00:00:00', ?)", (game, score, assisted))
    old_total = sum(xp_for(g, s) for g, s, a in rows if not a)
    conn.execute("UPDATE users SET xp = ?", (old_total,))
    conn.execute("PRAGMA user_version = 5")
    conn.commit()
    conn.close()

    db = DBManager(path, legacy_json=None)
    progress = {p.game_id: p for p in db.get_game_progress(1)}
    old_user = db.get_user("old")
    assert old_user is not None
    assert sum(p.xp for p in progress.values()) == old_total == old_user.xp
    assert (progress["mental_math"].xp, progress["mental_math"].sessions) == (150, 3)  # 50 + 100, assisted counts as a session
    assert progress["mystery"].xp == 37


def test_unplayed_games_never_lower_overall_level():
    played = [SimpleNamespace(xp=700)]
    assert overall(played + [SimpleNamespace(xp=0)] * 15).level == overall(played).level == 4


def test_overall_xp_monotonic():
    xp = [0, 0, 0]
    last = overall([SimpleNamespace(xp=x) for x in xp])
    for i in range(30):
        xp[i % 3] += 37
        now = overall([SimpleNamespace(xp=x) for x in xp])
        assert now.xp > last.xp and now.level >= last.level
        last = now


def test_overall_splits_xp_into_level_progress():
    assert overall([SimpleNamespace(xp=150), SimpleNamespace(xp=50)]) == Overall(level=2, xp=200, into_level=100, needed=200)
    assert overall([]) == Overall(level=1, xp=0, into_level=0, needed=100)


def test_game_level_uses_the_overall_curve():
    assert [game_level(x) for x in (0, 99, 100, 300)] == [1, 1, 2, 3]


def test_new_game_difficulty_is_1_whatever_other_games_xp(profile):
    profile.save_game_result("direction_sense", 100, 1.0, 1.0)
    profile.db.add_game_progress(profile.current_user.id, "mental_math", 5000, sessions=0)
    assert profile.overall().level > 5
    assert profile.difficulty("n_back") == 1
    assert profile.difficulty("quick_calc") == 1


def test_game_and_overall_levels_come_from_per_game_rows(profile):
    first = profile.save_game_result("direction_sense", 100, 1.0, 1.0)
    assert (first.game_level, first.game_leveled_up, first.overall_leveled_up) == (2, True, True)
    second = profile.save_game_result("n_back", 145, 1.0, 1.0)
    assert (second.game_leveled_up, second.overall_level) == (True, 2)
    assert profile.game_levels() == {"direction_sense": 2, "n_back": 2}
    assert profile.require_user().xp == profile.overall().xp == 200  # users.xp is a cache of the sum


def test_assisted_game_counts_a_session_but_no_xp(profile):
    profile.save_game_result("mental_math", 190, 1.0, 1.0, assisted=True)
    [row] = profile.db.get_game_progress(profile.current_user.id)
    assert (row.xp, row.sessions) == (0, 1)


def test_header_string_format():
    assert format_header("kim", overall([SimpleNamespace(xp=150)])) == "User: kim (Player Level 2 | XP 50/200)"
    assert format_header("kim", overall([])) == "User: kim (Player Level 1 | XP 0/100)"


def test_xp_for_defined_for_all_18_ids():
    from games.registry import GAMES

    ids = {g.game_id for g in GAMES}
    assert len(ids) == 18 and ids == set(PERFECT_SCORE)
    for game_id, perfect in PERFECT_SCORE.items():
        assert xp_for(game_id, perfect) == XP_FOR_PERFECT
        assert xp_for(game_id, 0) == 0
        assert xp_for(game_id, perfect // 2) == round(perfect // 2 / perfect * XP_FOR_PERFECT)


def test_xp_for_ignores_accuracy_and_difficulty_for_now():
    # golden values: the old two-argument results, which are what existing sessions were credited with
    golden = {("mental_math", 95): 50, ("quick_calc", 120): 50, ("n_back", 145): 100, ("anagrams", 60): 63,
              ("linear_seating", 99): 100, ("blood_relations", 75): 75, ("mystery", 37): 37}
    for (game_id, score), xp in golden.items():
        assert xp_for(game_id, score) == xp
        assert xp_for(game_id, score, 0.3, 9) == xp
