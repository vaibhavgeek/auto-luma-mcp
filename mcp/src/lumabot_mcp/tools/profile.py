from __future__ import annotations

from lumabot_mcp.models import ToolResponse
from lumabot_mcp.runtime_client import RuntimeClient
from lumabot_mcp.tools.common import runtime_envelope


async def handle_set_user_profile(runtime: RuntimeClient, *, profile_text: str) -> ToolResponse:
    async def set_profile(cid: str) -> ToolResponse:
        data = await runtime.set_profile(profile_text, correlation_id=cid)
        return ToolResponse(data=data, message="Profile saved.")

    return await runtime_envelope(set_profile)

