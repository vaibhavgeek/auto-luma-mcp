from __future__ import annotations

from lumabot_runtime.enrichment.models import EnrichedPerson, Event, UserProfile
from lumabot_runtime.reports.fixtures import demo_fixture, evidence
from lumabot_runtime.scoring import score_event, score_person


def test_missing_data_scoring_records_missing_fields() -> None:
    profile, _, _, _ = demo_fixture(full=True)
    person = EnrichedPerson(person_id="p-empty", full_name=evidence("Mystery Person"))

    result = score_person(user_profile=profile, person=person, identity_confidence=0.9)

    assert 0 <= result.score <= 100
    assert {"title", "company_stage", "company_employee_count", "industry", "location"} <= set(result.missing_fields)


def test_job_seeker_scoring_fixture() -> None:
    profile, event, _, enriched = demo_fixture(full=True)
    result = score_person(
        user_profile=profile,
        person=enriched[0],
        identity_confidence=0.98,
        event_context=event.description,
    )

    assert result.score > 70
    assert any("role" in reason for reason in result.reasons)
    assert result.identity_confidence == 0.98


def test_founder_scoring_fixture() -> None:
    profile = UserProfile(
        goals=["customers"],
        target_roles=["investor", "founder"],
        industries=["ai"],
        company_stages=["seed"],
        company_sizes=["fewer than 50 employees"],
        region="Bay Area",
    )
    person = EnrichedPerson(
        person_id="p-founder",
        full_name=evidence("Rina Shah"),
        title=evidence("Founder"),
        company_stage=evidence("seed"),
        company_employee_count=evidence(12),
        industry=evidence("AI"),
        location=evidence("Bay Area"),
    )

    assert score_person(user_profile=profile, person=person, identity_confidence=0.9).score >= 55


def test_customer_search_scoring_fixture() -> None:
    profile = UserProfile(
        goals=["customers"],
        target_roles=["head of sales"],
        industries=["developer tools"],
        keywords=["platform"],
        region="Bay Area",
    )
    person = EnrichedPerson(
        person_id="p-customer",
        full_name=evidence("Leo Martin"),
        title=evidence("Head of Platform"),
        industry=evidence("developer tools"),
        location=evidence("Bay Area"),
        interests=[evidence("platform reliability")],
    )

    result = score_person(user_profile=profile, person=person, identity_confidence=0.85)
    assert result.score > 25
    assert "industry" not in result.missing_fields


def test_event_relevance_score() -> None:
    profile, event, _, enriched = demo_fixture(full=True)
    score = score_event(user_profile=profile, event=event, likely_attendees=enriched)

    assert score.score > 50
    assert any("topic alignment" in reason for reason in score.reasons)

