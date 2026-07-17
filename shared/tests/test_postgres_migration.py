from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import psycopg
import pytest
from psycopg.rows import dict_row
from testcontainers.postgres import PostgresContainer

MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "supabase"
    / "migrations"
    / "20260717000000_lumabot_foundation.sql"
)


def docker_is_available() -> bool:
    try:
        import docker

        client = docker.from_env()
        client.ping()
    except Exception:
        return False
    return True


@pytest.fixture(scope="module")
def postgres_url() -> Iterator[str]:
    if not docker_is_available():
        pytest.skip("Docker is not available for Testcontainers PostgreSQL tests")

    with PostgresContainer("postgres:16-alpine") as postgres:
        url = postgres.get_connection_url()
        yield url.replace("postgresql+psycopg2://", "postgresql://")


@pytest.fixture()
def migrated_db(postgres_url: str) -> Iterator[str]:
    with psycopg.connect(postgres_url, autocommit=True) as conn:
        conn.execute(MIGRATION.read_text())
    yield postgres_url
    with psycopg.connect(postgres_url, autocommit=True) as conn:
        conn.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")


def test_postgresql_migration_applies(migrated_db: str) -> None:
    with psycopg.connect(migrated_db, row_factory=dict_row) as conn:
        tables = conn.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            """
        ).fetchall()

    table_names = {row["table_name"] for row in tables}
    assert "jobs" in table_names
    assert "notifications" in table_names
    assert "audit_log" in table_names


def claim_one(postgres_url: str, worker_id: str) -> list[dict[str, Any]]:
    with psycopg.connect(postgres_url, row_factory=dict_row) as conn:
        rows = conn.execute(
            "SELECT id, locked_by FROM claim_queued_jobs(%s, NULL, 1, 300)",
            (worker_id,),
        ).fetchall()
        conn.commit()
    return [dict(row) for row in rows]


def test_atomic_job_claim_concurrency(migrated_db: str) -> None:
    with psycopg.connect(migrated_db) as conn:
        for index in range(3):
            conn.execute(
                """
                INSERT INTO jobs (job_type, payload, priority, idempotency_key)
                VALUES ('DISCOVER_EVENTS', '{}'::jsonb, %s, %s)
                """,
                (10 - index, f"claim-demo-{index}"),
            )
        conn.commit()

    with ThreadPoolExecutor(max_workers=3) as executor:
        claimed = list(
            executor.map(
                lambda worker: claim_one(migrated_db, worker),
                ["worker-a", "worker-b", "worker-c"],
            )
        )

    flattened = [row for worker_rows in claimed for row in worker_rows]
    claimed_ids = {row["id"] for row in flattened}

    assert len(flattened) == 3
    assert len(claimed_ids) == 3

    with psycopg.connect(migrated_db, row_factory=dict_row) as conn:
        status_counts = conn.execute(
            "SELECT status, count(*) FROM jobs GROUP BY status"
        ).fetchall()

    assert {row["status"]: row["count"] for row in status_counts} == {"processing": 3}
