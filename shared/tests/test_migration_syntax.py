from pathlib import Path

MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "supabase"
    / "migrations"
    / "20260717000000_lumabot_foundation.sql"
)


def test_migration_contains_required_tables_and_function() -> None:
    sql = MIGRATION.read_text()
    required_tables = [
        "app_users",
        "user_profiles",
        "auth_sessions",
        "login_attempts",
        "events",
        "companies",
        "people",
        "person_employments",
        "event_attendees",
        "user_events",
        "person_scores",
        "event_reports",
        "jobs",
        "notifications",
        "external_actions",
        "audit_log",
    ]

    for table in required_tables:
        assert f"CREATE TABLE {table}" in sql

    assert "FOR UPDATE SKIP LOCKED" in sql
    assert "CREATE OR REPLACE FUNCTION claim_queued_jobs" in sql


def test_migration_contract_constraints_are_present() -> None:
    sql = MIGRATION.read_text()

    assert "encrypted_browser_session bytea NOT NULL" in sql
    assert "notifications_idempotency_key_unique" in sql
    assert "jobs_idempotency_key_unique" in sql
    assert "events_url_unique" in sql
    assert "people_linkedin_url_unique" in sql
    assert "companies_linkedin_url_unique" in sql
    assert "person_scores_range" in sql
    assert "event_reports_unique_version" in sql
    assert "AGENTMAIL_API_KEY" not in sql
