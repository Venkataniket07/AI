"""Gemini REST API provider.

Uses google's generateContent REST endpoint (no SDK dependency).
Instructs the model to output JSON matching the caller-supplied Pydantic schema.
"""

import json
import logging
from typing import Optional, Type

import httpx
from pydantic import BaseModel, ValidationError

from .base import BaseProvider
from ai.config import config as ai_config

logger = logging.getLogger("ai.provider.gemini")

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
        headers = {"x-goog-api-key": self._cfg.api_key}

        raw_text: Optional[str] = None
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                logger.debug(f"Gemini API request payload: {json.dumps(payload)}")
                resp = await client.post(url, json=payload, headers=headers)
                logger.info(f"Gemini API response status: {resp.status_code}")
                logger.debug(f"Gemini API response text: {resp.text}")
                resp.raise_for_status()
                data = resp.json()
                raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
                logger.debug(f"Gemini API extracted response content: {raw_text}")
        except httpx.HTTPStatusError as e:
            logger.error(f"Gemini HTTP error {e.response.status_code}: {e.response.text}", exc_info=True)
            return None
        except httpx.TimeoutException:
            logger.error("Gemini request timed out", exc_info=True)
            return None
        except Exception as e:
            logger.error(f"Gemini error: {type(e).__name__}: {str(e)}", exc_info=True)
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
        except (json.JSONDecodeError, ValidationError) as e:
            logger.error(f"Gemini JSON parse/validation error: {type(e).__name__}: {str(e)}. Raw content was: {raw}", exc_info=True)
            return None  # outer router will try next provider
