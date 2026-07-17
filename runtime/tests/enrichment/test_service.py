from __future__ import annotations

import pytest

from lumabot_runtime.clearbit import CompanyHint, FakeCompanyHintClient
from lumabot_runtime.enrichment import EnrichmentService
from lumabot_runtime.enrichment.models import EvidenceField, RawPerson
from lumabot_runtime.hunter import FakeHunterClient
from lumabot_runtime.pdl import FakePeopleDataLabsClient


@pytest.mark.asyncio
async def test_enrichment_service_combines_pdl_hunter_and_clearbit() -> None:
    service = EnrichmentService(
        primary=FakePeopleDataLabsClient(),
        email_intelligence=FakeHunterClient(found_email="maya@vectorforge.ai"),
        company_hints=FakeCompanyHintClient(
            hints=[
                CompanyHint(
                    name=EvidenceField(value="VectorForge", source="fixture", confidence=0.5),
                    domain=EvidenceField(value="vectorforge.ai", source="fixture", confidence=0.5),
                    logo_url=EvidenceField(
                        value="https://logo.clearbit.com/vectorforge.ai",
                        source="fixture",
                        confidence=0.4,
                    ),
                )
            ]
        ),
    )

    bundle = await service.enrich_attendee(
        RawPerson(
            person_id="p1",
            full_name="Maya Chen",
            company="VectorForge",
            company_domain="vectorforge.ai",
            social_urls=["https://linkedin.com/in/mayachen"],
        )
    )

    assert bundle.person.full_name.value == "Maya Chen"
    assert bundle.person.professional_email is not None
    assert bundle.person.professional_email.value == "maya@vectorforge.ai"
    assert bundle.person.profile_image_url is not None
    assert bundle.company is not None
    assert bundle.company.website is not None
    assert bundle.company.website.value == "https://vector.local" or bundle.company.website.value == "vectorforge.ai"


@pytest.mark.asyncio
async def test_enrichment_service_falls_back_when_primary_fails() -> None:
    class FailingPrimary:
        async def enrich_person(self, person: RawPerson):
            raise RuntimeError("pdl unavailable")

        async def enrich_company(self, company):
            raise RuntimeError("company unavailable")

        async def health_check(self) -> bool:
            return False

    service = EnrichmentService(primary=FailingPrimary())
    bundle = await service.enrich_attendee(RawPerson(person_id="p1", full_name="Maya Chen"))

    assert bundle.person.full_name.value == "Maya Chen"
    assert bundle.person.full_name.source == "luma-visible-attendee"
    assert bundle.warnings

