from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol
from uuid import uuid4

import httpx

from lumabot_runtime.models import RuntimeState


class ZeroClient(Protocol):
    async def list_capabilities(self) -> list[str]: ...

    async def invoke(self, capability: str, payload: dict[str, Any]) -> dict[str, Any]: ...


class FakeZeroClient:
    def __init__(self, capabilities: list[str] | None = None) -> None:
        self.capabilities = capabilities or ["hosted_page", "generated_image", "printable_artifact"]
        self.invocations: list[dict[str, Any]] = []

    async def list_capabilities(self) -> list[str]:
        return self.capabilities

    async def invoke(self, capability: str, payload: dict[str, Any]) -> dict[str, Any]:
        result = {
            "artifact_id": f"zero_{uuid4().hex}",
            "capability": capability,
            "url": f"https://zero.local/{capability}/{uuid4().hex}",
            "payload": payload,
        }
        self.invocations.append(result)
        return result


@dataclass
class ConfiguredZeroClient:
    base_url: str
    api_key: str | None = None
    timeout_seconds: float = 10.0

    async def list_capabilities(self) -> list[str]:
        headers = self._headers()
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.get(
                f"{self.base_url.rstrip('/')}/capabilities",
                headers=headers,
            )
            response.raise_for_status()
            payload = response.json()
        capabilities = payload.get("capabilities", payload)
        return [str(item) for item in capabilities]

    async def invoke(self, capability: str, payload: dict[str, Any]) -> dict[str, Any]:
        headers = self._headers()
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(
                f"{self.base_url.rstrip('/')}/invoke/{capability}",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data: dict[str, Any] = response.json()
            return data

    def _headers(self) -> dict[str, str]:
        if self.api_key is None:
            return {}
        return {"authorization": f"Bearer {self.api_key}"}


class ZeroArtifactService:
    def __init__(self, state: RuntimeState, zero_client: ZeroClient) -> None:
        self._state = state
        self._zero_client = zero_client

    async def create_networking_bingo(
        self,
        *,
        user_id: str,
        event_id: str,
        report_url: str,
        require_physical_mail_confirmation: bool = True,
    ) -> dict[str, Any]:
        capabilities = await self._zero_client.list_capabilities()
        capability = self._choose_capability(capabilities)
        if capability == "physical_mail" and require_physical_mail_confirmation:
            raise PermissionError("physical mail requires explicit confirmation")
        payload = {
            "user_id": user_id,
            "event_id": event_id,
            "title": "Networking Bingo",
            "people_to_meet": [
                "A founder raising a seed round",
                "A GTM leader at a developer-tool company",
                "A community organizer",
                "An investor focused on AI applications",
                "A product engineer building agent workflows",
            ],
            "conversation_starters": [
                "What would make this event worth your time?",
                "Which tool changed your workflow this month?",
                "Who here should more people meet?",
            ],
            "event_mission": "Find one person you can help within seven days.",
            "report_url": report_url,
        }
        result = await self._zero_client.invoke(capability, payload)
        self._state.zero_invocations.append(result)
        return result

    @staticmethod
    def _choose_capability(capabilities: list[str]) -> str:
        for capability in ("hosted_page", "generated_image", "printable_artifact", "physical_mail"):
            if capability in capabilities:
                return capability
        raise LookupError("no supported Zero artifact capability discovered")
