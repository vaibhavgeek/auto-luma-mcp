from __future__ import annotations

from dataclasses import dataclass

from lumabot_runtime.config import Settings
from lumabot_runtime.email.client import EmailClient, EmailNotificationService, FakeEmailClient
from lumabot_runtime.models import RuntimeState
from lumabot_runtime.repositories.jobs import InMemoryJobRepository, JobRepository
from lumabot_runtime.scheduler.service import RuntimeScheduler
from lumabot_runtime.zero.client import FakeZeroClient, ZeroArtifactService, ZeroClient


@dataclass
class RuntimeContainer:
    settings: Settings
    state: RuntimeState
    jobs: JobRepository
    email_client: EmailClient
    email_service: EmailNotificationService
    scheduler: RuntimeScheduler
    zero_client: ZeroClient
    zero_service: ZeroArtifactService


def build_container(
    *,
    settings: Settings | None = None,
    state: RuntimeState | None = None,
    jobs: JobRepository | None = None,
    email_client: EmailClient | None = None,
    zero_client: ZeroClient | None = None,
) -> RuntimeContainer:
    resolved_settings = settings or Settings.from_env()
    resolved_state = state or RuntimeState()
    resolved_jobs = jobs or InMemoryJobRepository()
    resolved_email = email_client or FakeEmailClient()
    email_service = EmailNotificationService(resolved_state, resolved_email)
    resolved_zero = zero_client or FakeZeroClient()
    return RuntimeContainer(
        settings=resolved_settings,
        state=resolved_state,
        jobs=resolved_jobs,
        email_client=resolved_email,
        email_service=email_service,
        scheduler=RuntimeScheduler(resolved_jobs),
        zero_client=resolved_zero,
        zero_service=ZeroArtifactService(resolved_state, resolved_zero),
    )
