from __future__ import annotations

from lumabot_runtime.enrichment.models import EnrichedPerson, Event, UserProfile
from lumabot_runtime.scoring.models import EventScore
from lumabot_runtime.scoring.person import score_person


def score_event(
    *,
    user_profile: UserProfile,
    event: Event,
    likely_attendees: list[EnrichedPerson],
) -> EventScore:
    score = 0.0
    reasons: list[str] = []
    evidence: list[str] = []

    score += _match_points(event.description, [*user_profile.industries, *user_profile.keywords], 20, "topic alignment", reasons)
    score += _match_points(event.event_type or "", user_profile.event_types, 15, "event-type alignment", reasons)
    score += _match_points(event.organizer or "", [*user_profile.industries, *user_profile.keywords], 10, "organizer relevance", reasons)
    if likely_attendees:
        attendee_scores = [
            score_person(
                user_profile=user_profile,
                person=person,
                identity_confidence=0.9,
                event_context=event.description,
            ).score
            for person in likely_attendees
        ]
        attendee_points = min(20.0, sum(attendee_scores) / max(1, len(attendee_scores)) * 0.2)
        score += attendee_points
        reasons.append(f"likely attendee relevance: +{attendee_points:.1f}")
        evidence.append("attendee scores")
    score += _match_points(event.location or "", [user_profile.region or ""], 10, "geography", reasons)
    if not event.registration_constraints:
        score += 10
        reasons.append("registration constraints: +10")
    else:
        reasons.append("registration constraints reduce confidence")
    quality_points = event.evidence_quality * 15
    score += quality_points
    reasons.append(f"evidence quality: +{quality_points:.1f}")
    evidence.append("event evidence quality")
    return EventScore(event_id=event.event_id, score=round(min(score, 100.0), 2), reasons=reasons, evidence=evidence)


def _match_points(
    text: str, desired: list[str], max_points: float, label: str, reasons: list[str]
) -> float:
    normalized = text.lower()
    matches = [item for item in desired if item and item.lower() in normalized]
    if not matches:
        return 0.0
    points = round(max_points * min(1.0, len(matches) / max(1, len(desired))), 2)
    reasons.append(f"{label}: +{points:g}")
    return points

