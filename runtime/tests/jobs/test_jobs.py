from __future__ import annotations

from datetime import timedelta

from lumabot_runtime.jobs.models import JobStatus
from lumabot_runtime.jobs.worker import JobWorker, WorkerConfig
from lumabot_runtime.models import utc_now
from lumabot_runtime.repositories.jobs import InMemoryJobRepository
from lumabot_runtime.scheduler.service import RuntimeScheduler


async def test_atomic_claim_and_per_type_concurrency() -> None:
    repo = InMemoryJobRepository()
    await repo.enqueue("A", {})
    await repo.enqueue("A", {})
    await repo.enqueue("B", {})
    first = await repo.claim_available(
        worker_id="w1",
        limit=3,
        lease_seconds=10,
        per_type_limits={"A": 1, "B": 1},
    )
    second = await repo.claim_available(worker_id="w2", limit=3, lease_seconds=10)
    assert sorted(job.type for job in first) == ["A", "B"]
    assert [job.type for job in second] == ["A"]


async def test_lease_expiry_recovery_retry_and_dead_letter() -> None:
    repo = InMemoryJobRepository()
    job = await repo.enqueue("A", {}, max_attempts=2)
    claimed = (await repo.claim_available(worker_id="w", limit=1, lease_seconds=10))[0]
    assert await repo.fail(claimed.id, claimed.lease_token or "", "boom")
    failed_once = await repo.get(job.id)
    assert failed_once is not None
    assert failed_once.status == JobStatus.QUEUED
    failed_once.run_at = utc_now() - timedelta(seconds=1)
    repo._jobs[job.id] = failed_once  # noqa: SLF001
    claimed_again = (await repo.claim_available(worker_id="w", limit=1, lease_seconds=10))[0]
    dead = await repo.fail(claimed_again.id, claimed_again.lease_token or "", "boom again")
    assert dead is not None
    assert dead.status == JobStatus.DEAD_LETTER

    stale = await repo.enqueue("B", {})
    claimed_stale = (await repo.claim_available(worker_id="w", limit=1, lease_seconds=1))[0]
    stored = await repo.get(stale.id)
    assert stored is not None
    stored.leased_until = utc_now() - timedelta(seconds=1)
    repo._jobs[claimed_stale.id] = stored  # noqa: SLF001
    assert await repo.recover_stale_leases() == 1
    recovered = await repo.get(stale.id)
    assert recovered is not None
    assert recovered.status == JobStatus.QUEUED


async def test_worker_completes_and_idempotency_and_scheduler_dedup() -> None:
    repo = InMemoryJobRepository()
    seen: list[str] = []

    async def handler(payload: dict[str, object]) -> None:
        seen.append(str(payload["value"]))

    first = await repo.enqueue("A", {"value": "one"}, idempotency_key="idem")
    second = await repo.enqueue("A", {"value": "two"}, idempotency_key="idem")
    assert first.id == second.id
    worker = JobWorker(repo, {"A": handler}, config=WorkerConfig(concurrency=1))
    assert await worker.run_once() == 1
    assert seen == ["one"]
    stored = await repo.get(first.id)
    assert stored is not None
    assert stored.status == JobStatus.SUCCEEDED

    scheduler = RuntimeScheduler(repo)
    ids_1 = await scheduler.tick(bucket="2026-07-17T10:00")
    ids_2 = await scheduler.tick(bucket="2026-07-17T10:00")
    assert ids_1 == ids_2
