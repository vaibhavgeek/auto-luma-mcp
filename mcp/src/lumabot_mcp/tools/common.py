from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TypeVar

from lumabot_mcp.context import correlation_id
from lumabot_mcp.errors import RuntimeAPIError, RuntimeAuthenticationError, RuntimeTimeoutError
from lumabot_mcp.models import ToolResponse

T = TypeVar("T")


async def runtime_envelope(call: Callable[[str], Awaitable[ToolResponse]]) -> ToolResponse:
    cid = correlation_id()
    try:
        return await call(cid)
    except RuntimeTimeoutError:
        return ToolResponse(
            ok=False,
            status="timeout",
            message="Runtime request timed out. Try again shortly.",
        )
    except RuntimeAuthenticationError:
        return ToolResponse(
            ok=False,
            status="auth_required",
            next_action={"type": "login"},
            message="Authentication is required or has expired.",
        )
    except RuntimeAPIError as exc:
        return ToolResponse(ok=False, status="error", message=exc.safe_message)

