"""AI router — maps task types to provider chains with fallback.

Usage:
    from ai.router import route, TaskType
    result = route(TaskType.THEME_WRAP, prompt, ThemedPuzzle)
    # returns a validated dict or None (caller uses deterministic fallback)

Calls are synchronous; run them via ai.background.submit() to keep the UI responsive.
"""

import logging
import re
import sys
from enum import Enum
from typing import Optional, Type

from pydantic import BaseModel

from ai.config import config as ai_config
from ai.providers.gemini import GeminiProvider
from ai.providers.openrouter import OpenRouterProvider

logger = logging.getLogger("ai.router")


class TaskType(Enum):
    THEME_WRAP = "theme_wrap"
    EXPLAIN = "explain"
    HINT = "hint"
    SEMANTIC_VALIDATE = "semantic_validate"
    GENERATE_CONTENT = "generate_content"
    SESSION_SUMMARY = "session_summary"
    STATS_ANALYSIS = "stats_analysis"


# Priority chain per task. "static" means: return None → caller uses fallback.
_ROUTING_TABLE: dict[TaskType, list[str]] = {
    TaskType.THEME_WRAP:        ["gemini", "openrouter", "static"],
    TaskType.EXPLAIN:           ["gemini", "openrouter", "static"],
    TaskType.HINT:              ["gemini", "openrouter", "static"],
    TaskType.SEMANTIC_VALIDATE: ["gemini", "openrouter", "exact_match"],
    TaskType.GENERATE_CONTENT:  ["gemini", "openrouter", "skip"],
    TaskType.SESSION_SUMMARY:   ["gemini", "openrouter", "static"],
    TaskType.STATS_ANALYSIS:    ["gemini", "openrouter", "static"],
}

_TIMEOUTS: dict[str, float] = {
    "gemini": 10.0,
    "openrouter": 12.0,
}

_PROVIDERS: dict = {}

# Errors that mean the provider is misconfigured (bad key, retired model, ...) rather than briefly
# unavailable. The player is told once per session; transient errors (429, 5xx, timeouts) stay quiet.
_CONFIG_ERROR = re.compile(r"^HTTP (?:400|401|403|404)(?!\d)")
_warned: set = set()


def _default_notify(message: str) -> None:
    print(message, file=sys.stderr)


notify = _default_notify  # replaced in tests


def _warn_if_misconfigured(name: str, provider) -> None:
    error = getattr(provider, "last_error", None)
    if name in _warned or not error or not _CONFIG_ERROR.match(error):
        return
    _warned.add(name)
    notify(f"[AI] {name} isn't working ({error}). Falling back to built-in behaviour; "
           "run 'python -m ai.check' to diagnose.")


def _get_provider(name: str):
    """Lazy-initialise providers once."""
    if name not in _PROVIDERS:
        if name == "gemini":
            _PROVIDERS[name] = GeminiProvider()
        elif name == "openrouter":
            _PROVIDERS[name] = OpenRouterProvider()
    return _PROVIDERS.get(name)


def route(task: TaskType, prompt: str, schema: Type[BaseModel]) -> Optional[dict]:
    """Try each provider in priority order; return first valid response or None."""
    if not ai_config.ai_enabled:
        logger.info(f"AI is disabled globally. Skipping routing for task '{task.value}'")
        return None

    logger.info(f"Routing task '{task.value}'")
    logger.debug(f"Prompt: {prompt[:100]}...")
    for provider_name in _ROUTING_TABLE[task]:
        if provider_name in ("static", "skip", "exact_match"):
            logger.info(f"Reached terminal routing state '{provider_name}' for task '{task.value}'")
            return None  # signal to caller: use deterministic fallback

        provider = _get_provider(provider_name)
        if provider is None:
            logger.warning(f"Provider '{provider_name}' is not recognized")
            continue
            
        if not provider.is_available():
            logger.info(f"Provider '{provider_name}' is not available (disabled or missing api key)")
            continue

        timeout = _TIMEOUTS.get(provider_name, 10.0)
        logger.info(f"Attempting provider '{provider_name}' (timeout={timeout}s)")
        try:
            result = provider.generate(prompt, schema, timeout=timeout)
            if result is not None:
                logger.info(f"Successfully generated response using provider '{provider_name}'")
                return result
            logger.warning(f"Provider '{provider_name}' returned None or invalid data")
            _warn_if_misconfigured(provider_name, provider)
        except Exception as e:
            logger.error(f"Provider '{provider_name}' failed with exception: {type(e).__name__}: {str(e)}", exc_info=True)
            continue

    logger.warning(f"All providers failed to generate response for task '{task.value}'")
    return None
