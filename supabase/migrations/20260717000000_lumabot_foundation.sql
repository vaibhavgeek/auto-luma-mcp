-- LumaBot foundation schema.
-- This SQL is intended to run as a Supabase/PostgreSQL migration or from Alembic
-- via op.execute(...).

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE app_users (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    email text NOT NULL UNIQUE,
    display_name text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE user_profiles (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL UNIQUE REFERENCES app_users(id) ON DELETE CASCADE,
    headline text,
    location text,
    goals jsonb NOT NULL DEFAULT '[]'::jsonb,
    target_roles jsonb NOT NULL DEFAULT '[]'::jsonb,
    target_industries jsonb NOT NULL DEFAULT '[]'::jsonb,
    skills jsonb NOT NULL DEFAULT '[]'::jsonb,
    auto_registration_preferences jsonb NOT NULL DEFAULT '{}'::jsonb,
    source_evidence jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE auth_sessions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
    provider text NOT NULL DEFAULT 'luma',
    encrypted_browser_session bytea NOT NULL,
    key_id text,
    expires_at timestamptz,
    revoked_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE login_attempts (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid REFERENCES app_users(id) ON DELETE SET NULL,
    email text,
    provider text NOT NULL DEFAULT 'luma',
    status text NOT NULL,
    failure_reason text,
    ip_hash text,
    user_agent_hash text,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source text NOT NULL DEFAULT 'luma',
    external_id text,
    url text NOT NULL,
    title text NOT NULL,
    description text,
    starts_at timestamptz NOT NULL,
    ends_at timestamptz,
    timezone text NOT NULL DEFAULT 'UTC',
    location_name text,
    city text,
    region text,
    country text,
    is_online boolean NOT NULL DEFAULT false,
    tags jsonb NOT NULL DEFAULT '[]'::jsonb,
    source_evidence jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT events_url_unique UNIQUE (url),
    CONSTRAINT events_external_unique UNIQUE (source, external_id),
    CONSTRAINT events_time_order CHECK (ends_at IS NULL OR ends_at >= starts_at)
);

CREATE TABLE companies (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL,
    domain text,
    website_url text,
    linkedin_url text,
    twitter_url text,
    industry text,
    size_range text,
    source_evidence jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT companies_domain_unique UNIQUE (domain)
);

CREATE UNIQUE INDEX companies_linkedin_url_unique
    ON companies (linkedin_url)
    WHERE linkedin_url IS NOT NULL;

CREATE UNIQUE INDEX companies_twitter_url_unique
    ON companies (twitter_url)
    WHERE twitter_url IS NOT NULL;

CREATE TABLE people (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    full_name text NOT NULL,
    headline text,
    location text,
    email text,
    linkedin_url text,
    twitter_url text,
    github_url text,
    source_evidence jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX people_linkedin_url_unique
    ON people (linkedin_url)
    WHERE linkedin_url IS NOT NULL;

CREATE UNIQUE INDEX people_twitter_url_unique
    ON people (twitter_url)
    WHERE twitter_url IS NOT NULL;

CREATE UNIQUE INDEX people_github_url_unique
    ON people (github_url)
    WHERE github_url IS NOT NULL;

CREATE TABLE person_employments (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    person_id uuid NOT NULL REFERENCES people(id) ON DELETE CASCADE,
    company_id uuid NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    title text,
    started_on date,
    ended_on date,
    is_current boolean NOT NULL DEFAULT true,
    source_evidence jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT employment_date_order CHECK (ended_on IS NULL OR started_on IS NULL OR ended_on >= started_on)
);

CREATE INDEX person_employments_person_id_idx ON person_employments (person_id);
CREATE INDEX person_employments_company_id_idx ON person_employments (company_id);

CREATE TABLE event_attendees (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id uuid NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    person_id uuid NOT NULL REFERENCES people(id) ON DELETE CASCADE,
    attendance_status text NOT NULL DEFAULT 'discovered',
    registration_status text,
    source_evidence jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT event_attendees_unique UNIQUE (event_id, person_id)
);

CREATE INDEX event_attendees_event_id_idx ON event_attendees (event_id);
CREATE INDEX event_attendees_person_id_idx ON event_attendees (person_id);

CREATE TABLE user_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
    event_id uuid NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    relationship text NOT NULL DEFAULT 'interested',
    registration_status text,
    source_evidence jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT user_events_unique UNIQUE (user_id, event_id)
);

CREATE TABLE person_scores (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    person_id uuid NOT NULL REFERENCES people(id) ON DELETE CASCADE,
    user_id uuid NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
    overall_score integer NOT NULL,
    role_fit_score integer NOT NULL,
    company_fit_score integer NOT NULL,
    networking_priority_score integer NOT NULL,
    rationale text,
    source_evidence jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT person_scores_range CHECK (
        overall_score BETWEEN 0 AND 100
        AND role_fit_score BETWEEN 0 AND 100
        AND company_fit_score BETWEEN 0 AND 100
        AND networking_priority_score BETWEEN 0 AND 100
    ),
    CONSTRAINT person_scores_unique UNIQUE (person_id, user_id)
);

CREATE INDEX person_scores_user_score_idx ON person_scores (user_id, overall_score DESC);

CREATE TABLE event_reports (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id uuid NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    user_id uuid NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
    version integer NOT NULL DEFAULT 1,
    status text NOT NULL DEFAULT 'partial',
    title text NOT NULL,
    summary text NOT NULL,
    event_score integer,
    report_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    source_evidence jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz,
    CONSTRAINT event_reports_version_positive CHECK (version > 0),
    CONSTRAINT event_reports_score_range CHECK (event_score IS NULL OR event_score BETWEEN 0 AND 100),
    CONSTRAINT event_reports_unique_version UNIQUE (event_id, user_id, version)
);

CREATE INDEX event_reports_event_user_idx ON event_reports (event_id, user_id);

CREATE TABLE jobs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    job_type text NOT NULL CHECK (job_type IN (
        'VALIDATE_LUMA_SESSION',
        'DISCOVER_EVENTS',
        'SYNC_EVENT_DETAILS',
        'SCRAPE_EVENT_GUESTS',
        'ENRICH_PERSON',
        'ENRICH_COMPANY',
        'SCORE_EVENT',
        'SCORE_PERSON',
        'GENERATE_EVENT_REPORT',
        'AUTO_REGISTER_EVENT',
        'SEND_EVENT_DIGEST',
        'SEND_REPORT_EMAIL',
        'SEND_REGISTRATION_CONFIRMATION',
        'CREATE_ZERO_NETWORKING_CARD'
    )),
    status text NOT NULL DEFAULT 'queued' CHECK (status IN (
        'completed',
        'queued',
        'processing',
        'needs_input',
        'auth_required',
        'needs_confirmation',
        'partial',
        'failed'
    )),
    user_id uuid REFERENCES app_users(id) ON DELETE SET NULL,
    payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    priority integer NOT NULL DEFAULT 0 CHECK (priority BETWEEN 0 AND 100),
    idempotency_key text,
    attempts integer NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    max_attempts integer NOT NULL DEFAULT 3 CHECK (max_attempts > 0),
    locked_by text,
    locked_at timestamptz,
    lease_expires_at timestamptz,
    scheduled_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz,
    last_error text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX jobs_idempotency_key_unique
    ON jobs (idempotency_key)
    WHERE idempotency_key IS NOT NULL;

CREATE INDEX jobs_queue_claim_idx
    ON jobs (status, scheduled_at, priority DESC)
    WHERE status = 'queued';

CREATE INDEX jobs_lease_idx
    ON jobs (lease_expires_at)
    WHERE status = 'processing';

CREATE TABLE notifications (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
    channel text NOT NULL,
    subject text,
    body text NOT NULL,
    provider text,
    sender_inbox_id text,
    provider_message_id text,
    provider_thread_id text,
    provider_status text,
    idempotency_key text NOT NULL,
    status text NOT NULL DEFAULT 'queued' CHECK (status IN (
        'completed',
        'queued',
        'processing',
        'needs_input',
        'auth_required',
        'needs_confirmation',
        'partial',
        'failed'
    )),
    created_at timestamptz NOT NULL DEFAULT now(),
    sent_at timestamptz,
    CONSTRAINT notifications_idempotency_key_unique UNIQUE (idempotency_key)
);

CREATE INDEX notifications_user_created_idx ON notifications (user_id, created_at DESC);
CREATE INDEX notifications_provider_message_idx ON notifications (provider, provider_message_id);

CREATE TABLE external_actions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
    action_type text NOT NULL,
    status text NOT NULL DEFAULT 'queued' CHECK (status IN (
        'completed',
        'queued',
        'processing',
        'needs_input',
        'auth_required',
        'needs_confirmation',
        'partial',
        'failed'
    )),
    provider text NOT NULL,
    external_id text,
    target_url text,
    request_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    response_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    idempotency_key text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX external_actions_idempotency_key_unique
    ON external_actions (idempotency_key)
    WHERE idempotency_key IS NOT NULL;

CREATE TABLE audit_log (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    actor_user_id uuid REFERENCES app_users(id) ON DELETE SET NULL,
    action text NOT NULL,
    entity_type text NOT NULL,
    entity_id uuid,
    before_state jsonb,
    after_state jsonb,
    source_evidence jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX audit_log_entity_idx ON audit_log (entity_type, entity_id, created_at DESC);
CREATE INDEX audit_log_actor_idx ON audit_log (actor_user_id, created_at DESC);

CREATE OR REPLACE FUNCTION claim_queued_jobs(
    p_worker_id text,
    p_job_types text[] DEFAULT NULL,
    p_limit integer DEFAULT 1,
    p_lease_seconds integer DEFAULT 300
)
RETURNS SETOF jobs
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    WITH claimable AS (
        SELECT id
        FROM jobs
        WHERE status = 'queued'
          AND scheduled_at <= now()
          AND attempts < max_attempts
          AND (p_job_types IS NULL OR job_type = ANY(p_job_types))
        ORDER BY priority DESC, scheduled_at ASC, created_at ASC
        FOR UPDATE SKIP LOCKED
        LIMIT p_limit
    )
    UPDATE jobs AS j
    SET status = 'processing',
        locked_by = p_worker_id,
        locked_at = now(),
        lease_expires_at = now() + make_interval(secs => p_lease_seconds),
        attempts = j.attempts + 1,
        updated_at = now()
    FROM claimable
    WHERE j.id = claimable.id
    RETURNING j.*;
END;
$$;
