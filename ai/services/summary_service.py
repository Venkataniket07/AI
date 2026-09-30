"""Session summary service — generates a personalised coaching message post-game."""

from typing import Optional

from ai.config import config as ai_config
from ai.router import route, TaskType
from ai.context import latest_game_facts
from ai.schemas import SessionSummary
from ai.utils import cache_key, load_prompt

_PROMPT_TEMPLATE = load_prompt("session_summary")


def build_prompt(username: str, level: int, sessions: list) -> tuple[str, str]:
    """(prompt, facts). `sessions` is newest first; the coaching is about the first one."""
    facts = latest_game_facts(sessions)
    return _PROMPT_TEMPLATE.format(username=username, level=level, facts=facts), facts


def summarize_session(
    username: str,
    level: int,
    sessions: list,
    db_manager=None,
) -> Optional[str]:
    """
    Returns a 2 sentence coaching string about the latest game, or None (caller shows stats table only).

    Args:
        username:   Current user's name.
        level:      Current user level.
        sessions:   GameSession objects, newest first (the latest is the game just played).
        db_manager: DBManager for caching.
    """
    if not ai_config.ai_enabled or not sessions:
        return None

    prompt, facts = build_prompt(username, level, sessions)
    key = cache_key("summary", username.lower(), str(level), facts)

    if db_manager and ai_config.cache.enabled:
        cached = db_manager.cache_get(key)
        if cached:
            return cached

    result = route(TaskType.SESSION_SUMMARY, prompt, SessionSummary)
    if result is None:
        return None

    coaching_text = SessionSummary(**result).coaching

    if db_manager and ai_config.cache.enabled:
        db_manager.cache_set(key, coaching_text, ai_config.cache.ttl_seconds)

    return coaching_text
