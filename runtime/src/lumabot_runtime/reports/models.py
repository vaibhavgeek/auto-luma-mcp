from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from lumabot_runtime.enrichment.models import EnrichmentStatus, Event, EventAttendee, utc_now
from lumabot_runtime.scoring.models import EventScore, PersonScore


REPORT_VERSION = "event-report-v1"


class ReportPerson(BaseModel):
    attendee: EventAttendee
    enrichment_status: EnrichmentStatus
    relevance_score: PersonScore | None = None
    identity_confidence: float = Field(ge=0.0, le=1.0)
    company: str | None = None
    company_size: str | None = None
    funding_stage: str | None = None
    profile_image_url: str | None = None
    why_the_person_matters: str
    conversation_opener: str
    evidence_links: list[str] = Field(default_factory=list)
    uncertainty_warnings: list[str] = Field(default_factory=list)


class EventReport(BaseModel):
    report_id: str
    event: Event
    event_summary: str
    registration_status: str
    organizers: list[str] = Field(default_factory=list)
    event_score: EventScore
    top_people_to_meet: list[ReportPerson] = Field(default_factory=list)
    attendees: list[ReportPerson] = Field(default_factory=list)
    report_completeness: float = Field(ge=0.0, le=1.0)
    report_version: str = REPORT_VERSION
    generated_at: datetime = Field(default_factory=utc_now)

