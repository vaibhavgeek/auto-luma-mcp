from __future__ import annotations

import asyncio
from pathlib import Path
from uuid import uuid4

from lumabot_runtime.browser import load_local_pages_with_chromium

from .discovery import LumaEventDiscoverer
from .guests import scrape_event_guests
from .repository import InMemoryLumaRepository
from .sync import sync_event_details


FIXTURE_DIR = Path(__file__).resolve().parents[3] / "tests" / "luma" / "fixtures"


async def main() -> None:
    repository = InMemoryLumaRepository()
    user_id = uuid4()
    discoverer = LumaEventDiscoverer(repository)
    discovery_html, event_html, guests_html = await load_local_pages_with_chromium(
        [
            FIXTURE_DIR / "discovery.html",
            FIXTURE_DIR / "event.html",
            FIXTURE_DIR / "guest-list.html",
        ]
    )

    discovered = await discoverer.discover_from_html(user_id, discovery_html, "https://lu.ma/sf")
    synced = await sync_event_details(user_id, discovered[0].url, repository=repository, html=event_html)
    scraped = await scrape_event_guests(user_id, synced.event_id, repository=repository, html=guests_html)
    organizer = repository.events[synced.event_id].organizer

    print(f"discovered event: {synced.title} ({discovered[0].url})")
    print(f"organizer: {organizer}")
    print(f"guest count: {scraped.visible_guest_count}")
    print(f"queued enrichment job count: {scraped.queued_enrichment_jobs}")


if __name__ == "__main__":
    asyncio.run(main())
