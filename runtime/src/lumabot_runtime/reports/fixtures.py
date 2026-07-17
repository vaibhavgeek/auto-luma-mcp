from __future__ import annotations

from lumabot_runtime.enrichment.models import (
    EnrichedPerson,
    Event,
    EventAttendee,
    EvidenceField,
    UserProfile,
)


def evidence(value: object, confidence: float = 0.9, source: str = "fixture") -> EvidenceField:
    return EvidenceField(
        value=value,
        source=source,
        source_url=f"https://pdl.local/fixtures/{source}",
        confidence=confidence,
    )


def demo_fixture(*, full: bool = True) -> tuple[UserProfile, Event, list[EventAttendee], list[EnrichedPerson]]:
    profile = UserProfile(
        goals=["engineering roles", "meet founders", "hiring managers"],
        target_roles=["founder", "engineering leader", "hiring manager"],
        industries=["ai", "developer tools"],
        company_stages=["seed"],
        company_sizes=["fewer than 50 employees"],
        event_types=["hackathon", "meetup"],
        region="Bay Area",
        keywords=["ai", "developer tools", "founder", "engineering"],
    )
    event = Event(
        event_id="evt-ai-hacknight",
        title="Bay Area AI Hacknight",
        description="Hackathon for seed-stage AI and developer tools builders.",
        event_type="hackathon",
        organizer="AI Builders Collective",
        location="San Francisco, Bay Area",
        registration_status="open",
        source_url="https://lu.ma/fixture-ai-hacknight",
        evidence_quality=0.9,
    )
    attendees = [
        EventAttendee(
            attendee_id="att-maya",
            person_id="person-maya",
            full_name="Maya Chen",
            title="Founder",
            company="VectorForge",
            social_urls=["https://linkedin.com/in/mayachen"],
        ),
        EventAttendee(
            attendee_id="att-avi",
            person_id="person-avi",
            full_name="Avi Patel",
            title="Head of Engineering",
            company="SmallStack",
            social_urls=["https://linkedin.com/in/avipatel"],
        ),
        EventAttendee(
            attendee_id="att-sam",
            person_id="person-sam",
            full_name="Sam Lee",
            title="Designer",
            company="ConsumerCo",
            social_urls=["https://linkedin.com/in/samlee"],
        ),
    ]
    enriched = [
        EnrichedPerson(
            person_id="person-maya",
            full_name=evidence("Maya Chen", 0.98),
            title=evidence("Founder and CEO", 0.95),
            company_name=evidence("VectorForge", 0.95),
            company_stage=evidence("seed", 0.9),
            company_employee_count=evidence(18, 0.85),
            industry=evidence("AI developer tools", 0.9),
            location=evidence("San Francisco Bay Area", 0.85),
            social_urls=[evidence("https://linkedin.com/in/mayachen", 0.98)],
            profile_image_url=evidence("https://images.local/maya.png", 0.7),
            interests=[evidence("agentic developer tools", 0.8)],
            sources_agreeing=3,
        ),
        EnrichedPerson(
            person_id="person-avi",
            full_name=evidence("Avi Patel", 0.98),
            title=evidence("Head of Engineering", 0.92),
            company_name=evidence("SmallStack", 0.9),
            company_stage=evidence("seed", 0.8),
            company_employee_count=evidence(34, 0.8),
            industry=evidence("developer tools", 0.9),
            location=evidence("Oakland, Bay Area", 0.8),
            social_urls=[evidence("https://linkedin.com/in/avipatel", 0.96)],
            interests=[evidence("platform engineering", 0.7)],
            sources_agreeing=2,
        ),
        EnrichedPerson(
            person_id="person-sam",
            full_name=evidence("Sam Lee", 0.95),
            title=evidence("Product Designer", 0.85),
            company_name=evidence("ConsumerCo", 0.85),
            company_stage=evidence("series b", 0.7),
            company_employee_count=evidence(140, 0.7),
            industry=evidence("consumer software", 0.7),
            location=evidence("San Francisco Bay Area", 0.8),
            social_urls=[evidence("https://linkedin.com/in/samlee", 0.95)],
            interests=[evidence("design systems", 0.65)],
            sources_agreeing=2,
        ),
    ]
    if not full:
        enriched = enriched[:1]
    return profile, event, attendees, enriched
