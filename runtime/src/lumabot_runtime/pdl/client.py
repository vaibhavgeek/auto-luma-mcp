from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx

from lumabot_runtime.enrichment.models import (
    EnrichedCompany,
    EnrichedPerson,
    EvidenceField,
    RawCompany,
    RawPerson,
)

PDL_BASE_URL = "https://api.peopledatalabs.com"
PDL_PERSON_ENRICH_PATH = "/v5/person/enrich"
PDL_COMPANY_ENRICH_PATH = "/v5/company/enrich"


class EnrichmentClient(Protocol):
    async def enrich_person(self, person: RawPerson) -> EnrichedPerson: ...

    async def enrich_company(self, company: RawCompany) -> EnrichedCompany: ...

    async def health_check(self) -> bool: ...


@dataclass
class PeopleDataLabsClient:
    api_key: str
    base_url: str = PDL_BASE_URL
    timeout_seconds: float = 10.0
    min_likelihood: int = 5

    async def enrich_person(self, person: RawPerson) -> EnrichedPerson:
        payload = await self._get(PDL_PERSON_ENRICH_PATH, self._person_params(person))
        return person_from_pdl(person.person_id, payload)

    async def enrich_company(self, company: RawCompany) -> EnrichedCompany:
        payload = await self._get(PDL_COMPANY_ENRICH_PATH, self._company_params(company))
        return company_from_pdl(company.company_id, payload)

    async def health_check(self) -> bool:
        try:
            await self._get(PDL_COMPANY_ENRICH_PATH, {"name": "People Data Labs"})
        except httpx.HTTPStatusError as exc:
            return exc.response.status_code == 404
        except httpx.HTTPError:
            return False
        return True

    async def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.get(
                f"{self.base_url.rstrip('/')}{path}",
                headers={"X-Api-Key": self.api_key},
                params={key: value for key, value in params.items() if value not in (None, "", [])},
            )
            if response.status_code == 404:
                raise LookupError("People Data Labs did not find a matching record")
            response.raise_for_status()
            data = response.json()
        if not isinstance(data, dict):
            raise ValueError("malformed People Data Labs response")
        return data

    def _person_params(self, person: RawPerson) -> dict[str, Any]:
        return {
            "name": person.full_name,
            "profile": person.social_urls[0] if person.social_urls else None,
            "company": person.company,
            "title": person.title,
            "location": person.location,
            "min_likelihood": self.min_likelihood,
        }

    def _company_params(self, company: RawCompany) -> dict[str, Any]:
        return {
            "name": company.name,
            "website": company.website,
            "min_likelihood": self.min_likelihood,
        }


@dataclass
class FakePeopleDataLabsClient:
    people: dict[str, EnrichedPerson] = field(default_factory=dict)
    companies: dict[str, EnrichedCompany] = field(default_factory=dict)
    fail_health: bool = False

    async def enrich_person(self, person: RawPerson) -> EnrichedPerson:
        self.people.setdefault(person.person_id, _enrich_raw_person(person))
        return self.people[person.person_id]

    async def enrich_company(self, company: RawCompany) -> EnrichedCompany:
        self.companies.setdefault(company.company_id, _enrich_raw_company(company))
        return self.companies[company.company_id]

    async def health_check(self) -> bool:
        return not self.fail_health


def person_from_pdl(person_id: str, payload: dict[str, Any]) -> EnrichedPerson:
    experience = _current_experience(payload)
    company = experience.get("company") if isinstance(experience.get("company"), dict) else {}
    title = experience.get("title") if isinstance(experience, dict) else None
    social_urls = _social_urls(payload)
    return EnrichedPerson(
        person_id=person_id,
        full_name=_pdl_field(payload.get("full_name") or payload.get("name"), "person.full_name", 0.92),
        title=_optional_pdl_field(title or payload.get("job_title"), "person.experience.title", 0.82),
        company_name=_optional_pdl_field(
            company.get("name") or payload.get("job_company_name"),
            "person.experience.company.name",
            0.8,
        ),
        company_stage=None,
        company_employee_count=_optional_pdl_field(
            company.get("employee_count") or payload.get("job_company_employee_count"),
            "person.experience.company.employee_count",
            0.65,
        ),
        industry=_optional_pdl_field(
            company.get("industry") or payload.get("industry"),
            "person.experience.company.industry",
            0.7,
        ),
        location=_optional_pdl_field(
            payload.get("location_name") or payload.get("location_locality"),
            "person.location",
            0.75,
        ),
        social_urls=[_pdl_field(url, "person.profiles", 0.9) for url in social_urls],
        profile_image_url=_optional_pdl_field(payload.get("profile_pic_url"), "person.profile_pic_url", 0.6),
        interests=[_pdl_field(item, "person.skills/interests", 0.55) for item in _list(payload.get("skills"))[:5]],
        sources_agreeing=2 if social_urls and company else 1,
    )


def company_from_pdl(company_id: str, payload: dict[str, Any]) -> EnrichedCompany:
    return EnrichedCompany(
        company_id=company_id,
        name=_pdl_field(
            payload.get("display_name") or payload.get("name"),
            "company.display_name",
            0.92,
        ),
        industry=_optional_pdl_field(payload.get("industry"), "company.industry", 0.82),
        employee_count=_optional_pdl_field(payload.get("employee_count"), "company.employee_count", 0.75),
        stage=_optional_pdl_field(
            payload.get("latest_funding_stage") or _last(_list(payload.get("funding_stages"))),
            "company.latest_funding_stage",
            0.7,
        ),
        website=_optional_pdl_field(payload.get("website"), "company.website", 0.8),
    )


def _field(value: object, confidence: float = 0.7) -> EvidenceField:
    return EvidenceField(
        value=value,
        source="fake-people-data-labs",
        source_url="https://docs.peopledatalabs.com/",
        confidence=confidence,
    )


def _pdl_field(value: object, field_name: str, confidence: float) -> EvidenceField:
    return EvidenceField(
        value=value,
        source=f"people-data-labs:{field_name}",
        source_url="https://docs.peopledatalabs.com/",
        confidence=confidence,
    )


def _optional_pdl_field(value: object | None, field_name: str, confidence: float) -> EvidenceField | None:
    if value in (None, "", []):
        return None
    return _pdl_field(value, field_name, confidence)


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


def _current_experience(payload: dict[str, Any]) -> dict[str, Any]:
    experiences = payload.get("experience")
    if not isinstance(experiences, list):
        return {}
    for item in experiences:
        if isinstance(item, dict) and item.get("end_date") in (None, "", "present"):
            return item
    return experiences[0] if experiences and isinstance(experiences[0], dict) else {}


def _social_urls(payload: dict[str, Any]) -> list[str]:
    urls: list[str] = []
    for profile in _list(payload.get("profiles")):
        if isinstance(profile, dict) and profile.get("url"):
            urls.append(str(profile["url"]).strip().lower())
        elif isinstance(profile, str):
            urls.append(profile.strip().lower())
    linkedin_url = payload.get("linkedin_url")
    if linkedin_url:
        urls.append(str(linkedin_url).strip().lower())
    return sorted(set(urls))


def _list(value: object) -> list[Any]:
    return value if isinstance(value, list) else []


def _last(values: list[Any]) -> Any | None:
    return values[-1] if values else None
