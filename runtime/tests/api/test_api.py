from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from lumabot_runtime.api import create_app
from lumabot_runtime.config import Settings
from lumabot_runtime.dependencies import build_container
from lumabot_runtime.models import ActionRecord, UserProfile
from lumabot_runtime.profiles import parse_profile


@pytest.fixture
def token() -> str:
    return "test-token"


@pytest.fixture
def auth_headers(token: str) -> dict[str, str]:
    return {"authorization": f"Bearer {token}"}


@pytest.fixture
def app(token: str):
    return create_app(build_container(settings=Settings(runtime_internal_token=token)))


@pytest.fixture
async def client(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as test_client:
        yield test_client


async def test_internal_token_required(client: AsyncClient) -> None:
    response = await client.get("/internal/users/u1/events")
    assert response.status_code == 401


async def test_profile_event_recommendation_and_report_flow(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    profile = await client.post(
        "/internal/profile",
        headers=auth_headers,
        json={
            "user_id": "u1",
            "notification_email": "u1@example.com",
            "description": "SF AI founder wants to network at free meetups and auto-register.",
        },
    )
    assert profile.status_code == 200
    assert profile.json()["structured"]["region"]["value"] == "Bay Area"

    events = await client.get("/internal/users/u1/events", headers=auth_headers)
    assert events.status_code == 200
    assert events.json()[0]["id"] == "evt_ai_founders"

    recs = await client.get("/internal/users/u1/recommendations", headers=auth_headers)
    assert recs.status_code == 200
    assert recs.json()[0]["score"] >= recs.json()[1]["score"]

    report = await client.post(
        "/internal/users/u1/events/evt_ai_founders/report",
        headers=auth_headers,
        json={"refresh": True},
    )
    assert report.status_code == 200
    job_id = report.json()["job_id"]

    job = await client.get(f"/internal/jobs/{job_id}", headers=auth_headers)
    assert job.status_code == 200
    assert job.json()["type"] == "QUEUE_REPORT_EMAIL"


async def test_action_confirmation_job_idempotency_and_webhook(
    app: FastAPI,
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    state = app.state.container.state
    state.profiles["u2"] = UserProfile(
        user_id="u2",
        notification_email="u2@example.com",
        original_text="SF AI founder",
        structured=parse_profile("SF AI founder"),
    )
    action = ActionRecord(
        user_id="u2",
        type="AUTO_REGISTER_EVENT",
        payload={"event_id": "evt_api_confirm"},
    )
    state.actions[action.id] = action
    confirmed = await client.post(
        f"/internal/actions/{action.id}/confirm",
        headers=auth_headers,
        json={"approved": True},
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "completed"

    job = await client.post(
        "/internal/jobs",
        headers=auth_headers,
        json={"type": "TEST", "payload": {"ok": True}, "idempotency_key": "same"},
    )
    assert job.status_code == 200
    duplicate = await client.post(
        "/internal/jobs",
        headers=auth_headers,
        json={"type": "TEST", "payload": {"ok": True}, "idempotency_key": "same"},
    )
    assert duplicate.json()["id"] == job.json()["id"]

    webhook = await client.post(
        "/webhooks/agentmail",
        headers={"x-agentmail-signature": "signed-fixture"},
        json={"id": "evt_1", "type": "message.delivered", "message": {"id": "msg_1"}},
    )
    assert webhook.status_code == 200
    replay = await client.post(
        "/webhooks/agentmail",
        headers={"x-agentmail-signature": "signed-fixture"},
        json={"id": "evt_1", "type": "message.delivered", "message": {"id": "msg_1"}},
    )
    assert replay.json()["event_id"] == "evt_1"


async def _create_profile(client: AsyncClient, auth_headers: dict[str, str]):
    response = await client.post(
        "/internal/profile",
        headers=auth_headers,
        json={
            "user_id": "u2",
            "notification_email": "u2@example.com",
            "description": "SF AI founder",
        },
    )
    return response.json()
