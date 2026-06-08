"""Abstract base provider interface."""

from abc import ABC, abstractmethod
from typing import Optional, Type
from pydantic import BaseModel


class BaseProvider(ABC):
    @abstractmethod
    def is_available(self) -> bool:
        """Return True if this provider is configured and reachable."""

    @abstractmethod
    async def generate(self, prompt: str, schema: Type[BaseModel], timeout: float = 8.0) -> Optional[dict]:
        """
        Send prompt to the model, parse JSON, validate against schema.
        Returns a schema-valid dict or None on any failure.
        """
