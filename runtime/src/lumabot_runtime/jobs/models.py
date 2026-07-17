from __future__ import annotations

from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from lumabot_runtime.models import utc_now


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    DEAD_LETTER = "dead_letter"


class Job(BaseModel):
    id: str = Field(default_factory=lambda: f"job_{uuid4().hex}")
    type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    status: JobStatus = JobStatus.QUEUED
    attempts: int = 0
    max_attempts: int = 3
    run_at: datetime = Field(default_factory=utc_now)
    lease_token: str | None = None
    leased_until: datetime | None = None
    progress: float = 0.0
    idempotency_key: str | None = None
    error: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    def next_backoff(self) -> timedelta:
        return timedelta(seconds=min(300, 2 ** max(0, self.attempts - 1)))
