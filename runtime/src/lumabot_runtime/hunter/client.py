from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx

from lumabot_runtime.enrichment.models import EvidenceField, RawPerson

HUNTER_BASE_URL = "https://api.hunter.io"


class EmailIntelligenceClient(Protocol):
    async def find_email(self, person: RawPerson) -> EvidenceField | None: ...

    async def verify_email(self, email: str) -> EvidenceField | None: ...

    async def domain_search(self, domain: str) -> list[EvidenceField]: ...

    async def health_check(self) -> bool: ...


@dataclass
class HunterClient:
    api_key: str
    base_url: str = HUNTER_BASE_URL
    timeout_seconds: float = 10.0

    async def find_email(self, person: RawPerson) -> EvidenceField | None:
        if not person.company_domain:
            return None
        first_name, last_name = _split_name(person.full_name)
        if not first_name or not last_name:
            return None
        payload = await self._get(
            "/v2/email-finder",
            {
                "domain": person.company_domain,
                "first_name": first_name,
                "last_name": last_name,
            },
        )
        data = _data(payload)
        email = data.get("email")
        if not email:
            return None
        return _hunter_field(
            email,
            "email-finder.email",
            _score_to_confidence(data.get("score")),
            source_url=_first_source(data),
        )

    async def verify_email(self, email: str) -> EvidenceField | None:
        payload = await self._get("/v2/email-verifier", {"email": email})
        data = _data(payload)
        status = data.get("status") or data.get("result")
        if not status:
            return None
        return _hunter_field(
            str(status),
            "email-verifier.status",
            _score_to_confidence(data.get("score")),
            source_url=_first_source(data),
        )

    async def domain_search(self, domain: str) -> list[EvidenceField]:
        payload = await self._get("/v2/domain-search", {"domain": domain})
        data = _data(payload)
        emails = data.get("emails")
        if not isinstance(emails, list):
            return []
        fields: list[EvidenceField] = []
        for item in emails:
            if not isinstance(item, dict) or not item.get("value"):
                continue
            fields.append(
                _hunter_field(
                    str(item["value"]),
                    "domain-search.email",
                    _score_to_confidence(item.get("confidence")),
                    source_url=_first_source(item),
                )
            )
        return fields

    async def health_check(self) -> bool:
        try:
            await self._get("/v2/account", {})
        except httpx.HTTPError:
            return False
        return True

    async def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        request_params = {
            key: value for key, value in params.items() if value not in (None, "", [])
        }
        request_params["api_key"] = self.api_key
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.get(f"{self.base_url.rstrip('/')}{path}", params=request_params)
            response.raise_for_status()
            payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("malformed Hunter response")
        return payload


@dataclass
class FakeHunterClient:
    found_email: str | None = None
    verification_status: str | None = "valid"
    domain_emails: list[str] = field(default_factory=list)
    healthy: bool = True

    async def find_email(self, person: RawPerson) -> EvidenceField | None:
        if not self.found_email:
            return None
        return _hunter_field(self.found_email, "fake.email-finder.email", 0.8)

    async def verify_email(self, email: str) -> EvidenceField | None:
        if not self.verification_status:
            return None
        return _hunter_field(self.verification_status, "fake.email-verifier.status", 0.85)

    async def domain_search(self, domain: str) -> list[EvidenceField]:
        del domain
        return [_hunter_field(email, "fake.domain-search.email", 0.65) for email in self.domain_emails]

    async def health_check(self) -> bool:
        return self.healthy


def _data(payload: dict[str, Any]) -> dict[str, Any]:
    data = payload.get("data", payload)
    if not isinstance(data, dict):
        raise ValueError("malformed Hunter response")
    return data


def _split_name(full_name: str) -> tuple[str | None, str | None]:
    parts = full_name.strip().split()
    if len(parts) < 2:
        return None, None
    return parts[0], parts[-1]


def _score_to_confidence(score: object) -> float:
    if isinstance(score, int | float):
        return max(0.0, min(1.0, float(score) / 100.0))
    return 0.5


def _first_source(payload: dict[str, Any]) -> str:
    sources = payload.get("sources")
    if isinstance(sources, list) and sources:
        first = sources[0]
        if isinstance(first, dict) and first.get("uri"):
            return str(first["uri"])
    return "https://hunter.io/api-documentation"


def _hunter_field(value: object, field_name: str, confidence: float, *, source_url: str | None = None) -> EvidenceField:
    return EvidenceField(
        value=value,
        source=f"hunter:{field_name}",
        source_url=source_url or "https://hunter.io/api-documentation",
        confidence=confidence,
    )

