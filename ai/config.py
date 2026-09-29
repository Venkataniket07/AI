"""AI configuration loader.

Reads ai_config.json from the project root and exposes a typed AIConfig singleton.
Falls back to AI-disabled state on any read/parse error (silent degradation).
"""

import json
import os
from dataclasses import dataclass, field

_CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ai_config.json")
_ENV_GEMINI_KEY = "GEMINI_API_KEY"
_ENV_OPENROUTER_KEY = "OPENROUTER_API_KEY"

FIXED_THEMES = ["mystery", "sci-fi", "sports", "fantasy"]


@dataclass
class GeminiConfig:
    enabled: bool
    api_key: str
    model: str


@dataclass
class OpenRouterConfig:
    enabled: bool
    api_key: str
    model: str


@dataclass
class OllamaConfig:
    enabled: bool
    base_url: str
    models: dict = field(default_factory=dict)


@dataclass
class CacheConfig:
    enabled: bool
    ttl_seconds: int


@dataclass
class AIConfig:
    ai_enabled: bool
    gemini: GeminiConfig
    openrouter: OpenRouterConfig
    ollama: OllamaConfig
    cache: CacheConfig
    themes: list[str] = field(default_factory=lambda: FIXED_THEMES)


def _load() -> AIConfig:
    _disabled = AIConfig(
        ai_enabled=False,
        gemini=GeminiConfig(enabled=False, api_key="", model=""),
        openrouter=OpenRouterConfig(enabled=False, api_key="", model=""),
        ollama=OllamaConfig(enabled=False, base_url=""),
        cache=CacheConfig(enabled=False, ttl_seconds=3600),
    )

    try:
        with open(_CONFIG_PATH, "r") as f:
            raw = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return _disabled

    env_ai_enabled = os.environ.get("AI_ENABLED", "").strip().lower()
    if env_ai_enabled in ("true", "1", "yes", "on"):
        is_ai_enabled = True
    elif env_ai_enabled in ("false", "0", "no", "off"):
        is_ai_enabled = False
    else:
        is_ai_enabled = raw.get("ai_enabled", False)

    if not is_ai_enabled:
        return _disabled

    p = raw.get("providers", {})
    g = p.get("gemini", {})
    o = p.get("openrouter", {})
    ol = p.get("ollama", {})
    ca = raw.get("cache", {})

    # API keys and models: prefer .env over config file
    gemini_key = os.environ.get(_ENV_GEMINI_KEY, "") or g.get("api_key", "")
    or_key = os.environ.get(_ENV_OPENROUTER_KEY, "") or o.get("api_key", "")
    
    gemini_model = os.environ.get("GEMINI_MODEL", "") or g.get("model", "gemini-2.0-flash")
    or_model = os.environ.get("OPENROUTER_MODEL", "") or o.get("model", "")

    return AIConfig(
        ai_enabled=True,
        gemini=GeminiConfig(
            enabled=g.get("enabled", False) and bool(gemini_key),
            api_key=gemini_key,
            model=gemini_model,
        ),
        openrouter=OpenRouterConfig(
            enabled=o.get("enabled", False) and bool(or_key),
            api_key=or_key,
            model=or_model,
        ),
        ollama=OllamaConfig(
            enabled=ol.get("enabled", False),
            base_url=ol.get("base_url", "http://localhost:11434"),
            models=ol.get("models", {}),
        ),
        cache=CacheConfig(
            enabled=ca.get("enabled", True),
            ttl_seconds=ca.get("ttl_seconds", 3600),
        ),
        themes=raw.get("themes", FIXED_THEMES),
    )


# Module-level singleton — load once at import time
config: AIConfig = _load()

