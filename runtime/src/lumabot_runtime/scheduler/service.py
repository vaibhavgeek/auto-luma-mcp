from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from lumabot_runtime.repositories.jobs import JobRepository


@dataclass(frozen=True)
class ScheduledJob:
    name: str
    job_type: str
    interval: timedelta
    payload: dict[str, Any]


class RuntimeScheduler:
    def __init__(self, repository: JobRepository) -> None:
        self._repository = repository
        self.jobs = [
            ScheduledJob(
                "bay-area-discovery",
                "DISCOVER_BAY_AREA_EVENTS",
                timedelta(minutes=20),
                {"region": "Bay Area"},
            ),
            ScheduledJob(
                "active-session-validation",
                "VALIDATE_ACTIVE_SESSIONS",
                timedelta(hours=6),
                {},
            ),
            ScheduledJob(
                "upcoming-event-refresh",
                "REFRESH_UPCOMING_EVENTS",
                timedelta(hours=1),
                {},
            ),
            ScheduledJob(
                "daily-recommendation-digest",
                "SEND_DAILY_RECOMMENDATION_DIGEST",
                timedelta(days=1),
                {},
            ),
            ScheduledJob(
                "registered-event-report-refresh",
                "REFRESH_REGISTERED_EVENT_REPORTS",
                timedelta(hours=3),
                {},
            ),
            ScheduledJob(
                "stale-job-recovery",
                "RECOVER_STALE_JOBS",
                timedelta(minutes=5),
                {},
            ),
        ]

    async def tick(self, *, bucket: str) -> list[str]:
        job_ids: list[str] = []
        for scheduled in self.jobs:
            job = await self._repository.enqueue(
                scheduled.job_type,
                scheduled.payload,
                idempotency_key=f"schedule:{scheduled.name}:{bucket}",
            )
            job_ids.append(job.id)
        return job_ids
