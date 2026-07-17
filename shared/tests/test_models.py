from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from lumabot_shared.enums import JobType, ToolStatus
from lumabot_shared.fixtures import (
    make_attendees,
    make_companies,
    make_demo_event_report,
    make_events,
    make_job,
    make_job_seeker,
    make_reports,
)
from lumabot_shared.models import EventScore, RuntimeJobRequest, ToolResponse


def test_pydantic_validation_rejects_out_of_range_scores() -> None:
    user, _profile = make_job_seeker()
    event = make_events()[0]

    with pytest.raises(ValidationError):
        EventScore(
            event_id=event.id,
            user_id=user.id,
            overall_score=101,
            relevance_score=90,
            attendee_quality_score=80,
            timing_score=70,
        )


def test_tool_response_json_contract() -> None:
    request = RuntimeJobRequest(
        job_type=JobType.DISCOVER_EVENTS,
        payload={"starts_after": datetime(2026, 8, 1, tzinfo=UTC).isoformat()},
        idempotency_key="discover-events-demo",
    )
    response = ToolResponse[dict[str, object]](
        status=ToolStatus.QUEUED,
        data=request.model_dump(mode="json"),
        message="Job queued",
        correlation_id="corr-demo",
    )

    payload = response.model_dump(mode="json")
    assert payload["status"] == "queued"
    assert payload["data"]["job_type"] == "DISCOVER_EVENTS"
    assert response.model_dump_json()


def test_fixture_factories_generate_sanitized_demo_shape() -> None:
    user, profile = make_job_seeker()
    companies = make_companies()
    events = make_events()
    people, employments, attendees = make_attendees(events, companies)
    partial_report, completed_report = make_reports()
    job = make_job()

    assert user.email.endswith("@lumabot.dev")
    assert profile.user_id == user.id
    assert len(events) == 2
    assert len(people) == 6
    assert len(attendees) == 6
    assert len(companies) == 4
    assert len(employments) == 6
    assert partial_report.status == "partial"
    assert completed_report.status == "completed"
    assert job.job_type == JobType.GENERATE_EVENT_REPORT


def test_demo_event_report_serializes_to_json() -> None:
    report = make_demo_event_report()
    serialized = report.model_dump_json()

    assert "AI Build Night report" in serialized
    assert "demo.jobseeker" not in serialized
