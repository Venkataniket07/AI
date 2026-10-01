import re
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

import main
from core.progression import PERFECT_SCORE
from core.scoring import difficulty_label, hinted, partial_points
from core.stats import (
    current_streak,
    display_name,
    format_history,
    format_summary_table,
    longest_streak,
    page_count,
    trend_arrow,
)
from database.models import GameSummary

TODAY = date(2026, 6, 10)


# ── streaks ──────────────────────────────────────────────────────────────────

def test_streak_counts_consecutive_days_ending_today():
    assert current_streak(["2026-06-10", "2026-06-09", "2026-06-08", "2026-06-05"], TODAY) == 3


def test_streak_survives_until_a_full_day_is_missed():
    assert current_streak(["2026-06-09", "2026-06-08"], TODAY) == 2   # played yesterday: still alive
    assert current_streak(["2026-06-08", "2026-06-07"], TODAY) == 0   # missed yesterday: reset


def test_streak_empty_and_garbage_input():
    assert current_streak([], TODAY) == 0
    assert current_streak(["not-a-date"], TODAY) == 0


def test_longest_streak():
    days = ["2026-06-10", "2026-06-09", "2026-06-04", "2026-06-03", "2026-06-02", "2026-06-01"]
    assert longest_streak(days) == 4
    assert longest_streak([]) == 0


# ── trend ────────────────────────────────────────────────────────────────────

def _summary(recent, previous, previous_plays=5):
    return GameSummary("g", 10, 100, 0.7, 500.0, recent, previous, previous_plays)


@pytest.mark.parametrize("recent,previous,arrow", [
    (0.9, 0.7, "↑"), (0.5, 0.7, "↓"), (0.72, 0.7, "→"),
])
def test_trend_arrow_direction(recent, previous, arrow):
    assert trend_arrow(_summary(recent, previous)) == arrow


def test_trend_needs_enough_previous_plays():
    assert trend_arrow(_summary(0.9, None, 0)) == "-"
    assert trend_arrow(_summary(0.9, 0.5, 2)) == "-"


# ── formatting / paging ──────────────────────────────────────────────────────

def test_display_names():
    assert display_name("seq_predict") == "Sequence Prediction"
    assert display_name("blood_relations") == "Blood Relations"


def test_page_count():
    assert [page_count(n, 20) for n in (0, 1, 20, 21, 40, 41)] == [1, 1, 1, 2, 2, 3]


def test_formatting_contains_the_numbers():
    table = format_summary_table([GameSummary("mental_math", 12, 150, 0.8, 1234.0, 0.9, 0.6, 5)])
    assert "Mental Math" in table and "12" in table and "150" in table and "80.0%" in table and "↑" in table
    row = SimpleNamespace(played_at="2026-06-10 12:34:56", game_type="n_back", score=40, accuracy=0.5,
                          reaction_time_ms=800.0)
    history = format_history([row])
    assert "2026-06-10 12:34" in history and "N-Back" in history and "50.0%" in history


def test_difficulty_label():
    assert difficulty_label(None) == "-"
    assert difficulty_label(7) == "7"


def test_partial_points():
    assert partial_points(100, 4, 6) == 67
    assert partial_points(100, 0, 6) == 0
    assert partial_points(100, 6, 6) == 100
    assert partial_points(100, 9, 6) == 100  # clamped
    assert partial_points(100, 1, 0) == 0


def test_hinted_matches_the_round_helper_penalty():
    assert hinted(25, 0) == 25
    assert hinted(25, 1) == 21
    assert hinted(100, 3) == 50
    assert hinted(100, 9) == 50  # no more than the last penalty


def _history_row(difficulty):
    return SimpleNamespace(played_at="2026-06-10 12:34:56", game_type="n_back", score=40, accuracy=0.5,
                           reaction_time_ms=800.0, difficulty=difficulty)


def test_history_shows_difficulty_and_dash_for_null_rows():
    lines = format_history([_history_row(None), _history_row(6)]).splitlines()
    assert "Diff" in lines[0]
    assert len({len(line) for line in lines}) == 1  # aligned
    assert lines[2].split("|")[2].strip() == "-" and lines[3].split("|")[2].strip() == "6"


def test_summary_table_with_and_without_difficulty():
    with_diff = format_summary_table([GameSummary("mental_math", 12, 150, 0.8, 1234.0, 0.9, 0.6, 5, 4)])
    without = format_summary_table([GameSummary("mental_math", 12, 150, 0.8, 1234.0, 0.9, 0.6, 5)])
    assert "Last diff" in with_diff and with_diff.splitlines()[2].split("|")[-2].strip() == "4"
    assert without.splitlines()[2].split("|")[-2].strip() == "-"


def test_game_summary_reports_latest_difficulty(db):
    uid = db.create_user("lee").id
    _seed(db, uid, "a", [0.5, 0.5, 0.5])
    with db._conn() as conn:
        conn.execute("UPDATE game_sessions SET difficulty = 3 WHERE played_at LIKE '2026-06-02%'")
    assert db.get_game_summaries(uid)[0].last_difficulty is None  # the newest play has no difficulty
    with db._conn() as conn:
        conn.execute("UPDATE game_sessions SET difficulty = 5 WHERE played_at LIKE '2026-06-03%'")
    assert db.get_game_summaries(uid)[0].last_difficulty == 5


