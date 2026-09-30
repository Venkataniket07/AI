import random
import sqlite3


from database.db_manager import MIGRATIONS, DBManager
from games.language import anagrams
from games.language.wordlist import (
    BANDS,
    in_band,
    is_valid_anagram,
    lengths_for,
    offline_words,
    pick_words,
    round_difficulties,
)


def test_bands_get_longer_and_rarer_as_difficulty_rises():
    for level in range(1, 10):
        lo_len, hi_len, lo_freq, _ = BANDS[level]
        next_lo_len, next_hi_len, next_lo_freq, _ = BANDS[level + 1]
        assert next_lo_len >= lo_len and next_hi_len >= hi_len
        assert next_lo_freq <= lo_freq


def test_every_band_has_enough_built_in_words_for_a_game():
    words = offline_words()
    for level in BANDS:
        assert sum(in_band(w, level) for w in words) >= 20, level


def test_easy_levels_only_use_common_words():
    """The complaint that started this: level-1 anagrams must not be words like 'sough' or 'scowl'."""
    for _ in range(20):
        for item in pick_words(offline_words(), 1, 5, random.Random()):
            assert item["freq"] >= 5, item


def test_ramp_starts_easier_and_reaches_the_level():
    assert round_difficulties(6, 5) == [4, 5, 6, 6, 6]
    assert round_difficulties(1, 5) == [1, 1, 1, 1, 1]  # never below 1
    assert round_difficulties(20, 5)[-1] == max(BANDS)   # never above the hardest band


def test_pick_words_gives_distinct_words_one_per_round():
    words = pick_words(offline_words(), 5, 5, random.Random(1))
    assert len(words) == 5 and len({w["word"] for w in words}) == 5


def test_pick_words_still_fills_the_game_when_a_band_is_empty():
    pool = [{"word": w, "clue": "c", "freq": 0.001} for w in ("alpha", "bravo", "delta", "gamma", "sigma")]
    assert len(pick_words(pool, 1, 5, random.Random(1))) == 5


def test_lengths_for_covers_the_band():
    assert lengths_for(1) == [4, 5]
    assert lengths_for(10) == [8, 9, 10]


def test_any_real_anagram_is_accepted():
    known = {"tar", "rat", "art"}.__contains__
    assert is_valid_anagram("rat", "art", known)
    assert is_valid_anagram("art", "art", lambda w: False)   # the intended word needs no lookup
    assert not is_valid_anagram("tra", "art", known)         # right letters, not a word
    assert not is_valid_anagram("rats", "art", lambda w: True)  # wrong letters
    assert not is_valid_anagram("", "art", lambda w: True)


def test_fetch_parses_frequency_and_drops_clues_that_give_the_word_away(monkeypatch):
    import io
    import json

    data = [
        {"word": "sneer", "defs": ["v\tshow contempt"], "tags": ["v", "f:0.875"]},
        {"word": "chair", "defs": ["n\ta chair is a seat"], "tags": ["n", "f:20.0"]},   # clue names the word
        {"word": "scowl", "defs": ["v\tfrown"]},                                           # no frequency
        {"word": "ab1de", "defs": ["n\tx"], "tags": ["f:1.0"]},                            # not alphabetic
    ]
    monkeypatch.setattr(anagrams.urllib.request, "urlopen",
                        lambda *a, **k: io.BytesIO(json.dumps(data).encode()))
    assert anagrams.fetch_words_from_api(5) == [{"word": "sneer", "clue": "show contempt", "freq": 0.875}]


def test_is_real_word_needs_an_exact_match(monkeypatch):
    import io
    import json

    reply = [{"word": "rat", "score": 1}]
    monkeypatch.setattr(anagrams.urllib.request, "urlopen",
                        lambda *a, **k: io.BytesIO(json.dumps(reply).encode()))
    assert anagrams.is_real_word("rat") is True
    assert anagrams.is_real_word("rta") is False

    def down(*a, **k):
        raise OSError("offline")
    monkeypatch.setattr(anagrams.urllib.request, "urlopen", down)
    assert anagrams.is_real_word("rat") is False


# ── schema v4 ────────────────────────────────────────────────────────────────

def test_difficulty_is_stored_with_the_session(tmp_path):
    db = DBManager(str(tmp_path / "t.db"), legacy_json=None)
    user = db.create_user("ann")
    db.save_session(user.id, "anagrams", 40, 0.8, 900.0, difficulty=6)
    db.save_session(user.id, "anagrams", 40, 0.8, 900.0)
    newest, older = db.get_user_stats(user.id)
    assert older.difficulty == 6 and newest.difficulty is None


def test_v4_migration_keeps_existing_sessions(tmp_path):
    path = str(tmp_path / "old.db")
    conn = sqlite3.connect(path)
    for script in MIGRATIONS[:3]:
        conn.executescript(script)
    conn.execute("PRAGMA user_version = 3")
    conn.execute("INSERT INTO users (username, created_at) VALUES ('bo', '2026-01-01 00:00:00')")
    conn.execute("INSERT INTO game_sessions (user_id, game_type, score, accuracy, reaction_time_ms, played_at) "
                 "VALUES (1, 'n_back', 50, 0.9, 500, '2026-01-01 00:00:00')")
    conn.commit()
    conn.close()

    db = DBManager(path, legacy_json=None)
    assert db.schema_version() == len(MIGRATIONS) >= 4
    (session,) = db.get_user_stats(1)
    assert session.score == 50 and session.difficulty is None


def test_play_records_the_difficulty(tmp_path, monkeypatch):
    from core.profile_manager import ProfileManager

    db = DBManager(str(tmp_path / "t.db"), legacy_json=None)
    profile = ProfileManager(db)
    profile.login("cy")
    pool = offline_words()
    monkeypatch.setattr(anagrams, "build_word_pool", lambda lengths: (pool, True))
    answers = iter([""] + ["x"] * 5 + [""])          # start, five wrong guesses, return to menu
    monkeypatch.setattr("builtins.input", lambda *_: next(answers))
    anagrams.play_anagrams(profile)
    (session,) = db.get_user_stats(profile.current_user.id)
    assert session.game_type == "anagrams" and session.difficulty == 1


def test_ai_declaration_marks_the_session_assisted_and_instant_answers_are_reviewed(tmp_path, monkeypatch):
    from core.profile_manager import ProfileManager

    db = DBManager(str(tmp_path / "t.db"), legacy_json=None)
    profile = ProfileManager(db)
    profile.login("cy")
    pool = offline_words()
    monkeypatch.setattr(anagrams, "build_word_pool", lambda lengths: (pool, True))
    monkeypatch.setattr(anagrams.random, "shuffle", lambda chars: None)  # scramble == word, so guess "" never matches
    picked = anagrams.pick_words(pool, 1, anagrams.ROUNDS, __import__("random").Random(1))
    monkeypatch.setattr(anagrams, "pick_words", lambda *a, **k: picked)
    answers = iter([""] + ["/ai"] + [p["word"] for p in picked] + [""])
    monkeypatch.setattr("builtins.input", lambda *_: next(answers))
    anagrams.play_anagrams(profile)
    (session,) = db.get_user_stats(profile.current_user.id)
    assert session.assisted == 1 and session.integrity == "review"
    assert profile.current_user.xp == 0
