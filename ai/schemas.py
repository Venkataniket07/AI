"""Pydantic response schemas for all AI tasks.

All AI providers must return JSON that validates against one of these models.
"""

from typing import Annotated

from pydantic import BaseModel, BeforeValidator, Field


def _clip(limit: int):
    """Trim an over-long reply at a word boundary instead of rejecting it (the schema still states the limit)."""
    def clip(value):
        if isinstance(value, str) and len(value) > limit:
            cut = value[:limit - 1].rsplit(" ", 1)[0].rstrip(" ,;:-")
            return (cut or value[:limit - 1]) + "…"
        return value
    return BeforeValidator(clip)


def Text(limit: int, description: str = "") -> object:
    """A string of at most `limit` characters; longer model output is trimmed."""
    return Annotated[str, _clip(limit), Field(max_length=limit, description=description)]


class ThemedPuzzle(BaseModel):
    scenario: str = Field(..., max_length=500, description="Short themed story setting for the puzzle")
    clues: list[str] = Field(..., min_length=2, max_length=8)


class Explanation(BaseModel):
    steps: list[Text(100, "One short step")] = Field(..., min_length=1, max_length=6,
                                                     description="Step-by-step logical breakdown")
    summary: Text(200)


class HintResponse(BaseModel):
    hint_text: Text(150)


class SemanticMatch(BaseModel):
    is_equivalent: bool
    confidence: float = Field(ge=0.0, le=1.0)
    canonical_answer: str


class SessionSummary(BaseModel):
    coaching: Text(400, "2 sentence personalised coaching message")

class StatsAnalysis(BaseModel):
    analysis: Text(700, "3 sentence analysis of the player's strengths, weaknesses and next step")

