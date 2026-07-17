from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, EmailStr, Field, SecretBytes


def utc_now() -> datetime:
    return datetime.now(UTC)


class AutoRegistrationPreferences(BaseModel):
    enabled: bool = False
    max_events_per_week: int = Field(default=2, ge=0, le=20)
    min_event_score: int = Field(default=70, ge=0, le=100)
    required_tags: list[str] = Field(default_factory=list)
    blocked_tags: list[str] = Field(default_factory=list)
    require_confirmation: bool = True


class User(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    email: EmailStr
    display_name: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class UserProfile(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    headline: str | None = None
    location: str | None = None
    goals: list[str] = Field(default_factory=list)
    target_roles: list[str] = Field(default_factory=list)
    target_industries: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    auto_registration: AutoRegistrationPreferences = Field(
        default_factory=AutoRegistrationPreferences
    )
    source_evidence: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class AuthSession(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    provider: str = "luma"
    encrypted_browser_session: SecretBytes = Field(repr=False)
    expires_at: datetime | None = None
    created_at: datetime = Field(default_factory=utc_now)
