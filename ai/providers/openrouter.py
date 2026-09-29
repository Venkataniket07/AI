"""OpenRouter provider (OpenAI-compatible REST API)."""

import json
import logging
from typing import Optional, Type

import httpx
from pydantic import BaseModel, ValidationError

from .base import BaseProvider
from ai.config import config as ai_config

logger = logging.getLogger("ai.provider.openrouter")

_BASE_URL = "https://openrouter.ai/api/v1/chat/completions"

_SYSTEM_MSG = """You MUST respond with valid JSON matching the schema below.
Do NOT include any text outside the JSON object.
Do NOT wrap it in markdown code fences.

Schema:
{schema_json}"""


class OpenRouterProvider(BaseProvider):
    def __init__(self):
        self._cfg = ai_config.openrouter

    def is_available(self) -> bool:
        return self._cfg.enabled and bool(self._cfg.api_key)

    async def generate(self, prompt: str, schema: Type[BaseModel], timeout: float = 10.0) -> Optional[dict]:
        if not self.is_available():
            return None

        schema_json = json.dumps(schema.model_json_schema(), indent=2)
        payload = {
            "model": self._cfg.model,
            "messages": [
                {"role": "system", "content": _SYSTEM_MSG.format(schema_json=schema_json)},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.7,
            "max_tokens": 512,
        }
        headers = {
            "Authorization": f"Bearer {self._cfg.api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                logged_headers = headers.copy()
                if "Authorization" in logged_headers:
                    logged_headers["Authorization"] = "Bearer ***"
                logger.debug(f"OpenRouter API request headers: {logged_headers}")
                logger.debug(f"OpenRouter API request payload: {json.dumps(payload)}")
                resp = await client.post(_BASE_URL, json=payload, headers=headers)
                logger.info(f"OpenRouter API response status: {resp.status_code}")
                logger.debug(f"OpenRouter API response text: {resp.text}")
                resp.raise_for_status()
                raw = resp.json()["choices"][0]["message"]["content"]
                logger.debug(f"OpenRouter API extracted response content: {raw}")
        except httpx.HTTPStatusError as e:
            logger.error(f"OpenRouter HTTP error {e.response.status_code}: {e.response.text}", exc_info=True)
            return None
        except httpx.TimeoutException:
            logger.error("OpenRouter request timed out", exc_info=True)
            return None
        except Exception as e:
            logger.error(f"OpenRouter error: {type(e).__name__}: {str(e)}", exc_info=True)
            return None

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
            logger.error(f"OpenRouter JSON parse/validation error: {type(e).__name__}: {str(e)}. Raw content was: {raw}", exc_info=True)
            return None
