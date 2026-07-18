from __future__ import annotations

from lumabot_mcp.models import ToolResponse
from lumabot_mcp.runtime_client import RuntimeClient
from lumabot_mcp.tools.common import runtime_envelope


async def handle_login(
    runtime: RuntimeClient,
    *,
    email: str | None,
    attempt_id: str | None,
    code: str | None,
) -> ToolResponse:
    if not email:
        return ToolResponse(
            status="needs_input",
            next_action={"type": "request_email", "field": "email"},
            message="Enter the email address for your Luma account.",
        )

    if not code:
        async def start(cid: str) -> ToolResponse:
            data = await runtime.start_login(email, correlation_id=cid)
            if data.get("ok") is False:
                return ToolResponse(
                    ok=False,
                    status="error",
                    data=data,
                    message=(
                        "Luma login did not reach the email-code screen. "
                        "The runtime may be blocked by Luma or the login page changed."
                    ),
                )
            return ToolResponse(
                status="needs_input",
                data=data,
                next_action={
                    "type": "request_code",
                    "field": "code",
                    "attempt_id": data.get("attempt_id"),
                },
                message="Check your email for the login code.",
            )

        return await runtime_envelope(start)

    if not attempt_id:
        return ToolResponse(
            ok=False,
            status="needs_input",
            next_action={"type": "request_attempt_id", "field": "attempt_id"},
            message="Provide the attempt_id returned by the login start step.",
        )

    async def verify(cid: str) -> ToolResponse:
        data = await runtime.verify_login(attempt_id, code, correlation_id=cid)
        return ToolResponse(data=data, message="Login verified.")

    return await runtime_envelope(verify)
