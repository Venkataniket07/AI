"""Statistics analysis service — generates a comprehensive analysis of user performance."""

from typing import Optional

from ai.config import config as ai_config
from ai.context import game_history_facts
from ai.router import route, TaskType
from ai.schemas import StatsAnalysis
from ai.utils import cache_key, load_prompt
from core.insights import compute_insights, template_text, text_consistent

_PROMPT_TEMPLATE = load_prompt("stats_analysis")


def build_prompt(username: str, level: int, sessions: list) -> tuple[str, str]:
    """(prompt, facts). `sessions` is newest first."""
    facts = game_history_facts(sessions)
    prompt = _PROMPT_TEMPLATE.format(username=username, level=level, total_games=len(sessions), stats_summary=facts)
    return prompt, facts


def analyze_stats(
    username: str,
    level: int,
    sessions: list,
    db_manager=None,
) -> Optional[str]:
    """
    Returns a 3 sentence analysis string based on per-game facts.
    """
    if not ai_config.ai_enabled or not sessions:
        return None

    prompt, facts = build_prompt(username, level, sessions)
    key = cache_key("stats_analysis", username.lower(), str(level), facts)

    if db_manager and ai_config.cache.enabled:
        cached = db_manager.cache_get(key)
        if cached:
            return cached

    result = route(TaskType.STATS_ANALYSIS, prompt, StatsAnalysis)
    if result is None:
        return None

    analysis_text = StatsAnalysis(**result).analysis
    insight = compute_insights(sessions)
    if not text_consistent(analysis_text, insight):
        analysis_text = template_text(insight)  # the model contradicted the app's own facts

    if db_manager and ai_config.cache.enabled:
        db_manager.cache_set(key, analysis_text, ai_config.cache.ttl_seconds)

    return analysis_text
