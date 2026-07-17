from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from lumabot_runtime.luma import InMemoryLumaRepository, scrape_event_guests, sync_event_details
from lumabot_runtime.luma.extractors import event_id_for_url, extract_event_details

FIXTURES = Path(__file__).parent / "fixtures"
EVENT_URL = "https://lu.ma/sf-ai-build-night"


def test_event_detail_extraction_from_fixture() -> None:
    event = extract_event_details((FIXTURES / "event.html").read_text(), EVENT_URL)

    assert event.title == "SF AI Build Night"
    assert event.organizer == "LumaBot Collective"
    assert event.registration_state == "open"
    assert event.image_url == "https://images.example/sf-ai-build-night.png"


@pytest.mark.asyncio
async def test_sync_event_details_upserts_visible_metadata() -> None:
    repository = InMemoryLumaRepository()

    result = await sync_event_details(uuid4(), EVENT_URL, repository=repository, html=(FIXTURES / "event.html").read_text())

    assert result.title == "SF AI Build Night"
    assert repository.events[result.event_id].venue == "Mission Bay Lab"


@pytest.mark.asyncio
async def test_attendee_ingestion_and_job_idempotency() -> None:
    repository = InMemoryLumaRepository()
    event_id = event_id_for_url(EVENT_URL)
    html = (FIXTURES / "guest-list.html").read_text()

    first = await scrape_event_guests(uuid4(), event_id, repository=repository, html=html)
    second = await scrape_event_guests(uuid4(), event_id, repository=repository, html=html)

    assert first.visible_guest_count == 2
    assert first.queued_enrichment_jobs == 2
    assert second.visible_guest_count == 2
    assert second.queued_enrichment_jobs == 0
    assert len(repository.people) == 2
    assert len(repository.attendees) == 2
    assert {job["job_type"] for job in repository.jobs.values()} == {"ENRICH_PERSON"}


@pytest.mark.asyncio
async def test_inaccessible_guest_list_does_not_ingest() -> None:
    repository = InMemoryLumaRepository()

    result = await scrape_event_guests(
        uuid4(),
        event_id_for_url(EVENT_URL),
        repository=repository,
        html=(FIXTURES / "inaccessible-guest-list.html").read_text(),
    )

    assert result.visible_guest_count == 0
    assert len(repository.people) == 0
    assert len(repository.jobs) == 0

