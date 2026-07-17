from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from lumabot_runtime.enrichment.models import EnrichedCompany, EnrichedPerson, EvidenceField, RawCompany, RawPerson
from lumabot_runtime.pdl.client import company_from_pdl, person_from_pdl

DEFAULT_PDL_PERSON_CAPABILITY = "pdl-person-enrich-e8ccbe47"
DEFAULT_PDL_COMPANY_CAPABILITY = "pdl-company-enrich-0f2efa9c"
DEFAULT_HUNTER_VERIFY_CAPABILITY = "hunter-email-verifier-1d1a2575"

ZeroRunner = Callable[[list[str], str | None], Awaitable[dict[str, Any]]]


@dataclass
class ZeroCapabilityClient:
    runner: ZeroRunner | None = None
    zero_bin: str = "zero"
    max_pay_usdc: str = "0.25"
    timeout_seconds: int = 60
    pdl_person_capability: str = DEFAULT_PDL_PERSON_CAPABILITY
    pdl_company_capability: str = DEFAULT_PDL_COMPANY_CAPABILITY
    hunter_verify_capability: str = DEFAULT_HUNTER_VERIFY_CAPABILITY

    async def enrich_person(self, person: RawPerson) -> EnrichedPerson:
        payload = _zero_http_payload(_person_body(person))
        result = await self._fetch(self.pdl_person_capability, payload)
        return person_from_pdl(person.person_id, _provider_body(result))

    async def enrich_company(self, company: RawCompany) -> EnrichedCompany:
        payload = _zero_http_payload(_company_body(company))
        result = await self._fetch(self.pdl_company_capability, payload)
        return company_from_pdl(company.company_id, _provider_body(result))

    async def find_email(self, person: RawPerson) -> EvidenceField | None:
        del person
        return None

    async def verify_email(self, email: str) -> EvidenceField | None:
        result = await self._fetch(self.hunter_verify_capability, {"email": email})
        body = _provider_body(result)
        data = _nested_data(body)
        status = data.get("status") or data.get("result")
        if not status:
            return None
        score = data.get("score")
        confidence = float(score) / 100 if isinstance(score, int | float) else 0.5
        return EvidenceField(
            value=str(status),
            source="zero:hunter-email-verifier",
            source_url="https://info.zero.xyz/",
            confidence=max(0.0, min(1.0, confidence)),
        )

    async def domain_search(self, domain: str) -> list[EvidenceField]:
        del domain
        return []

    async def health_check(self) -> bool:
        try:
            await self._run(["get", "--json", self.pdl_person_capability], None)
        except Exception:
            return False
        return True

    async def _fetch(self, capability: str, payload: dict[str, Any]) -> dict[str, Any]:
        result = await self._run(
            [
                "fetch",
                "--json",
                "--capability",
                capability,
                "--method",
                "POST",
                "--max-pay",
                self.max_pay_usdc,
                "--timeout",
                str(self.timeout_seconds),
                "--data-stdin",
            ],
            json.dumps(payload),
        )
        if not result.get("ok", False):
            raise RuntimeError(f"Zero capability call failed: {result.get('status')}")
        return result

    async def _run(self, args: list[str], stdin: str | None) -> dict[str, Any]:
        if self.runner:
            return await self.runner(args, stdin)
        process = await asyncio.create_subprocess_exec(
            self.zero_bin,
            *args,
            stdin=asyncio.subprocess.PIPE if stdin is not None else None,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate(stdin.encode() if stdin is not None else None)
        if process.returncode != 0:
            raise RuntimeError(stderr.decode().strip() or "zero command failed")
        try:
            payload = json.loads(stdout.decode())
        except json.JSONDecodeError as exc:
            raise ValueError("malformed Zero CLI response") from exc
        if not isinstance(payload, dict):
            raise ValueError("malformed Zero CLI response")
        return payload


def _zero_http_payload(body: dict[str, Any]) -> dict[str, Any]:
    return {
        "input": {
            "type": "http",
            "method": "POST",
            "bodyType": "json",
            "body": {key: value for key, value in body.items() if value not in (None, "", [])},
        }
    }


def _person_body(person: RawPerson) -> dict[str, Any]:
    return {
        "name": person.full_name,
        "email": person.email,
        "profile": person.social_urls[0] if person.social_urls else None,
        "company": person.company or person.company_domain,
        "location": person.location,
        "min_likelihood": 5,
    }


def _company_body(company: RawCompany) -> dict[str, Any]:
    return {
        "name": company.name,
        "website": company.website,
        "min_likelihood": 5,
    }


def _provider_body(result: dict[str, Any]) -> dict[str, Any]:
    body = result.get("body")
    if isinstance(body, dict):
        candidate = body
    elif isinstance(body, str):
        parsed = json.loads(body)
        candidate = parsed if isinstance(parsed, dict) else {}
    else:
        body_raw = result.get("bodyRaw")
        parsed = json.loads(body_raw) if isinstance(body_raw, str) and body_raw else {}
        candidate = parsed if isinstance(parsed, dict) else {}
    if "body" in candidate and isinstance(candidate["body"], dict):
        candidate = candidate["body"]
    if "data" in candidate and isinstance(candidate["data"], dict) and set(candidate) <= {"data", "success", "meta"}:
        return candidate["data"]
    return candidate


def _nested_data(payload: dict[str, Any]) -> dict[str, Any]:
    current: object = payload
    for _ in range(3):
        if isinstance(current, dict) and isinstance(current.get("data"), dict):
            current = current["data"]
        else:
            break
    return current if isinstance(current, dict) else {}

