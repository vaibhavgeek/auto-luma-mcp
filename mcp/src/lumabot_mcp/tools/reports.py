from __future__ import annotations

from lumabot_mcp.models import ToolResponse
from lumabot_mcp.runtime_client import RuntimeClient
from lumabot_mcp.tools.common import runtime_envelope


async def handle_get_event_report(
    runtime: RuntimeClient,
    *,
    event_id: str,
    refresh: bool,
    event_url: str | None = None,
    event_html: str | None = None,
    guest_html: str | None = None,
    profile_text: str | None = None,
    scrape: bool = False,
    email: str | None = None,
) -> ToolResponse:
    async def get_report(cid: str) -> ToolResponse:
        data = await runtime.get_event_report(
            event_id,
            refresh=refresh,
            event_url=event_url,
            event_html=event_html,
            guest_html=guest_html,
            profile_text=profile_text,
            scrape=scrape,
            email=email,
            correlation_id=cid,
        )
        job_id = data.get("job_id")
        return ToolResponse(
            status="queued" if isinstance(job_id, str) else "completed",
            data=data,
            job_id=job_id if isinstance(job_id, str) else None,
            message="Report job queued." if isinstance(job_id, str) else "Returned event report.",
        )

    return await runtime_envelope(get_report)
