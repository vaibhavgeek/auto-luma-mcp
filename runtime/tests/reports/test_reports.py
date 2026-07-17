from __future__ import annotations

import pytest

from lumabot_runtime.enrichment.models import EnrichmentStatus
from lumabot_runtime.reports import generate_event_report, render_html_report, render_text_email
from lumabot_runtime.reports.fixtures import demo_fixture


@pytest.mark.asyncio
async def test_full_report_snapshot() -> None:
    profile, event, attendees, enriched = demo_fixture(full=True)
    report = await generate_event_report(profile, event, attendees, enriched)

    assert report.report_version == "event-report-v1"
    assert report.report_completeness == pytest.approx(1.0)
    assert report.top_people_to_meet[0].attendee.full_name == "Maya Chen"
    assert report.top_people_to_meet[0].relevance_score is not None
    assert report.top_people_to_meet[0].evidence_links
    assert "Bay Area AI Hacknight" in report.model_dump_json()


@pytest.mark.asyncio
async def test_partial_report_snapshot() -> None:
    profile, event, attendees, enriched = demo_fixture(full=False)
    report = await generate_event_report(profile, event, attendees, enriched)

    statuses = {person.enrichment_status for person in report.attendees}
    assert EnrichmentStatus.ENRICHMENT_PENDING in statuses
    assert 0 < report.report_completeness < 1
    assert len(report.attendees) == len(attendees)


@pytest.mark.asyncio
async def test_report_renderers() -> None:
    profile, event, attendees, enriched = demo_fixture(full=True)
    report = await generate_event_report(profile, event, attendees, enriched)

    html = render_html_report(report)
    text = render_text_email(report)

    assert "<table>" in html
    assert "Maya Chen" in html
    assert "Top people:" in text
    assert "identity=" in text


@pytest.mark.asyncio
async def test_no_hallucination_invariant() -> None:
    profile, event, attendees, _ = demo_fixture(full=True)
    report = await generate_event_report(profile, event, attendees, [])

    assert all(person.company is None for person in report.attendees)
    assert all(person.relevance_score is None for person in report.attendees)
    assert all(person.enrichment_status == EnrichmentStatus.ENRICHMENT_PENDING for person in report.attendees)

