from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class DiscoveredEvent:
    url: str
    title: str
    starts_at: str | None
    venue: str | None
    evidence: dict[str, Any]


@dataclass(frozen=True)
class LumaEvent:
    event_id: UUID
    url: str
    title: str
    description: str | None = None
    starts_at: str | None = None
    ends_at: str | None = None
    venue: str | None = None
    image_url: str | None = None
    organizer: str | None = None
    registration_state: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LumaPerson:
    person_id: UUID
    full_name: str
    profile_url: str | None
    image_url: str | None
    social_links: list[str]
    identity_confidence: float
    title: str | None = None
    company: str | None = None
    location: str | None = None
    bio: str | None = None


@dataclass(frozen=True)
class EventSyncResult:
    event_id: UUID
    title: str
    registration_state: str | None
    synchronized_at: datetime
