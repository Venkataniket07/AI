"""N-Back: sitting still never earns a perfect game, and perfect play scores the maximum."""

import builtins
import random
import re

import pytest

from core.timing import nback_n
from games.memory import n_back


def _play(monkeypatch, capsys, profile, level, press_policy):
    """Run one game at `level`. `press_policy(seen, n)` gets the letters shown so far and N, and returns a key or None."""
    results = []
    seen = []
    monkeypatch.setattr(profile, "difficulty", lambda game_type: level)
    monkeypatch.setattr(n_back, "clear_screen", lambda: None)
    monkeypatch.setattr("time.sleep", lambda s: None)
    monkeypatch.setattr(builtins, "input", lambda prompt="": "")
    monkeypatch.setattr(
        n_back, "finish_game", lambda profile, game_id, score, tracker, *a, **kw: results.append((score, tracker))
    )
    n = nback_n(level)

    def keypress(timeout):
        letters = re.findall(r"^\s+([A-F])\s*$", capsys.readouterr().out, re.M)
        seen.append(letters[-1])
        return press_policy(seen, n)

    monkeypatch.setattr(n_back, "get_single_keypress_with_timeout", keypress)
    n_back.play_n_back(profile)
    assert len(results) == 1
    return results[0]


@pytest.mark.parametrize("level", [1, 4, 10])
def test_targets_are_guaranteed(monkeypatch, capsys, profile, level):
    for s in range(50):
        random.seed(s)
        score, tracker = _play(monkeypatch, capsys, profile, level, lambda seen, n: None)
        assert tracker.accuracy < 1.0
        assert score < 145


@pytest.mark.parametrize("level", [1, 4, 10])
def test_perfect_play_scores_145(monkeypatch, capsys, profile, level):
    def perfect(seen, n):
        return "y" if len(seen) > n and seen[-1] == seen[-1 - n] else None

    for s in range(50):
        random.seed(s)
        score, tracker = _play(monkeypatch, capsys, profile, level, perfect)
        assert score == 145
        assert tracker.accuracy == 1.0


@pytest.mark.parametrize("level", [1, 4, 10])
def test_stored_difficulty_is_the_policy_level(monkeypatch, capsys, profile, level):
    stored = []
    monkeypatch.setattr(profile, "difficulty", lambda game_type: level)
    monkeypatch.setattr(n_back, "clear_screen", lambda: None)
    monkeypatch.setattr("time.sleep", lambda s: None)
    monkeypatch.setattr(builtins, "input", lambda prompt="": "")
    monkeypatch.setattr(n_back, "get_single_keypress_with_timeout", lambda timeout: None)
    monkeypatch.setattr(n_back, "finish_game", lambda *a, **kw: stored.append(kw["difficulty"]))
    n_back.play_n_back(profile)
    assert stored == [level]
