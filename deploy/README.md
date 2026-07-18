# Deployment

The easiest Akash/demo deployment is the all-in-one image in this directory.
It starts the runtime API on `127.0.0.1:8080`, then exposes the MCP server on
`0.0.0.0:8000`.

## Build and Push

Use a registry Akash can pull from, such as GitHub Container Registry or Docker
Hub.

```bash
docker build -f deploy/Dockerfile -t ghcr.io/YOUR_GITHUB_OWNER/auto-luma-mcp:latest .
docker push ghcr.io/YOUR_GITHUB_OWNER/auto-luma-mcp:latest
```

Update `deploy/akash.yml` to use the pushed image name before deploying.

## Runtime Environment

- `LUMABOT_ENRICHMENT_PROVIDER=visible` uses only scraped Luma guest fields.
- `LUMABOT_ENRICHMENT_PROVIDER=zero` calls Zero capabilities for PDL/email
  enrichment.
- `ZERO_MAX_PAY_USDC` caps the per-call Zero spend.
- `PDL_MIN_LIKELIHOOD=1` works best for sparse Luma-visible profiles; raise it
  when you have stronger identifiers.
- `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` let the runtime load/store
  saved Luma sessions outside the container filesystem.

Without Supabase or a persistent volume, saved Luma sessions, cached reports,
and in-memory jobs disappear when the container restarts.

## Invoke The MCP

The MCP server exposes Streamable HTTP from the public service URL. In a client,
use the service URL as the MCP endpoint and call:

1. `login` with `{ "email": "you@example.com" }`
2. `login` again with `{ "email": "...", "attempt_id": "...", "code": "123456" }`
3. `get_event_report` with:

```json
{
  "event_id": "my-event",
  "refresh": true,
  "scrape": true,
  "event_url": "https://lu.ma/...",
  "email": "you@example.com",
  "profile_text": "I want to meet AI developer tools founders."
}
```

For deterministic demos, pass `event_html` and `guest_html` instead of
`scrape=true`.
