from __future__ import annotations

import json

import pytest

from lumabot_runtime.enrichment.models import RawCompany, RawPerson
from lumabot_runtime.zero_provider import ZeroCapabilityClient


@pytest.mark.asyncio
async def test_zero_pdl_person_uses_capability_fetch_payload() -> None:
    calls: list[tuple[list[str], str | None]] = []

    async def runner(args: list[str], stdin: str | None) -> dict:
        calls.append((args, stdin))
        return {
            "ok": True,
            "status": 200,
            "body": {
                "full_name": "Maya Chen",
                "linkedin_url": "https://linkedin.com/in/mayachen",
                "job_title": "Founder",
                "job_company_name": "VectorForge",
            },
        }

    client = ZeroCapabilityClient(runner=runner, max_pay_usdc="0.03")
    person = await client.enrich_person(
        RawPerson(
            person_id="p1",
            full_name="Maya Chen",
            social_urls=["https://linkedin.com/in/mayachen"],
            company="VectorForge",
        )
    )

    args, stdin = calls[0]
    assert args[:4] == ["fetch", "--json", "--capability", "pdl-person-enrich-e8ccbe47"]
    assert "--max-pay" in args
    assert "0.03" in args
    payload = json.loads(stdin or "{}")
    assert payload["input"]["type"] == "http"
    assert payload["input"]["method"] == "POST"
    assert payload["input"]["body"]["profile"] == "https://linkedin.com/in/mayachen"
    assert person.full_name.value == "Maya Chen"
    assert person.full_name.source == "people-data-labs:person.full_name"


@pytest.mark.asyncio
async def test_zero_pdl_company_maps_provider_body() -> None:
    async def runner(args: list[str], stdin: str | None) -> dict:
        del args, stdin
        return {
            "ok": True,
            "status": 200,
            "body": {
                "data": {
                    "display_name": "VectorForge",
                    "employee_count": 18,
                    "latest_funding_stage": "seed",
                },
                "success": True,
            },
        }

    client = ZeroCapabilityClient(runner=runner)
    company = await client.enrich_company(RawCompany(company_id="c1", name="VectorForge"))

    assert company.name.value == "VectorForge"
    assert company.employee_count.value == 18
    assert company.stage.value == "seed"


@pytest.mark.asyncio
async def test_zero_hunter_email_verifier_maps_nested_response() -> None:
    async def runner(args: list[str], stdin: str | None) -> dict:
        assert args[3] == "hunter-email-verifier-1d1a2575"
        assert json.loads(stdin or "{}") == {"email": "maya@vectorforge.ai"}
        return {
            "ok": True,
            "status": 200,
            "body": {
                "data": {
                    "data": {
                        "email": "maya@vectorforge.ai",
                        "status": "valid",
                        "score": 92,
                    }
                },
                "success": True,
            },
        }

    client = ZeroCapabilityClient(runner=runner)
    result = await client.verify_email("maya@vectorforge.ai")

    assert result is not None
    assert result.value == "valid"
    assert result.source == "zero:hunter-email-verifier"
    assert result.confidence == pytest.approx(0.92)


@pytest.mark.asyncio
async def test_zero_failure_raises_safe_error() -> None:
    async def runner(args: list[str], stdin: str | None) -> dict:
        del args, stdin
        return {"ok": False, "status": 402, "body": {"error": "payment required"}}

    client = ZeroCapabilityClient(runner=runner)
    with pytest.raises(RuntimeError, match="Zero capability call failed"):
        await client.enrich_person(RawPerson(person_id="p1", full_name="Maya Chen"))

