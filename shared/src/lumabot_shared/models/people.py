from datetime import date
from typing import Any
from uuid import UUID, uuid4

from pydantic import AnyUrl, BaseModel, Field

from lumabot_shared.models.users import utc_now


class Company(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    name: str
    domain: str | None = None
    website_url: AnyUrl | None = None
    linkedin_url: AnyUrl | None = None
    twitter_url: AnyUrl | None = None
    industry: str | None = None
    size_range: str | None = None
    source_evidence: dict[str, Any] = Field(default_factory=dict)
    created_at: object = Field(default_factory=utc_now)
    updated_at: object = Field(default_factory=utc_now)


class Person(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    full_name: str
    headline: str | None = None
    location: str | None = None
    email: str | None = None
    linkedin_url: AnyUrl | None = None
    twitter_url: AnyUrl | None = None
    github_url: AnyUrl | None = None
    source_evidence: dict[str, Any] = Field(default_factory=dict)
    created_at: object = Field(default_factory=utc_now)
    updated_at: object = Field(default_factory=utc_now)


class Employment(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    person_id: UUID
    company_id: UUID
    title: str | None = None
    started_on: date | None = None
    ended_on: date | None = None
    is_current: bool = True
    source_evidence: dict[str, Any] = Field(default_factory=dict)


class EventAttendee(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    event_id: UUID
    person_id: UUID
    attendance_status: str = "discovered"
    registration_status: str | None = None
    source_evidence: dict[str, Any] = Field(default_factory=dict)
    created_at: object = Field(default_factory=utc_now)


class PersonScore(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    person_id: UUID
    user_id: UUID
    overall_score: int = Field(ge=0, le=100)
    role_fit_score: int = Field(ge=0, le=100)
    company_fit_score: int = Field(ge=0, le=100)
    networking_priority_score: int = Field(ge=0, le=100)
    rationale: str | None = None
    source_evidence: dict[str, Any] = Field(default_factory=dict)
    created_at: object = Field(default_factory=utc_now)
