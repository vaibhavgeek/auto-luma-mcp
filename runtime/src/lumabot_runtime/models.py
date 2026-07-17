from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, EmailStr, Field


def utc_now() -> datetime:
    return datetime.now(UTC)


class InferredValue(BaseModel):
    value: str
    inferred: bool = True


class AutoRegistrationSettings(BaseModel):
    enabled: bool = False
    relevance_threshold: float = 0.82
    max_price_usd: float = 0.0


class StructuredProfile(BaseModel):
    goals: list[InferredValue] = Field(default_factory=list)
    target_roles: list[InferredValue] = Field(default_factory=list)
    industries: list[InferredValue] = Field(default_factory=list)
    company_stages: list[InferredValue] = Field(default_factory=list)
    company_sizes: list[InferredValue] = Field(default_factory=list)
    event_types: list[InferredValue] = Field(default_factory=list)
    region: InferredValue | None = None
    keywords: list[InferredValue] = Field(default_factory=list)
    exclusions: list[InferredValue] = Field(default_factory=list)
    auto_registration: AutoRegistrationSettings = Field(default_factory=AutoRegistrationSettings)


class ProfileCreate(BaseModel):
    user_id: str = Field(min_length=1)
    notification_email: EmailStr
    description: str = Field(min_length=1)


class UserProfile(BaseModel):
    user_id: str
    notification_email: EmailStr
    original_text: str
    structured: StructuredProfile
    created_at: datetime = Field(default_factory=utc_now)


class AuthStartRequest(BaseModel):
    user_id: str = Field(min_length=1)


class AuthStartResponse(BaseModel):
    login_url: str
    session_id: str


class AuthVerifyRequest(BaseModel):
    user_id: str = Field(min_length=1)
    code: str = Field(min_length=1)


class AuthVerifyResponse(BaseModel):
    verified: bool
    session_id: str


class Event(BaseModel):
    id: str
    title: str
    starts_at: datetime
    region: str = "Bay Area"
    relevance_score: float = 0.0
    price_usd: float = 0.0
    requires_payment: bool = False
    requires_custom_answers: bool = False
    requires_unusual_consent: bool = False
    registered: bool = False
    calendar_conflict: bool = False


class Recommendation(BaseModel):
    event_id: str
    title: str
    score: float
    reasons: list[str] = Field(default_factory=list)


class ReportRequest(BaseModel):
    refresh: bool = False


class Report(BaseModel):
    report_id: str
    user_id: str
    event_id: str
    status: Literal["queued", "ready"] = "queued"
    job_id: str | None = None
    url: str | None = None
    updated_at: datetime = Field(default_factory=utc_now)


class JobCreateRequest(BaseModel):
    type: str = Field(min_length=1)
    payload: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str | None = None
    max_attempts: int = Field(default=3, ge=1, le=20)


class ActionConfirmRequest(BaseModel):
    approved: bool
    comment: str | None = None


class ActionRecord(BaseModel):
    id: str = Field(default_factory=lambda: f"act_{uuid4().hex}")
    user_id: str
    type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    status: Literal["pending", "approved", "rejected", "completed"] = "pending"
    created_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime | None = None


class EmailRecord(BaseModel):
    idempotency_key: str
    inbox_id: str
    message_id: str
    thread_id: str | None = None
    provider_status: str
    sent_at: datetime = Field(default_factory=utc_now)


class WebhookRecord(BaseModel):
    event_id: str
    event_type: str
    message_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    received_at: datetime = Field(default_factory=utc_now)


class RuntimeState(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    profiles: dict[str, UserProfile] = Field(default_factory=dict)
    events: dict[str, list[Event]] = Field(default_factory=dict)
    reports: dict[tuple[str, str], Report] = Field(default_factory=dict)
    actions: dict[str, ActionRecord] = Field(default_factory=dict)
    user_events: set[tuple[str, str]] = Field(default_factory=set)
    audit_records: list[dict[str, Any]] = Field(default_factory=list)
    emails: dict[str, EmailRecord] = Field(default_factory=dict)
    webhooks: dict[str, WebhookRecord] = Field(default_factory=dict)
    zero_invocations: list[dict[str, Any]] = Field(default_factory=list)
