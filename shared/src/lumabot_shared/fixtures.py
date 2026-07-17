from datetime import UTC, datetime, timedelta

from lumabot_shared.enums import JobType, ToolStatus
from lumabot_shared.models import (
    Company,
    Employment,
    Event,
    EventAttendee,
    EventReport,
    EventScore,
    Job,
    Person,
    PersonScore,
    User,
    UserProfile,
)


def make_job_seeker() -> tuple[User, UserProfile]:
    user = User(email="demo.jobseeker@lumabot.dev", display_name="Demo Job Seeker")
    profile = UserProfile(
        user_id=user.id,
        headline="Early-career product engineer",
        location="San Francisco, CA",
        goals=["meet hiring managers", "find climate-tech teams"],
        target_roles=["Software Engineer", "AI Engineer"],
        target_industries=["Climate", "Developer Tools"],
        skills=["Python", "TypeScript", "LLM agents"],
    )
    return user, profile


def make_companies() -> list[Company]:
    return [
        Company(name="Northstar Robotics", domain="northstar.example"),
        Company(name="Prism Climate", domain="prism.example"),
        Company(name="Relay Data", domain="relay.example"),
        Company(name="Foundry Labs", domain="foundry.example"),
    ]


def make_events() -> list[Event]:
    start = datetime(2026, 8, 5, 18, 0, tzinfo=UTC)
    return [
        Event(
            url="https://lu.ma/demo-ai-build-night",
            title="AI Build Night",
            description="A focused builder meetup for applied AI teams.",
            starts_at=start,
            city="San Francisco",
            region="CA",
            country="US",
            tags=["ai", "builders", "hiring"],
        ),
        Event(
            url="https://lu.ma/demo-climate-founders",
            title="Climate Founders Mixer",
            description="Climate operators and founders sharing hiring plans.",
            starts_at=start + timedelta(days=3),
            city="San Francisco",
            region="CA",
            country="US",
            tags=["climate", "founders"],
        ),
    ]


def make_attendees(
    events: list[Event],
    companies: list[Company],
) -> tuple[list[Person], list[Employment], list[EventAttendee]]:
    people = [
        Person(full_name="Avery Chen", headline="Engineering Manager"),
        Person(full_name="Morgan Patel", headline="Founder"),
        Person(full_name="Jordan Lee", headline="Staff AI Engineer"),
        Person(full_name="Riley Stone", headline="Talent Partner"),
        Person(full_name="Casey Nguyen", headline="Product Lead"),
        Person(full_name="Taylor Brooks", headline="Platform Engineer"),
    ]
    employments = [
        Employment(
            person_id=person.id,
            company_id=companies[index % len(companies)].id,
            title=person.headline,
        )
        for index, person in enumerate(people)
    ]
    attendees = [
        EventAttendee(event_id=events[index % len(events)].id, person_id=person.id)
        for index, person in enumerate(people)
    ]
    return people, employments, attendees


def make_reports() -> tuple[EventReport, EventReport]:
    user, _profile = make_job_seeker()
    companies = make_companies()
    events = make_events()
    people, _employments, attendees = make_attendees(events, companies)
    event_score = EventScore(
        event_id=events[0].id,
        user_id=user.id,
        overall_score=86,
        relevance_score=90,
        attendee_quality_score=84,
        timing_score=80,
        rationale="Strong overlap with AI engineering goals.",
    )
    attendee_scores = [
        PersonScore(
            person_id=person.id,
            user_id=user.id,
            overall_score=80 + (index % 5),
            role_fit_score=78,
            company_fit_score=82,
            networking_priority_score=85,
        )
        for index, person in enumerate(people[:3])
    ]
    partial = EventReport(
        event_id=events[0].id,
        user_id=user.id,
        status="partial",
        title="AI Build Night draft report",
        summary="Draft report with initial event fit and attendee discovery.",
        event_score=event_score,
        featured_attendees=attendees[:2],
        source_evidence={"fixture": True},
    )
    completed = EventReport(
        event_id=events[0].id,
        user_id=user.id,
        status="completed",
        title="AI Build Night report",
        summary="High-fit event with several engineering and hiring contacts.",
        event_score=event_score,
        attendee_scores=attendee_scores,
        featured_attendees=attendees[:3],
        recommendations=[
            "Register if schedule allows.",
            "Prioritize Avery Chen and Jordan Lee for follow-up.",
        ],
        source_evidence={"fixture": True},
        completed_at=datetime.now(UTC),
    )
    return partial, completed


def make_job() -> Job:
    user, _profile = make_job_seeker()
    events = make_events()
    return Job(
        job_type=JobType.GENERATE_EVENT_REPORT,
        status=ToolStatus.QUEUED,
        user_id=user.id,
        payload={"event_id": str(events[0].id)},
        idempotency_key=f"fixture-report-{events[0].id}",
    )


def make_demo_event_report() -> EventReport:
    _partial, completed = make_reports()
    return completed
