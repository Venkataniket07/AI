from ai.providers.base import parse_model_json
from ai.schemas import SessionSummary, ThemedPuzzle
from ai.services import theme_service
from ai.services.theme_service import clues_preserved
from ai.utils import cache_key

ORIG = ["B sits immediately left of C.", "D sits at the extreme left end."]


def test_clues_preserved_accepts_reworded_clues():
    assert clues_preserved(ORIG, ["Detective B stands beside C, on the left.", "D holds the far left post."])


def test_clues_preserved_rejects_swapped_direction_count_or_labels():
    assert not clues_preserved(ORIG, ["C sits immediately left of B.", "D sits at the extreme left end."])
    assert not clues_preserved(ORIG, ["B sits immediately left of C."])
    assert not clues_preserved(ORIG, ["B sits immediately left of E.", "D sits at the extreme left end."])


def test_clues_preserved_ignores_english_article_a():
    assert clues_preserved(ORIG, ["A quiet B sits immediately left of C.", "D sits at the extreme left end."])


def test_clues_preserved_with_label_a_compares_sets():
    assert clues_preserved(["A sits opposite to C."], ["C faces A across the table."])
    assert not clues_preserved(["A sits opposite to C."], ["C faces E across the table."])


def _wrap(monkeypatch, db, result):
    monkeypatch.setattr(theme_service.ai_config, "ai_enabled", True)
    monkeypatch.setattr(theme_service.ai_config.cache, "enabled", True)
    monkeypatch.setattr(theme_service, "route", lambda *a, **k: result)
    return theme_service.wrap_puzzle_in_theme(ORIG, db_manager=db, theme="mystery")


def test_wrap_rejects_logic_changing_rewrite_and_does_not_cache_it(monkeypatch, db):
    bad = {"scenario": "s", "clues": ["C sits immediately left of B.", "D sits at the extreme left end."]}
    assert _wrap(monkeypatch, db, bad) is None
    assert db.cache_get(cache_key("theme", "mystery", *ORIG)) is None


def test_wrap_accepts_and_caches_valid_rewrite(monkeypatch, db):
    good = {"scenario": "s", "clues": ["B is right next to C on the left.", "D is at the far left."]}
    assert isinstance(_wrap(monkeypatch, db, good), ThemedPuzzle)
    assert db.cache_get(cache_key("theme", "mystery", *ORIG)) is not None


def test_cache_key_is_namespaced_and_unambiguous():
    assert cache_key("a", "x") != cache_key("b", "x")
    assert cache_key("a", "ab", "c") != cache_key("a", "a", "bc")


def test_parse_model_json_handles_fences_and_invalid_data():
    assert parse_model_json('```json\n{"coaching": "hi"}\n```', SessionSummary, "T") == {"coaching": "hi"}
    assert parse_model_json("not json", SessionSummary, "T") is None
    assert parse_model_json('{"wrong": 1}', SessionSummary, "T") is None
