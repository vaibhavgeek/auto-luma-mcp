from __future__ import annotations

from lumabot_mcp.models import ToolResponse
from lumabot_mcp.runtime_client import RuntimeClient
from lumabot_mcp.tools.common import runtime_envelope

VALID_SCOPES = {"all", "attended", "registered", "recommended"}


async def handle_recommend_events(
    runtime: RuntimeClient,
    *,
    query: str | None,
    date_range: str | None,
    minimum_score: float | None,
    limit: int,
    location_override: str | None,
) -> ToolResponse:
    async def recommend(cid: str) -> ToolResponse:
        data = await runtime.recommend_events(
            query=query,
            date_range=date_range,
            minimum_score=minimum_score,
            limit=limit,
            location_override=location_override,
            correlation_id=cid,
        )
        refresh_job_id = data.get("refresh_job_id")
        return ToolResponse(
            status="queued" if refresh_job_id else "completed",
            data=data,
            job_id=refresh_job_id if isinstance(refresh_job_id, str) else None,
            message="Returned stored recommendations."
            if not refresh_job_id
            else "Recommendation refresh queued.",
        )

    return await runtime_envelope(recommend)


async def handle_get_user_events(
    runtime: RuntimeClient,
    *,
    scope: str,
    query: str | None,
    limit: int,
    cursor: str | None,
) -> ToolResponse:
    if scope not in VALID_SCOPES:
        return ToolResponse(
            ok=False,
            status="error",
            message="scope must be one of all, attended, registered, recommended.",
        )

    async def get_events(cid: str) -> ToolResponse:
        data = await runtime.get_user_events(
            scope=scope,
            query=query,
            limit=limit,
            cursor=cursor,
            correlation_id=cid,
        )
        return ToolResponse(data=data, message="Returned user events.")

    return await runtime_envelope(get_events)

