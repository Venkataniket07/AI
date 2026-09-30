"""Abstract base provider interface and shared response parsing."""

import json
import logging
import time
from abc import ABC, abstractmethod
from typing import Optional, Type

import httpx
from pydantic import BaseModel, ValidationError

logger = logging.getLogger("ai.provider")

SCHEMA_INSTRUCTIONS = """You MUST respond with valid JSON matching the schema below.
Do NOT include any text outside the JSON object.
Do NOT wrap it in markdown code fences.

Schema:
{schema_json}"""


RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})
_MAX_RETRY_AFTER = 2.0  # never sleep longer than this on a Retry-After header
_sleep = time.sleep  # replaced in tests


def post_with_retry(
    client: httpx.Client, url: str, *, timeout: float, retries: int = 1, backoff: float = 0.5, **kwargs
) -> httpx.Response:
    """
    POST with retries on transient HTTP statuses (429/5xx).

    `timeout` is a total time budget: every attempt gets only the time that is left, so retrying
    never makes a call slower than the caller's timeout. A timed-out attempt is not retried
    (the budget is gone). Returns the final response; the caller checks the status.
    """
    deadline = time.monotonic() + timeout
    attempt = 0
    while True:
        remaining = deadline - time.monotonic()
        resp = client.post(url, timeout=max(remaining, 0.1), **kwargs)
        if resp.status_code not in RETRY_STATUSES or attempt >= retries:
            return resp

        delay = backoff * (2 ** attempt)
        retry_after = resp.headers.get("Retry-After", "")
        if retry_after.isdigit():
            delay = max(delay, min(float(retry_after), _MAX_RETRY_AFTER))
        if deadline - time.monotonic() <= delay + 1.0:  # not enough budget for a useful retry
            return resp
        logger.warning("HTTP %s from %s; retrying in %.1fs", resp.status_code, url.split("?")[0], delay)
        _sleep(delay)
        attempt += 1


def parse_model_json(raw: str, schema: Type[BaseModel], provider: str) -> Optional[dict]:
    """Strip accidental markdown fences, parse JSON and validate it against `schema`."""
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
        logger.error("%s JSON parse/validation error: %s: %s. Raw content was: %s",
                     provider, type(e).__name__, e, raw)
        return None


def describe_http_error(resp: httpx.Response, secrets=()) -> str:
    """One-line description of a failed response, e.g. 'HTTP 404: model not found'. Secrets are redacted."""
    message = ""
    try:
        body = resp.json()
        err = body.get("error", body) if isinstance(body, dict) else {}
        message = err.get("message", "") if isinstance(err, dict) else str(err)
    except ValueError:
        message = resp.text
    message = " ".join(str(message).split())[:140]
    for secret in secrets:
        if secret:
            message = message.replace(secret, "***")
    return f"HTTP {resp.status_code}: {message}" if message else f"HTTP {resp.status_code}"


class BaseProvider(ABC):
    last_error: Optional[str] = None  # why the most recent generate() returned None; None after a success

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if this provider is configured."""

    @abstractmethod
    def generate(self, prompt: str, schema: Type[BaseModel], timeout: float = 8.0) -> Optional[dict]:
        """
        Send prompt to the model, parse JSON, validate against schema.
        Returns a schema-valid dict or None on any failure.
        """
