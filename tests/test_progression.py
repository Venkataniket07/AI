from types import SimpleNamespace

import pytest

from core.difficulty import MAX_DIFFICULTY, adjustment_for_accuracy, difficulty_for
from core.progression import PERFECT_SCORE, XP_FOR_PERFECT, level_for_xp, xp_for, xp_to_reach
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


def test_not_enough_history_uses_level():
    assert difficulty_for([], 4) == 4
    assert difficulty_for(sessions(1.0), 4) == 4


def test_strong_and_weak_players_move_in_opposite_directions():
    assert difficulty_for(sessions(1.0, 1.0, 0.9), 3) == 5
    assert difficulty_for(sessions(0.1, 0.2, 0.3), 3) == 1


def test_difficulty_never_drops_below_one():
    assert difficulty_for(sessions(0.0, 0.0), 1) == 1


def test_only_the_most_recent_window_counts():
    recent_bad_old_good = sessions(0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 1.0)
    assert difficulty_for(recent_bad_old_good, 5) == 3  # the good games fall outside the window


def test_profile_difficulty_reads_that_games_history(profile):
    uid = profile.current_user.id
    for _ in range(3):
        profile.db.save_session(uid, "mental_math", 100, 1.0, 100)
        profile.db.save_session(uid, "n_back", 0, 0.0, 100)
    assert profile.difficulty("mental_math") == 3   # level 1 + 2
    assert profile.difficulty("n_back") == 1        # floor
    assert profile.difficulty("never_played") == 1  # level


def test_difficulty_is_capped():
    assert difficulty_for([], 25) == MAX_DIFFICULTY
    assert difficulty_for(sessions(1.0, 1.0), 10) == MAX_DIFFICULTY


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
        ids |= set(re.findall(r'(?:finish_game|save_game_result)\(profile, "(\w+)"', path.read_text(encoding="utf-8")))
    assert len(ids) >= 15  # the pattern found the games' save calls
    assert ids <= set(PERFECT_SCORE)
    assert {"linear_seating", "circular_seating"} <= set(PERFECT_SCORE)  # saved via a conditional expression


def test_save_game_result_uses_normalised_xp_but_stores_raw_score(profile):
    xp = profile.save_game_result("mental_math", 95, 1.0, 100.0)
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
