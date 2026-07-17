from __future__ import annotations

from lumabot_runtime.enrichment.models import EnrichedPerson, UserProfile
from lumabot_runtime.scoring.models import PersonScore


def score_person(
    *,
    user_profile: UserProfile,
    person: EnrichedPerson,
    identity_confidence: float,
    event_context: str | None = None,
) -> PersonScore:
    score = 0.0
    reasons: list[str] = []
    evidence: list[str] = []
    missing: list[str] = []

    role_points = _weighted_match(
        _strings([person.title.value if person.title else None]),
        [*user_profile.target_roles, *user_profile.keywords],
        35.0,
    )
    score += role_points
    _record(role_points, "role and user-goal alignment", reasons, evidence, person.title is not None)
    if person.title is None:
        missing.append("title")

    company_points = _company_alignment(user_profile, person)
    score += company_points
    _record(company_points, "company stage and size alignment", reasons, evidence, company_points > 0)
    if person.company_stage is None:
        missing.append("company_stage")
    if person.company_employee_count is None:
        missing.append("company_employee_count")

    industry_points = _weighted_match(
        _strings([person.industry.value if person.industry else None]),
        user_profile.industries,
        15.0,
    )
    score += industry_points
    _record(industry_points, "industry alignment", reasons, evidence, person.industry is not None)
    if person.industry is None:
        missing.append("industry")

    seniority_points = _seniority_points(str(person.title.value) if person.title else "")
    score += seniority_points
    _record(seniority_points, "seniority or hiring influence", reasons, evidence, seniority_points > 0)

    context_points = _weighted_match(
        _strings([*(item.value for item in person.interests), event_context]),
        [*user_profile.goals, *user_profile.keywords],
        10.0,
    )
    score += context_points
    _record(context_points, "shared interests and event context", reasons, evidence, context_points > 0)

    location_points = _weighted_match(
        _strings([person.location.value if person.location else None]),
        [user_profile.region] if user_profile.region else [],
        5.0,
    )
    score += location_points
    _record(location_points, "location alignment", reasons, evidence, person.location is not None)
    if person.location is None:
        missing.append("location")

    identity_multiplier = 1.0 if identity_confidence >= 0.75 else max(0.35, identity_confidence)
    adjusted = round(min(100.0, score * identity_multiplier), 2)
    if identity_confidence < 0.75:
        reasons.append("identity confidence reduced relevance score")
    return PersonScore(
        person_id=person.person_id,
        score=adjusted,
        reasons=reasons,
        evidence=evidence,
        missing_fields=sorted(set(missing)),
        identity_confidence=identity_confidence,
    )


def _company_alignment(user_profile: UserProfile, person: EnrichedPerson) -> float:
    points = 0.0
    if person.company_stage:
        points += _weighted_match([str(person.company_stage.value)], user_profile.company_stages, 15.0)
    if person.company_employee_count:
        size_value = str(person.company_employee_count.value)
        points += _weighted_match([size_value], user_profile.company_sizes, 10.0)
        if "fewer than 50" in " ".join(user_profile.company_sizes).lower():
            try:
                if int(size_value) < 50:
                    points += 10.0
            except ValueError:
                pass
    return min(points, 25.0)


def _seniority_points(title: str) -> float:
    text = title.lower()
    if any(term in text for term in ["founder", "ceo", "cto", "vp", "head", "director"]):
        return 10.0
    if any(term in text for term in ["manager", "lead", "principal", "staff"]):
        return 7.0
    if "engineer" in text:
        return 4.0
    return 0.0


def _weighted_match(values: list[str], desired: list[str], max_points: float) -> float:
    if not values or not desired:
        return 0.0
    haystack = " ".join(values).lower()
    hits = [item for item in desired if item and item.lower() in haystack]
    if not hits:
        return 0.0
    if len(desired) <= 2:
        return max_points
    return round(max_points * min(1.0, len(hits) / 2), 2)


def _strings(values: list[object | None]) -> list[str]:
    return [str(value) for value in values if value not in (None, "")]


def _record(
    points: float, label: str, reasons: list[str], evidence: list[str], had_source: bool
) -> None:
    if points > 0:
        reasons.append(f"{label}: +{points:g}")
    if had_source:
        evidence.append(label)
