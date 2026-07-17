from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol
from uuid import UUID


class LumaRepository(Protocol):
    async def save_login_attempt(self, **kwargs: Any) -> None: ...
    async def save_encrypted_session(self, user_id: UUID, encrypted_session: dict[str, Any]) -> None: ...
    async def load_encrypted_session(self, user_id: UUID) -> dict[str, Any] | None: ...
    async def upsert_event(self, event: Any) -> Any: ...
    async def upsert_person(self, person: Any) -> Any: ...
    async def upsert_attendee(self, attendee: dict[str, Any]) -> Any: ...
    async def enqueue_job(self, job_type: str, payload: dict[str, Any], idempotency_key: str) -> bool: ...


@dataclass
class InMemoryLumaRepository:
    login_attempts: dict[UUID, dict[str, Any]] = field(default_factory=dict)
    encrypted_sessions: dict[UUID, dict[str, Any]] = field(default_factory=dict)
    events: dict[UUID, Any] = field(default_factory=dict)
    people: dict[UUID, Any] = field(default_factory=dict)
    attendees: dict[tuple[UUID, UUID], dict[str, Any]] = field(default_factory=dict)
    jobs: dict[str, dict[str, Any]] = field(default_factory=dict)

    async def save_login_attempt(self, **kwargs: Any) -> None:
        self.login_attempts[kwargs["attempt_id"]] = kwargs

    async def save_encrypted_session(self, user_id: UUID, encrypted_session: dict[str, Any]) -> None:
        self.encrypted_sessions[user_id] = encrypted_session

    async def load_encrypted_session(self, user_id: UUID) -> dict[str, Any] | None:
        return self.encrypted_sessions.get(user_id)

    async def upsert_event(self, event: Any) -> Any:
        self.events[event.event_id] = event
        return event

    async def upsert_person(self, person: Any) -> Any:
        self.people[person.person_id] = person
        return person

    async def upsert_attendee(self, attendee: dict[str, Any]) -> Any:
        self.attendees[(attendee["event_id"], attendee["person_id"])] = attendee
        return attendee

    async def enqueue_job(self, job_type: str, payload: dict[str, Any], idempotency_key: str) -> bool:
        if idempotency_key in self.jobs:
            return False
        self.jobs[idempotency_key] = {
            "job_type": job_type,
            "payload": payload,
            "idempotency_key": idempotency_key,
        }
        return True

