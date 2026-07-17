from __future__ import annotations

import os
from typing import Any

import pytest

from lumabot_runtime.email.client import (
    AgentMailEmailClient,
    EmailNotificationService,
    FakeEmailClient,
)
from lumabot_runtime.email.webhook import (
    AgentMailWebhookHandler,
    FakeWebhookVerifier,
    redact_headers,
)
from lumabot_runtime.models import RuntimeState, UserProfile
from lumabot_runtime.profiles import parse_profile


async def test_fake_send_persists_ids_and_prevents_duplicates() -> None:
    state = RuntimeState()
    client = FakeEmailClient(inbox_id="inbox_123")
    service = EmailNotificationService(state, client)
    first = await service.send_once(
        to="user@example.com",
        subject="Hello",
        text="Body",
        idempotency_key="logical-1",
    )
    second = await service.send_once(
        to="user@example.com",
        subject="Hello",
        text="Body",
        idempotency_key="logical-1",
    )
    assert first.message_id == second.message_id
    assert first.inbox_id == "inbox_123"
    assert first.thread_id is not None
    assert len(client.sent) == 1


async def test_sdk_adapter_passes_exact_inbox_id_and_handles_drafts() -> None:
    class MockAgentMail:
        def __init__(self) -> None:
            self.calls: list[tuple[str, dict[str, Any]]] = []

        async def send_message(self, **payload: Any) -> dict[str, Any]:
            self.calls.append(("send_message", payload))
            return {"id": "msg_sdk", "thread_id": "thr_sdk", "provider_status": "sent"}

        async def create_draft(self, **payload: Any) -> dict[str, Any]:
            self.calls.append(("create_draft", payload))
            return {"id": "draft_sdk", "provider_status": "draft"}

    sdk = MockAgentMail()
    client = AgentMailEmailClient(api_key="not-real", inbox_id="inbox_exact", sdk_client=sdk)
    sent = await client.send_message(
        to="u@example.com", subject="S", text="T", idempotency_key="idem"
    )
    draft = await client.create_draft(
        to="u@example.com", subject="S", text="T", idempotency_key="draft-idem"
    )
    assert sent.message_id == "msg_sdk"
    assert draft.provider_status == "draft"
    assert sdk.calls[0][1]["inbox_id"] == "inbox_exact"
    assert sdk.calls[1][0] == "create_draft"


async def test_api_exception_and_rate_limit_surface_for_retry() -> None:
    client = FakeEmailClient()
    client.fail_next = RuntimeError("429 rate limited")
    with pytest.raises(RuntimeError, match="429"):
        await client.send_message(
            to="user@example.com",
            subject="Hello",
            text="Body",
            idempotency_key="logical-2",
        )


def test_webhook_replay_protection_and_redaction() -> None:
    state = RuntimeState()
    handler = AgentMailWebhookHandler(state, FakeWebhookVerifier())
    body = b'{"id":"evt_1","type":"message.bounced","message":{"id":"msg_1"},"body":"secret"}'
    headers = {"x-agentmail-signature": "signed-fixture", "authorization": "Bearer secret"}
    first = handler.handle(body=body, headers=headers)
    second = handler.handle(body=body, headers=headers)
    assert first == second
    assert second.message_id == "msg_1"
    assert redact_headers(headers)["authorization"] == "<redacted>"
    assert state.webhooks["evt_1"].metadata["safe_headers"]["authorization"] == "<redacted>"


@pytest.mark.live_agentmail
async def test_live_agentmail_smoke() -> None:
    if (
        os.getenv("RUN_LIVE_AGENTMAIL_TESTS") != "1"
        or not os.getenv("AGENTMAIL_API_KEY")
        or not os.getenv("AGENTMAIL_INBOX_ID")
        or not os.getenv("AGENTMAIL_TEST_RECIPIENT")
    ):
        pytest.skip("live AgentMail smoke test is disabled")
    state = RuntimeState()
    state.profiles["live"] = UserProfile(
        user_id="live",
        notification_email=os.environ["AGENTMAIL_TEST_RECIPIENT"],
        original_text="live smoke test",
        structured=parse_profile("live smoke test"),
    )
    client = AgentMailEmailClient(
        api_key=os.environ["AGENTMAIL_API_KEY"],
        inbox_id=os.environ["AGENTMAIL_INBOX_ID"],
    )
    service = EmailNotificationService(state, client)
    result = await service.send_once(
        to=os.environ["AGENTMAIL_TEST_RECIPIENT"],
        subject="LumaBot live AgentMail smoke test",
        text="This is a one-time LumaBot runtime smoke test.",
        idempotency_key="live-agentmail-smoke-v1",
    )
    assert result.message_id
