from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any, Protocol

import httpx

from lumabot_mcp.errors import RuntimeAPIError, RuntimeAuthenticationError, RuntimeTimeoutError

JSONDict = dict[str, Any]


class RuntimeClient(Protocol):
    async def start_login(self, email: str, *, correlation_id: str) -> JSONDict: ...

    async def verify_login(
        self,
        attempt_id: str,
        code: str,
        *,
        correlation_id: str,
    ) -> JSONDict: ...

    async def check_login(self, email: str, *, correlation_id: str) -> JSONDict: ...

    async def discover_events(self, email: str, *, correlation_id: str) -> JSONDict: ...

    async def inspect_registration(
        self, email: str, event_url: str, *, correlation_id: str
    ) -> JSONDict: ...

    async def submit_registration(
        self, email: str, event_url: str, form_data: dict[str, str], *, correlation_id: str
    ) -> JSONDict: ...

    async def set_profile(self, profile_text: str, *, correlation_id: str) -> JSONDict: ...

    async def recommend_events(
        self,
        *,
        query: str | None,
        date_range: str | None,
        minimum_score: float | None,
        limit: int,
        location_override: str | None,
        correlation_id: str,
    ) -> JSONDict: ...

    async def get_user_events(
        self,
        *,
        scope: str,
        query: str | None,
        limit: int,
        cursor: str | None,
        correlation_id: str,
    ) -> JSONDict: ...

    async def get_event_report(
        self,
        event_id: str,
        *,
        refresh: bool,
        correlation_id: str,
    ) -> JSONDict: ...

    async def create_event_report_job(
        self,
        event_id: str,
        *,
        correlation_id: str,
    ) -> JSONDict: ...

    async def get_job(self, job_id: str, *, correlation_id: str) -> JSONDict: ...

    async def confirm_action(
        self,
        action_id: str,
        *,
        confirmation_token: str | None,
        correlation_id: str,
    ) -> JSONDict: ...


