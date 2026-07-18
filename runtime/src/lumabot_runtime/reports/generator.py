from __future__ import annotations

from uuid import uuid5, NAMESPACE_URL

from lumabot_runtime.enrichment.models import (
    EnrichedPerson,
    EnrichmentStatus,
    Event,
    EventAttendee,
    UserProfile,
)
from lumabot_runtime.enrichment.resolution import IdentityResolver
from lumabot_runtime.reports.models import EventReport, ReportPerson
from lumabot_runtime.scoring.event import score_event
from lumabot_runtime.scoring.person import score_person


async def generate_event_report(
    user_profile: UserProfile,
    event: Event,
    attendees: list[EventAttendee],
    enriched_people: list[EnrichedPerson],
) -> EventReport:
    resolver = IdentityResolver()
    report_people: list[ReportPerson] = []
    enriched_by_id = {person.person_id: person for person in enriched_people}
    for attendee in attendees:
        person = enriched_by_id.get(attendee.person_id)
        match = None if person is not None else resolver.match(attendee, enriched_people)
        identity_confidence = 1.0 if person is not None else match.confidence
        if person is None:
            assert match is not None
            status = EnrichmentStatus.IDENTITY_UNCERTAIN if match.candidates else EnrichmentStatus.ENRICHMENT_PENDING
            report_people.append(
                ReportPerson(
                    attendee=attendee,
                    enrichment_status=status,
                    identity_confidence=match.confidence,
                    why_the_person_matters="Enrichment is not confident enough yet; keep them visible for manual review.",
                    conversation_opener=f"Ask {attendee.full_name} what brought them to {event.title}.",
                    uncertainty_warnings=match.evidence,
                )
            )
            continue
        person_score = score_person(
            user_profile=user_profile,
            person=person,
            identity_confidence=identity_confidence,
            event_context=event.description,
        )
        status = (
            EnrichmentStatus.IDENTITY_UNCERTAIN
            if identity_confidence < 0.75
            else person.enrichment_status
        )
        report_people.append(
            ReportPerson(
                attendee=attendee,
                enrichment_status=status,
                relevance_score=person_score,
                identity_confidence=identity_confidence,
                company=_value(person.company_name),
                company_size=_value(person.company_employee_count),
                funding_stage=_value(person.company_stage),
                profile_image_url=_value(person.profile_image_url),
                why_the_person_matters=_why(person, person_score.score),
                conversation_opener=_opener(attendee, event, person),
                evidence_links=_links(person),
                uncertainty_warnings=[] if match is None or match.matched else match.evidence,
            )
        )
    ranked = sorted(
        report_people,
        key=lambda item: item.relevance_score.score if item.relevance_score else 0.0,
        reverse=True,
    )
    enriched_count = sum(
        1
        for item in report_people
        if item.enrichment_status in {EnrichmentStatus.ENRICHED, EnrichmentStatus.IDENTITY_UNCERTAIN}
    )
    event_score = score_event(user_profile=user_profile, event=event, likely_attendees=enriched_people)
    return EventReport(
        report_id=str(uuid5(NAMESPACE_URL, f"{event.event_id}:event-report-v1")),
        event=event,
        event_summary=_summary(event, len(attendees), enriched_count),
        registration_status=event.registration_status,
        organizers=[event.organizer] if event.organizer else [],
        event_score=event_score,
        top_people_to_meet=ranked[:5],
        attendees=ranked,
        report_completeness=round(enriched_count / max(1, len(attendees)), 2),
    )


def _value(field: object | None) -> str | None:
    return str(getattr(field, "value", "")) if field is not None else None


def _links(person: EnrichedPerson) -> list[str]:
    links: list[str] = []
    for field in [*person.social_urls, person.company_name, person.title, person.industry]:
        if field is not None and field.source_url:
            links.append(field.source_url)
    return sorted(set(links))


def _why(person: EnrichedPerson, score: float) -> str:
    title = _value(person.title) or "attendee"
    company = _value(person.company_name) or "their company"
    return f"{person.full_name.value} is a {title} at {company} with relevance score {score:g}."


def _opener(attendee: EventAttendee, event: Event, person: EnrichedPerson) -> str:
    interest = _value(person.interests[0]) if person.interests else event.title
    return f"Ask {attendee.full_name} about {interest} and what they hope to learn at {event.title}."


def _summary(event: Event, attendee_count: int, enriched_count: int) -> str:
    return (
        f"{event.title} has {attendee_count} visible attendees; "
        f"{enriched_count} have enrichment useful for prioritization."
    )
