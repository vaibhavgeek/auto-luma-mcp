from __future__ import annotations

import httpx
import pytest
import respx

from lumabot_runtime.enrichment.models import RawPerson
from lumabot_runtime.hunter import FakeHunterClient, HunterClient


@pytest.mark.asyncio
async def test_hunter_finds_and_verifies_email() -> None:
    with respx.mock(assert_all_called=True) as router:
        finder = router.get("https://api.hunter.io/v2/email-finder").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": {
                        "email": "maya@vectorforge.ai",
                        "score": 91,
                        "sources": [{"uri": "https://example.com/maya"}],
                    }
                },
            )
        )
        verifier = router.get("https://api.hunter.io/v2/email-verifier").mock(
            return_value=httpx.Response(200, json={"data": {"status": "valid", "score": 96}})
        )
        client = HunterClient(api_key="hunter-secret")
        email = await client.find_email(
            RawPerson(
                person_id="p1",
                full_name="Maya Chen",
                company="VectorForge",
                company_domain="vectorforge.ai",
            )
        )
        verification = await client.verify_email("maya@vectorforge.ai")

    assert finder.calls[0].request.url.params["domain"] == "vectorforge.ai"
    assert finder.calls[0].request.url.params["first_name"] == "Maya"
    assert finder.calls[0].request.url.params["last_name"] == "Chen"
    assert finder.calls[0].request.url.params["api_key"] == "hunter-secret"
    assert email is not None
    assert email.value == "maya@vectorforge.ai"
    assert email.confidence == pytest.approx(0.91)
    assert verification is not None
    assert verification.value == "valid"
    assert verification.confidence == pytest.approx(0.96)


@pytest.mark.asyncio
async def test_hunter_domain_search_maps_sources() -> None:
    with respx.mock(assert_all_called=True) as router:
        router.get("https://api.hunter.io/v2/domain-search").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": {
                        "emails": [
                            {
                                "value": "founder@vectorforge.ai",
                                "confidence": 84,
                                "sources": [{"uri": "https://example.com/source"}],
                            }
                        ]
                    }
                },
            )
        )
        client = HunterClient(api_key="hunter-secret")
        emails = await client.domain_search("vectorforge.ai")

    assert emails[0].source == "hunter:domain-search.email"
    assert emails[0].source_url == "https://example.com/source"


@pytest.mark.asyncio
async def test_fake_hunter_client() -> None:
    client = FakeHunterClient(found_email="maya@vectorforge.ai", domain_emails=["team@vectorforge.ai"])

    found = await client.find_email(
        RawPerson(person_id="p1", full_name="Maya Chen", company_domain="vectorforge.ai")
    )
    verified = await client.verify_email("maya@vectorforge.ai")
    domain = await client.domain_search("vectorforge.ai")

    assert found is not None and found.value == "maya@vectorforge.ai"
    assert verified is not None and verified.value == "valid"
    assert domain[0].value == "team@vectorforge.ai"

