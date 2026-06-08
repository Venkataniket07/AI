"""AI router — maps task types to provider chains with fallback.

Usage:
    from ai.router import route, TaskType
    result = await route(TaskType.THEME_WRAP, prompt, ThemedPuzzle)
    # returns a validated dict or None (caller uses deterministic fallback)
"""

import asyncio
from enum import Enum
from typing import Optional, Type

from pydantic import BaseModel

from ai.config import config as ai_config
from ai.providers.gemini import GeminiProvider
from ai.providers.openrouter import OpenRouterProvider


class TaskType(Enum):
    THEME_WRAP = "theme_wrap"
    EXPLAIN = "explain"
    HINT = "hint"
    SEMANTIC_VALIDATE = "semantic_validate"
    GENERATE_CONTENT = "generate_content"
    SESSION_SUMMARY = "session_summary"


# Priority chain per task. "static" means: return None → caller uses fallback.
_ROUTING_TABLE: dict[TaskType, list[str]] = {
    TaskType.THEME_WRAP:        ["gemini", "openrouter", "static"],
    TaskType.EXPLAIN:           ["gemini", "openrouter", "static"],
    TaskType.HINT:              ["gemini", "openrouter", "static"],
    TaskType.SEMANTIC_VALIDATE: ["gemini", "openrouter", "exact_match"],
    TaskType.GENERATE_CONTENT:  ["gemini", "openrouter", "skip"],
    TaskType.SESSION_SUMMARY:   ["gemini", "openrouter", "static"],
}

_TIMEOUTS: dict[str, float] = {
    "gemini": 10.0,
    "openrouter": 12.0,
}

_PROVIDERS: dict = {}


def _get_provider(name: str):
    """Lazy-initialise providers once."""
    if name not in _PROVIDERS:
        if name == "gemini":
            _PROVIDERS[name] = GeminiProvider()
        elif name == "openrouter":
            _PROVIDERS[name] = OpenRouterProvider()
    return _PROVIDERS.get(name)


async def route(task: TaskType, prompt: str, schema: Type[BaseModel]) -> Optional[dict]:
    """Try each provider in priority order; return first valid response or None."""
    if not ai_config.ai_enabled:
        return None

    for provider_name in _ROUTING_TABLE[task]:
        if provider_name in ("static", "skip", "exact_match"):
            return None  # signal to caller: use deterministic fallback

        provider = _get_provider(provider_name)
        if provider is None or not provider.is_available():
            continue

        timeout = _TIMEOUTS.get(provider_name, 10.0)
        try:
            result = await asyncio.wait_for(
                provider.generate(prompt, schema, timeout=timeout),
                timeout=timeout + 2.0,  # outer guard
            )
            if result is not None:
                return result
        except (asyncio.TimeoutError, Exception):
            continue

    return None
