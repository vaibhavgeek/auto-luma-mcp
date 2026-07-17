from __future__ import annotations

import asyncio
import importlib
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol, cast
from uuid import uuid4

from pydantic import BaseModel, EmailStr, Field

from lumabot_runtime.models import EmailRecord, RuntimeState, utc_now


class EmailSendResult(BaseModel):
    inbox_id: str
    message_id: str
    thread_id: str | None = None
    provider_status: str = "sent"
    sent_at: datetime = Field(default_factory=utc_now)


class EmailClient(Protocol):
    async def send_message(
        self,
        *,
        to: EmailStr,
        subject: str,
        text: str,
        idempotency_key: str,
    ) -> EmailSendResult: ...

    async def create_draft(
        self,
        *,
        to: EmailStr,
        subject: str,
        text: str,
        idempotency_key: str,
    ) -> EmailSendResult: ...

    async def send_draft(self, *, draft_id: str, idempotency_key: str) -> EmailSendResult: ...

    async def health_check(self) -> bool: ...


class FakeEmailClient:
    def __init__(self, inbox_id: str = "fake_inbox") -> None:
        self.inbox_id = inbox_id
        self.sent: list[dict[str, Any]] = []
        self.drafts: dict[str, dict[str, Any]] = {}
        self.fail_next: Exception | None = None

    async def send_message(
        self,
        *,
        to: EmailStr,
        subject: str,
        text: str,
        idempotency_key: str,
    ) -> EmailSendResult:
        if self.fail_next:
            exc = self.fail_next
            self.fail_next = None
            raise exc
        message_id = f"fake_msg_{uuid4().hex}"
        result = EmailSendResult(
            inbox_id=self.inbox_id,
            message_id=message_id,
            thread_id=f"fake_thread_{uuid4().hex}",
            provider_status="sent",
        )
        self.sent.append(
            {
                "to": str(to),
                "subject": subject,
                "text": text,
                "idempotency_key": idempotency_key,
                "result": result,
            }
        )
        return result

    async def create_draft(
        self,
        *,
        to: EmailStr,
        subject: str,
        text: str,
        idempotency_key: str,
    ) -> EmailSendResult:
        draft_id = f"fake_draft_{uuid4().hex}"
        result = EmailSendResult(
            inbox_id=self.inbox_id,
            message_id=draft_id,
            thread_id=None,
            provider_status="draft",
        )
        self.drafts[draft_id] = {
            "to": str(to),
            "subject": subject,
            "text": text,
            "idempotency_key": idempotency_key,
            "result": result,
        }
        return result

    async def send_draft(self, *, draft_id: str, idempotency_key: str) -> EmailSendResult:
        if draft_id not in self.drafts:
            raise ValueError("draft not found")
        draft = self.drafts[draft_id]
        return await self.send_message(
            to=draft["to"],
            subject=draft["subject"],
            text=draft["text"],
            idempotency_key=idempotency_key,
        )

    async def health_check(self) -> bool:
        return True


@dataclass
class AgentMailEmailClient:
    api_key: str
    inbox_id: str
    sdk_client: Any | None = None

    def _client(self) -> Any:
        if self.sdk_client is not None:
            return self.sdk_client
        module = importlib.import_module("agentmail")
        client_type = module.AgentMail if hasattr(module, "AgentMail") else module.Client
        self.sdk_client = client_type(api_key=self.api_key)
        return self.sdk_client

    async def send_message(
        self,
        *,
        to: EmailStr,
        subject: str,
        text: str,
        idempotency_key: str,
    ) -> EmailSendResult:
        return await self._call_provider(
            "send_message",
            {
                "inbox_id": self.inbox_id,
                "to": str(to),
                "subject": subject,
                "text": text,
                "idempotency_key": idempotency_key,
            },
        )

    async def create_draft(
        self,
        *,
        to: EmailStr,
        subject: str,
        text: str,
        idempotency_key: str,
    ) -> EmailSendResult:
        return await self._call_provider(
            "create_draft",
            {
                "inbox_id": self.inbox_id,
                "to": str(to),
                "subject": subject,
                "text": text,
                "idempotency_key": idempotency_key,
            },
            default_status="draft",
        )

    async def send_draft(self, *, draft_id: str, idempotency_key: str) -> EmailSendResult:
        return await self._call_provider(
            "send_draft",
            {
                "inbox_id": self.inbox_id,
                "draft_id": draft_id,
                "idempotency_key": idempotency_key,
            },
        )

    async def health_check(self) -> bool:
        try:
            result = self._client()
            health = getattr(result, "health_check", None)
            if health is None:
                return True
            value = health()
            if asyncio.iscoroutine(value):
                value = await value
            return bool(value)
        except Exception:
            return False

    async def _call_provider(
        self, method_name: str, payload: dict[str, Any], *, default_status: str = "sent"
    ) -> EmailSendResult:
        client = self._client()
        method = getattr(client, method_name, None)
        if method is None and hasattr(client, "messages"):
            method = getattr(client.messages, method_name)
        if method is None:
            raise AttributeError(f"AgentMail client has no {method_name} method")
        result = method(**payload)
        if asyncio.iscoroutine(result):
            result = await result
        data = self._normalize_result(result)
        message_id = data.get("message_id") or data.get("id")
        if not message_id:
            raise ValueError("AgentMail response did not include a message id")
        return EmailSendResult(
            inbox_id=data.get("inbox_id", self.inbox_id),
            message_id=str(message_id),
            thread_id=data.get("thread_id"),
            provider_status=data.get("provider_status", default_status),
        )

    @staticmethod
    def _normalize_result(result: Any) -> dict[str, Any]:
        if isinstance(result, dict):
            return result
        if hasattr(result, "model_dump"):
            return cast(dict[str, Any], result.model_dump())
        if hasattr(result, "__dict__"):
            return cast(dict[str, Any], vars(result))
        raise TypeError("unsupported AgentMail response")


class EmailNotificationService:
    def __init__(self, state: RuntimeState, email_client: EmailClient) -> None:
        self._state = state
        self._email_client = email_client

    async def send_once(
        self,
        *,
        to: EmailStr,
        subject: str,
        text: str,
        idempotency_key: str,
        draft: bool = False,
    ) -> EmailRecord:
        existing = self._state.emails.get(idempotency_key)
        if existing:
            return existing
        result = (
            await self._email_client.create_draft(
                to=to, subject=subject, text=text, idempotency_key=idempotency_key
            )
            if draft
            else await self._email_client.send_message(
                to=to, subject=subject, text=text, idempotency_key=idempotency_key
            )
        )
        record = EmailRecord(
            idempotency_key=idempotency_key,
            inbox_id=result.inbox_id,
            message_id=result.message_id,
            thread_id=result.thread_id,
            provider_status=result.provider_status,
            sent_at=result.sent_at,
        )
        self._state.emails[idempotency_key] = record
        return record

    async def send_report_ready(self, *, user_id: str, report_url: str) -> EmailRecord:
        profile = self._state.profiles[user_id]
        return await self.send_once(
            to=profile.notification_email,
            subject="Your LumaBot event report is ready",
            text=f"Your event report is ready: {report_url}",
            idempotency_key=f"report-ready:{user_id}:{report_url}",
        )

    async def send_registration_confirmation(self, *, user_id: str, event_id: str) -> EmailRecord:
        profile = self._state.profiles[user_id]
        return await self.send_once(
            to=profile.notification_email,
            subject="LumaBot registration confirmed",
            text=f"You are registered for event {event_id}.",
            idempotency_key=f"registration-confirmed:{user_id}:{event_id}",
        )
