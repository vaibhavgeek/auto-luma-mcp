from __future__ import annotations

import asyncio
import json
from typing import Any, cast

from mcp.shared.memory import create_connected_server_and_client_session

from lumabot_mcp.app import create_mcp_server
from lumabot_mcp.runtime_client import FakeRuntimeClient


async def run_demo() -> None:
    server = create_mcp_server(FakeRuntimeClient())
    async with create_connected_server_and_client_session(server, raise_exceptions=True) as session:
        await session.initialize()

        first = response_payload(await session.call_tool("login", {}))
        print_json("login.request_email", first)

        started = response_payload(await session.call_tool("login", {"email": "demo@example.com"}))
        print_json("login.start", started)
        attempt_id = started["data"]["attempt_id"]

        verified = response_payload(
            await session.call_tool(
                "login",
                {"email": "demo@example.com", "attempt_id": attempt_id, "code": "123456"},
            )
        )
        print_json("login.verify", verified)

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

        report = response_payload(
            await session.call_tool(
                "get_event_report",
                {"event_id": "evt-founder-salon", "refresh": True},
            )
        )
        print_json("get_event_report", report)

        job = response_payload(
            await session.call_tool(
                "get_job_status",
                {"job_id": report["job_id"]},
            )
        )
        print_json("get_job_status", job)

        top_match = recs["data"]["events"][0]["top_attendee_match"]
        print(f"top_attendee_match: {top_match}")


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
