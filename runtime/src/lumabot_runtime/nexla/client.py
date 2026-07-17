from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

import httpx

from lumabot_runtime.enrichment.models import (
    EnrichedCompany,
    EnrichedPerson,
    EvidenceField,
    RawCompany,
    RawPerson,
)


class NexlaClient(Protocol):
    async def submit_person(self, person: RawPerson) -> str: ...

    async def submit_company(self, company: RawCompany) -> str: ...

    async def get_enriched_person(self, person_id: str) -> EnrichedPerson: ...

    async def get_enriched_company(self, company_id: str) -> EnrichedCompany: ...

    async def health_check(self) -> bool: ...


@dataclass
class HttpNexlaClient:
    base_url: str
    api_key: str | None = None
    timeout_seconds: float = 10.0

    async def submit_person(self, person: RawPerson) -> str:
        payload = await self._post("/people", person.model_dump(mode="json"))
        return str(payload.get("person_id") or payload.get("id") or person.person_id)

    async def submit_company(self, company: RawCompany) -> str:
        payload = await self._post("/companies", company.model_dump(mode="json"))
        return str(payload.get("company_id") or payload.get("id") or company.company_id)

    async def get_enriched_person(self, person_id: str) -> EnrichedPerson:
        payload = await self._get(f"/people/{person_id}/enriched")
        return EnrichedPerson.model_validate(payload)

    async def get_enriched_company(self, company_id: str) -> EnrichedCompany:
        payload = await self._get(f"/companies/{company_id}/enriched")
        return EnrichedCompany.model_validate(payload)

    async def health_check(self) -> bool:
        try:
            payload = await self._get("/health")
        except httpx.HTTPError:
            return False
        return bool(payload.get("ok", payload.get("healthy", True)))

    async def _post(self, path: str, payload: dict[str, object]) -> dict[str, object]:
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(
                f"{self.base_url.rstrip('/')}{path}",
                headers=self._headers(),
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
        if not isinstance(data, dict):
            raise ValueError("malformed Nexla response")
        return data

    async def _get(self, path: str) -> dict[str, object]:
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.get(
                f"{self.base_url.rstrip('/')}{path}",
                headers=self._headers(),
            )
            response.raise_for_status()
            data = response.json()
        if not isinstance(data, dict):
            raise ValueError("malformed Nexla response")
        return data

    def _headers(self) -> dict[str, str]:
        if not self.api_key:
            return {}
        return {"authorization": f"Bearer {self.api_key}"}


@dataclass
class FakeNexlaClient:
    people: dict[str, EnrichedPerson] = field(default_factory=dict)
    companies: dict[str, EnrichedCompany] = field(default_factory=dict)
    submitted_people: list[RawPerson] = field(default_factory=list)
    submitted_companies: list[RawCompany] = field(default_factory=list)
    fail_health: bool = False

    async def submit_person(self, person: RawPerson) -> str:
        self.submitted_people.append(person)
        self.people.setdefault(person.person_id, _enrich_raw_person(person))
        return person.person_id

    async def submit_company(self, company: RawCompany) -> str:
        self.submitted_companies.append(company)
        self.companies.setdefault(company.company_id, _enrich_raw_company(company))
        return company.company_id

    async def get_enriched_person(self, person_id: str) -> EnrichedPerson:
        try:
            return self.people[person_id]
        except KeyError as exc:
            raise LookupError(f"missing enriched person {person_id}") from exc

    async def get_enriched_company(self, company_id: str) -> EnrichedCompany:
        try:
            return self.companies[company_id]
        except KeyError as exc:
            raise LookupError(f"missing enriched company {company_id}") from exc

    async def health_check(self) -> bool:
        return not self.fail_health


def _field(value: object, confidence: float = 0.7) -> EvidenceField:
    return EvidenceField(
        value=value,
        source="fake-nexla",
        source_url="https://nexla.local/fixtures",
        confidence=confidence,
    )


def _enrich_raw_person(person: RawPerson) -> EnrichedPerson:
    return EnrichedPerson(
        person_id=person.person_id,
        full_name=_field(person.full_name, 0.95),
        title=_field(person.title, 0.7) if person.title else None,
        company_name=_field(person.company, 0.7) if person.company else None,
        location=_field(person.location, 0.65) if person.location else None,
        social_urls=[_field(url.strip().lower(), 0.9) for url in person.social_urls],
    )


def _enrich_raw_company(company: RawCompany) -> EnrichedCompany:
    return EnrichedCompany(
        company_id=company.company_id,
        name=_field(company.name, 0.95),
        website=_field(company.website, 0.8) if company.website else None,
    )

