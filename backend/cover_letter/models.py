from __future__ import annotations

from pydantic import BaseModel, Field


class CompanyResearch(BaseModel):
    known: bool = False
    industry: str | None = None
    what_they_do: str | None = None
    culture_signals: str | None = None
    why_interesting: str | None = None


class ValidationResult(BaseModel):
    passed: bool
    unsupported_claims: list[str] = Field(default_factory=list)
    word_count: int
    failure_reason: str | None = None


class CoverLetterResult(BaseModel):
    success: bool
    content: str | None = None
    validation: ValidationResult | None = None
    attempts: int = 0
