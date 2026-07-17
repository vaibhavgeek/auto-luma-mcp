from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from lumabot_shared.models.events import EventScore
from lumabot_shared.models.people import EventAttendee, PersonScore
from lumabot_shared.models.users import utc_now


class EventReport(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    event_id: UUID
    user_id: UUID
    version: int = Field(default=1, ge=1)
    status: str = "partial"
    title: str
    summary: str
    event_score: EventScore | None = None
    attendee_scores: list[PersonScore] = Field(default_factory=list)
    featured_attendees: list[EventAttendee] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    source_evidence: dict[str, Any] = Field(default_factory=dict)
    created_at: object = Field(default_factory=utc_now)
    completed_at: object | None = None
