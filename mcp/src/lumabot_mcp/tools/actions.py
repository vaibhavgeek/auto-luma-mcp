from __future__ import annotations

from lumabot_mcp.models import ToolResponse
from lumabot_mcp.runtime_client import RuntimeClient
from lumabot_mcp.tools.common import runtime_envelope


async def handle_confirm_action(
    runtime: RuntimeClient,
    *,
    action_id: str,
    confirmation_token: str | None,
) -> ToolResponse:
    async def confirm(cid: str) -> ToolResponse:
        data = await runtime.confirm_action(
            action_id,
            confirmation_token=confirmation_token,
            correlation_id=cid,
        )
        return ToolResponse(data=data, message="Action confirmed.")

    return await runtime_envelope(confirm)

