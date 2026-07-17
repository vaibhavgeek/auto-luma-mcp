from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import AnyUrl, BaseModel, Field

from lumabot_shared.models.users import utc_now


class Event(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    source: str = "luma"
    external_id: str | None = None
    url: AnyUrl
    title: str
    description: str | None = None
    starts_at: datetime
    ends_at: datetime | None = None
    timezone: str = "UTC"
    location_name: str | None = None
    city: str | None = None
    region: str | None = None
    country: str | None = None
    is_online: bool = False
    tags: list[str] = Field(default_factory=list)
    source_evidence: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class EventScore(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    event_id: UUID
    user_id: UUID
    overall_score: int = Field(ge=0, le=100)
    relevance_score: int = Field(ge=0, le=100)
    attendee_quality_score: int = Field(ge=0, le=100)
    timing_score: int = Field(ge=0, le=100)
    rationale: str | None = None
    source_evidence: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
