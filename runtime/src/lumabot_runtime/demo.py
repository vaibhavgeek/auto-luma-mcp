from __future__ import annotations

import asyncio

from lumabot_runtime.actions.registration import RegistrationService
from lumabot_runtime.dependencies import build_container
from lumabot_runtime.email.client import FakeEmailClient
from lumabot_runtime.jobs.handlers import build_job_handlers
from lumabot_runtime.jobs.worker import JobWorker
from lumabot_runtime.models import Event, UserProfile, utc_now
from lumabot_runtime.profiles import parse_profile


async def main() -> None:
    email_client = FakeEmailClient()
    container = build_container(email_client=email_client)
    description = "SF AI founder looking to network at free events. Do not auto-register."
    profile = UserProfile(
        user_id="demo-user",
        notification_email="demo@example.com",
        original_text=description,
        structured=parse_profile(description),
    )
    profile.structured.auto_registration.enabled = False
    container.state.profiles[profile.user_id] = profile
    event = Event(
        id="demo-event",
        title="Demo AI Mixer",
        starts_at=utc_now(),
        relevance_score=0.95,
    )
    container.state.events[profile.user_id] = [event]

    report_url = "https://reports.lumabot.local/demo-user/demo-event"
    await container.jobs.enqueue(
        "QUEUE_REPORT_EMAIL",
        {"user_id": profile.user_id, "event_id": event.id, "report_url": report_url},
        idempotency_key="demo-report-email",
    )
    handlers = build_job_handlers(
        state=container.state,
        repository=container.jobs,
        email_service=container.email_service,
    )
    await JobWorker(container.jobs, handlers).run_once()
    print(f"Fake AgentMail message ID: {email_client.sent[0]['result'].message_id}")

    artifact = await container.zero_service.create_networking_bingo(
        user_id=profile.user_id,
        event_id=event.id,
        report_url=report_url,
    )
    print(f"Fake Zero Networking Bingo page: {artifact['url']}")

    decision = await RegistrationService(
        container.state,
        container.email_service,
    ).auto_register_event(
        user_id=profile.user_id,
        event=event,
    )
    print(f"Auto-registration path: {decision.outcome} ({decision.reason})")
    if decision.action:
        print(f"Confirmation action ID: {decision.action.id}")


if __name__ == "__main__":
    asyncio.run(main())
