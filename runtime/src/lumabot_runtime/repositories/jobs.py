from __future__ import annotations

import asyncio
from collections import Counter
from datetime import datetime, timedelta
from typing import Any, Protocol
from uuid import uuid4

from lumabot_runtime.jobs.models import Job, JobStatus
from lumabot_runtime.models import utc_now


class JobRepository(Protocol):
    async def enqueue(
        self,
        job_type: str,
        payload: dict[str, Any],
        *,
        idempotency_key: str | None = None,
        run_at: datetime | None = None,
        max_attempts: int = 3,
    ) -> Job: ...

    async def get(self, job_id: str) -> Job | None: ...

    async def claim_available(
        self,
        *,
        worker_id: str,
        limit: int,
        lease_seconds: int,
        job_types: set[str] | None = None,
        per_type_limits: dict[str, int] | None = None,
    ) -> list[Job]: ...

    async def heartbeat(self, job_id: str, lease_token: str, lease_seconds: int) -> bool: ...

    async def update_progress(self, job_id: str, lease_token: str, progress: float) -> bool: ...

    async def complete(self, job_id: str, lease_token: str) -> bool: ...

    async def fail(self, job_id: str, lease_token: str, error: str) -> Job | None: ...

    async def recover_stale_leases(self) -> int: ...


class InMemoryJobRepository:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._idempotency_index: dict[str, str] = {}
        self._lock = asyncio.Lock()

    async def enqueue(
        self,
        job_type: str,
        payload: dict[str, Any],
        *,
        idempotency_key: str | None = None,
        run_at: datetime | None = None,
        max_attempts: int = 3,
    ) -> Job:
        async with self._lock:
            if idempotency_key and idempotency_key in self._idempotency_index:
                return self._jobs[self._idempotency_index[idempotency_key]].model_copy(deep=True)
            job = Job(
                type=job_type,
                payload=payload,
                idempotency_key=idempotency_key,
                run_at=run_at or utc_now(),
                max_attempts=max_attempts,
            )
            self._jobs[job.id] = job
            if idempotency_key:
                self._idempotency_index[idempotency_key] = job.id
            return job.model_copy(deep=True)

    async def get(self, job_id: str) -> Job | None:
        async with self._lock:
            job = self._jobs.get(job_id)
            return job.model_copy(deep=True) if job else None

    async def claim_available(
        self,
        *,
        worker_id: str,
        limit: int,
        lease_seconds: int,
        job_types: set[str] | None = None,
        per_type_limits: dict[str, int] | None = None,
    ) -> list[Job]:
        del worker_id
        now = utc_now()
        claimed: list[Job] = []
        claimed_by_type: Counter[str] = Counter()
        async with self._lock:
            candidates = sorted(self._jobs.values(), key=lambda job: (job.run_at, job.created_at))
            for job in candidates:
                if len(claimed) >= limit:
                    break
                if job.status != JobStatus.QUEUED or job.run_at > now:
                    continue
                if job_types and job.type not in job_types:
                    continue
                if (
                    per_type_limits
                    and claimed_by_type[job.type] >= per_type_limits.get(job.type, limit)
                ):
                    continue
                job.status = JobStatus.RUNNING
                job.attempts += 1
                job.lease_token = f"lease_{uuid4().hex}"
                job.leased_until = now + timedelta(seconds=lease_seconds)
                job.updated_at = now
                claimed.append(job.model_copy(deep=True))
                claimed_by_type[job.type] += 1
        return claimed

    async def heartbeat(self, job_id: str, lease_token: str, lease_seconds: int) -> bool:
        async with self._lock:
            job = self._jobs.get(job_id)
            if not self._has_live_lease(job, lease_token):
                return False
            assert job is not None
            job.leased_until = utc_now() + timedelta(seconds=lease_seconds)
            job.updated_at = utc_now()
            return True

    async def update_progress(self, job_id: str, lease_token: str, progress: float) -> bool:
        async with self._lock:
            job = self._jobs.get(job_id)
            if not self._has_live_lease(job, lease_token):
                return False
            assert job is not None
            job.progress = max(0.0, min(1.0, progress))
            job.updated_at = utc_now()
            return True

    async def complete(self, job_id: str, lease_token: str) -> bool:
        async with self._lock:
            job = self._jobs.get(job_id)
            if not self._has_live_lease(job, lease_token):
                return False
            assert job is not None
            job.status = JobStatus.SUCCEEDED
            job.progress = 1.0
            job.lease_token = None
            job.leased_until = None
            job.updated_at = utc_now()
            return True

    async def fail(self, job_id: str, lease_token: str, error: str) -> Job | None:
        async with self._lock:
            job = self._jobs.get(job_id)
            if not self._has_live_lease(job, lease_token):
                return None
            assert job is not None
            job.error = error
            job.lease_token = None
            job.leased_until = None
            job.updated_at = utc_now()
            if job.attempts >= job.max_attempts:
                job.status = JobStatus.DEAD_LETTER
            else:
                job.status = JobStatus.QUEUED
                job.run_at = utc_now() + job.next_backoff()
            return job.model_copy(deep=True)

    async def recover_stale_leases(self) -> int:
        now = utc_now()
        recovered = 0
        async with self._lock:
            for job in self._jobs.values():
                if (
                    job.status == JobStatus.RUNNING
                    and job.leased_until is not None
                    and job.leased_until <= now
                ):
                    job.status = JobStatus.QUEUED
                    job.lease_token = None
                    job.leased_until = None
                    job.updated_at = now
                    recovered += 1
        return recovered

    @staticmethod
    def _has_live_lease(job: Job | None, lease_token: str) -> bool:
        return (
            job is not None
            and job.status == JobStatus.RUNNING
            and job.lease_token == lease_token
            and job.leased_until is not None
            and job.leased_until > utc_now()
        )


