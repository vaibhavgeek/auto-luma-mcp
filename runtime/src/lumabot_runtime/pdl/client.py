from __future__ import annotations

from typing import Any

from lumabot_runtime.enrichment.models import (
    EnrichedCompany,
    EnrichedPerson,
    EvidenceField,
)


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
