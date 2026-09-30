"""Health check for the AI providers:  python -m ai.check [--full] [--all-models]

Sends real requests using the game's own prompts and reports, per provider and model, whether the
reply was complete and valid, how long it took, and how many tokens it used. On failure it says why
and what to change. Exits 0 if at least one provider works. API keys are never printed.

By default it sends ONE request per provider (the coaching prompt, which is the one most likely to
fail when a model "thinks" too long) and stops at the first model that passes. Free tiers have small
daily quotas, so use --full (all task prompts) and --all-models (every configured model) sparingly.
"""

import argparse
import copy
import dataclasses
import logging
import os
import sys
import time
from types import SimpleNamespace
from typing import Optional

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from utils.env import load_dotenv  # noqa: E402

load_dotenv(os.path.join(ROOT, ".env"))  # must run before ai.config reads the environment

import httpx  # noqa: E402

from ai.config import config as ai_config  # noqa: E402
from ai.providers.gemini import GeminiProvider  # noqa: E402
from ai.providers.openrouter import OpenRouterProvider  # noqa: E402
from ai.schemas import Explanation, HintResponse, SessionSummary, StatsAnalysis  # noqa: E402

# The providers log failures; the report below is the user-facing output, so keep raw log lines off the console.
logging.getLogger("ai").addHandler(logging.NullHandler())

CHECK_PROMPT = "You are a brain-training coach. The player got 80% right. Write one short encouraging sentence."
CHECK_TIMEOUT = 20.0
_SKIP_WORDS = ("tts", "image", "live", "transcribe", "robotics", "computer-use", "lyria", "antigravity",
               "deep-research", "omni", "customtools")

_SAMPLE_SESSIONS = [
    SimpleNamespace(game_type="mental_math", score=96, accuracy=0.8, reaction_time_ms=12066.0, difficulty=3),
    SimpleNamespace(game_type="anagrams", score=95, accuracy=1.0, reaction_time_ms=50710.0, difficulty=2),
    SimpleNamespace(game_type="anagrams", score=56, accuracy=0.8, reaction_time_ms=85536.0, difficulty=2),
    SimpleNamespace(game_type="mental_math", score=190, accuracy=1.0, reaction_time_ms=5673.0, difficulty=2),
]


def build_tasks(full: bool = False) -> list[tuple[str, str, type]]:
    """(name, prompt, schema) using the game's real prompt templates, so the check exercises real prompts."""
    from ai.services import assist_service, stats_service, summary_service

    tasks = [("session_summary", summary_service.build_prompt("check", 3, _SAMPLE_SESSIONS)[0], SessionSummary)]
    if full:
        tasks += [
            ("stats_analysis", stats_service.build_prompt("check", 3, _SAMPLE_SESSIONS)[0], StatsAnalysis),
            ("hint", assist_service._HINT_PROMPT.format(
                game_type="rankings", puzzle_state="Rank A-E. A ranks above B. B ranks above C.",
                answer="ABCDE", hints_used=0), HintResponse),
            ("explain", assist_service._EXPLAIN_PROMPT.format(
                game_type="direction_sense", question="Alice walks 3m East then 4m North. How far from the start?",
                user_answer="7", correct_answer="5"), Explanation),
        ]
    return tasks


def suggest_gemini_models(api_key: str, limit: int = 6) -> list[str]:
    """Text models the key can use (from Gemini's model list), newest-looking first."""
    try:
        resp = httpx.get("https://generativelanguage.googleapis.com/v1beta/models",
                         headers={"x-goog-api-key": api_key}, params={"pageSize": 200}, timeout=15)
        resp.raise_for_status()
        names = [m["name"].removeprefix("models/") for m in resp.json().get("models", [])
                 if "generateContent" in m.get("supportedGenerationMethods", [])]
    except Exception:
        return []
    names = [n for n in names if n.startswith("gemini") and "flash" in n and not any(w in n for w in _SKIP_WORDS)]
    return sorted(names, reverse=True)[:limit]


def suggest_openrouter_models(limit: int = 6) -> list[str]:
    """Free OpenRouter models that support structured (JSON) output, from the public catalog."""
    try:
        resp = httpx.get("https://openrouter.ai/api/v1/models", timeout=15)
        resp.raise_for_status()
        models = resp.json()["data"]
    except Exception:
        return []
    ids = [m["id"] for m in models if m["id"].endswith(":free")
           and {"structured_outputs", "response_format"} & set(m.get("supported_parameters") or [])]
    return ids[:limit]