class PostgresJobRepository:
    """PostgreSQL-backed repository using SKIP LOCKED for atomic claims.

    The pool object is intentionally duck-typed so tests can remain dependency-free. In production,
    pass an asyncpg pool with a `fetchrow`, `fetch`, and `execute` compatible API.
    """

    def __init__(self, pool: Any) -> None:
        self._pool = pool

    async def enqueue(
        self,
        job_type: str,
        payload: dict[str, Any],
        *,
        idempotency_key: str | None = None,
        run_at: datetime | None = None,
        max_attempts: int = 3,
    ) -> Job:
        row = await self._pool.fetchrow(
            """
            INSERT INTO runtime_jobs (type, payload, idempotency_key, run_at, max_attempts)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (idempotency_key) WHERE idempotency_key IS NOT NULL
            DO UPDATE SET idempotency_key = EXCLUDED.idempotency_key
            RETURNING *
            """,
            job_type,
            payload,
            idempotency_key,
            run_at or utc_now(),
            max_attempts,
        )
        return self._job_from_row(row)

    async def get(self, job_id: str) -> Job | None:
        row = await self._pool.fetchrow("SELECT * FROM runtime_jobs WHERE id = $1", job_id)
        return self._job_from_row(row) if row else None

    async def claim_available(
        self,
        *,
        worker_id: str,
        limit: int,
        lease_seconds: int,
        job_types: set[str] | None = None,
        per_type_limits: dict[str, int] | None = None,
    ) -> list[Job]:
        del worker_id, per_type_limits
        rows = await self._pool.fetch(
            """
            WITH candidates AS (
                SELECT id
                FROM runtime_jobs
                WHERE status = 'queued'
                  AND run_at <= now()
                  AND ($1::text[] IS NULL OR type = ANY($1::text[]))
                ORDER BY run_at, created_at
                LIMIT $2
                FOR UPDATE SKIP LOCKED
            )
            UPDATE runtime_jobs j
            SET status = 'running',
                attempts = attempts + 1,
                lease_token = gen_random_uuid()::text,
                leased_until = now() + make_interval(secs => $3),
                updated_at = now()
            FROM candidates
            WHERE j.id = candidates.id
            RETURNING j.*
            """,
            list(job_types) if job_types else None,
            limit,
            lease_seconds,
        )
        return [self._job_from_row(row) for row in rows]

    async def heartbeat(self, job_id: str, lease_token: str, lease_seconds: int) -> bool:
        result = await self._pool.execute(
            """
            UPDATE runtime_jobs
            SET leased_until = now() + make_interval(secs => $3), updated_at = now()
            WHERE id = $1 AND lease_token = $2 AND status = 'running' AND leased_until > now()
            """,
            job_id,
            lease_token,
            lease_seconds,
        )
        return self._changed(result)

    async def update_progress(self, job_id: str, lease_token: str, progress: float) -> bool:
        result = await self._pool.execute(
            """
            UPDATE runtime_jobs
            SET progress = least(1, greatest(0, $3)), updated_at = now()
            WHERE id = $1 AND lease_token = $2 AND status = 'running' AND leased_until > now()
            """,
            job_id,
            lease_token,
            progress,
        )
        return self._changed(result)

    async def complete(self, job_id: str, lease_token: str) -> bool:
        result = await self._pool.execute(
            """
            UPDATE runtime_jobs
            SET status = 'succeeded', progress = 1, lease_token = NULL,
                leased_until = NULL, updated_at = now()
            WHERE id = $1 AND lease_token = $2 AND status = 'running' AND leased_until > now()
            """,
            job_id,
            lease_token,
        )
        return self._changed(result)

    async def fail(self, job_id: str, lease_token: str, error: str) -> Job | None:
        row = await self._pool.fetchrow(
            """
            UPDATE runtime_jobs
            SET status = CASE WHEN attempts >= max_attempts THEN 'dead_letter' ELSE 'queued' END,
                run_at = CASE
                    WHEN attempts >= max_attempts THEN run_at
                    ELSE now() + (power(2, greatest(0, attempts - 1)) || ' seconds')::interval
                END,
                error = $3,
                lease_token = NULL,
                leased_until = NULL,
                updated_at = now()
            WHERE id = $1 AND lease_token = $2 AND status = 'running' AND leased_until > now()
            RETURNING *
            """,
            job_id,
            lease_token,
            error,
        )
        return self._job_from_row(row) if row else None

    async def recover_stale_leases(self) -> int:
        result = await self._pool.execute(
            """
            UPDATE runtime_jobs
            SET status = 'queued', lease_token = NULL, leased_until = NULL, updated_at = now()
            WHERE status = 'running' AND leased_until <= now()
            """
        )
        return self._rowcount(result)

    @staticmethod
    def _job_from_row(row: Any) -> Job:
        data = dict(row)
        data["status"] = JobStatus(data["status"])
        return Job.model_validate(data)

    @staticmethod
    def _changed(result: str) -> bool:
        return PostgresJobRepository._rowcount(result) > 0

    @staticmethod
    def _rowcount(result: str) -> int:
        try:
            return int(result.rsplit(" ", 1)[-1])
        except (ValueError, IndexError):
            return 0
