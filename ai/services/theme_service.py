"""Theme service — wraps puzzle clues in a fixed-theme narrative.

Fixed themes: mystery, sci-fi, sports, fantasy  (no user prompt; no AI needed to pick).
AI is used only to rephrase the clues into the chosen theme's flavour text.
"""

import logging
import random
from typing import Optional

from ai.config import config as ai_config, FIXED_THEMES
from ai.router import route, TaskType
from ai.schemas import ThemedPuzzle
from ai.utils import cache_key, load_prompt
from core.textguard import themed_consistent

logger = logging.getLogger("ai.theme")

_PROMPT_TEMPLATE = load_prompt("theme_wrap")


def clues_preserved(original: list[str], themed: list[str]) -> bool:
    """Guard against the model changing a puzzle's logic; see `core.textguard.themed_consistent`."""
    return themed_consistent(original, themed)


def wrap_puzzle_in_theme(
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
    key = cache_key("theme", chosen_theme, *clues)

    if db_manager and ai_config.cache.enabled:
        cached = db_manager.cache_get(key)
        if cached:
            try:
                return ThemedPuzzle.model_validate_json(cached)
            except Exception:
                logger.warning("Ignoring unreadable cached themed puzzle.")

    prompt = _PROMPT_TEMPLATE.format(
        theme=chosen_theme,
        clues="\n".join(f"- {c}" for c in clues),
    )

    result = route(TaskType.THEME_WRAP, prompt, ThemedPuzzle)
    if result is None:
        return None

    themed = ThemedPuzzle(**result)
    if not clues_preserved(clues, themed.clues):
        logger.warning("Themed clues did not preserve the original labels; discarding.")
        return None

    if db_manager and ai_config.cache.enabled:
        db_manager.cache_set(key, themed.model_dump_json(), ai_config.cache.ttl_seconds)

    return themed
