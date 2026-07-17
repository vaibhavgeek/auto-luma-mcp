from __future__ import annotations

from pathlib import Path

import pytest

from lumabot_runtime.enrichment.models import EnrichedCompany, EnrichedPerson, EvidenceField, RawCompany, RawPerson, UserProfile
from lumabot_runtime.luma.enrichment import generate_report_from_luma_guest_html

FIXTURES = Path(__file__).parent / "fixtures"


class FakeProvider:
    async def enrich_person(self, person: RawPerson) -> EnrichedPerson:
        return EnrichedPerson(
            person_id=person.person_id,
            full_name=EvidenceField(
                value=person.full_name,
                source="fake-zero:person",
                confidence=0.9,
            ),
            title=EvidenceField(value=person.title, source="fake-zero:title", confidence=0.85)
            if person.title
            else None,
            company_name=EvidenceField(
                value=person.company,
                source="fake-zero:company",
                confidence=0.85,
            )
            if person.company
            else None,
            company_stage=EvidenceField(value="seed", source="fake-zero:stage", confidence=0.8),
            company_employee_count=EvidenceField(value=18, source="fake-zero:size", confidence=0.8),
            industry=EvidenceField(value="AI developer tools", source="fake-zero:industry", confidence=0.8),
            location=EvidenceField(value=person.location, source="fake-zero:location", confidence=0.7)
            if person.location
            else None,
            social_urls=[
                EvidenceField(value=url, source="fake-zero:social", confidence=0.8)
                for url in person.social_urls
            ],
            interests=[EvidenceField(value=person.event_context, source="fake-zero:bio", confidence=0.7)]
            if person.event_context
            else [],
            sources_agreeing=2,
        )

    async def enrich_company(self, company: RawCompany) -> EnrichedCompany:
        return EnrichedCompany(
            company_id=company.company_id,
            name=EvidenceField(value=company.name, source="fake-zero:company", confidence=0.8),
            stage=EvidenceField(value="seed", source="fake-zero:stage", confidence=0.8),
        )

    async def verify_email(self, email: str) -> EvidenceField | None:
        del email
        return None


@pytest.mark.asyncio
async def test_luma_guest_html_feeds_enrichment_and_report_generation() -> None:
    result = await generate_report_from_luma_guest_html(
        user_profile=UserProfile(
            goals=["meet founders building developer tools"],
            target_roles=["founder", "engineering leader"],
            industries=["ai", "developer tools"],
            company_stages=["seed"],
            company_sizes=["fewer than 50 employees"],
            event_types=["meetup"],
            region="Bay Area",
            keywords=["ai", "developer tools", "platform"],
        ),
        event_url="https://lu.ma/sf-ai-build-night",
        event_html=(FIXTURES / "event.html").read_text(),
        guest_html=(FIXTURES / "guest-list.html").read_text(),
        provider=FakeProvider(),
    )

    assert result.visible_guest_count == 2
    assert result.enriched_guest_count == 2
    assert result.report.event.title == "SF AI Build Night"
    assert result.report.report_completeness == 1.0
    assert result.report.top_people_to_meet[0].attendee.full_name == "Ava Chen"
    assert result.report.top_people_to_meet[0].company == "VectorForge"
    assert result.warnings == []
