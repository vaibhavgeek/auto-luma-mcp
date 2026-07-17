from __future__ import annotations

from lumabot_mcp.models import ToolResponse
from lumabot_mcp.runtime_client import RuntimeClient
from lumabot_mcp.tools.common import runtime_envelope


async def handle_get_job_status(runtime: RuntimeClient, *, job_id: str) -> ToolResponse:
    async def get_job(cid: str) -> ToolResponse:
        data = await runtime.get_job(job_id, correlation_id=cid)
        job = data.get("job", {})
        return ToolResponse(
            data={
                "status": job.get("status"),
                "progress": job.get("progress"),
                "result": job.get("result"),
                "error": job.get("error"),
                "job": job,
            },
            job_id=job_id,
            message="Returned job status.",
        )

    return await runtime_envelope(get_job)

