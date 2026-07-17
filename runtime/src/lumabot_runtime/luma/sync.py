from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from .extractors import extract_event_details
from .models import EventSyncResult
from .repository import LumaRepository


async def sync_event_details(
    user_id: UUID,
    event_url: str,
    *,
    repository: LumaRepository,
    html: str,
) -> EventSyncResult:
    del user_id
    event = extract_event_details(html, event_url)
    await repository.upsert_event(event)
    return EventSyncResult(
        event_id=event.event_id,
        title=event.title,
        registration_state=event.registration_state,
        synchronized_at=datetime.now(UTC),
    )

