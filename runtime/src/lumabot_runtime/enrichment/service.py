from __future__ import annotations

import asyncio
from dataclasses import dataclass

from lumabot_runtime.clearbit import CompanyHintClient
from lumabot_runtime.enrichment.models import EnrichedCompany, EnrichedPerson, EvidenceField, RawCompany, RawPerson
from lumabot_runtime.hunter import EmailIntelligenceClient
from lumabot_runtime.pdl import EnrichmentClient


@dataclass
class EnrichmentBundle:
    person: EnrichedPerson
    company: EnrichedCompany | None = None
    warnings: list[str] | None = None


@dataclass
class EnrichmentService:
    primary: EnrichmentClient
    email_intelligence: EmailIntelligenceClient | None = None
    company_hints: CompanyHintClient | None = None

    async def enrich_attendee(self, person: RawPerson) -> EnrichmentBundle:
        tasks: list[asyncio.Task[object]] = [
            asyncio.create_task(self.primary.enrich_person(person)),
        ]
        company_task: asyncio.Task[object] | None = None
        email_task: asyncio.Task[object] | None = None
        verify_task: asyncio.Task[object] | None = None
        clearbit_task: asyncio.Task[object] | None = None

        if person.company:
            company_task = asyncio.create_task(
                self.primary.enrich_company(
                    RawCompany(
                        company_id=f"company:{person.company.lower()}",
                        name=person.company,
                        website=person.company_domain,
                    )
                )
            )
            tasks.append(company_task)
        if self.email_intelligence:
            email_task = asyncio.create_task(self.email_intelligence.find_email(person))
            tasks.append(email_task)
            if person.email:
                verify_task = asyncio.create_task(self.email_intelligence.verify_email(person.email))
                tasks.append(verify_task)
        if self.company_hints and person.company:
            clearbit_task = asyncio.create_task(self.company_hints.suggest_companies(person.company))
            tasks.append(clearbit_task)

        await asyncio.gather(*tasks, return_exceptions=True)
        warnings: list[str] = []
        enriched_person = _result(tasks[0], warnings)
        if not isinstance(enriched_person, EnrichedPerson):
            enriched_person = _fallback_person(person)

        enriched_company = _result(company_task, warnings) if company_task else None
        if not isinstance(enriched_company, EnrichedCompany):
            enriched_company = None

        found_email = _result(email_task, warnings) if email_task else None
        if isinstance(found_email, EvidenceField):
            enriched_person.professional_email = found_email
        verification = _result(verify_task, warnings) if verify_task else None
        if isinstance(verification, EvidenceField):
            enriched_person.email_verification = verification

        hints = _result(clearbit_task, warnings) if clearbit_task else None
        if isinstance(hints, list):
            _apply_company_hints(enriched_company, enriched_person, hints)

        return EnrichmentBundle(
            person=enriched_person,
            company=enriched_company,
            warnings=warnings,
        )


def _result(task: asyncio.Task[object] | None, warnings: list[str]) -> object | None:
    if task is None:
        return None
    exception = task.exception()
    if exception is not None:
        warnings.append(str(exception))
        return None
    result = task.result()
    if isinstance(result, Exception):
        warnings.append(str(result))
        return None
    return result


def _fallback_person(person: RawPerson) -> EnrichedPerson:
    return EnrichedPerson(
        person_id=person.person_id,
        full_name=EvidenceField(
            value=person.full_name,
            source="luma-visible-attendee",
            source_url=None,
            confidence=0.6,
        ),
    )


def _apply_company_hints(
    company: EnrichedCompany | None,
    person: EnrichedPerson,
    hints: list[object],
) -> None:
    if not hints:
        return
    first = hints[0]
    hint_domain = getattr(first, "domain", None)
    hint_logo = getattr(first, "logo_url", None)
    if company and company.website is None and hint_domain:
        company.website = hint_domain
    if person.profile_image_url is None and hint_logo:
        person.profile_image_url = hint_logo