class HttpRuntimeClient:
    def __init__(
        self,
        base_url: str,
        *,
        bearer_token: str | None,
        timeout_seconds: float,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._bearer_token = bearer_token
        self._timeout_seconds = timeout_seconds

    async def start_login(self, email: str, *, correlation_id: str) -> JSONDict:
        return await self._request(
            "POST",
            "/login/start",
            json={"email": email},
            correlation_id=correlation_id,
        )

    async def verify_login(
        self,
        attempt_id: str,
        code: str,
        *,
        correlation_id: str,
    ) -> JSONDict:
        return await self._request(
            "POST",
            "/login/verify",
            json={"attempt_id": attempt_id, "code": code},
            correlation_id=correlation_id,
        )

    async def check_login(self, email: str, *, correlation_id: str) -> JSONDict:
        return await self._request(
            "POST",
            "/login/check",
            json={"email": email},
            correlation_id=correlation_id,
        )

    async def discover_events(self, email: str, *, correlation_id: str) -> JSONDict:
        return await self._request(
            "POST",
            "/discover/events",
            json={"email": email},
            correlation_id=correlation_id,
        )

    async def inspect_registration(
        self, email: str, event_url: str, *, correlation_id: str
    ) -> JSONDict:
        return await self._request(
            "POST",
            "/register/inspect",
            json={"email": email, "event_url": event_url},
            correlation_id=correlation_id,
        )

    async def submit_registration(
        self, email: str, event_url: str, form_data: dict[str, str], *, correlation_id: str
    ) -> JSONDict:
        return await self._request(
            "POST",
            "/register/submit",
            json={"email": email, "event_url": event_url, "form_data": form_data},
            correlation_id=correlation_id,
        )

    async def set_profile(self, profile_text: str, *, correlation_id: str) -> JSONDict:
        return await self._request(
            "PUT",
            "/profile",
            json={"profile_text": profile_text},
            correlation_id=correlation_id,
        )

    async def recommend_events(
        self,
        *,
        query: str | None,
        date_range: str | None,
        minimum_score: float | None,
        limit: int,
        location_override: str | None,
        correlation_id: str,
    ) -> JSONDict:
        return await self._request(
            "POST",
            "/events/recommendations",
            json={
                "query": query,
                "date_range": date_range,
                "minimum_score": minimum_score,
                "limit": limit,
                "location_override": location_override,
            },
            correlation_id=correlation_id,
        )

    async def get_user_events(
        self,
        *,
        scope: str,
        query: str | None,
        limit: int,
        cursor: str | None,
        correlation_id: str,
    ) -> JSONDict:
        return await self._request(
            "GET",
            "/users/events",
            params={"scope": scope, "query": query, "limit": limit, "cursor": cursor},
            correlation_id=correlation_id,
        )

    async def get_event_report(
        self,
        event_id: str,
        *,
        refresh: bool,
        correlation_id: str,
    ) -> JSONDict:
        return await self._request(
            "GET",
            f"/events/{event_id}/report",
            params={"refresh": str(refresh).lower()},
            correlation_id=correlation_id,
        )

    async def create_event_report_job(self, event_id: str, *, correlation_id: str) -> JSONDict:
        return await self._request(
            "POST",
            f"/events/{event_id}/report/jobs",
            json={},
            correlation_id=correlation_id,
        )

    async def get_job(self, job_id: str, *, correlation_id: str) -> JSONDict:
        return await self._request("GET", f"/jobs/{job_id}", correlation_id=correlation_id)

    async def confirm_action(
        self,
        action_id: str,
        *,
        confirmation_token: str | None,
        correlation_id: str,
    ) -> JSONDict:
        return await self._request(
            "POST",
            f"/actions/{action_id}/confirm",
            json={"confirmation_token": confirmation_token},
            correlation_id=correlation_id,
        )

    async def _request(
        self,
        method: str,
        path: str,
        *,
        correlation_id: str,
        json: Mapping[str, Any] | None = None,
        params: Mapping[str, Any] | None = None,
    ) -> JSONDict:
        headers = {"X-Correlation-ID": correlation_id}
        if self._bearer_token:
            headers["Authorization"] = f"Bearer {self._bearer_token}"

        timeout = httpx.Timeout(self._timeout_seconds)
        try:
            async with httpx.AsyncClient(base_url=self._base_url, timeout=timeout) as client:
                filtered_params = {
                    key: value for key, value in (params or {}).items() if value is not None
                }
                response = await client.request(
                    method,
                    path,
                    json=json,
                    params=filtered_params,
                    headers=headers,
                )
        except httpx.TimeoutException as exc:
            raise RuntimeTimeoutError(RuntimeTimeoutError.safe_message) from exc

        if response.status_code in {401, 403}:
            raise RuntimeAuthenticationError(RuntimeAuthenticationError.safe_message)
        if response.status_code >= 400:
            raise RuntimeAPIError(f"Runtime returned HTTP {response.status_code}.")

        data = response.json()
        if not isinstance(data, dict):
            raise RuntimeAPIError("Runtime returned an invalid response.")
        return dict(data)


class FakeRuntimeClient:
    def __init__(self, *, delay_seconds: float = 0.0, fail_auth: bool = False) -> None:
        self.delay_seconds = delay_seconds
        self.fail_auth = fail_auth
        self.login_attempts: dict[str, str] = {}
        self.profile: JSONDict | None = None
        self.report_jobs: dict[str, JSONDict] = {}
        self.confirmed_actions: set[str] = set()
        self.fixture_events: list[JSONDict] = [
            {
                "event_id": "evt-luma-ai-builders",
                "title": "AI Builders Night",
                "date": "2026-07-24",
                "location": "San Francisco, CA",
                "score": 0.94,
                "top_attendee_match": "Maya Chen, developer relations lead",
            },
            {
                "event_id": "evt-founder-salon",
                "title": "Founder Salon",
                "date": "2026-07-26",
                "location": "Oakland, CA",
                "score": 0.83,
                "top_attendee_match": "Arjun Patel, early-stage founder",
            },
        ]

    async def start_login(self, email: str, *, correlation_id: str) -> JSONDict:
        await self._maybe_delay()
        self._maybe_fail_auth()
        attempt_id = f"attempt-{len(self.login_attempts) + 1}"
        self.login_attempts[attempt_id] = email
        return {
            "attempt_id": attempt_id,
            "delivery": "email",
            "expires_in_seconds": 600,
        }

    async def verify_login(
        self,
        attempt_id: str,
        code: str,
        *,
        correlation_id: str,
    ) -> JSONDict:
        await self._maybe_delay()
        self._maybe_fail_auth()
        if code == "expired":
            raise RuntimeAuthenticationError("Login code expired.")
        if attempt_id not in self.login_attempts:
            raise RuntimeAPIError("Unknown login attempt.")
        return {
            "user_id": "user-demo",
            "email": self.login_attempts[attempt_id],
            "session_expires_in_seconds": 3600,
        }

    async def check_login(self, email: str, *, correlation_id: str) -> JSONDict:
        await self._maybe_delay()
        self._maybe_fail_auth()
        return {
            "authenticated": True,
            "session_exists": True,
            "current_url": "https://lu.ma/home",
            "message": "Session is valid.",
        }

    async def discover_events(self, email: str, *, correlation_id: str) -> JSONDict:
        await self._maybe_delay()
        self._maybe_fail_auth()
        return {
            "scraped_at": "2026-07-17T00:00:00Z",
            "event_count": 2,
            "events": self.fixture_events,
        }

    async def inspect_registration(
        self, email: str, event_url: str, *, correlation_id: str
    ) -> JSONDict:
        await self._maybe_delay()
        self._maybe_fail_auth()
        return {
            "event_url": event_url,
            "form_fields": [
                {"name": "name", "label": "Full Name", "type": "text", "required": True},
                {"name": "email", "label": "Email", "type": "email", "required": True},
                {"name": "company", "label": "Company", "type": "text", "required": False},
            ],
            "has_captcha": False,
        }

    async def submit_registration(
        self, email: str, event_url: str, form_data: dict[str, str], *, correlation_id: str
    ) -> JSONDict:
        await self._maybe_delay()
        self._maybe_fail_auth()
        return {
            "event_url": event_url,
            "submitted": True,
            "success": True,
            "current_url": event_url,
        }

    async def set_profile(self, profile_text: str, *, correlation_id: str) -> JSONDict:
        await self._maybe_delay()
        self._maybe_fail_auth()
        self.profile = {
            "profile_text": profile_text,
            "interests": self._extract_interests(profile_text),
            "location": "San Francisco, CA",
        }
        return {"profile": self.profile}

    async def recommend_events(
        self,
        *,
        query: str | None,
        date_range: str | None,
        minimum_score: float | None,
        limit: int,
        location_override: str | None,
        correlation_id: str,
    ) -> JSONDict:
        await self._maybe_delay()
        self._maybe_fail_auth()
        score_floor = minimum_score if minimum_score is not None else 0.0
        events = [
            {
                **event,
                "location": location_override or event["location"],
                "matched_query": query,
                "date_range": date_range,
            }
            for event in self.fixture_events
            if float(event["score"]) >= score_floor
        ][:limit]
        return {
            "events": events,
            "source": "stored_recommendations",
            "refresh_job_id": None,
        }

    async def get_user_events(
        self,
        *,
        scope: str,
        query: str | None,
        limit: int,
        cursor: str | None,
        correlation_id: str,
    ) -> JSONDict:
        await self._maybe_delay()
        self._maybe_fail_auth()
        events = self.fixture_events[:limit]
        return {
            "scope": scope,
            "query": query,
            "cursor": cursor,
            "events": events,
            "next_cursor": None,
        }

    async def get_event_report(
        self,
        event_id: str,
        *,
        refresh: bool,
        correlation_id: str,
    ) -> JSONDict:
        await self._maybe_delay()
        self._maybe_fail_auth()
        if refresh:
            return await self.create_event_report_job(event_id, correlation_id=correlation_id)
        if event_id == "evt-luma-ai-builders":
            return {
                "report": {
                    "event_id": event_id,
                    "summary": (
                        "AI operators, founders, and developer-tools builders are attending."
                    ),
                    "top_attendee_match": "Maya Chen, developer relations lead",
                }
            }
        return await self.create_event_report_job(event_id, correlation_id=correlation_id)

    async def create_event_report_job(self, event_id: str, *, correlation_id: str) -> JSONDict:
        await self._maybe_delay()
        self._maybe_fail_auth()
        job_id = f"job-report-{event_id}"
        self.report_jobs[job_id] = {
            "job_id": job_id,
            "status": "completed",
            "progress": 1.0,
            "result": {
                "event_id": event_id,
                "summary": "Queued fixture report completed by fake runtime.",
                "top_attendee_match": "Maya Chen, developer relations lead",
            },
            "error": None,
        }
        return {"job_id": job_id, "status": "queued"}

    async def get_job(self, job_id: str, *, correlation_id: str) -> JSONDict:
        await self._maybe_delay()
        self._maybe_fail_auth()
        job = self.report_jobs.get(job_id)
        if job is None:
            job = {
                "job_id": job_id,
                "status": "pending",
                "progress": 0.2,
                "result": None,
                "error": None,
            }
        return {"job": job}

    async def confirm_action(
        self,
        action_id: str,
        *,
        confirmation_token: str | None,
        correlation_id: str,
    ) -> JSONDict:
        await self._maybe_delay()
        self._maybe_fail_auth()
        self.confirmed_actions.add(action_id)
        return {
            "action_id": action_id,
            "status": "confirmed",
            "confirmation_token_used": bool(confirmation_token),
        }

    async def _maybe_delay(self) -> None:
        if self.delay_seconds:
            await asyncio.sleep(self.delay_seconds)

    def _maybe_fail_auth(self) -> None:
        if self.fail_auth:
            raise RuntimeAuthenticationError(RuntimeAuthenticationError.safe_message)

    @staticmethod
    def _extract_interests(profile_text: str) -> list[str]:
        words = [
            word.strip("., ").lower()
            for word in profile_text.split()
            if len(word.strip("., ")) > 4
        ]
        return sorted(set(words[:5]))
