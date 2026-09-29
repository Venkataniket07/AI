"""Statistics analysis service — generates a comprehensive analysis of user performance."""

from typing import Optional

from ai.config import config as ai_config
from ai.router import route, TaskType
from ai.schemas import StatsAnalysis
from ai.utils import cache_key, load_prompt

_PROMPT_TEMPLATE = load_prompt("stats_analysis")


def _aggregate_stats(sessions: list) -> str:
    if not sessions:
        return "No games played yet."

    stats_by_game = {}
    for s in sessions:
        if s.game_type not in stats_by_game:
            stats_by_game[s.game_type] = {"count": 0, "score": 0, "accuracy": 0, "reaction_time_ms": 0}

        stats_by_game[s.game_type]["count"] += 1
        stats_by_game[s.game_type]["score"] += s.score
        stats_by_game[s.game_type]["accuracy"] += s.accuracy
        stats_by_game[s.game_type]["reaction_time_ms"] += s.reaction_time_ms

    lines = []
    for game, data in stats_by_game.items():
        count = data["count"]
        avg_score = data["score"] / count
        avg_acc = data["accuracy"] / count
        avg_rx = data["reaction_time_ms"] / count

        lines.append(
            f"  {game}: played {count} times, avg score={avg_score:.1f}, "
            f"avg accuracy={avg_acc*100:.1f}%, avg reaction={avg_rx:.0f}ms"
        )
    return "\n".join(lines)


def analyze_stats(
    username: str,
    level: int,
    sessions: list,
    db_manager=None,
) -> Optional[str]:
    """
    Returns a 3-4 sentence analysis string based on aggregated stats.
    """
    if not ai_config.ai_enabled or not sessions:
        return None

    stats_text = _aggregate_stats(sessions)
    key = cache_key("stats_analysis", username.lower(), stats_text)

    if db_manager and ai_config.cache.enabled:
        cached = db_manager.cache_get(key)
        if cached:
            return cached

    prompt = _PROMPT_TEMPLATE.format(
        username=username,
        level=level,
        total_games=len(sessions),
        stats_summary=stats_text,
    )

    result = route(TaskType.STATS_ANALYSIS, prompt, StatsAnalysis)
    if result is None:
        return None

    analysis_text = StatsAnalysis(**result).analysis

    if db_manager and ai_config.cache.enabled:
        db_manager.cache_set(key, analysis_text, ai_config.cache.ttl_seconds)

    return analysis_text
