"""Gemini REST API provider (generateContent endpoint, no SDK dependency)."""

import json
import logging
from typing import Optional, Type

import httpx
from pydantic import BaseModel

from .base import BaseProvider, SCHEMA_INSTRUCTIONS, parse_model_json
from ai.config import config as ai_config

logger = logging.getLogger("ai.provider.gemini")

_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


class GeminiProvider(BaseProvider):
    def __init__(self):
        self._cfg = ai_config.gemini

    def is_available(self) -> bool:
        return self._cfg.enabled and bool(self._cfg.api_key)

    def generate(self, prompt: str, schema: Type[BaseModel], timeout: float = 8.0) -> Optional[dict]:
        if not self.is_available():
            return None

        schema_json = json.dumps(schema.model_json_schema(), indent=2)
        full_prompt = prompt + "\n\n" + SCHEMA_INSTRUCTIONS.format(schema_json=schema_json)
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

        try:
            with httpx.Client(timeout=timeout) as client:
                logger.debug("Gemini API request payload: %s", json.dumps(payload))
                resp = client.post(url, json=payload, headers=headers)
                logger.info("Gemini API response status: %s", resp.status_code)
                logger.debug("Gemini API response text: %s", resp.text)
                resp.raise_for_status()
                raw_text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
                logger.debug("Gemini API extracted response content: %s", raw_text)
        except httpx.HTTPStatusError as e:
            logger.error("Gemini HTTP error %s: %s", e.response.status_code, e.response.text)
            return None
        except httpx.TimeoutException:
            logger.error("Gemini request timed out")
            return None
        except Exception as e:
            logger.error("Gemini error: %s: %s", type(e).__name__, e, exc_info=True)
            return None

        return parse_model_json(raw_text, schema, "Gemini")
