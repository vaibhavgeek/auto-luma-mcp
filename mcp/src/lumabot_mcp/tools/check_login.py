from __future__ import annotations

from lumabot_mcp.models import ToolResponse
from lumabot_mcp.runtime_client import RuntimeClient
from lumabot_mcp.tools.common import runtime_envelope


async def handle_check_login(runtime: RuntimeClient, *, email: str) -> ToolResponse:
    async def check(cid: str) -> ToolResponse:
        data = await runtime.check_login(email, correlation_id=cid)
        authenticated = data.get("authenticated", False)
        if authenticated:
            return ToolResponse(
                data=data,
                message="Luma session is valid.",
            )
        return ToolResponse(
            ok=False,
            status="auth_required",
            data=data,
            next_action={"type": "login"},
            message=data.get("message", "Session invalid or not found. Please login."),
        )

    return await runtime_envelope(check)
