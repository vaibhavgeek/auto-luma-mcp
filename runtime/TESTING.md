# LumaBot Runtime Testing

Default tests use `InMemoryJobRepository`, `FakeEmailClient`, `FakeWebhookVerifier`, and
`FakeZeroClient`. They never call external services and never send real email.

## Acceptance Commands

```bash
cd runtime
uv sync
uv run ruff check .
uv run mypy src
uv run pytest
make demo
```

## Environment Variables

- `RUNTIME_INTERNAL_TOKEN`: bearer token or `x-runtime-token` value for `/internal/*` routes.
- `RUNTIME_JOB_CONCURRENCY`: default job worker concurrency.
- `AUTO_REGISTRATION_THRESHOLD`: default relevance score required for automatic registration.
- `AGENTMAIL_API_KEY`: AgentMail API key for production and live tests.
- `AGENTMAIL_INBOX_ID`: configured LumaBot AgentMail inbox.
- `AGENTMAIL_WEBHOOK_SECRET`: shared secret used by the production webhook verifier.
- `RUN_LIVE_AGENTMAIL_TESTS`: set to `1` to enable the live smoke test.
- `AGENTMAIL_TEST_RECIPIENT`: recipient for the live smoke test.

## Live AgentMail Smoke Test

The live test is skipped unless all of these are present:

```bash
RUN_LIVE_AGENTMAIL_TESTS=1
AGENTMAIL_API_KEY=...
AGENTMAIL_INBOX_ID=...
AGENTMAIL_TEST_RECIPIENT=you@example.com
```

Run it with:

```bash
uv run pytest -m live_agentmail
```

The test sends one clearly labeled email through `AgentMailEmailClient`, passes a deterministic
idempotency key, stores the returned message identifier in memory for the assertion, and never
prints keys.

## Runtime API

Protected routes require `Authorization: Bearer $RUNTIME_INTERNAL_TOKEN` or
`X-Runtime-Token: $RUNTIME_INTERNAL_TOKEN`.

Implemented routes:

- `POST /internal/auth/luma/start`
- `POST /internal/auth/luma/verify`
- `POST /internal/profile`
- `GET /internal/users/{user_id}/events`
- `GET /internal/users/{user_id}/recommendations`
- `POST /internal/users/{user_id}/events/{event_id}/report`
- `GET /internal/users/{user_id}/events/{event_id}/report`
- `POST /internal/jobs`
- `GET /internal/jobs/{job_id}`
- `POST /internal/actions/{action_id}/confirm`
- `POST /webhooks/agentmail`
- `GET /health`
- `GET /ready`

## Demo

`make demo` creates a fixture user and event report, queues a report email through
`FakeEmailClient`, prints the fake AgentMail message ID, creates a fake Zero Networking Bingo page,
and exercises the auto-registration confirmation path. It does not call external services.
