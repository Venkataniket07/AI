"""Gemini REST API provider.

Uses google's generateContent REST endpoint (no SDK dependency).
Instructs the model to output JSON matching the caller-supplied Pydantic schema.
"""

import json
from typing import Optional, Type

import httpx
from pydantic import BaseModel, ValidationError

from .base import BaseProvider
from ai.config import config as ai_config

_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

_SYSTEM_SUFFIX = """
You MUST respond with valid JSON matching the schema below.
Do NOT include any text outside the JSON object.
Do NOT wrap it in markdown code fences.

Schema:
{schema_json}
"""


class GeminiProvider(BaseProvider):
    def __init__(self):
        self._cfg = ai_config.gemini

    def is_available(self) -> bool:
        return self._cfg.enabled and bool(self._cfg.api_key)

    async def generate(self, prompt: str, schema: Type[BaseModel], timeout: float = 8.0) -> Optional[dict]:
        if not self.is_available():
            return None

        schema_json = json.dumps(schema.model_json_schema(), indent=2)
        full_prompt = prompt + "\n\n" + _SYSTEM_SUFFIX.format(schema_json=schema_json)
        url = _BASE_URL.format(model=self._cfg.model)

        payload = {
            "contents": [{"parts": [{"text": full_prompt}]}],
            "generationConfig": {
                "response_mime_type": "application/json",
                "temperature": 0.7,
                "maxOutputTokens": 512,
            },
        }
        params = {"key": self._cfg.api_key}

        raw_text: Optional[str] = None
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(url, json=payload, params=params)
                resp.raise_for_status()
                data = resp.json()
                raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
        except (httpx.TimeoutException, httpx.HTTPStatusError, KeyError, IndexError):
            return None

        return self._parse(raw_text, schema)

    def _parse(self, raw: str, schema: Type[BaseModel]) -> Optional[dict]:
        # Strip accidental markdown fences
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        try:
            obj = json.loads(raw)
            schema.model_validate(obj)
            return obj
        except (json.JSONDecodeError, ValidationError):
            # Retry once: ask the model to fix its JSON
            return None  # outer router will try next provider
