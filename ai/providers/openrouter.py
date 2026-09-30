"""OpenRouter provider (OpenAI-compatible REST API)."""

import json
import logging
from typing import Optional, Type

import httpx
from pydantic import BaseModel

from .base import BaseProvider, SCHEMA_INSTRUCTIONS, describe_http_error, parse_model_json, post_with_retry
from ai.config import config as ai_config

logger = logging.getLogger("ai.provider.openrouter")

_BASE_URL = "https://openrouter.ai/api/v1/chat/completions"


class OpenRouterProvider(BaseProvider):
    def __init__(self):
        self._cfg = ai_config.openrouter

    def is_available(self) -> bool:
        return self._cfg.enabled and bool(self._cfg.api_key)

    def generate(self, prompt: str, schema: Type[BaseModel], timeout: float = 10.0) -> Optional[dict]:
        if not self.is_available():
            return None

        schema_json = json.dumps(schema.model_json_schema(), indent=2)
        payload = {
            "model": self._cfg.model,
            "messages": [
                {"role": "system", "content": SCHEMA_INSTRUCTIONS.format(schema_json=schema_json)},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.7,
            "max_tokens": 512,
        }
        headers = {
            "Authorization": f"Bearer {self._cfg.api_key}",
            "Content-Type": "application/json",
        }

        self.last_error = None
        try:
            with httpx.Client(timeout=timeout) as client:
                logger.debug("OpenRouter API request payload: %s", json.dumps(payload))
                resp = post_with_retry(client, _BASE_URL, timeout=timeout, json=payload, headers=headers)
                logger.info("OpenRouter API response status: %s", resp.status_code)
                logger.debug("OpenRouter API response text: %s", resp.text)
                resp.raise_for_status()
                raw = resp.json()["choices"][0]["message"]["content"]
                logger.debug("OpenRouter API extracted response content: %s", raw)
        except httpx.HTTPStatusError as e:
            logger.error("OpenRouter HTTP error %s: %s", e.response.status_code, e.response.text)
            self.last_error = describe_http_error(e.response, [self._cfg.api_key])
            return None
        except httpx.TimeoutException:
            logger.error("OpenRouter request timed out")
            self.last_error = "request timed out"
            return None
        except Exception as e:
            logger.error("OpenRouter error: %s: %s", type(e).__name__, e, exc_info=True)
            self.last_error = f"{type(e).__name__}: {e}".replace(self._cfg.api_key, "***")[:140]
            return None

        result = parse_model_json(raw, schema, "OpenRouter")
        if result is None:
            self.last_error = "response was not valid JSON for the expected schema"
        return result
