from __future__ import annotations

from lumabot_runtime.enrichment.models import EnrichedPerson, EventAttendee
from lumabot_runtime.enrichment.resolution import IdentityResolver, normalize_social_url
from lumabot_runtime.reports.fixtures import evidence


def test_exact_social_profile_match() -> None:
    attendee = EventAttendee(
        attendee_id="att-1",
        person_id="unknown",
        full_name="Maya Chen",
        social_urls=["https://www.linkedin.com/in/MayaChen/"],
    )
    person = EnrichedPerson(
        person_id="p1",
        full_name=evidence("Maya Chen"),
        social_urls=[evidence("https://linkedin.com/in/mayachen")],
        sources_agreeing=2,
    )

    match = IdentityResolver().match(attendee, [person])

    assert match.matched is True
    assert match.person_id == "p1"
    assert match.confidence >= IdentityResolver.exact_social_threshold
    assert "exact social URL match" in match.evidence


def test_same_name_collision_preserves_candidates() -> None:
    attendee = EventAttendee(attendee_id="att-1", person_id="unknown", full_name="Sam Lee")
    candidates = [
        EnrichedPerson(person_id="p1", full_name=evidence("Sam Lee")),
        EnrichedPerson(person_id="p2", full_name=evidence("Sam Lee")),
    ]

    match = IdentityResolver().match(attendee, candidates)

    assert match.matched is False
    assert match.person_id is None
    assert sorted(match.candidates) == []
    assert "name-only match capped" in match.evidence


def test_conflicting_company_prevents_confident_merge() -> None:
    attendee = EventAttendee(
        attendee_id="att-1",
        person_id="unknown",
        full_name="Jordan Kim",
        company="Aperture",
        title="Engineer",
    )
    person = EnrichedPerson(
        person_id="p1",
        full_name=evidence("Jordan Kim"),
        company_name=evidence("DifferentCo"),
        title=evidence("Engineer"),
    )

    match = IdentityResolver().match(attendee, [person])

    assert match.matched is False
    assert match.confidence < IdentityResolver.confident_threshold


def test_normalize_social_url() -> None:
    assert normalize_social_url(" https://WWW.LinkedIn.com/in/MayaChen/ ") == "https://linkedin.com/in/mayachen"

