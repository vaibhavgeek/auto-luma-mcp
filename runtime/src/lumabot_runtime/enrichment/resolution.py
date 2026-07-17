from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urlparse, urlunparse

from lumabot_runtime.enrichment.models import EnrichedPerson, EventAttendee


def normalize_social_url(url: str) -> str:
    parsed = urlparse(url.strip())
    scheme = parsed.scheme or "https"
    netloc = parsed.netloc.lower()
    path = re.sub(r"/+$", "", parsed.path.lower())
    if netloc.startswith("www."):
        netloc = netloc[4:]
    return urlunparse((scheme, netloc, path, "", "", ""))


def normalize_text(text: str | None) -> str:
    if not text:
        return ""
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


@dataclass(frozen=True)
class IdentityMatch:
    attendee_id: str
    person_id: str | None
    confidence: float
    matched: bool
    candidates: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)


class IdentityResolver:
    exact_social_threshold = 0.92
    confident_threshold = 0.78
    uncertain_threshold = 0.55

    def match(self, attendee: EventAttendee, people: list[EnrichedPerson]) -> IdentityMatch:
        scored = sorted(
            (self._score_candidate(attendee, person) for person in people),
            key=lambda item: item[1],
            reverse=True,
        )
        if not scored:
            return IdentityMatch(attendee.attendee_id, None, 0.0, False, evidence=["no candidates"])
        best_person, best_score, evidence = scored[0]
        candidates = [person.person_id for person, score, _ in scored if score >= self.uncertain_threshold]
        if len(scored) > 1 and best_score - scored[1][1] < 0.12:
            return IdentityMatch(
                attendee.attendee_id,
                None,
                round(best_score, 2),
                False,
                candidates=candidates,
                evidence=[*evidence, "ambiguous candidates preserved"],
            )
        matched = best_score >= self.confident_threshold
        return IdentityMatch(
            attendee.attendee_id,
            best_person.person_id if matched else None,
            round(best_score, 2),
            matched,
            candidates=candidates,
            evidence=evidence if evidence else ["insufficient corroborating evidence"],
        )

    def _score_candidate(
        self, attendee: EventAttendee, person: EnrichedPerson
    ) -> tuple[EnrichedPerson, float, list[str]]:
        score = 0.0
        evidence: list[str] = []
        attendee_social = {normalize_social_url(url) for url in attendee.social_urls}
        person_social = {
            normalize_social_url(str(item.value))
            for item in person.social_urls
            if isinstance(item.value, str)
        }
        if attendee_social & person_social:
            score += 0.92
            evidence.append("exact social URL match")
        name_match = normalize_text(attendee.full_name) == normalize_text(str(person.full_name.value))
        if name_match:
            score += 0.18
            evidence.append("normalized full name match")
        company_match = _field_matches(attendee.company, person.company_name.value if person.company_name else None)
        if company_match:
            score += 0.18
            evidence.append("current company match")
        title_match = _field_matches(attendee.title, person.title.value if person.title else None)
        if title_match:
            score += 0.1
            evidence.append("title match")
        if person.location and person.location.confidence >= 0.7:
            score += 0.05
            evidence.append("location evidence")
        if person.sources_agreeing >= 2:
            score += 0.12
            evidence.append("independent source agreement")
        if name_match and not (company_match or title_match or attendee_social & person_social):
            score = min(score, 0.45)
            evidence.append("name-only match capped")
        return person, min(score, 1.0), evidence


def _field_matches(left: str | None, right: object | None) -> bool:
    if right is None:
        return False
    return normalize_text(left) == normalize_text(str(right)) and bool(normalize_text(left))

