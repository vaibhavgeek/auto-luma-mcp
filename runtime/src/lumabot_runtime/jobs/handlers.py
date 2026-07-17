from __future__ import annotations

from typing import Any

from lumabot_runtime.email.client import EmailNotificationService
from lumabot_runtime.models import RuntimeState
from lumabot_runtime.repositories.jobs import JobRepository


def build_job_handlers(
    *, state: RuntimeState, repository: JobRepository, email_service: EmailNotificationService
) -> dict[str, Any]:
    _ = state

    async def queue_report_email(payload: dict[str, Any]) -> None:
        user_id = str(payload["user_id"])
        report_url = str(payload["report_url"])
        await email_service.send_report_ready(user_id=user_id, report_url=report_url)

    async def recover_stale_jobs(payload: dict[str, Any]) -> None:
        del payload
        await repository.recover_stale_leases()

    async def no_op(payload: dict[str, Any]) -> None:
        del payload

    return {
        "QUEUE_REPORT_EMAIL": queue_report_email,
        "RECOVER_STALE_JOBS": recover_stale_jobs,
        "DISCOVER_BAY_AREA_EVENTS": no_op,
        "VALIDATE_ACTIVE_SESSIONS": no_op,
        "REFRESH_UPCOMING_EVENTS": no_op,
        "SEND_DAILY_RECOMMENDATION_DIGEST": no_op,
        "REFRESH_REGISTERED_EVENT_REPORTS": no_op,
    }
