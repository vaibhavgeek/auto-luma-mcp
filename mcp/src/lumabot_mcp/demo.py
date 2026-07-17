from __future__ import annotations

import asyncio
import json
import os
import secrets
from typing import Any, cast

import httpx
from mcp.shared.memory import create_connected_server_and_client_session

from lumabot_mcp.app import create_mcp_server
from lumabot_mcp.runtime_client import FakeRuntimeClient

DEMO_EMAIL = "vaibhavblogger@gmail.com"
AGENTMAIL_API_URL = "https://api.agentmail.to/v0"


async def send_login_email(inbox_id: str, api_key: str, to_email: str, code: str) -> str:
    """Send a real login code email via AgentMail API. Returns message_id."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{AGENTMAIL_API_URL}/inboxes/{inbox_id}/messages/send",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "to": to_email,
                "subject": f"LumaBot Login Code: {code}",
                "text": f"Your LumaBot login code is: {code}\n\nThis code expires in 10 minutes.",
                "html": (
                    f"<h2>Your LumaBot Login Code</h2>"
                    f"<p>Your code is: <strong>{code}</strong></p>"
                    f"<p>This code expires in 10 minutes.</p>"
                ),
            },
            timeout=15.0,
        )
        resp.raise_for_status()
        data = resp.json()
        return str(data.get("message_id", "unknown"))


async def run_demo() -> None:
    agentmail_api_key = os.environ.get("AGENTMAIL_API_KEY", "")
    agentmail_inbox_id = os.environ.get("AGENTMAIL_INBOX_ID", "")

    login_code = secrets.token_hex(3).upper()

    if agentmail_api_key and agentmail_inbox_id:
        print(f"\n[demo] Sending real login email to {DEMO_EMAIL} via AgentMail...")
        msg_id = await send_login_email(
            agentmail_inbox_id, agentmail_api_key, DEMO_EMAIL, login_code
        )
        print(f"[demo] Email sent! message_id={msg_id}")
        print(f"[demo] Login code: {login_code}")
    else:
        login_code = "123456"
        print("\n[demo] AGENTMAIL_API_KEY/AGENTMAIL_INBOX_ID not set, using fake code: 123456")

    server = create_mcp_server(FakeRuntimeClient())
    async with create_connected_server_and_client_session(server, raise_exceptions=True) as session:
        await session.initialize()

        # Step 1: login - request email
        first = response_payload(await session.call_tool("login", {}))
        print_json("login.request_email", first)

        # Step 2: login - submit email (sends code)
        started = response_payload(
            await session.call_tool("login", {"email": DEMO_EMAIL})
        )
        print_json("login.start", started)
        attempt_id = started["data"]["attempt_id"]

        # Step 3: login - verify code
        verified = response_payload(
            await session.call_tool(
                "login",
                {"email": DEMO_EMAIL, "attempt_id": attempt_id, "code": login_code},
            )
        )
        print_json("login.verify", verified)

        # Step 4: set user profile
        profile = response_payload(
            await session.call_tool(
                "set_user_profile",
                {
                    "profile_text": (
                        "I like AI infrastructure, developer tools, intimate founder events, "
                        "and useful conversations in San Francisco."
                    )
                },
            )
        )
        print_json("set_user_profile", profile)

        # Step 5: recommend events
        recs = response_payload(
            await session.call_tool(
                "recommend_events",
                {
                    "query": "AI builder gatherings",
                    "date_range": "next two weeks",
                    "minimum_score": 0.8,
                    "limit": 2,
                },
            )
        )
        print_json("recommend_events", recs)

        # Step 6: request a report
        report = response_payload(
            await session.call_tool(
                "get_event_report",
                {"event_id": "evt-founder-salon", "refresh": True},
            )
        )
        print_json("get_event_report", report)

        # Step 7: poll the report job
        job = response_payload(
            await session.call_tool(
                "get_job_status",
                {"job_id": report["job_id"]},
            )
        )
        print_json("get_job_status", job)

        # Step 8: print top attendee match
        top_match = recs["data"]["events"][0]["top_attendee_match"]
        print(f"\n{'='*60}")
        print(f"TOP ATTENDEE MATCH: {top_match}")
        print(f"{'='*60}")


def response_payload(result: Any) -> dict[str, Any]:
    payload = result.structuredContent
    if payload is None:
        raise RuntimeError("Expected structured MCP tool response.")
    return cast(dict[str, Any], payload)


def print_json(label: str, payload: dict[str, Any]) -> None:
    print(f"\n{label}")
    print(json.dumps(payload, indent=2, sort_keys=True))


def main() -> None:
    asyncio.run(run_demo())


if __name__ == "__main__":
    main()
