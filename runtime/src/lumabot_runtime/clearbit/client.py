from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx
from pydantic import BaseModel, Field

from lumabot_runtime.enrichment.models import EvidenceField

CLEARBIT_AUTOCOMPLETE_URL = "https://autocomplete.clearbit.com/v1/companies/suggest"


class CompanyHint(BaseModel):
    name: EvidenceField
    domain: EvidenceField | None = None
    logo_url: EvidenceField | None = None


class CompanyHintClient(Protocol):
    async def suggest_companies(self, query: str) -> list[CompanyHint]: ...


@dataclass
class ClearbitAutocompleteClient:
    timeout_seconds: float = 10.0
    url: str = CLEARBIT_AUTOCOMPLETE_URL

    async def suggest_companies(self, query: str) -> list[CompanyHint]:
        if not query.strip():
            return []
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.get(self.url, params={"query": query})
            response.raise_for_status()
            payload = response.json()
        if not isinstance(payload, list):
            raise ValueError("malformed Clearbit autocomplete response")
        return [_hint(item) for item in payload if isinstance(item, dict) and item.get("name")]


@dataclass
class FakeCompanyHintClient:
    hints: list[CompanyHint] = field(default_factory=list)

    async def suggest_companies(self, query: str) -> list[CompanyHint]:
        del query
        return self.hints


def _hint(payload: dict[str, Any]) -> CompanyHint:
    domain = payload.get("domain")
    logo = payload.get("logo")
    return CompanyHint(
        name=_clearbit_field(payload["name"], "autocomplete.name", 0.55),
        domain=_clearbit_field(domain, "autocomplete.domain", 0.55) if domain else None,
        logo_url=_clearbit_field(logo, "autocomplete.logo", 0.45) if logo else None,
    )


def _clearbit_field(value: object, field_name: str, confidence: float) -> EvidenceField:
    return EvidenceField(
        value=value,
        source=f"clearbit:{field_name}",
        source_url="https://autocomplete.clearbit.com/v1/companies/suggest",
        confidence=confidence,
    )

