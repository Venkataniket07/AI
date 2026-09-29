import json
import logging

import pytest

from ai import config as ai_config_module
from games.language import anagrams
from games.language.wordlist import OFFLINE_WORDS, offline_words
from utils import logger as logger_module

# ── word list ────────────────────────────────────────────────────────────────


def test_offline_words_have_the_right_length_and_a_clue():
    assert set(OFFLINE_WORDS) == set(range(4, 11))  # every length the game can ask for
    for length, entries in OFFLINE_WORDS.items():
        assert len(entries) >= 6
        assert len({w for w, _ in entries}) == len(entries)
        for word, clue in entries:
            assert len(word) == length and word.isalpha() and word.islower()
            assert clue.strip()


def test_offline_words_shape_matches_the_api_shape():
    assert set(offline_words(5)[0]) == {"word", "clue"}
    assert offline_words(99) == []


def test_pool_uses_the_service_when_it_answers():
    online = [{"word": f"w{i}", "clue": "c"} for i in range(6)]
    pool, offline = anagrams.build_word_pool([4, 5], fetch=lambda n: online if n == 4 else [])
    assert pool == online and offline is False


def test_pool_falls_back_to_built_in_words_when_offline():
    pool, offline = anagrams.build_word_pool([6, 7], fetch=lambda n: [])
    assert offline is True
    assert len(pool) >= anagrams.MIN_POOL
    assert {len(item["word"]) for item in pool} == {6, 7}


def test_pool_is_topped_up_without_duplicates():
    duplicate = {"word": "garden", "clue": "from the service"}
    pool, offline = anagrams.build_word_pool([6], fetch=lambda n: [duplicate])
    assert offline is True
    assert [item["word"] for item in pool].count("garden") == 1
    assert len(pool) >= anagrams.MIN_POOL


# ── logging ──────────────────────────────────────────────────────────────────

@pytest.fixture
def clean_loggers():
    yield
    for name in ("app", "ai"):
        lg = logging.getLogger(name)
        for h in list(lg.handlers):
            lg.removeHandler(h)
            h.close()


def test_logs_are_single_rotating_files(tmp_path, clean_loggers):
    logger_module.init_loggers(str(tmp_path))
    for name in ("app", "ai"):
        handlers = logging.getLogger(name).handlers
        assert len(handlers) == 1
        h = handlers[0]
        assert h.maxBytes == logger_module.MAX_LOG_BYTES and h.backupCount == logger_module.LOG_BACKUPS
    logging.getLogger("app").info("hello")
    assert "hello" in (tmp_path / "app.log").read_text(encoding="utf-8")


def test_reinitialising_does_not_stack_handlers_or_create_new_files(tmp_path, clean_loggers):
    for _ in range(3):
        logger_module.init_loggers(str(tmp_path))
    assert len(logging.getLogger("app").handlers) == 1
    assert sorted(p.name for p in tmp_path.iterdir()) == ["ai.log", "app.log"]


def test_log_levels_come_from_the_environment(tmp_path, monkeypatch, clean_loggers):
    monkeypatch.setenv("APP_LOG_LEVEL", "warning")
    monkeypatch.setenv("AI_LOG_LEVEL", "nonsense")
    logger_module.init_loggers(str(tmp_path))
    assert logging.getLogger("app").level == logging.WARNING
    assert logging.getLogger("ai").level == logging.DEBUG  # invalid value -> default


# ── AI config ────────────────────────────────────────────────────────────────

def _write_config(tmp_path, **overrides):
    raw = {
        "ai_enabled": True,
        "providers": {
            "gemini": {"enabled": True, "model": "g-model", "api_key": "from-json"},
            "openrouter": {"enabled": True, "model": "o-model"},
        },
        "cache": {"enabled": True, "ttl_seconds": 60},
    }
    raw.update(overrides)
    path = tmp_path / "ai_config.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    return str(path)


@pytest.fixture
def env(monkeypatch):
    for key in ("AI_ENABLED", "GEMINI_API_KEY", "OPENROUTER_API_KEY", "GEMINI_MODEL", "OPENROUTER_MODEL"):
        monkeypatch.delenv(key, raising=False)
    return monkeypatch


def test_api_keys_come_only_from_the_environment(tmp_path, env):
    cfg = ai_config_module._load(_write_config(tmp_path))
    assert cfg.gemini.api_key == "" and cfg.gemini.enabled is False  # the key in the json is ignored
    env.setenv("GEMINI_API_KEY", "from-env")
    cfg = ai_config_module._load(_write_config(tmp_path))
    assert cfg.gemini.api_key == "from-env" and cfg.gemini.enabled is True
    assert cfg.openrouter.enabled is False  # no key, so not available


def test_models_and_cache_settings_are_loaded(tmp_path, env):
    env.setenv("OPENROUTER_MODEL", "override")
    cfg = ai_config_module._load(_write_config(tmp_path))
    assert cfg.gemini.model == "g-model" and cfg.openrouter.model == "override"
    assert cfg.cache.ttl_seconds == 60


def test_env_can_disable_ai_and_missing_file_disables_it(tmp_path, env):
    env.setenv("AI_ENABLED", "false")
    assert ai_config_module._load(_write_config(tmp_path)).ai_enabled is False
    env.delenv("AI_ENABLED")
    assert ai_config_module._load(str(tmp_path / "missing.json")).ai_enabled is False


def test_ollama_is_gone_from_config_and_shipped_json():
    assert not hasattr(ai_config_module, "OllamaConfig")
    shipped = json.loads(open(ai_config_module._CONFIG_PATH, encoding="utf-8").read())
    assert "ollama" not in shipped["providers"]
    assert all("api_key" not in p for p in shipped["providers"].values())
