from __future__ import annotations

from pydantic import BaseModel, Field


SCORING_VERSION = "person-v1:event-v1"


class PersonScore(BaseModel):
    person_id: str
    score: float = Field(ge=0.0, le=100.0)
    reasons: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    identity_confidence: float = Field(ge=0.0, le=1.0)
    scoring_version: str = SCORING_VERSION


class EventScore(BaseModel):
    event_id: str
    score: float = Field(ge=0.0, le=100.0)
    reasons: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    scoring_version: str = SCORING_VERSION

