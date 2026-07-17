from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any, Protocol

from lumabot_runtime.models import RuntimeState, WebhookRecord

SENSITIVE_HEADERS = {"authorization", "x-agentmail-signature", "cookie", "set-cookie"}


class WebhookVerifier(Protocol):
    def verify(self, *, body: bytes, headers: dict[str, str]) -> bool: ...


class AgentMailWebhookVerifier:
    def __init__(self, secret: str) -> None:
        self._secret = secret.encode()

    def verify(self, *, body: bytes, headers: dict[str, str]) -> bool:
        signature = headers.get("x-agentmail-signature", "")
        expected = hmac.new(self._secret, body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(signature, expected)


class FakeWebhookVerifier:
    def __init__(self, valid_signature: str = "signed-fixture") -> None:
        self._valid_signature = valid_signature

    def verify(self, *, body: bytes, headers: dict[str, str]) -> bool:
        del body
        return headers.get("x-agentmail-signature") == self._valid_signature


def redact_headers(headers: dict[str, str]) -> dict[str, str]:
    return {
        key: ("<redacted>" if key.lower() in SENSITIVE_HEADERS else value)
        for key, value in headers.items()
    }


class AgentMailWebhookHandler:
    def __init__(self, state: RuntimeState, verifier: WebhookVerifier) -> None:
        self._state = state
        self._verifier = verifier

    def handle(self, *, body: bytes, headers: dict[str, str]) -> WebhookRecord:
        if not self._verifier.verify(body=body, headers=headers):
            raise ValueError("invalid webhook signature")
        try:
            payload = json.loads(body)
        except json.JSONDecodeError as exc:
            raise ValueError("invalid webhook payload") from exc
        event_id = str(payload.get("id") or payload.get("event_id") or "")
        event_type = str(payload.get("type") or payload.get("event_type") or "")
        if not event_id or not event_type:
            raise ValueError("missing webhook event id or type")
        existing = self._state.webhooks.get(event_id)
        if existing:
            return existing
        message = payload.get("message") if isinstance(payload.get("message"), dict) else {}
        metadata: dict[str, Any] = {
            "provider_status": payload.get("status"),
            "safe_headers": redact_headers(headers),
        }
        record = WebhookRecord(
            event_id=event_id,
            event_type=event_type,
            message_id=message.get("id") or payload.get("message_id"),
            metadata=metadata,
        )
        self._state.webhooks[event_id] = record
        return record
