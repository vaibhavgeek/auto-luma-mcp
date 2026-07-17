from __future__ import annotations

import httpx
import pytest
import respx

from lumabot_runtime.enrichment.models import EvidenceField, RawCompany, RawPerson
from lumabot_runtime.nexla import FakeNexlaClient, HttpNexlaClient


@pytest.mark.asyncio
async def test_fake_nexla_contract_round_trip() -> None:
    client = FakeNexlaClient()
    person = RawPerson(
        person_id="p1",
        full_name="Maya Chen",
        social_urls=["https://LinkedIn.com/in/MayaChen"],
        company="VectorForge",
        title="Founder",
    )
    company = RawCompany(company_id="c1", name="VectorForge", website="https://vector.local")

    assert await client.submit_person(person) == "p1"
    assert await client.submit_company(company) == "c1"
    enriched = await client.get_enriched_person("p1")
    enriched_company = await client.get_enriched_company("c1")

    assert enriched.full_name.value == "Maya Chen"
    assert enriched.social_urls[0].value == "https://linkedin.com/in/mayachen"
    assert enriched_company.name.value == "VectorForge"
    assert await client.health_check() is True


@pytest.mark.asyncio
async def test_http_client_with_respx() -> None:
    base = "https://nexla.example"
    person_payload = {
        "person_id": "p1",
        "full_name": {"value": "Maya Chen", "source": "nexset", "confidence": 0.97},
        "social_urls": [],
    }
    with respx.mock(assert_all_called=True) as router:
        router.post(f"{base}/people").mock(return_value=httpx.Response(200, json={"id": "p1"}))
        router.get(f"{base}/people/p1/enriched").mock(
            return_value=httpx.Response(200, json=person_payload)
        )
        router.get(f"{base}/health").mock(return_value=httpx.Response(200, json={"ok": True}))
        client = HttpNexlaClient(base_url=base, api_key="secret")
        assert await client.submit_person(RawPerson(person_id="p1", full_name="Maya Chen")) == "p1"
        assert (await client.get_enriched_person("p1")).full_name.value == "Maya Chen"
        assert await client.health_check() is True


@pytest.mark.asyncio
async def test_provider_timeout_maps_to_httpx_timeout() -> None:
    with respx.mock(assert_all_called=True) as router:
        router.get("https://nexla.example/health").mock(side_effect=httpx.ReadTimeout("timeout"))
        client = HttpNexlaClient(base_url="https://nexla.example", timeout_seconds=0.01)
        assert await client.health_check() is False


@pytest.mark.asyncio
async def test_malformed_enrichment_response() -> None:
    with respx.mock(assert_all_called=True) as router:
        router.get("https://nexla.example/people/p1/enriched").mock(
            return_value=httpx.Response(200, json=["not", "a", "dict"])
        )
        client = HttpNexlaClient(base_url="https://nexla.example")
        with pytest.raises(ValueError, match="malformed Nexla response"):
            await client.get_enriched_person("p1")


def test_evidence_field_requires_confidence_and_source() -> None:
    with pytest.raises(ValueError):
        EvidenceField(value="invented", source="", confidence=0.5)
    with pytest.raises(ValueError):
        EvidenceField(value="invented", source="provider", confidence=1.5)
