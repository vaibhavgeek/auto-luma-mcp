# LumaBot Foundation

This branch owns the shared Python contracts and Supabase schema used by later
MCP service and runtime workers.

## Shared package

`shared/` publishes the `lumabot-shared` package. It exposes:

- `ToolStatus` and `JobType` enums matching the job queue and tool response
  contracts.
- Pydantic models for users, profiles, events, companies, people, attendees,
  scores, reports, jobs, notifications, external actions, and runtime API
  requests/responses.
- Scoring helpers that keep model and database score ranges aligned to `0..100`.
- Security models that represent browser sessions as encrypted bytes and use
  Pydantic secret types for secret-bearing values.
- Sanitized fixture factories for local demos and contract tests.

## Database schema

`supabase/migrations/20260717000000_lumabot_foundation.sql` defines the initial
PostgreSQL/Supabase schema. It uses UUID primary keys, `timestamptz` timestamps,
JSONB evidence payloads, idempotency keys, report versioning, social URL unique
indexes, score constraints, audit records, notification delivery metadata, and a
`claim_queued_jobs` function using `FOR UPDATE SKIP LOCKED`.

The schema stores encrypted browser session bytes, never raw cookies, and does
not include storage for provider API keys such as AgentMail.

## Boundaries

This foundation intentionally does not implement MCP tools, runtime API routes,
browser automation, Nexla calls, AgentMail calls, Zero calls, or deployment.
