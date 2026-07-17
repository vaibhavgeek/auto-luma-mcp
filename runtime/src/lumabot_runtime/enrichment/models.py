from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator


def utc_now() -> datetime:
    return datetime.now(UTC)


class EnrichmentStatus(StrEnum):
    ENRICHED = "enriched"
    ENRICHMENT_PENDING = "enrichment_pending"
    ENRICHMENT_FAILED = "enrichment_failed"
    IDENTITY_UNCERTAIN = "identity_uncertain"


class EvidenceField(BaseModel):
    value: Any
    source: str = Field(min_length=1)
    source_url: str | None = None
    retrieved_at: datetime = Field(default_factory=utc_now)
    confidence: float = Field(ge=0.0, le=1.0)


class RawPerson(BaseModel):
    person_id: str
    full_name: str
    social_urls: list[str] = Field(default_factory=list)
    company: str | None = None
    title: str | None = None
    location: str | None = None
    event_context: str | None = None


class RawCompany(BaseModel):
    company_id: str
    name: str
    website: str | None = None


class EnrichedCompany(BaseModel):
    company_id: str
    name: EvidenceField
    industry: EvidenceField | None = None
    employee_count: EvidenceField | None = None
    stage: EvidenceField | None = None
    website: EvidenceField | None = None


class EnrichedPerson(BaseModel):
    person_id: str
    full_name: EvidenceField
    title: EvidenceField | None = None
    company_name: EvidenceField | None = None
    company_stage: EvidenceField | None = None
    company_employee_count: EvidenceField | None = None
    industry: EvidenceField | None = None
    location: EvidenceField | None = None
    social_urls: list[EvidenceField] = Field(default_factory=list)
    profile_image_url: EvidenceField | None = None
    interests: list[EvidenceField] = Field(default_factory=list)
    sources_agreeing: int = 1
    enrichment_status: EnrichmentStatus = EnrichmentStatus.ENRICHED
    error: str | None = None

    @field_validator("social_urls")
    @classmethod
    def social_values_must_be_normalized(cls, urls: list[EvidenceField]) -> list[EvidenceField]:
        for item in urls:
            if isinstance(item.value, str) and item.value != item.value.strip().lower():
                raise ValueError("social URL evidence values must be normalized")
        return urls


class UserProfile(BaseModel):
    goals: list[str] = Field(default_factory=list)
    target_roles: list[str] = Field(default_factory=list)
    industries: list[str] = Field(default_factory=list)
    company_stages: list[str] = Field(default_factory=list)
    company_sizes: list[str] = Field(default_factory=list)
    event_types: list[str] = Field(default_factory=list)
    region: str | None = None
    keywords: list[str] = Field(default_factory=list)


class Event(BaseModel):
    event_id: str
    title: str
    description: str = ""
    event_type: str | None = None
    organizer: str | None = None
    location: str | None = None
    starts_at: datetime = Field(default_factory=utc_now)
    registration_status: str = "unknown"
    registration_constraints: list[str] = Field(default_factory=list)
    source_url: str | None = None
    evidence_quality: float = Field(default=0.5, ge=0.0, le=1.0)


class EventAttendee(BaseModel):
    attendee_id: str
    person_id: str
    full_name: str
    title: str | None = None
    company: str | None = None
    social_urls: list[str] = Field(default_factory=list)
    profile_image_url: str | None = None
    status: str = "attending"

