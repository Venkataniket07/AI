"""Player-assistance services: hints, explanations and free-text answer matching.

AI only *explains*, *nudges* and judges whether a free-text phrase means the same thing as the
known answer. It never decides whether a numeric or logical answer is right, and every result is
validated before it reaches the player.
"""

import logging
import re
from typing import Iterable, Optional

from ai.config import config as ai_config
from ai.router import route, TaskType
from ai.schemas import Explanation, HintResponse, SemanticMatch
from ai.utils import cache_key, load_prompt
from core.textguard import leaks

logger = logging.getLogger("ai.assist")

_EXPLAIN_PROMPT = load_prompt("explain")
_HINT_PROMPT = load_prompt("hint")
_SEMANTIC_PROMPT = load_prompt("semantic_match")

MIN_CONFIDENCE = 0.85
_MAX_INPUT_CHARS = 60


def _clean(text: str, limit: int = _MAX_INPUT_CHARS) -> str:
    """Player-typed text goes into prompts: single line, bounded length, no quote characters."""
    return re.sub(r"\s+", " ", text).replace('"', "'").strip()[:limit]


def explain(game_type: str, question: str, user_answer: str, correct_answer: str) -> Optional[Explanation]:
    """Step-by-step explanation of why `correct_answer` is right, or None if AI is unavailable."""
    if not ai_config.ai_enabled:
        return None
    prompt = _EXPLAIN_PROMPT.format(
        game_type=game_type,
        question=question,
        user_answer=_clean(user_answer),
        correct_answer=correct_answer,
    )
    result = route(TaskType.EXPLAIN, prompt, Explanation)
    return Explanation(**result) if result else None


def hint_leaks_answer(hint_text: str, forbidden: Iterable[str]) -> bool:
    return leaks(hint_text, "", forbidden)


def hint(game_type: str, puzzle_state: str, answer: str, hints_used: int,
         forbidden: Iterable[str] = ()) -> Optional[str]:
    """
    Next progressive hint text, or None if AI is unavailable or the hint would give the answer away.

    `forbidden` lists strings that must not appear in the hint (normally the answer itself).
    """
    if not ai_config.ai_enabled:
        return None
    prompt = _HINT_PROMPT.format(
        game_type=game_type, puzzle_state=puzzle_state, answer=answer, hints_used=hints_used
    )
    result = route(TaskType.HINT, prompt, HintResponse)
    if not result:
        return None
    text = HintResponse(**result).hint_text.strip()
    if hint_leaks_answer(text, [answer, *forbidden]):
        logger.warning("Discarding AI hint that contained the answer.")
        return None
    return text


def semantically_equivalent(target: str, user_input: str, game_type: str, db_manager=None) -> bool:
    """
    True if the AI is confident `user_input` means the same as `target`.

    Only meant for free-text answers after an exact/alias match has already failed. Returns False
    when AI is disabled or unsure.
    """
    if not ai_config.ai_enabled:
        return False
    user_input = _clean(user_input)
    if not user_input:
        return False

    key = cache_key("semantic", game_type, target.lower(), user_input.lower())
    if db_manager and ai_config.cache.enabled:
        cached = db_manager.cache_get(key)
        if cached is not None:
            return cached == "1"

    prompt = _SEMANTIC_PROMPT.format(target=target, user_input=user_input, game_type=game_type)
    result = route(TaskType.SEMANTIC_VALIDATE, prompt, SemanticMatch)
    if not result:
        return False

    match = SemanticMatch(**result)
    verdict = match.is_equivalent and match.confidence >= MIN_CONFIDENCE

    if db_manager and ai_config.cache.enabled:
        db_manager.cache_set(key, "1" if verdict else "0", ai_config.cache.ttl_seconds)
    return verdict
