from types import SimpleNamespace

import pytest

from ai import context
from ai.schemas import Explanation, HintResponse, SessionSummary, StatsAnalysis
from ai.services import assist_service, stats_service, summary_service


def s(game, acc, ms=5000.0, score=50, difficulty=None):
    return SimpleNamespace(game_type=game, accuracy=acc, reaction_time_ms=ms, score=score, difficulty=difficulty)


# ── coaching facts ───────────────────────────────────────────────────────────

def test_first_play_of_a_game_is_reported_as_such():
    facts = context.latest_game_facts([s("n_back", 0.6), s("mental_math", 1.0)])
    assert "Game: N-Back" in facts and "first recorded play" in facts
    assert "Other games played recently: Mental Math (100%)" in facts


def test_latest_game_is_compared_with_earlier_plays_of_the_same_game_only():
    sessions = [s("anagrams", 1.0, 40000), s("mental_math", 0.2, 1000),
                s("anagrams", 0.6, 50000), s("anagrams", 0.6, 50000)]
    facts = context.latest_game_facts(sessions)
    assert "previous 2 plays of this game (average 60%): up 40 points" in facts
    assert "average 50.0s): faster by 20%" in facts
    assert "average 1.0s" not in facts  # the mental-math session is not a baseline


@pytest.mark.parametrize("now,before,expected", [
    (0.90, 0.60, "up 30 points"), (0.40, 0.60, "down 20 points"), (0.62, 0.60, "about the same"),
])
def test_accuracy_change_wording(now, before, expected):
    facts = context.latest_game_facts([s("n_back", now), s("n_back", before)])
    assert expected in facts


def test_speed_is_only_called_faster_or_slower_beyond_ten_percent():
    same = context.latest_game_facts([s("n_back", 1, 5300), s("n_back", 1, 5000)])
    slower = context.latest_game_facts([s("n_back", 1, 6000), s("n_back", 1, 5000)])
    assert "about the same" in same.split("Speed compared")[1]
    assert "slower by 20%" in slower


def test_difficulty_changes_are_reported_when_known():
    rose = context.latest_game_facts([s("anagrams", 1, difficulty=4), s("anagrams", 1, difficulty=3)])
    assert "at difficulty 4" in rose and "rose from 3 to 4" in rose
    fell = context.latest_game_facts([s("anagrams", 1, difficulty=2), s("anagrams", 1, difficulty=3)])
    assert "fell from 3 to 2" in fell
    legacy = context.latest_game_facts([s("anagrams", 1, difficulty=None), s("anagrams", 1)])
    assert "ifficulty" not in legacy  # old sessions have no difficulty; nothing is invented


def test_personal_best_needs_enough_history():
    few = context.latest_game_facts([s("n_back", 1, score=90), s("n_back", 1, score=10)])
    many = context.latest_game_facts([s("n_back", 1, score=90)] + [s("n_back", 1, score=10)] * 3)
    assert "personal best" not in few and "personal best" in many


# ── stats facts ──────────────────────────────────────────────────────────────

def test_stats_facts_never_compare_speed_across_games():
    sessions = [s("mental_math", 0.9, 4000)] * 5 + [s("anagrams", 0.5, 60000)] * 5
    facts = context.game_history_facts(sessions)
    assert "Mental Math: 5 plays" in facts and "Anagrams: 5 plays" in facts
    assert "too few earlier plays" in facts
    assert "faster" not in facts and "slower" not in facts  # no earlier window, so no speed claim
    assert "Highest recent accuracy: Mental Math (90%). Lowest: Anagrams (50%)." in facts


def test_stats_facts_show_trend_and_speed_within_a_game():
    recent = [s("n_back", 0.9, 3000, difficulty=4)] * 5
    before = [s("n_back", 0.6, 6000, difficulty=2)] * 5
    facts = context.game_history_facts(recent + before)
    assert "10 plays" in facts and "recent accuracy 90%" in facts
    assert "vs the 5 plays before: up 30 points" in facts
    assert "3.0s per question, faster by 50%" in facts
    assert "latest difficulty 4 (highest so far 4)" in facts


def test_stats_facts_ignore_games_with_too_few_plays_when_ranking():
    facts = context.game_history_facts([s("a", 1.0)] * 5 + [s("b", 0.1)] + [s("c", 0.5)] * 5)
    assert "Lowest: C" in facts and "B" not in facts.split("Highest")[1]


def test_no_history():
    assert context.game_history_facts([]) == "No games played yet."


# ── prompts ──────────────────────────────────────────────────────────────────

def test_coaching_prompt_carries_the_facts_and_the_rules():
    prompt, facts = summary_service.build_prompt("Ann", 4, [s("n_back", 0.8, difficulty=3)])
    assert "Ann (level 4)" in prompt and facts in prompt
    assert "exactly 2 sentences" in prompt and "Never compare speed between different games" in prompt
    assert "{" not in prompt  # every placeholder was filled


def test_stats_prompt_forbids_cross_game_speed_and_uses_facts():
    prompt, facts = stats_service.build_prompt("Ann", 4, [s("n_back", 0.8)] * 3)
    assert "3 games in total" in prompt and facts in prompt
    assert "Never compare speed between different games" in prompt and "{" not in prompt
    assert "within 5 points" in prompt  # no invented "weakest game" when results are level


def test_hint_and_explain_prompts_fill_all_placeholders():
    hint = assist_service._HINT_PROMPT.format(game_type="rankings", puzzle_state="A>B", answer="AB", hints_used=1)
    explain = assist_service._EXPLAIN_PROMPT.format(game_type="g", question="q", user_answer="", correct_answer="5")
    assert "{" not in hint and "{" not in explain
    assert "under 120 characters" in hint and "Never state the correct answer" in hint


# ── replies that run long are trimmed, not thrown away ───────────────────────

def test_long_replies_are_trimmed_at_a_word_boundary():
    hint = HintResponse(hint_text="word " * 60).hint_text
    assert len(hint) <= 150 and hint.endswith("…") and "wor…" not in hint
    assert SessionSummary(coaching="ok. " * 200).coaching.endswith("…")
    assert len(StatsAnalysis(analysis="x " * 900).analysis) <= 700


def test_short_replies_are_untouched_and_steps_are_clipped_individually():
    assert HintResponse(hint_text="Look at the ends.").hint_text == "Look at the ends."
    e = Explanation(steps=["short", "long " * 60], summary="Fine.")
    assert e.steps[0] == "short" and len(e.steps[1]) <= 100
