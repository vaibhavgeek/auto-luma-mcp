from __future__ import annotations

import re

from lumabot_runtime.models import (
    AutoRegistrationSettings,
    InferredValue,
    StructuredProfile,
)


def parse_profile(description: str) -> StructuredProfile:
    text = description.lower()
    auto_enabled = bool(
        re.search(r"\b(auto[- ]?register|automatically register|register me)\b", text)
    )
    max_price = 0.0 if "free" in text else 50.0 if "paid" in text or "budget" in text else 0.0
    return StructuredProfile(
        goals=_values(_matches(text, ["network", "fundraise", "hire", "learn", "customers"])),
        target_roles=_values(
            _matches(text, ["founder", "investor", "engineer", "designer", "gtm"])
        ),
        industries=_values(
            _matches(text, ["ai", "fintech", "climate", "healthcare", "developer tools"])
        ),
        company_stages=_values(_matches(text, ["pre-seed", "seed", "series a", "growth"])),
        company_sizes=_values(_matches(text, ["startup", "enterprise", "small team"])),
        event_types=_values(
            _matches(text, ["conference", "meetup", "demo day", "hackathon", "dinner"])
        ),
        region=InferredValue(value="Bay Area", inferred=True)
        if "bay area" in text or "sf" in text or "san francisco" in text
        else None,
        keywords=_values(sorted(set(re.findall(r"[a-z][a-z0-9-]{3,}", text)))[:12]),
        exclusions=_values(_after_markers(text, ["avoid", "exclude", "not interested in"])),
        auto_registration=AutoRegistrationSettings(
            enabled=auto_enabled,
            relevance_threshold=0.82,
            max_price_usd=max_price,
        ),
    )


def _matches(text: str, choices: list[str]) -> list[str]:
    return [choice for choice in choices if choice in text]


def _values(values: list[str]) -> list[InferredValue]:
    return [InferredValue(value=value, inferred=True) for value in values]


def _after_markers(text: str, markers: list[str]) -> list[str]:
    exclusions: list[str] = []
    for marker in markers:
        if marker in text:
            exclusions.extend(re.findall(r"[a-z][a-z0-9-]{3,}", text.split(marker, 1)[1])[:5])
    return sorted(set(exclusions))
