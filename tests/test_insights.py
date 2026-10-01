import json
from types import SimpleNamespace

import pytest

from core.insights import Action, compute_insights, template_text, text_consistent


def s(game, acc, ms=5000.0, trials=None):
    return SimpleNamespace(
        game_type=game,
        accuracy=acc,
        reaction_time_ms=ms,
        score=50,
        difficulty=None,
        trial_data=json.dumps(trials) if trials else None,
    )


def plays(game, accs, ms=5000.0):
    """Sessions newest first, accuracies given newest first."""
    return [s(game, a, ms) for a in accs]


@pytest.mark.parametrize(
    "accs,expected",
    [
        ([0.90, 0.90, 0.90, 0.5, 0.5], Action.RAISE),  # boundary: exactly 90%
        ([0.89, 0.90, 0.90, 0.5, 0.5], Action.HOLD),  # just under 90% (average of 3 = 89.67%)
        ([0.60, 0.60, 0.60, 1.0, 1.0], Action.LOWER),  # boundary: exactly 60%
        ([0.61, 0.60, 0.62, 1.0, 1.0], Action.HOLD),
        ([0.75] * 5, Action.HOLD),
    ],
)
def test_action_rule_table(accs, expected):
    insight = compute_insights(plays("anagrams", accs))
    assert insight.action["anagrams"] is expected


def test_boundary_just_below_ninety_is_hold():
    assert compute_insights(plays("n_back", [0.89, 0.89, 0.89, 1.0, 1.0])).action["n_back"] is Action.HOLD


def test_never_played_game_is_try_new():
    insight = compute_insights(plays("n_back", [1.0] * 5), all_games=["n_back", "rankings"])
    assert insight.action["rankings"] is Action.TRY_NEW


def test_need_data_and_no_ranking_under_five_plays():
    insight = compute_insights(plays("anagrams", [0.9] * 6) + plays("mental_math", [0.1] * 2))
    assert insight.action["mental_math"] is Action.NEED_DATA
    assert insight.strongest is None and insight.weakest is None  # only one game has 5 plays


def test_strongest_and_weakest_with_enough_plays():
    insight = compute_insights(plays("anagrams", [0.9] * 5) + plays("n_back", [0.5] * 5) + plays("rankings", [1.0] * 4))
    assert (insight.strongest, insight.weakest) == ("anagrams", "n_back")


def test_trend_needs_ten_plays():
    assert compute_insights(plays("n_back", [0.9] * 9)).trend["n_back"] == "n/a (10 plays)"
    assert compute_insights(plays("n_back", [0.9] * 5 + [0.5] * 5)).trend["n_back"] == "up"
    assert compute_insights(plays("n_back", [0.5] * 5 + [0.9] * 5)).trend["n_back"] == "down"
    assert compute_insights(plays("n_back", [0.7] * 10)).trend["n_back"] == "steady"


def test_slow_down_target_is_never_faster_than_the_current_time():
    # current play: 45 s at 70% accuracy; earlier accurate plays took about 60 s per question
    sessions = [s("anagrams", 0.7, 45000)] + [s("anagrams", 0.9, 60000) for _ in range(4)]
    target = compute_insights(sessions).speed_target_ms["anagrams"]
    assert target is not None and target >= 45000


def test_slow_down_uses_the_median_of_correct_trials():
    trials = [[20000, 1, 0, None], [40000, 1, 0, None], [90000, 1, 0, None], [1000, 0, 0, None]]
    sessions = [s("anagrams", 0.7, 30000, trials)] + [s("anagrams", 0.7, 30000) for _ in range(4)]
    assert compute_insights(sessions).speed_target_ms["anagrams"] == 40000


def test_no_slow_down_advice_when_accurate_or_already_slow():
    accurate = [s("anagrams", 0.9, 45000)] + [s("anagrams", 0.9, 60000) for _ in range(4)]
    assert compute_insights(accurate).speed_target_ms["anagrams"] is None
    slow = [s("anagrams", 0.7, 90000)] + [s("anagrams", 0.9, 60000) for _ in range(4)]
    assert compute_insights(slow).speed_target_ms["anagrams"] is None


def test_deterministic():
    sessions = plays("anagrams", [0.9, 0.7, 0.8, 0.6, 0.5, 0.9]) + plays("n_back", [0.4] * 6)
    assert compute_insights(sessions) == compute_insights(sessions)
    assert template_text(compute_insights(sessions)) == template_text(compute_insights(sessions))


def test_guard_rejects_contradiction_and_accepts_consistent_text():
    insight = compute_insights(plays("anagrams", [0.5] * 6))  # LOWER
    assert text_consistent("Anagrams is at 50%, so lower the difficulty for now.", insight)
    assert not text_consistent("Anagrams is going well, so raise the difficulty.", insight)
    assert not text_consistent("Hold the difficulty in Anagrams.", insight)


def test_guard_rejects_games_not_in_the_facts_and_unsupported_superlatives():
    insight = compute_insights(plays("anagrams", [0.5] * 6))
    assert not text_consistent("Anagrams is fine, but Mental Math is your best.", insight)
    assert not text_consistent("Anagrams is your strongest game.", insight)  # nothing was ranked


def test_template_text_passes_its_own_guard():
    sessions = plays("anagrams", [0.95] * 6) + plays("n_back", [0.5] * 6) + plays("mental_math", [0.1] * 2)
    insight = compute_insights(sessions, all_games=["rankings"])
    assert text_consistent(template_text(insight), insight)
    assert "raise the difficulty" in template_text(insight, "anagrams")
