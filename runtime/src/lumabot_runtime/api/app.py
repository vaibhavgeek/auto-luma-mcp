from __future__ import annotations

from datetime import timedelta
from typing import Annotated, Any, cast

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status

from lumabot_runtime.actions.registration import RegistrationService
from lumabot_runtime.dependencies import RuntimeContainer, build_container
from lumabot_runtime.email.webhook import (
    AgentMailWebhookHandler,
    AgentMailWebhookVerifier,
    FakeWebhookVerifier,
)
from lumabot_runtime.jobs.models import Job
from lumabot_runtime.models import (
    ActionConfirmRequest,
    AuthStartRequest,
    AuthStartResponse,
    AuthVerifyRequest,
    AuthVerifyResponse,
    Event,
    JobCreateRequest,
    ProfileCreate,
    Recommendation,
    Report,
    ReportRequest,
    UserProfile,
    utc_now,
)
from lumabot_runtime.profiles import parse_profile


def container_from_request(request: Request) -> RuntimeContainer:
    return cast(RuntimeContainer, request.app.state.container)


RuntimeDep = Annotated[RuntimeContainer, Depends(container_from_request)]


def create_app(container: RuntimeContainer | None = None) -> FastAPI:
    resolved = container or build_container()
    app = FastAPI(title="LumaBot Runtime", version="0.1.0")
    app.state.container = resolved

    async def require_internal_token(
        runtime: RuntimeDep,
        authorization: Annotated[str | None, Header()] = None,
        x_runtime_token: Annotated[str | None, Header()] = None,
    ) -> None:
        expected = runtime.settings.runtime_internal_token
        bearer = f"Bearer {expected}"
        if authorization != bearer and x_runtime_token != expected:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid token")

    internal = [Depends(require_internal_token)]

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/ready")
    async def ready(runtime: RuntimeDep) -> dict[str, Any]:
        return {"ready": await runtime.email_client.health_check()}

    @app.post("/internal/auth/luma/start", dependencies=internal)
    async def auth_start(payload: AuthStartRequest) -> AuthStartResponse:
        return AuthStartResponse(
            login_url=f"https://luma.local/oauth/{payload.user_id}",
            session_id=f"sess_{payload.user_id}",
        )

    @app.post("/internal/auth/luma/verify", dependencies=internal)
    async def auth_verify(payload: AuthVerifyRequest) -> AuthVerifyResponse:
        return AuthVerifyResponse(verified=True, session_id=f"sess_{payload.user_id}")

    @app.post("/internal/profile", dependencies=internal)
    async def create_profile(
        payload: ProfileCreate,
        runtime: RuntimeDep,
    ) -> UserProfile:
        profile = UserProfile(
            user_id=payload.user_id,
            notification_email=payload.notification_email,
            original_text=payload.description,
            structured=parse_profile(payload.description),
        )
        runtime.state.profiles[payload.user_id] = profile
        runtime.state.events.setdefault(payload.user_id, _fixture_events())
        return profile

    @app.get("/internal/users/{user_id}/events", dependencies=internal)
    async def list_events(user_id: str, runtime: RuntimeDep) -> list[Event]:
        _require_profile(runtime, user_id)
        return runtime.state.events.setdefault(user_id, _fixture_events())

    @app.get("/internal/users/{user_id}/recommendations", dependencies=internal)
    async def list_recommendations(user_id: str, runtime: RuntimeDep) -> list[Recommendation]:
        events = runtime.state.events.setdefault(user_id, _fixture_events())
        return [
            Recommendation(
                event_id=event.id,
                title=event.title,
                score=event.relevance_score,
                reasons=["Matches profile keywords", "Near configured region"],
            )
            for event in sorted(events, key=lambda item: item.relevance_score, reverse=True)
        ]

    @app.post("/internal/users/{user_id}/events/{event_id}/report", dependencies=internal)
    async def queue_report(
        user_id: str,
        event_id: str,
        payload: ReportRequest,
        runtime: RuntimeDep,
    ) -> Report:
        del payload
        _require_profile(runtime, user_id)
        report_url = f"https://reports.lumabot.local/{user_id}/{event_id}"
        job = await runtime.jobs.enqueue(
            "QUEUE_REPORT_EMAIL",
            {"user_id": user_id, "event_id": event_id, "report_url": report_url},
            idempotency_key=f"report:{user_id}:{event_id}",
        )
        report = Report(
            report_id=f"rep_{user_id}_{event_id}",
            user_id=user_id,
            event_id=event_id,
            job_id=job.id,
            url=report_url,
        )
        runtime.state.reports[(user_id, event_id)] = report
        return report

    @app.get("/internal/users/{user_id}/events/{event_id}/report", dependencies=internal)
    async def get_report(
        user_id: str,
        event_id: str,
        runtime: RuntimeDep,
    ) -> Report:
        report = runtime.state.reports.get((user_id, event_id))
        if report is None:
            raise HTTPException(status_code=404, detail="report not found")
        return report

    @app.post("/internal/jobs", dependencies=internal)
    async def create_job(payload: JobCreateRequest, runtime: RuntimeDep) -> Job:
        return await runtime.jobs.enqueue(
            payload.type,
            payload.payload,
            idempotency_key=payload.idempotency_key,
            max_attempts=payload.max_attempts,
        )

    @app.get("/internal/jobs/{job_id}", dependencies=internal)
    async def get_job(job_id: str, runtime: RuntimeDep) -> Job:
        job = await runtime.jobs.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="job not found")
        return job

    @app.post("/internal/actions/{action_id}/confirm", dependencies=internal)
    async def confirm_action(
        action_id: str,
        payload: ActionConfirmRequest,
        runtime: RuntimeDep,
    ) -> dict[str, Any]:
        if action_id not in runtime.state.actions:
            raise HTTPException(status_code=404, detail="action not found")
        service = RegistrationService(runtime.state, runtime.email_service)
        action = await service.confirm_action(action_id=action_id, approved=payload.approved)
        return action.model_dump(mode="json")

    @app.post("/webhooks/agentmail")
    async def agentmail_webhook(request: Request, runtime: RuntimeDep) -> dict[str, Any]:
        verifier = (
            AgentMailWebhookVerifier(runtime.settings.agentmail_webhook_secret)
            if runtime.settings.agentmail_webhook_secret
            else FakeWebhookVerifier()
        )
        body = await request.body()
        headers = {key: value for key, value in request.headers.items()}
        try:
            record = AgentMailWebhookHandler(runtime.state, verifier).handle(
                body=body,
                headers=headers,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return record.model_dump(mode="json")

    return app


def _require_profile(runtime: RuntimeContainer, user_id: str) -> None:
    if user_id not in runtime.state.profiles:
        raise HTTPException(status_code=404, detail="profile not found")


def _fixture_events() -> list[Event]:
    now = utc_now()
    return [
        Event(
            id="evt_ai_founders",
            title="AI Founders Mixer",
            starts_at=now + timedelta(days=3),
            relevance_score=0.91,
        ),
        Event(
            id="evt_fintech_demo",
            title="Fintech Demo Night",
            starts_at=now + timedelta(days=8),
            relevance_score=0.74,
            price_usd=20,
        ),
    ]
