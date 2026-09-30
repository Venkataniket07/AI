"""Health check for the AI providers:  python -m ai.check

Sends one tiny real request to every provider that is configured and reports whether it works, how
long it took, and - if it failed - why and what to change. Exits 0 if at least one provider works.
API keys are never printed.
"""

import logging
import os
import sys
import time
from typing import Optional

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from utils.env import load_dotenv  # noqa: E402

load_dotenv(os.path.join(ROOT, ".env"))  # must run before ai.config reads the environment

import httpx  # noqa: E402

from ai.config import config as ai_config  # noqa: E402
from ai.providers.gemini import GeminiProvider  # noqa: E402
from ai.providers.openrouter import OpenRouterProvider  # noqa: E402
from ai.schemas import SessionSummary  # noqa: E402

# The providers log failures; the report below is the user-facing output, so keep raw log lines off the console.
logging.getLogger("ai").addHandler(logging.NullHandler())

CHECK_PROMPT = "You are a brain-training coach. The player got 80% right. Write one short encouraging sentence."
CHECK_TIMEOUT = 20.0
_SKIP_WORDS = ("tts", "image", "live", "transcribe", "robotics", "computer-use", "lyria", "antigravity",
               "deep-research", "omni", "customtools")


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
    if error.startswith(("HTTP 401", "HTTP 403")):
        env = "GEMINI_API_KEY" if name == "gemini" else "OPENROUTER_API_KEY"
        tips.append(f"The API key was rejected. Create a new key and set {env} in .env.")
    elif error.startswith("HTTP 404") and name == "gemini":
        found = suggest_gemini_models(provider._cfg.api_key)
        tips.append(f"Model '{provider._cfg.model}' is not available. Set GEMINI_MODEL in .env"
                    + (f" to one of: {', '.join(found)}" if found else "."))
    elif error.startswith("HTTP 404"):
        found = suggest_openrouter_models()
        tips.append(f"Model '{provider._cfg.model}' is not available. Set OPENROUTER_MODEL in .env"
                    + (f" to one of: {', '.join(found)}" if found else "."))
    elif error.startswith("HTTP 429"):
        tips.append("Rate limit or free quota reached. Wait a while, or switch to another model.")
    elif "timed out" in error:
        tips.append("The model was too slow. Try a lighter model (e.g. a flash-lite variant).")
    return tips


def check_provider(name: str, provider, timeout: float = CHECK_TIMEOUT) -> tuple[bool, str]:
    """Returns (ok, one-line description). Never raises."""
    if not provider.is_available():
        cfg = provider._cfg
        reason = "no API key set" if not cfg.api_key else "disabled in ai_config.json"
        return False, f"skipped ({reason})"
    start = time.perf_counter()
    try:
        result = provider.generate(CHECK_PROMPT, SessionSummary, timeout=timeout)
    except Exception as e:  # providers should not raise, but a health check must not crash
        return False, f"FAILED: {type(e).__name__}: {e}"
    elapsed = time.perf_counter() - start
    if result is None:
        return False, f"FAILED: {provider.last_error or 'no usable response'}"
    return True, f"OK in {elapsed:.1f}s"


def run(providers: Optional[dict] = None, out=print) -> int:
    providers = providers if providers is not None else {"gemini": GeminiProvider(), "openrouter": OpenRouterProvider()}
    if not ai_config.ai_enabled:
        out("AI is disabled (AI_ENABLED=false or ai_enabled=false in ai_config.json).")
        return 1

    out("AI provider check")
    any_ok = False
    for name, provider in providers.items():
        ok, description = check_provider(name, provider)
        any_ok = any_ok or ok
        model = getattr(provider._cfg, "model", "?")
        out(f"  {'PASS' if ok else 'FAIL'}  {name:<11} model={model}  {description}")
        if not ok and description.startswith("FAILED: "):
            for tip in advice_for(name, description.removeprefix("FAILED: "), provider):
                out(f"        -> {tip}")

    out("Result: " + ("at least one provider works." if any_ok else "no provider works - AI features are off."))
    return 0 if any_ok else 1


if __name__ == "__main__":
    sys.exit(run())
