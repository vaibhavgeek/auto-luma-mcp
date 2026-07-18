from __future__ import annotations

from lumabot_mcp.models import ToolResponse
from lumabot_mcp.runtime_client import RuntimeClient
from lumabot_mcp.tools.common import runtime_envelope


async def handle_discover_events(runtime: RuntimeClient, *, email: str) -> ToolResponse:
    async def discover(cid: str) -> ToolResponse:
        data = await runtime.discover_events(email, correlation_id=cid)
        if "error" in data:
            return ToolResponse(
                ok=False,
                status="auth_required",
                data=data,
                next_action={"type": "login"},
                message=data["error"],
            )
        return ToolResponse(
            data=data,
            message=f"Discovered {data.get('event_count', 0)} events.",
        )

    return await runtime_envelope(discover)


async def handle_inspect_registration(
    runtime: RuntimeClient, *, email: str, event_url: str
) -> ToolResponse:
    async def inspect(cid: str) -> ToolResponse:
        data = await runtime.inspect_registration(email, event_url, correlation_id=cid)
        if "error" in data:
            return ToolResponse(ok=False, status="error", data=data, message=data["error"])
        return ToolResponse(
            data=data,
            message=f"Found {len(data.get('form_fields', []))} registration fields.",
        )

    return await runtime_envelope(inspect)


async def handle_register_event(
    runtime: RuntimeClient, *, email: str, event_url: str, form_data: dict[str, str]
) -> ToolResponse:
    async def register(cid: str) -> ToolResponse:
        data = await runtime.submit_registration(
            email, event_url, form_data, correlation_id=cid
        )
        if data.get("submitted") and data.get("success"):
            return ToolResponse(data=data, message="Successfully registered for event.")
        return ToolResponse(
            ok=False,
            status="error",
            data=data,
            message=data.get("error", "Registration may not have succeeded."),
        )

    return await runtime_envelope(register)
