"""Session summary service — generates a personalised coaching message post-game."""

import hashlib
import os
from typing import Optional

from ai.config import config as ai_config
from ai.router import route, TaskType
from ai.schemas import SessionSummary

_PROMPT_PATH = os.path.join(os.path.dirname(__file__), "..", "prompts", "session_summary.txt")

with open(_PROMPT_PATH, "r", encoding="utf-8") as _f:
    _PROMPT_TEMPLATE = _f.read()


def _format_stats(sessions: list) -> str:
    if not sessions:
        return "No games played yet."
    lines = []
    for s in sessions[:5]:  # last 5 sessions only
        lines.append(
            f"  {s.game_type}: score={s.score}, accuracy={s.accuracy*100:.0f}%, "
            f"reaction={s.reaction_time_ms:.0f}ms"
        )
    return "\n".join(lines)


async def summarize_session(
    username: str,
    level: int,
    sessions: list,
    db_manager=None,
) -> Optional[str]:
    """
    Returns a 2-3 sentence coaching string, or None (caller shows stats table only).

    Args:
        username:   Current user's name.
        level:      Current user level.
        sessions:   List of GameSession objects (recent first).
        db_manager: DBManager for caching.
    """
    if not ai_config.ai_enabled or not sessions:
        return None

    stats_text = _format_stats(sessions)
    key = "summary:" + hashlib.md5((username + stats_text).encode()).hexdigest()

    if db_manager and ai_config.cache.enabled:
        cached = db_manager.cache_get(key)
        if cached:
            return cached

    prompt = _PROMPT_TEMPLATE.format(
        username=username,
        level=level,
        games_played=len(sessions),
        stats_summary=stats_text,
    )

    result = await route(TaskType.SESSION_SUMMARY, prompt, SessionSummary)
    if result is None:
        return None

    summary = SessionSummary(**result)
    coaching_text = summary.coaching

    if db_manager and ai_config.cache.enabled:
        db_manager.cache_set(key, coaching_text, ai_config.cache.ttl_seconds)

    return coaching_text
