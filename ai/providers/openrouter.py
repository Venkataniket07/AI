"""OpenRouter provider (OpenAI-compatible REST API)."""

import json
import logging
import time
from typing import Optional, Type

import httpx
from pydantic import BaseModel

from .base import (
    MAX_OUTPUT_TOKENS,
    RETRY_STATUSES,
    SCHEMA_INSTRUCTIONS,
    BaseProvider,
    describe_http_error,
    parse_model_json,
    post_with_retry,
)
from . import base
from ai.config import config as ai_config

logger = logging.getLogger("ai.provider.openrouter")

_BASE_URL = "https://openrouter.ai/api/v1/chat/completions"


class OpenRouterProvider(BaseProvider):
    def __init__(self):
        self._cfg = ai_config.openrouter
        self._reasoning_off = True  # cleared if the model refuses to run without reasoning

    def is_available(self) -> bool:
        return self._cfg.enabled and bool(self._cfg.api_key)

    @staticmethod
    def _body_error(data) -> tuple:
        """(code, message) of an error object in the response body, or (None, "") if there is none."""
        err = data.get("error") if isinstance(data, dict) else None
        if not err:
            return None, ""
        if not isinstance(err, dict):
            return None, " ".join(str(err).split())
        code = err.get("code")
        return (code if isinstance(code, int) else None), " ".join(str(err.get("message", "")).split())

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
            "max_tokens": MAX_OUTPUT_TOKENS,
        }
        if self._reasoning_off:
            # Reasoning models otherwise spend the whole reply budget thinking (nemotron used 2000+ tokens).
            payload["reasoning"] = {"enabled": False}
        headers = {
            "Authorization": f"Bearer {self._cfg.api_key}",
            "Content-Type": "application/json",
        }

        self.last_error, self.last_usage, self.last_model = None, {}, None
        deadline = time.monotonic() + timeout
        try:
            with httpx.Client(timeout=timeout) as client:
                logger.debug("OpenRouter API request payload: %s", json.dumps(payload))
                for attempt in range(2):
                    resp = post_with_retry(client, _BASE_URL, timeout=max(deadline - time.monotonic(), 0.5),
                                           json=payload, headers=headers)
                    logger.info("OpenRouter API response status: %s", resp.status_code)
                    logger.debug("OpenRouter API response text: %s", resp.text)
                    resp.raise_for_status()
                    data = resp.json()
                    code, message = self._body_error(data)
                    # OpenRouter reports upstream failures as HTTP 200 with an "error" object in the body.
                    transient = code in RETRY_STATUSES and attempt == 0 and deadline - time.monotonic() > 2.0
                    if not transient:
                        break
                    logger.warning("OpenRouter upstream error %s (%s); retrying once", code, message)
                    base._sleep(0.5)
        except httpx.HTTPStatusError as e:
            if (e.response.status_code == 400 and self._reasoning_off
                    and "reasoning" in e.response.text.lower()):
                logger.warning("OpenRouter model %s rejected reasoning=off; retrying without it", self._cfg.model)
                self._reasoning_off = False
                return self.generate(prompt, schema, timeout)
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

        if message or code:
            logger.error("OpenRouter returned an error in a 200 response: %s %s", code, message)
            label = f"HTTP {code}" if code else "provider error"
            self.last_error = f"{label}: {message}".replace(self._cfg.api_key, "***")[:160]
            return None

        choice = (data.get("choices") or [{}])[0]
        usage = data.get("usage") or {}
        finish = choice.get("finish_reason")
        reasoning_tokens = (usage.get("completion_tokens_details") or {}).get("reasoning_tokens", 0)
        self.last_usage = {"finish_reason": finish, "thinking_tokens": reasoning_tokens,
                           "output_tokens": usage.get("completion_tokens", 0)}
        # Only `content` is the answer. Reasoning models also return a separate `reasoning` field,
        # which is deliberately never used.
        content = (choice.get("message") or {}).get("content") or ""
        logger.debug("OpenRouter API extracted response content: %s", content)

        if finish == "length":
            self.last_error = f"reply cut off (finish_reason=length; {reasoning_tokens} reasoning tokens used)"
            return None
        if not content.strip():
            self.last_error = f"no content returned (finish_reason={finish})"
            return None

        result = parse_model_json(content, schema, "OpenRouter")
        if result is None:
            self.last_error = "response was not valid JSON for the expected schema"
            return None
        self.last_model = self._cfg.model
        return result
