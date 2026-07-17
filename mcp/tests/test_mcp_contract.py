from __future__ import annotations

import asyncio
import logging
from typing import Any

import pytest
from mcp.client.session import ClientSession
from starlette.testclient import TestClient

from lumabot_mcp.app import create_asgi_app, create_mcp_server
from lumabot_mcp.context import redact_secrets
from lumabot_mcp.errors import RuntimeTimeoutError
from lumabot_mcp.models import ToolResponse
from lumabot_mcp.runtime_client import FakeRuntimeClient
from lumabot_mcp.tools.common import runtime_envelope


def structured(result: Any) -> dict[str, Any]:
    content = result.structuredContent
    assert isinstance(content, dict)
    return content


@pytest.mark.anyio
async def test_tool_list_contract(client_session: ClientSession) -> None:
    result = await client_session.list_tools()
    tools = {tool.name: tool for tool in result.tools}
    assert set(tools) == {
        "check_login",
        "login",
        "set_user_profile",
        "recommend_events",
        "get_user_events",
        "get_event_report",
        "get_job_status",
        "confirm_action",
    }
    assert set(tools["login"].inputSchema["properties"]) == {"email", "attempt_id", "code"}
    assert "profile_text" in tools["set_user_profile"].inputSchema["properties"]
    assert set(tools["recommend_events"].inputSchema["properties"]) == {
        "query",
        "date_range",
        "minimum_score",
        "limit",
        "location_override",
    }
    assert set(tools["get_event_report"].inputSchema["properties"]) == {
        "event_id",
        "refresh",
        "event_url",
        "event_html",
        "guest_html",
        "profile_text",
        "scrape",
        "email",
    }


@pytest.mark.anyio
async def test_login_state_machine(client_session: ClientSession) -> None:
    missing_email = structured(await client_session.call_tool("login", {}))
    assert missing_email["status"] == "needs_input"
    assert missing_email["next_action"] == {"type": "request_email", "field": "email"}

    start = structured(await client_session.call_tool("login", {"email": "test@example.com"}))
    assert start["status"] == "needs_input"
    assert start["next_action"]["type"] == "request_code"  # type: ignore[index]

    verify = structured(
        await client_session.call_tool(
            "login",
            {
                "email": "test@example.com",
                "attempt_id": start["data"]["attempt_id"],  # type: ignore[index]
                "code": "123456",
            },
        )
    )
    assert verify["ok"] is True
    assert verify["status"] == "completed"
    assert verify["data"]["email"] == "test@example.com"  # type: ignore[index]

    expired = structured(
        await client_session.call_tool(
            "login",
            {
                "email": "test@example.com",
                "attempt_id": start["data"]["attempt_id"],  # type: ignore[index]
                "code": "expired",
            },
        )
    )
    assert expired["ok"] is False
    assert expired["status"] == "auth_required"


@pytest.mark.anyio
async def test_runtime_timeout_mapping() -> None:
    runtime = FakeRuntimeClient(delay_seconds=0.2)
    server = create_mcp_server(runtime)
    async with asyncio.timeout(1):
        async def timeout_call(cid: str) -> ToolResponse:
            raise RuntimeTimeoutError()

        mapped = await runtime_envelope(timeout_call)
        assert mapped.status == "timeout"
        assert mapped.ok is False
    assert server is not None


@pytest.mark.anyio
async def test_runtime_authentication_failure() -> None:
    server = create_mcp_server(FakeRuntimeClient(fail_auth=True))
    from mcp.shared.memory import create_connected_server_and_client_session

    async with create_connected_server_and_client_session(server, raise_exceptions=True) as session:
        await session.initialize()
        response = structured(
            await session.call_tool("set_user_profile", {"profile_text": "AI events"})
        )
    assert response["status"] == "auth_required"
    assert response["next_action"] == {"type": "login"}


@pytest.mark.anyio
async def test_report_queue(client_session: ClientSession) -> None:
    response = structured(
        await client_session.call_tool(
            "get_event_report",
            {"event_id": "evt-founder-salon", "refresh": True},
        )
    )
    assert response["status"] == "queued"
    assert response["job_id"] == "job-report-evt-founder-salon"


@pytest.mark.anyio
async def test_job_status(client_session: ClientSession) -> None:
    queued = structured(
        await client_session.call_tool(
            "get_event_report",
            {"event_id": "evt-founder-salon", "refresh": True},
        )
    )
    response = structured(
        await client_session.call_tool("get_job_status", {"job_id": queued["job_id"]})
    )
    assert response["status"] == "completed"
    assert response["data"]["progress"] == 1.0  # type: ignore[index]
    assert response["data"]["error"] is None  # type: ignore[index]


@pytest.mark.anyio
async def test_confirmation(client_session: ClientSession) -> None:
    response = structured(
        await client_session.call_tool(
            "confirm_action",
            {"action_id": "act-register-1", "confirmation_token": "secret-token"},
        )
    )
    assert response["status"] == "completed"
    assert response["data"]["action_id"] == "act-register-1"  # type: ignore[index]
    assert response["data"]["status"] == "confirmed"  # type: ignore[index]


def test_secret_redaction(caplog: pytest.LogCaptureFixture) -> None:
    assert redact_secrets(
        {
            "code": "123456",
            "nested": {"authorization": "Bearer secret", "safe": "ok"},
        }
    ) == {"code": "[REDACTED]", "nested": {"authorization": "[REDACTED]", "safe": "ok"}}

    from lumabot_mcp.context import log_tool_call

    logger = logging.getLogger("lumabot_mcp.tests.redaction")
    with caplog.at_level(logging.INFO):
        log_tool_call(logger, "login", {"email": "a@example.com", "code": "123456"})
    assert "123456" not in caplog.text


def test_streamable_http_initialization() -> None:
    app = create_asgi_app(FakeRuntimeClient())
    with TestClient(app) as client:
        health = client.get("/health")
        ready = client.get("/ready")
        assert health.status_code == 200
        assert health.json() == {"ok": True, "status": "healthy"}
        assert ready.status_code == 200
        assert ready.json() == {"ok": True, "status": "ready"}


@pytest.mark.anyio
async def test_concurrent_tool_calls(client_session: ClientSession) -> None:
    results = await asyncio.gather(
        client_session.call_tool("recommend_events", {"query": "AI", "limit": 1}),
        client_session.call_tool("get_user_events", {"scope": "recommended", "limit": 1}),
        client_session.call_tool("confirm_action", {"action_id": "act-email-1"}),
    )
    payloads = [structured(result) for result in results]
    assert all(payload["ok"] is True for payload in payloads)
