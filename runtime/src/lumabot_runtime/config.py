from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    runtime_internal_token: str
    agentmail_api_key: str | None = None
    agentmail_inbox_id: str | None = None
    agentmail_webhook_secret: str | None = None
    job_concurrency: int = 4
    auto_registration_threshold: float = 0.82

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            runtime_internal_token=os.getenv("RUNTIME_INTERNAL_TOKEN", "dev-runtime-token"),
            agentmail_api_key=os.getenv("AGENTMAIL_API_KEY"),
            agentmail_inbox_id=os.getenv("AGENTMAIL_INBOX_ID"),
            agentmail_webhook_secret=os.getenv("AGENTMAIL_WEBHOOK_SECRET"),
            job_concurrency=int(os.getenv("RUNTIME_JOB_CONCURRENCY", "4")),
            auto_registration_threshold=float(os.getenv("AUTO_REGISTRATION_THRESHOLD", "0.82")),
        )
