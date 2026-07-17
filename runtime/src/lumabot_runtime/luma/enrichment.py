from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, NAMESPACE_URL, uuid5

from lumabot_runtime.enrichment.models import (
    EnrichedCompany,
    EnrichedPerson,
    Event,
    EventAttendee,
    EvidenceField,
    RawCompany,
    RawPerson,
    UserProfile,
)
from lumabot_runtime.enrichment.service import EnrichmentBundle, EnrichmentProvider, EnrichmentService
from lumabot_runtime.luma.extractors import extract_event_details, extract_visible_guests
from lumabot_runtime.luma.models import LumaEvent, LumaPerson
from lumabot_runtime.luma.repository import LumaRepository
from lumabot_runtime.reports.generator import generate_event_report
from lumabot_runtime.reports.models import EventReport


@dataclass(frozen=True)
class LumaGuestReportResult:
    report: EventReport
    visible_guest_count: int
    enriched_guest_count: int
    warnings: list[str] = field(default_factory=list)


@dataclass
class VisibleGuestProvider:
    """Offline provider used for local demos when paid Zero enrichment is disabled."""

    async def enrich_person(self, person: RawPerson) -> EnrichedPerson:
        return EnrichedPerson(
            person_id=person.person_id,
            full_name=_visible_field(person.full_name, 0.7),
            title=_optional_visible_field(person.title, 0.6),
            company_name=_optional_visible_field(person.company, 0.6),
            location=_optional_visible_field(person.location, 0.55),
            social_urls=[_visible_field(url, 0.75) for url in person.social_urls],
            interests=[_visible_field(person.event_context, 0.45)] if person.event_context else [],
            sources_agreeing=1,
        )

    async def enrich_company(self, company: RawCompany) -> EnrichedCompany:
        return EnrichedCompany(
            company_id=company.company_id,
            name=_visible_field(company.name, 0.6),
            website=_optional_visible_field(company.website, 0.5),
        )

    async def verify_email(self, email: str) -> EvidenceField | None:
        del email
        return None


async def generate_report_from_luma_guest_html(
    *,
    user_profile: UserProfile,
    event_url: str,
    event_html: str,
    guest_html: str,
    provider: EnrichmentProvider,
    repository: LumaRepository | None = None,
    user_id: UUID | None = None,
) -> LumaGuestReportResult:
    del user_id
    luma_event = extract_event_details(event_html, event_url)
    scraped_guests = extract_visible_guests(guest_html)

    if repository is not None:
        await repository.upsert_event(luma_event)

    attendees: list[EventAttendee] = []
    raw_people: list[RawPerson] = []
    for luma_person, attendee_fields in scraped_guests:
        if repository is not None:
            await repository.upsert_person(luma_person)
            await repository.upsert_attendee(
                {
                    "event_id": luma_event.event_id,
                    "person_id": luma_person.person_id,
                    "attendee_status": attendee_fields["attendee_status"],
                    "organizer_status": attendee_fields["organizer_status"],
                    "identity_confidence": luma_person.identity_confidence,
                    "source_selector": attendee_fields["source_selector"],
                }
            )
            await repository.enqueue_job(
                "ENRICH_PERSON",
                {"person_id": str(luma_person.person_id), "event_id": str(luma_event.event_id)},
                idempotency_key=f"enrich-person:{luma_person.person_id}",
            )
        attendees.append(_attendee_from_luma(luma_event.event_id, luma_person))
        raw_people.append(_raw_person_from_luma(luma_person))

    service = EnrichmentService(provider=provider)
    bundles = await _enrich_all(service, raw_people)
    warnings = [warning for bundle in bundles for warning in (bundle.warnings or [])]
    enriched_people = [bundle.person for bundle in bundles]
    report = await generate_event_report(
        user_profile=user_profile,
        event=_event_from_luma(luma_event),
        attendees=attendees,
        enriched_people=enriched_people,
    )
    enriched_count = sum(1 for bundle in bundles if not bundle.warnings)
    return LumaGuestReportResult(
        report=report,
        visible_guest_count=len(scraped_guests),
        enriched_guest_count=enriched_count,
        warnings=warnings,
    )


def _raw_person_from_luma(person: LumaPerson) -> RawPerson:
    social_urls = sorted(set(person.social_links))
    return RawPerson(
        person_id=str(person.person_id),
        full_name=person.full_name,
        social_urls=social_urls,
        company=person.company,
        title=person.title,
        location=person.location,
        event_context=person.bio,
    )


def _attendee_from_luma(event_id: UUID, person: LumaPerson) -> EventAttendee:
    social_urls = sorted({*person.social_links, *([person.profile_url] if person.profile_url else [])})
    return EventAttendee(
        attendee_id=str(uuid5(NAMESPACE_URL, f"attendee:{event_id}:{person.person_id}")),
        person_id=str(person.person_id),
        full_name=person.full_name,
        title=person.title,
        company=person.company,
        social_urls=social_urls,
        profile_image_url=person.image_url,
    )


def _event_from_luma(event: LumaEvent) -> Event:
    return Event(
        event_id=str(event.event_id),
        title=event.title,
        description=event.description or "",
        organizer=event.organizer,
        location=event.venue,
        starts_at=_parse_datetime(event.starts_at),
        registration_status=event.registration_state or "unknown",
        source_url=event.url,
        evidence_quality=0.85,
    )


async def _enrich_all(service: EnrichmentService, people: list[RawPerson]) -> list[EnrichmentBundle]:
    return list(await _gather_bundles(service, people))


async def _gather_bundles(
    service: EnrichmentService,
    people: list[RawPerson],
) -> tuple[EnrichmentBundle, ...]:
    import asyncio

    return tuple(await asyncio.gather(*(service.enrich_attendee(person) for person in people)))


def _parse_datetime(value: str | None) -> datetime:
    if not value:
        return datetime.now(UTC)
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return datetime.now(UTC)


def _visible_field(value: object, confidence: float) -> EvidenceField:
    return EvidenceField(
        value=value,
        source="luma-visible-guest-list",
        source_url="https://lu.ma/",
        confidence=confidence,
    )


def _optional_visible_field(value: object | None, confidence: float) -> EvidenceField | None:
    if value in (None, "", []):
        return None
    return _visible_field(value, confidence)
