from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Protocol

from lumabot_runtime.enrichment.models import EnrichedCompany, EnrichedPerson, EvidenceField, RawCompany, RawPerson


class EnrichmentProvider(Protocol):
    async def enrich_person(self, person: RawPerson) -> EnrichedPerson: ...

    async def enrich_company(self, company: RawCompany) -> EnrichedCompany: ...

    async def verify_email(self, email: str) -> EvidenceField | None: ...


@dataclass
class EnrichmentBundle:
    person: EnrichedPerson
    company: EnrichedCompany | None = None
    warnings: list[str] | None = None


@dataclass
class EnrichmentService:
    provider: EnrichmentProvider

    async def enrich_attendee(self, person: RawPerson) -> EnrichmentBundle:
        tasks: list[asyncio.Task[object]] = [
            asyncio.create_task(self.provider.enrich_person(person)),
        ]
        company_task: asyncio.Task[object] | None = None
        verify_task: asyncio.Task[object] | None = None

        if person.company:
            company_task = asyncio.create_task(
                self.provider.enrich_company(
                    RawCompany(
                        company_id=f"company:{person.company.lower()}",
                        name=person.company,
                        website=person.company_domain,
                    )
                )
            )
            tasks.append(company_task)
        if person.email:
            verify_task = asyncio.create_task(self.provider.verify_email(person.email))
            tasks.append(verify_task)

        await asyncio.gather(*tasks, return_exceptions=True)
        warnings: list[str] = []
        enriched_person = _result(tasks[0], warnings)
        if not isinstance(enriched_person, EnrichedPerson):
            enriched_person = _fallback_person(person)

        enriched_company = _result(company_task, warnings) if company_task else None
        if not isinstance(enriched_company, EnrichedCompany):
            enriched_company = None

        verification = _result(verify_task, warnings) if verify_task else None
        if isinstance(verification, EvidenceField):
            enriched_person.email_verification = verification

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
