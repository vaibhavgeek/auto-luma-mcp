from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from contextlib import suppress
from dataclasses import dataclass, field
from typing import Any

from lumabot_runtime.repositories.jobs import JobRepository

JobHandler = Callable[[dict[str, Any]], Awaitable[None]]


@dataclass
class WorkerConfig:
    concurrency: int = 4
    lease_seconds: int = 30
    poll_seconds: float = 0.2
    per_type_limits: dict[str, int] = field(default_factory=dict)


class JobWorker:
    def __init__(
        self,
        repository: JobRepository,
        handlers: dict[str, JobHandler],
        *,
        config: WorkerConfig | None = None,
        worker_id: str = "runtime-worker",
    ) -> None:
        self._repository = repository
        self._handlers = handlers
        self._config = config or WorkerConfig()
        self._worker_id = worker_id
        self._stopping = asyncio.Event()

    async def run_once(self) -> int:
        jobs = await self._repository.claim_available(
            worker_id=self._worker_id,
            limit=self._config.concurrency,
            lease_seconds=self._config.lease_seconds,
            job_types=set(self._handlers),
            per_type_limits=self._config.per_type_limits,
        )
        await asyncio.gather(
            *(self._run_job(job.id, job.lease_token, job.type, job.payload) for job in jobs)
        )
        return len(jobs)

    async def run_forever(self) -> None:
        while not self._stopping.is_set():
            await self.run_once()
            with suppress(asyncio.TimeoutError):
                await asyncio.wait_for(self._stopping.wait(), timeout=self._config.poll_seconds)

    def stop(self) -> None:
        self._stopping.set()

    async def _run_job(
        self, job_id: str, lease_token: str | None, job_type: str, payload: dict[str, Any]
    ) -> None:
        if lease_token is None:
            return
        handler = self._handlers[job_type]
        try:
            await handler(payload)
        except Exception as exc:
            await self._repository.fail(job_id, lease_token, str(exc))
        else:
            await self._repository.complete(job_id, lease_token)
