# LumaBot MCP Server

This package implements a stateless Python MCP server for LumaBot. Tools are fast adapters over a
`RuntimeClient` protocol; stateful work lives behind the runtime API boundary.

## Run

```bash
uv sync
uv run ruff check .
uv run mypy src
uv run pytest
make demo
```

## Environment

- `LUMABOT_RUNTIME_URL`: runtime API base URL, default `http://127.0.0.1:8080`
- `LUMABOT_RUNTIME_BEARER_TOKEN`: bearer token sent only to the runtime API
- `LUMABOT_RUNTIME_TIMEOUT_SECONDS`: runtime request timeout, default `5.0`
- `LUMABOT_MCP_HOST`: MCP bind host, default `127.0.0.1`
- `LUMABOT_MCP_PORT`: MCP bind port, default `8000`

The production entrypoint serves health endpoints at `/health` and `/ready`, and mounts the
Streamable HTTP MCP endpoint at `/mcp` through the official Python MCP SDK.

## Runtime API assumptions

The HTTP runtime adapter assumes these endpoints:

- `POST /login/start`
- `POST /login/verify`
- `PUT /profile`
- `POST /events/recommendations`
- `GET /users/events`
- `GET /events/{event_id}/report`
- `POST /events/{event_id}/report/jobs`
- `GET /jobs/{job_id}`
- `POST /actions/{action_id}/confirm`

Every runtime request includes `X-Correlation-ID`. If `LUMABOT_RUNTIME_BEARER_TOKEN` is set, it is
sent as `Authorization: Bearer ...`. HTTP 401/403 responses map to `auth_required`; runtime timeouts
map to a safe timeout envelope.

