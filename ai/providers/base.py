"""Abstract base provider interface and shared response parsing."""

import json
import logging
from abc import ABC, abstractmethod
from typing import Optional, Type

from pydantic import BaseModel, ValidationError

logger = logging.getLogger("ai.provider")

SCHEMA_INSTRUCTIONS = """You MUST respond with valid JSON matching the schema below.
Do NOT include any text outside the JSON object.
Do NOT wrap it in markdown code fences.

Schema:
{schema_json}"""


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


class BaseProvider(ABC):
    @abstractmethod
    def is_available(self) -> bool:
        """Return True if this provider is configured."""

    @abstractmethod
    def generate(self, prompt: str, schema: Type[BaseModel], timeout: float = 8.0) -> Optional[dict]:
        """
        Send prompt to the model, parse JSON, validate against schema.
        Returns a schema-valid dict or None on any failure.
        """
