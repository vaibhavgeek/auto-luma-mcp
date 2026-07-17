from __future__ import annotations

import pytest

from lumabot_runtime.enrichment import EnrichmentService
from lumabot_runtime.enrichment.models import (
    EnrichedCompany,
    EnrichedPerson,
    EvidenceField,
    RawCompany,
    RawPerson,
)


class FakeZeroLikeProvider:
    async def enrich_person(self, person: RawPerson) -> EnrichedPerson:
        return EnrichedPerson(
            person_id=person.person_id,
            full_name=EvidenceField(
                value=person.full_name,
                source="people-data-labs:person.full_name",
                confidence=0.9,
            ),
            company_name=EvidenceField(
                value=person.company,
                source="people-data-labs:person.experience.company.name",
                confidence=0.8,
            )
            if person.company
            else None,
        )

    async def enrich_company(self, company: RawCompany) -> EnrichedCompany:
        return EnrichedCompany(
            company_id=company.company_id,
            name=EvidenceField(
                value=company.name,
                source="people-data-labs:company.display_name",
                confidence=0.9,
            ),
            website=EvidenceField(
                value=company.website,
                source="people-data-labs:company.website",
                confidence=0.8,
            )
            if company.website
            else None,
        )

    async def verify_email(self, email: str) -> EvidenceField | None:
        return EvidenceField(
            value="valid",
            source="zero:hunter-email-verifier",
            confidence=0.92,
        )


@pytest.mark.asyncio
async def test_enrichment_service_combines_zero_person_company_and_email_verification() -> None:
    service = EnrichmentService(provider=FakeZeroLikeProvider())

    bundle = await service.enrich_attendee(
        RawPerson(
            person_id="p1",
            full_name="Maya Chen",
            email="maya@vectorforge.ai",
            company="VectorForge",
            company_domain="vectorforge.ai",
            social_urls=["https://linkedin.com/in/mayachen"],
        )
    )

    assert bundle.person.full_name.value == "Maya Chen"
    assert bundle.person.email_verification is not None
    assert bundle.person.email_verification.source == "zero:hunter-email-verifier"
    assert bundle.company is not None
    assert bundle.company.name.value == "VectorForge"
    assert bundle.warnings == []


@pytest.mark.asyncio
async def test_enrichment_service_falls_back_when_zero_provider_fails() -> None:
    class FailingProvider:
        async def enrich_person(self, person: RawPerson):
            raise RuntimeError("zero unavailable")

        async def enrich_company(self, company: RawCompany):
            raise RuntimeError("company unavailable")

        async def verify_email(self, email: str):
            raise RuntimeError("email unavailable")

    service = EnrichmentService(provider=FailingProvider())
    bundle = await service.enrich_attendee(RawPerson(person_id="p1", full_name="Maya Chen"))

    assert bundle.person.full_name.value == "Maya Chen"
    assert bundle.person.full_name.source == "luma-visible-attendee"
    assert bundle.warnings == ["zero unavailable"]