# Registry titles differ from stats names for these ids; core must not import games, so the mapping lives here.
_REGISTRY_TITLE_TO_STATS_NAME = {
    "Mental Arithmetic": "Mental Math",
    "Word Anagrams": "Anagrams",
    "Quick Calculation Duel": "Quick Calculation",
    "N-Back Memory": "N-Back",
    "Ranking Puzzles": "Rankings",
}


def test_every_game_has_a_display_name_and_perfect_score():
    from games.registry import GAMES
    for game in GAMES:
        expected = _REGISTRY_TITLE_TO_STATS_NAME.get(game.title, game.title)
        assert display_name(game.game_id) == expected, game.game_id
        assert game.game_id in PERFECT_SCORE, game.game_id
    assert display_name("coding_decoding") == "Coding-Decoding"


def test_every_finish_game_id_in_source_has_a_perfect_score():
    root = Path(__file__).resolve().parent.parent / "games"
    found = set()
    for path in root.rglob("*.py"):
        for call in re.findall(r"finish_game\(([^)]*)\)", path.read_text(encoding="utf-8")):
            first_arg_onwards = call.split("score", 1)[0]
            found.update(re.findall(r'"([a-z_]+)"', first_arg_onwards))
    assert found and found <= set(PERFECT_SCORE), found - set(PERFECT_SCORE)


# ── database aggregates ──────────────────────────────────────────────────────

def _seed(db, user_id, game, accuracies, score=10):
    for i, acc in enumerate(accuracies):
        with db._conn() as conn:  # explicit timestamps so ordering is deterministic
            conn.execute(
                "INSERT INTO game_sessions (user_id, game_type, score, accuracy, reaction_time_ms, played_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, game, score + i, acc, 100.0 * (i + 1), f"2026-06-{i + 1:02d} 10:00:00"))


def test_game_summaries_aggregate_per_game(db):
    uid = db.create_user("sam").id
    _seed(db, uid, "a", [0.5] * 5 + [1.0] * 5)  # oldest 5 at 50%, newest 5 at 100%
    _seed(db, uid, "b", [0.8])
    summaries = {s.game_type: s for s in db.get_game_summaries(uid)}

    a = summaries["a"]
    assert (a.plays, a.best_score) == (10, 19)
    assert a.avg_accuracy == pytest.approx(0.75)
    assert a.recent_accuracy == pytest.approx(1.0) and a.previous_accuracy == pytest.approx(0.5)
    assert a.previous_plays == 5 and trend_arrow(a) == "↑"

    b = summaries["b"]
    assert b.plays == 1 and b.previous_accuracy is None and trend_arrow(b) == "-"
    assert [s.game_type for s in db.get_game_summaries(uid)] == ["a", "b"]  # most played first


def test_summaries_are_per_user(db):
    a, b = db.create_user("a").id, db.create_user("b").id
    _seed(db, a, "g", [1.0])
    assert db.get_game_summaries(b) == []


def test_history_paging_and_count(db):
    uid = db.create_user("pat").id
    _seed(db, uid, "g", [0.1 * i for i in range(1, 8)])
    assert db.count_user_sessions(uid) == 7
    everything = db.get_user_stats(uid)
    assert [s.id for s in db.get_user_stats(uid, limit=3)] == [s.id for s in everything[:3]]
    assert [s.id for s in db.get_user_stats(uid, limit=3, offset=3)] == [s.id for s in everything[3:6]]
    assert db.get_user_stats(uid, limit=3, offset=6) == everything[6:]
    assert everything[0].played_at > everything[-1].played_at  # newest first


def test_play_days_are_distinct_and_newest_first(db):
    uid = db.create_user("dee").id
    _seed(db, uid, "g", [0.5, 0.5, 0.5])
    with db._conn() as conn:
        conn.execute("UPDATE game_sessions SET played_at = '2026-06-03 23:00:00' WHERE played_at LIKE '2026-06-02%'")
    assert db.get_play_days(uid) == ["2026-06-03", "2026-06-01"]


# ── the screen ───────────────────────────────────────────────────────────────

def test_stats_screen_when_nothing_played(profile, monkeypatch, capsys):
    monkeypatch.setattr("builtins.input", lambda *a: "")
    main.display_stats(profile)
    assert "No games played yet" in capsys.readouterr().out


def test_stats_screen_pages_through_history(profile, monkeypatch, capsys):
    monkeypatch.setattr(main, "_ai_enabled", lambda: False)
    uid = profile.current_user.id
    _seed(profile.db, uid, "mental_math", [0.5] * 25)
    answers = iter(["n", "p", ""])  # next page, previous page, leave
    monkeypatch.setattr("builtins.input", lambda *a: next(answers))

    main.display_stats(profile)

    out = capsys.readouterr().out
    assert "Games played: 25" in out and "Mental Math" in out
    assert "page 1/2" in out and "page 2/2" in out
    assert out.count("page 1/2") == 2  # shown again after 'previous'
