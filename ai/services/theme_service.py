"""Theme service — wraps puzzle clues in a fixed-theme narrative.

Fixed themes: mystery, sci-fi, sports, fantasy  (no user prompt; no AI needed to pick).
AI is used only to rephrase the clues into the chosen theme's flavour text.
"""

import hashlib
import json
import os
import random
from typing import Optional

from ai.config import config as ai_config, FIXED_THEMES
from ai.router import route, TaskType
from ai.schemas import ThemedPuzzle

_PROMPT_PATH = os.path.join(os.path.dirname(__file__), "..", "prompts", "theme_wrap.txt")

with open(_PROMPT_PATH, "r", encoding="utf-8") as _f:
    _PROMPT_TEMPLATE = _f.read()


def _cache_key(theme: str, clues: list[str]) -> str:
    raw = theme + "|".join(clues)
    return "theme:" + hashlib.md5(raw.encode()).hexdigest()


async def wrap_puzzle_in_theme(
    clues: list[str],
    db_manager=None,
    theme: Optional[str] = None,
) -> Optional[ThemedPuzzle]:
    """
    Returns a ThemedPuzzle (scenario + rewritten clues) or None (caller shows raw clues).

    Args:
        clues:      Original puzzle clues.
        db_manager: DBManager instance for caching. If None, no caching.
        theme:      Override theme. If None, picks randomly from FIXED_THEMES.
    """
    if not ai_config.ai_enabled:
        return None

    chosen_theme = theme or random.choice(ai_config.themes or FIXED_THEMES)
    key = _cache_key(chosen_theme, clues)

    # Cache read
    if db_manager and ai_config.cache.enabled:
        cached = db_manager.cache_get(key)
        if cached:
            try:
                return ThemedPuzzle.model_validate_json(cached)
            except Exception:
                pass

    prompt = _PROMPT_TEMPLATE.format(
        theme=chosen_theme,
        clues="\n".join(f"- {c}" for c in clues),
    )

    result = await route(TaskType.THEME_WRAP, prompt, ThemedPuzzle)
    if result is None:
        return None

    themed = ThemedPuzzle(**result)

    # Cache write
    if db_manager and ai_config.cache.enabled:
        db_manager.cache_set(key, themed.model_dump_json(), ai_config.cache.ttl_seconds)

    return themed
