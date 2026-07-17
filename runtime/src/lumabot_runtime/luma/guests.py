from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from .extractors import extract_visible_guests
from .repository import LumaRepository


@dataclass(frozen=True)
class GuestScrapeResult:
    event_id: UUID
    visible_guest_count: int
    queued_enrichment_jobs: int


async def scrape_event_guests(
    user_id: UUID,
    event_id: UUID,
    *,
    repository: LumaRepository,
    html: str,
) -> GuestScrapeResult:
    del user_id
    queued = 0
    visible_guests = extract_visible_guests(html)
    for person, attendee_fields in visible_guests:
        await repository.upsert_person(person)
        await repository.upsert_attendee(
            {
                "event_id": event_id,
                "person_id": person.person_id,
                "attendee_status": attendee_fields["attendee_status"],
                "organizer_status": attendee_fields["organizer_status"],
                "identity_confidence": person.identity_confidence,
                "source_selector": attendee_fields["source_selector"],
            }
        )
        was_queued = await repository.enqueue_job(
            "ENRICH_PERSON",
            {"person_id": str(person.person_id), "event_id": str(event_id)},
            idempotency_key=f"enrich-person:{person.person_id}",
        )
        queued += int(was_queued)
    return GuestScrapeResult(event_id=event_id, visible_guest_count=len(visible_guests), queued_enrichment_jobs=queued)
