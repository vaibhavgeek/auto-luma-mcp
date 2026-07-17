from __future__ import annotations

import pytest

from lumabot_runtime.enrichment.models import EvidenceField
from lumabot_runtime.pdl import company_from_pdl, person_from_pdl


def test_person_mapping_preserves_pdl_provenance() -> None:
    person = person_from_pdl(
        "p1",
        {
            "full_name": "Maya Chen",
            "linkedin_url": "https://linkedin.com/in/mayachen",
            "job_title": "Founder",
            "job_company_name": "VectorForge",
            "location_name": "San Francisco Bay Area",
            "skills": ["agentic developer tools"],
        },
    )

    assert person.full_name.value == "Maya Chen"
    assert person.full_name.source == "people-data-labs:person.full_name"
    assert person.social_urls[0].source == "people-data-labs:person.profiles"
    assert person.title.value == "Founder"
    assert person.company_name.value == "VectorForge"
    assert person.interests[0].value == "agentic developer tools"


def test_company_mapping_preserves_pdl_provenance() -> None:
    company = company_from_pdl(
        "c1",
        {
            "display_name": "VectorForge",
            "employee_count": 18,
            "industry": "AI developer tools",
            "funding_stages": ["pre_seed", "seed"],
            "website": "vectorforge.ai",
        },
    )

    assert company.name.value == "VectorForge"
    assert company.employee_count.value == 18
    assert company.stage.value == "seed"
    assert company.stage.source == "people-data-labs:company.latest_funding_stage"


def test_evidence_field_requires_confidence_and_source() -> None:
    with pytest.raises(ValueError):
        EvidenceField(value="invented", source="", confidence=0.5)
    with pytest.raises(ValueError):
        EvidenceField(value="invented", source="provider", confidence=1.5)
