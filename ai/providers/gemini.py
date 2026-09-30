"""Gemini REST API provider (generateContent endpoint, no SDK dependency).

`model` may be a comma-separated list ("gemini-3.1-flash-lite,gemini-2.5-flash"). Models are tried
in order: each free-tier model has its own daily request quota, so when one is used up the next
one keeps the game working. A model whose daily quota is exhausted is skipped for a while instead
of being asked again on every call.
"""

import json
import logging
import time
from typing import Optional, Type

import httpx
from pydantic import BaseModel

from .base import (
    MAX_OUTPUT_TOKENS,
    SCHEMA_INSTRUCTIONS,
    BaseProvider,
    describe_http_error,
    is_daily_quota_error,
    parse_model_json,
    post_with_retry,
)
from ai.config import config as ai_config

logger = logging.getLogger("ai.provider.gemini")

_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
EXHAUSTED_SKIP_SECONDS = 3600  # how long a model with a used-up daily quota is skipped
_MIN_BUDGET = 1.0              # don't start another model with less than this many seconds left


class _Attempt:
    """Outcome of one model attempt: a result, or an error with a kind used to decide what to do next."""

    def __init__(self, result=None, error=None, kind=None):
        self.result, self.error, self.kind = result, error, kind  # kind: quota_day | quota_rate | config | other


class GeminiProvider(BaseProvider):
    def __init__(self):
        self._cfg = ai_config.gemini
        self._exhausted: dict[str, float] = {}     # model -> monotonic time until which it is skipped
        self._no_thinking_config: set[str] = set()  # models that rejected the thinking setting

    def is_available(self) -> bool:
        return self._cfg.enabled and bool(self._cfg.api_key)

    def _models(self) -> list[str]:
        return [m.strip() for m in self._cfg.model.split(",") if m.strip()]

    def _thinking_config(self, model: str) -> Optional[dict]:
        """Turn thinking off for Flash models: the game needs a short JSON answer, not reasoning."""
        if "flash" not in model or model in self._no_thinking_config:
            return None
        return {"thinkingBudget": 0}

    def generate(self, prompt: str, schema: Type[BaseModel], timeout: float = 8.0) -> Optional[dict]:
        if not self.is_available():
            return None

        schema_json = json.dumps(schema.model_json_schema(), indent=2)
        full_prompt = prompt + "\n\n" + SCHEMA_INSTRUCTIONS.format(schema_json=schema_json)
        deadline = time.monotonic() + timeout

        self.last_error, self.last_usage, self.last_model = None, {}, None
        failures: list[tuple[str, _Attempt]] = []
        for model in self._models():
            if self._exhausted.get(model, 0) > time.monotonic():
                failures.append((model, _Attempt(error="daily free quota used up", kind="quota_day")))
                continue
            remaining = deadline - time.monotonic()
            if remaining < _MIN_BUDGET and failures:
                break
            attempt = self._try_model(model, full_prompt, schema, max(remaining, _MIN_BUDGET))
            if attempt.result is not None:
                self.last_model = model
                return attempt.result
            failures.append((model, attempt))

        self.last_error = self._summarise(failures)
        return None

    def _summarise(self, failures: list[tuple[str, "_Attempt"]]) -> Optional[str]:
        if not failures:
            return "no model configured"
        if all(a.kind == "quota_day" for _, a in failures):
            names = ", ".join(m for m, _ in failures)
            return f"HTTP 429: daily free quota used up for {names} (it resets about midnight Pacific time)"
        # Report the most actionable problem first: a bad key/model beats a quota or format issue.
        for _, attempt in failures:
            if attempt.kind == "config":
                return attempt.error
        model, attempt = failures[-1]
        suffix = f" [{model}]" if len(failures) > 1 else ""
        return f"{attempt.error}{suffix}"

    def _try_model(self, model: str, prompt: str, schema: Type[BaseModel], budget: float) -> _Attempt:
        deadline = time.monotonic() + budget
        headers = {"x-goog-api-key": self._cfg.api_key}
        url = _BASE_URL.format(model=model)

        for _ in range(2):  # the second pass only happens if the model rejects the thinking setting
            generation = {
                "response_mime_type": "application/json",
                "temperature": 0.7,
                "maxOutputTokens": MAX_OUTPUT_TOKENS,
            }
            thinking = self._thinking_config(model)
            if thinking:
                generation["thinkingConfig"] = thinking
            payload = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": generation}

            try:
                with httpx.Client(timeout=budget) as client:
                    logger.debug("Gemini API request payload: %s", json.dumps(payload))
                    resp = post_with_retry(client, url, timeout=max(deadline - time.monotonic(), 0.5),
                                           json=payload, headers=headers)
                    logger.info("Gemini API response status (%s): %s", model, resp.status_code)
                    logger.debug("Gemini API response text: %s", resp.text)
            except httpx.TimeoutException:
                logger.error("Gemini request timed out (%s)", model)
                return _Attempt(error="request timed out", kind="other")
            except Exception as e:
                logger.error("Gemini error: %s: %s", type(e).__name__, e, exc_info=True)
                text = f"{type(e).__name__}: {e}".replace(self._cfg.api_key, "***")[:140]
                return _Attempt(error=text, kind="other")

            if resp.status_code == 400 and thinking and "think" in resp.text.lower():
                logger.warning("%s rejected the thinking setting; retrying without it", model)
                self._no_thinking_config.add(model)
                continue
            if resp.status_code != 200:
                return self._http_failure(model, resp)
            return self._read_reply(model, resp, schema)
        return _Attempt(error="request was rejected", kind="config")

    def _http_failure(self, model: str, resp: httpx.Response) -> _Attempt:
        logger.error("Gemini HTTP error %s (%s): %s", resp.status_code, model, resp.text)
        message = describe_http_error(resp, [self._cfg.api_key])
        if is_daily_quota_error(resp):
            self._exhausted[model] = time.monotonic() + EXHAUSTED_SKIP_SECONDS
            return _Attempt(error=message, kind="quota_day")
        if resp.status_code == 429:
            return _Attempt(error=message, kind="quota_rate")
        if resp.status_code in (400, 401, 403, 404):
            return _Attempt(error=message, kind="config")
        return _Attempt(error=message, kind="other")

    def _read_reply(self, model: str, resp: httpx.Response, schema: Type[BaseModel]) -> _Attempt:
        try:
            data = resp.json()
            candidate = (data.get("candidates") or [{}])[0]
            usage = data.get("usageMetadata") or {}
        except ValueError:
            return _Attempt(error="response was not valid JSON", kind="other")

        finish = candidate.get("finishReason")
        thinking_tokens = usage.get("thoughtsTokenCount", 0)
        self.last_usage = {"finish_reason": finish, "thinking_tokens": thinking_tokens,
                           "output_tokens": usage.get("candidatesTokenCount", 0)}
        text = "".join(p.get("text", "") for p in (candidate.get("content") or {}).get("parts") or [])
        logger.debug("Gemini API extracted response content: %s", text)

        if finish == "MAX_TOKENS":
            return _Attempt(kind="other", error=f"reply cut off (MAX_TOKENS; {thinking_tokens} thinking tokens used)")
        if not text:
            return _Attempt(kind="other", error=f"no content returned (finishReason={finish})")
        result = parse_model_json(text, schema, "Gemini")
        if result is None:
            return _Attempt(kind="other", error="response was not valid JSON for the expected schema")
        return _Attempt(result=result)
