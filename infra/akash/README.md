# Akash Deployment

These SDL manifests are pinned to the hackathon fixture image tag `2026.07.17-p6`; do not deploy mutable tags.

## Images

- `ghcr.io/lumabot/lumabot-mcp:2026.07.17-p6`
- `ghcr.io/lumabot/lumabot-runtime-api:2026.07.17-p6`
- `ghcr.io/lumabot/lumabot-runtime-worker:2026.07.17-p6`
- `ghcr.io/lumabot/lumabot-scheduler:2026.07.17-p6`

## Required Secret Names

- `LUMABOT_RUNTIME_URL`
- `LUMABOT_RUNTIME_INTERNAL_TOKEN`
- `LUMABOT_DATABASE_URL`
- `LUMABOT_SESSION_ENCRYPTION_KEY`
- `AGENTMAIL_INBOX_ID`
- `AGENTMAIL_API_KEY`
- `AGENTMAIL_WEBHOOK_SECRET`
- `NEXLA_MCP_ENDPOINT`
- `NEXLA_TOOLSET_ID`
- `ZERO_API_KEY`
- `LUMABOT_WORKER_CONCURRENCY`

## Deployment Commands

```sh
akash tx deployment create infra/akash/runtime-api.deploy.yaml --from "$AKASH_KEY_NAME"
akash tx deployment create infra/akash/mcp-service.deploy.yaml --from "$AKASH_KEY_NAME"
akash tx deployment create infra/akash/runtime-worker.deploy.yaml --from "$AKASH_KEY_NAME"
akash tx deployment create infra/akash/scheduler.deploy.yaml --from "$AKASH_KEY_NAME"
```

Deploy the runtime API first, set `LUMABOT_RUNTIME_URL` to its lease URI, then deploy the MCP service, worker, and scheduler. The worker and scheduler expose no public endpoint. The runtime API keeps `/healthz` public and protects `/internal/*` with `LUMABOT_RUNTIME_INTERNAL_TOKEN`.
