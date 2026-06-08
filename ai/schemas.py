"""Pydantic response schemas for all AI tasks.

All AI providers must return JSON that validates against one of these models.
"""

from pydantic import BaseModel, Field


class ThemedPuzzle(BaseModel):
    scenario: str = Field(..., max_length=500, description="Short themed story setting for the puzzle")
    clues: list[str] = Field(..., min_length=2, max_length=8)


class Explanation(BaseModel):
    steps: list[str] = Field(..., min_length=1, max_length=6, description="Step-by-step logical breakdown")
    summary: str = Field(..., max_length=200)


class HintResponse(BaseModel):
    hint_text: str = Field(..., max_length=150)
    difficulty_reduction: float = Field(ge=0.0, le=0.5,
        description="Fraction of base score removed when hint is used")


class SemanticMatch(BaseModel):
    is_equivalent: bool
    confidence: float = Field(ge=0.0, le=1.0)
    canonical_answer: str


class SessionSummary(BaseModel):
    coaching: str = Field(..., max_length=400, description="2-3 sentence personalised coaching message")
