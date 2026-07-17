from __future__ import annotations

import httpx
import pytest
import respx

from lumabot_runtime.enrichment.models import EvidenceField, RawCompany, RawPerson
from lumabot_runtime.pdl import (
    FakePeopleDataLabsClient,
    PeopleDataLabsClient,
    company_from_pdl,
    person_from_pdl,
)


@pytest.mark.asyncio
async def test_fake_people_data_labs_contract_round_trip() -> None:
    client = FakePeopleDataLabsClient()
    person = RawPerson(
        person_id="p1",
        full_name="Maya Chen",
        social_urls=["https://LinkedIn.com/in/MayaChen"],
        company="VectorForge",
        title="Founder",
    )
    company = RawCompany(company_id="c1", name="VectorForge", website="https://vector.local")

    enriched = await client.enrich_person(person)
    enriched_company = await client.enrich_company(company)

    assert enriched.full_name.value == "Maya Chen"
    assert enriched.social_urls[0].value == "https://linkedin.com/in/mayachen"
    assert enriched_company.name.value == "VectorForge"
    assert await client.health_check() is True


@pytest.mark.asyncio
async def test_people_data_labs_client_uses_official_endpoints_and_header() -> None:
    base = "https://api.peopledatalabs.com"
    person_payload = {
        "full_name": "Maya Chen",
        "profiles": [{"network": "linkedin", "url": "https://linkedin.com/in/mayachen"}],
        "experience": [
            {
                "title": "Founder",
                "end_date": None,
                "company": {
                    "name": "VectorForge",
                    "industry": "AI developer tools",
                    "employee_count": 18,
                },
            }
        ],
        "location_name": "San Francisco Bay Area",
        "skills": ["agentic developer tools"],
    }
    company_payload = {
        "display_name": "VectorForge",
        "industry": "computer software",
        "employee_count": 18,
        "latest_funding_stage": "seed",
        "website": "vectorforge.ai",
    }
    with respx.mock(assert_all_called=True) as router:
        person_route = router.get(f"{base}/v5/person/enrich").mock(
            return_value=httpx.Response(200, json=person_payload)
        )
        company_route = router.get(f"{base}/v5/company/enrich").mock(
            return_value=httpx.Response(200, json=company_payload)
        )
        client = PeopleDataLabsClient(api_key="secret")
        person = await client.enrich_person(
            RawPerson(
                person_id="p1",
                full_name="Maya Chen",
                social_urls=["https://linkedin.com/in/mayachen"],
                company="VectorForge",
            )
        )
        company = await client.enrich_company(
            RawCompany(company_id="c1", name="VectorForge", website="vectorforge.ai")
        )

    assert person_route.calls[0].request.headers["X-Api-Key"] == "secret"
    assert company_route.calls[0].request.headers["X-Api-Key"] == "secret"
    assert person_route.calls[0].request.url.params["profile"] == "https://linkedin.com/in/mayachen"
    assert company_route.calls[0].request.url.params["website"] == "vectorforge.ai"
    assert person.full_name.value == "Maya Chen"
    assert person.title.value == "Founder"
    assert person.company_name.value == "VectorForge"
    assert person.company_employee_count.value == 18
    assert company.stage.value == "seed"


@pytest.mark.asyncio
async def test_provider_timeout_maps_to_unhealthy() -> None:
    with respx.mock(assert_all_called=True) as router:
        router.get("https://api.peopledatalabs.com/v5/company/enrich").mock(
            side_effect=httpx.ReadTimeout("timeout")
        )
        client = PeopleDataLabsClient(api_key="secret", timeout_seconds=0.01)
        assert await client.health_check() is False


@pytest.mark.asyncio
async def test_not_found_is_lookup_error() -> None:
    with respx.mock(assert_all_called=True) as router:
        router.get("https://api.peopledatalabs.com/v5/person/enrich").mock(
            return_value=httpx.Response(404, json={"status": 404})
        )
        client = PeopleDataLabsClient(api_key="secret")
        with pytest.raises(LookupError, match="People Data Labs did not find"):
            await client.enrich_person(RawPerson(person_id="p1", full_name="Unknown Person"))


@pytest.mark.asyncio
async def test_malformed_enrichment_response() -> None:
    with respx.mock(assert_all_called=True) as router:
        router.get("https://api.peopledatalabs.com/v5/person/enrich").mock(
            return_value=httpx.Response(200, json=["not", "a", "dict"])
        )
        client = PeopleDataLabsClient(api_key="secret")
        with pytest.raises(ValueError, match="malformed People Data Labs response"):
            await client.enrich_person(RawPerson(person_id="p1", full_name="Maya Chen"))


def test_response_mapping_preserves_pdl_provenance() -> None:
    person = person_from_pdl(
        "p1",
        {
            "full_name": "Maya Chen",
            "linkedin_url": "https://linkedin.com/in/mayachen",
            "job_title": "Founder",
            "job_company_name": "VectorForge",
        },
    )
    company = company_from_pdl(
        "c1",
        {"display_name": "VectorForge", "funding_stages": ["pre_seed", "seed"]},
    )

    assert person.full_name.source == "people-data-labs:person.full_name"
    assert person.social_urls[0].source == "people-data-labs:person.profiles"
    assert company.stage.value == "seed"
    assert company.stage.source == "people-data-labs:company.latest_funding_stage"


def test_evidence_field_requires_confidence_and_source() -> None:
    with pytest.raises(ValueError):
        EvidenceField(value="invented", source="", confidence=0.5)
    with pytest.raises(ValueError):
        EvidenceField(value="invented", source="provider", confidence=1.5)