def advice_for(name: str, error: str, provider) -> list[str]:
    """Plain-language next steps for a failed provider."""
    tips = []
    model = getattr(provider._cfg, "model", "?")
    if error.startswith(("HTTP 401", "HTTP 403")):
        env = "GEMINI_API_KEY" if name == "gemini" else "OPENROUTER_API_KEY"
        tips.append(f"The API key was rejected. Create a new key and set {env} in .env.")
    elif error.startswith("HTTP 404") and name == "gemini":
        found = suggest_gemini_models(provider._cfg.api_key)
        tips.append(f"Model '{model}' is not available. Set GEMINI_MODEL in .env"
                    + (f" to one of: {', '.join(found)}" if found else "."))
    elif error.startswith("HTTP 404"):
        found = suggest_openrouter_models()
        tips.append(f"Model '{model}' is not available. Set OPENROUTER_MODEL in .env"
                    + (f" to one of: {', '.join(found)}" if found else "."))
    elif "daily free quota" in error:
        tips.append("This model's free requests for today are used up. Add more models to GEMINI_MODEL "
                    "(comma-separated) so the next one takes over, or wait for the daily reset.")
    elif error.startswith("HTTP 429"):
        tips.append("Rate limit reached. Wait a moment, or switch to another model.")
    elif "cut off" in error:
        tips.append("The model used its whole reply budget (usually on hidden reasoning). "
                    "Choose a model that doesn't think at length.")
    elif "timed out" in error:
        tips.append("The model was too slow. Try a lighter model (e.g. a flash-lite variant).")
    return tips


def _model_names(provider) -> list[str]:
    models = getattr(provider, "_models", None)
    return models() if callable(models) else [getattr(provider._cfg, "model", "?")]


def _with_model(provider, model: str):
    """A copy of `provider` restricted to a single model (so each model is tested on its own)."""
    if not hasattr(provider, "_models"):
        return provider
    clone = copy.copy(provider)
    clone._cfg = dataclasses.replace(provider._cfg, model=model)
    return clone


def check_provider(name: str, provider, prompt: str = CHECK_PROMPT, schema=SessionSummary,
                   timeout: float = CHECK_TIMEOUT) -> tuple[bool, str]:
    """Returns (ok, one-line description). Never raises."""
    if not provider.is_available():
        cfg = provider._cfg
        reason = "no API key set" if not cfg.api_key else "disabled in ai_config.json"
        return False, f"skipped ({reason})"
    start = time.perf_counter()
    try:
        result = provider.generate(prompt, schema, timeout=timeout)
    except Exception as e:  # providers should not raise, but a health check must not crash
        return False, f"FAILED: {type(e).__name__}: {e}"
    elapsed = time.perf_counter() - start
    if result is None:
        return False, f"FAILED: {provider.last_error or 'no usable response'}"
    usage = getattr(provider, "last_usage", None) or {}
    detail = ""
    if usage:
        detail = (f" (finish={usage.get('finish_reason')}, thinking={usage.get('thinking_tokens', 0)}, "
                  f"output={usage.get('output_tokens', 0)} tokens)")
    return True, f"OK in {elapsed:.1f}s{detail}"


def run(providers: Optional[dict] = None, out=print, full: bool = False, all_models: bool = False) -> int:
    providers = providers if providers is not None else {"gemini": GeminiProvider(), "openrouter": OpenRouterProvider()}
    if not ai_config.ai_enabled:
        out("AI is disabled (AI_ENABLED=false or ai_enabled=false in ai_config.json).")
        return 1

    tasks = build_tasks(full)
    out("AI provider check" + ("  (all task prompts)" if full else "  (coaching prompt)"))
    any_ok = False
    for name, provider in providers.items():
        provider_ok = False
        for model in _model_names(provider):
            if provider_ok and not all_models:
                out(f"  ----  {name:<11} model={model}  not tested (an earlier model passed; use --all-models)")
                continue
            target = _with_model(provider, model)
            model_ok = True
            for task_name, prompt, schema in tasks:
                ok, description = check_provider(name, target, prompt, schema)
                model_ok = model_ok and ok
                out(f"  {'PASS' if ok else 'FAIL'}  {name:<11} model={model}  [{task_name}]  {description}")
                if not ok and description.startswith("FAILED: "):
                    for tip in advice_for(name, description.removeprefix("FAILED: "), target):
                        out(f"        -> {tip}")
            provider_ok = provider_ok or model_ok
        any_ok = any_ok or provider_ok

    out("Result: " + ("at least one provider works." if any_ok else "no provider works - AI features are off."))
    return 0 if any_ok else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Check that the configured AI providers work.")
    parser.add_argument("--full", action="store_true", help="test every task prompt, not just coaching")
    parser.add_argument("--all-models", action="store_true", help="test every configured model, not just until one passes")
    args = parser.parse_args()
    sys.exit(run(full=args.full, all_models=args.all_models))
