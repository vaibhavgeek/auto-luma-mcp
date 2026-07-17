from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from lumabot_runtime.luma import InMemoryLumaRepository, LumaEventDiscoverer
from lumabot_runtime.luma.extractors import SELECTORS, extract_discovered_events

FIXTURES = Path(__file__).parent / "fixtures"


def test_event_selector_extraction() -> None:
    events = extract_discovered_events((FIXTURES / "discovery.html").read_text(), "https://lu.ma/sf")

    assert len(events) == 3
    assert events[0].title == "SF AI Build Night"
    assert events[0].evidence["selector"] == SELECTORS["event_card"]


@pytest.mark.asyncio
async def test_event_deduplication_and_sync_jobs() -> None:
    repository = InMemoryLumaRepository()
    discoverer = LumaEventDiscoverer(repository)

    events = await discoverer.discover_from_html(uuid4(), (FIXTURES / "discovery.html").read_text(), "https://lu.ma/sf")

    assert [event.title for event in events] == ["SF AI Build Night", "Oakland Founder Breakfast"]
    assert len(repository.events) == 2
    assert len(repository.jobs) == 2
    assert all(job["job_type"] == "SYNC_EVENT_DETAILS" for job in repository.jobs.values())

