from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Iterable
from uuid import UUID

from .extractors import event_id_for_url, extract_discovered_events
from .models import DiscoveredEvent, LumaEvent
from .repository import LumaRepository


@dataclass
class LumaEventDiscoverer:
    repository: LumaRepository
    rolling_window: timedelta = timedelta(days=30)

    async def discover_from_html(self, user_id: UUID, html: str, source_url: str) -> list[DiscoveredEvent]:
        deduped: dict[str, DiscoveredEvent] = {}
        for event in extract_discovered_events(html, source_url):
            deduped[event.url] = event

        for event in deduped.values():
            event_record = LumaEvent(
                event_id=event_id_for_url(event.url),
                url=event.url,
                title=event.title,
                starts_at=event.starts_at,
                venue=event.venue,
                metadata={"discovery_evidence": event.evidence},
            )
            await self.repository.upsert_event(event_record)
            await self.repository.enqueue_job(
                "SYNC_EVENT_DETAILS",
                {"user_id": str(user_id), "event_url": event.url},
                idempotency_key=f"sync-event:{event.url}",
            )
        return list(deduped.values())

    async def discover_bay_area_events(
        self,
        user_id: UUID,
        pages: Iterable[tuple[str, str]],
    ) -> list[DiscoveredEvent]:
        discovered: dict[str, DiscoveredEvent] = {}
        for source_url, html in pages:
            for event in await self.discover_from_html(user_id, html, source_url):
                discovered[event.url] = event
        return list(discovered.values())

