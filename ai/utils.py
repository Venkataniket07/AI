"""Helpers shared by the AI services."""

import hashlib
import os

_PROMPT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prompts")


def load_prompt(name: str) -> str:
    """Read ai/prompts/<name>.txt."""
    with open(os.path.join(_PROMPT_DIR, f"{name}.txt"), "r", encoding="utf-8") as f:
        return f.read()


def cache_key(namespace: str, *parts: str) -> str:
    """Namespaced, collision-safe cache key (parts are length-prefixed before hashing)."""
    raw = "".join(f"{len(p)}:{p}" for p in parts)
    return f"{namespace}:{hashlib.sha256(raw.encode('utf-8')).hexdigest()}"
