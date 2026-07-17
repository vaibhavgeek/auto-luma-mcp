# LumaBot P6 Integration and Akash Deployment

This branch provides an independently testable fake integration stack for the LumaBot hackathon demo. It does not require live Nexla, AgentMail, Zero, Supabase, Luma, or Akash credentials for default tests.

## What Is Included

- Standard-library integration tests for MCP login, fixture Luma discovery, guest scraping, fake Nexla enrichment, scoring, report generation, AgentMail queueing, Zero Networking Bingo creation, and idempotent replay.
- Failure coverage for Nexla, AgentMail, Zero, browser auth expiry, malformed enrichment records, partial reports, and worker restart replay.
- Docker Compose fixture stack with PostgreSQL, MCP server, runtime API, runtime worker, scheduler, fixture Luma site, fake Nexla, fake AgentMail, and fake Zero.
- Akash SDL manifests with pinned image tags and public/private endpoint separation.
- Security checks for committed `.env` files, likely API keys, PostgreSQL URLs with passwords, fixture cookies, login-code leaks, AgentMail snapshot credentials, unauthenticated internal routes, auto-registration defaults, and physical-mail confirmation.
- Infrastructure checks for pinned Akash images and required secret references.

## Acceptance Commands

```sh
uv sync
make integration-test
make demo-up
make demo-run
make demo-down
```

If `uv` is not installed, the default local tests can still run with:

```sh
make integration-test
```

## Demo Commands

```sh
make demo-up
make demo-seed
make demo-run
make demo-logs
make demo-down
```

`make demo-run` executes the full fixture workflow and prints the saved report returned through the fake MCP/runtime contract. `make demo-seed` writes a local `.tmp/fixture_seed.json` artifact for rehearsals.

## Docker Images

Local fake stack:

- `postgres:16.3-alpine`
- `python:3.12.4-slim-bookworm`

Akash deployment manifests:

- `ghcr.io/lumabot/lumabot-mcp:2026.07.17-p6`
- `ghcr.io/lumabot/lumabot-runtime-api:2026.07.17-p6`
- `ghcr.io/lumabot/lumabot-runtime-worker:2026.07.17-p6`
- `ghcr.io/lumabot/lumabot-scheduler:2026.07.17-p6`

## Nexla Setup Status

Default status: fixture mode implemented; live Nexla is documented and opt-in.

Live setup checklist:

1. Install and authenticate the Nexla CLI on the deployment workstation.
2. Store live values in the deployment secret manager, not in this repository.
3. In Express.dev, create a flow that accepts attendee identity records and returns company, stage, headcount, source, and identity confidence.
4. Create the Nexset that backs that flow.
5. Register Nexla as an external MCP provider.
6. Create a ToolSet scoped to enrichment tools only.
7. Configure the Streamable HTTP MCP endpoint as `NEXLA_MCP_ENDPOINT`.
8. Filter MCP tools to the approved enrichment ToolSet before exposing them to the runtime.
9. Validate with the opt-in smoke path by enriching one fixture attendee and confirming no credentials are printed.

## AgentMail Setup Status

Default status: fixture queue implemented; live AgentMail is documented and opt-in.

Live setup checklist:

1. Create or select the LumaBot inbox in AgentMail.
2. Set `AGENTMAIL_INBOX_ID` in the deployment secret manager.
3. Set `AGENTMAIL_API_KEY` in the deployment secret manager.
4. Configure the AgentMail webhook URL to the runtime API webhook route.
5. Set `AGENTMAIL_WEBHOOK_SECRET` in the deployment secret manager.
6. Run the opt-in live smoke test from a non-production inbox.
7. Check that runtime records persist `message_id` and `thread_id`.

## Security Posture

- No live keys are committed.
- Default integration tests use fake services only.
- Runtime internal routes require `LUMABOT_RUNTIME_INTERNAL_TOKEN`.
- Auto-registration defaults to disabled.
- Physical mail requires explicit confirmation and is not part of the automatic fixture workflow.
- Akash manifests use pinned image tags, not `latest`.

## Known Limitations

- The branch contains a fixture contract and deployment scaffolding, not merged production implementations from sibling prompts.
- Docker Compose starts fake HTTP services for demo topology; the full workflow is executed by `scripts/run_fixture_workflow.py`.
- Live Nexla, AgentMail, Zero, Supabase, and Akash validation remain opt-in because credentials and provider accounts are intentionally absent.
